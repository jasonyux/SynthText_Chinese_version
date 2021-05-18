# -*- coding: utf-8 -*-
# Author: Ankush Gupta
# Date: 2015

"""
Entry-point for generating synthetic text images, as described in:

@InProceedings{Gupta16,
      author       = "Gupta, A. and Vedaldi, A. and Zisserman, A.",
      title        = "Synthetic Data for Text Localisation in Natural Images",
      booktitle    = "IEEE Conference on Computer Vision and Pattern Recognition",
      year         = "2016",
    }
"""

import numpy as np
import h5py
import os, sys, traceback
import os.path as osp
from synthgen import *
from common import *
import wget, tarfile
import cv2 as cv
import time 
import logging

## Define some configuration variables:
NUM_IMG = -1 # no. of images to use for generation (-1 to use all available):
INSTANCE_PER_IMAGE = 1 # no. of times to use the same image
SECS_PER_IMG = 5 #max time per image in seconds

# path to the data-file, containing image, depth and segmentation:
DATA_PATH = 'data' # this is also used by other resources. This should NOT be changed
DB_FNAME = osp.join(DATA_PATH,'dset.h5')
# DB_FNAME = osp.join(DATA_PATH,'game_dset/data/dset.h5')
# url of the data (google-drive public file):
DATA_URL = 'http://www.robots.ox.ac.uk/~ankush/data.tar.gz'

""" 
#used for debuggin
OUT_FILE = 'results/SynthText_game.h5' #TODO: changed for testing
DEPTH_PATH='data/game_dset/prev_work/depth.h5'
SEG_PATH='data/game_dset/prev_work/seg.h5'
IM_DIR='data/game_dset/prev_work/images'
"""

#"""
# used for production
OUT_FILE = 'results/SynthText_game_3000.h5' #TODO: changed for testing
DEPTH_PATH='data/game_dset/depth.h5'
SEG_PATH='data/game_dset/seg.h5'
IM_DIR='data/game_dset/images/results'
#"""

"""
# path to the data-file, containing image, depth and segmentation:
DATA_PATH = 'data'
DB_FNAME = osp.join(DATA_PATH,'dset.h5')
# url of the data (google-drive public file):
DATA_URL = 'http://www.robots.ox.ac.uk/~ankush/data.tar.gz'
OUT_FILE = 'results/SynthText.h5'
"""

def get_data():
  """
  Download the image,depth and segmentation data:
  Returns, the h5 database.
  """
  if not osp.exists(DB_FNAME):
    try:
      colorprint(Color.BLUE,'\tdownloading data (56 M) from: '+DATA_URL,bold=True)
      print
      sys.stdout.flush()
      out_fname = 'data.tar.gz'
      wget.download(DATA_URL,out=out_fname)
      tar = tarfile.open(out_fname)
      tar.extractall()
      tar.close()
      os.remove(out_fname)
      colorprint(Color.BLUE,'\n\tdata saved at:'+DB_FNAME,bold=True)
      sys.stdout.flush()
    except:
      print colorize(Color.RED,'Data not found and have problems downloading.',bold=True)
      sys.stdout.flush()
      sys.exit(-1)
  # open the h5 file and return:
  return h5py.File(DB_FNAME,'r')


def add_res_to_db(imgname,res,db):
  """
  Add the synthetically generated text image instance
  and other metadata to the dataset.
  """
  ninstance = len(res)
  logging.info(colorize(Color.GREEN, "{} has text rendered".format(imgname.encode('utf-8'))))
  for i in xrange(ninstance):
    logging.info(colorize(Color.GREEN,'added into the db %s '%res[i]['txt']))
    
    dname = "%s_%d"%(imgname, i)
    db['data'].create_dataset(dname,data=res[i]['img'])
    db['data'][dname].attrs['charBB'] = res[i]['charBB']
    db['data'][dname].attrs['wordBB'] = res[i]['wordBB']
    logging.debug('type of res[i][\'txt\'] {}'.format(type(res[i]['txt'])))
         
    # edited in the same manner as original repo
    #"""
    L = res[i]['txt']
    L = [t.encode('utf-8', "ignore") for t in L]
    db['data'][dname].attrs['txt'] = L
    #"""
    #db['data'][dname].attrs.create('txt', res[i]['txt'], dtype=h5py.special_dtype(vlen=unicode))
    logging.debug('type of db: {}'.format(type(db['data'][dname].attrs['txt'])))
    logging.debug(colorize(Color.GREEN,'successfully added'))
    logging.debug(res[i]['txt'])
    logging.debug(res[i]['img'].shape)
    logging.debug('charBB {}'.format(res[i]['charBB'].shape))
    logging.debug('charBB {}'.format(res[i]['charBB']))
    logging.debug('wordBB {}'.format(res[i]['wordBB'].shape))
    logging.debug('wordBB {}'.format(res[i]['wordBB']))

    
def rgb2hsv(image):
    return image.convert('HSV')

def rgb2gray(image):
    
    rgb=np.array(image)
    
    r, g, b = rgb[:,:,0], rgb[:,:,1], rgb[:,:,2]

    gray = 0.2989 * r + 0.5870 * g + 0.1140 * b
    return gray


def main(viz=False):
  # open databases:
  logging.info(colorize(Color.BLUE,'getting data..',bold=True))
  
  #add more data into the dset
  depth_db = h5py.File(DEPTH_PATH,'r')
  seg_db = h5py.File(SEG_PATH,'r')

  imnames = sorted(depth_db.keys())

  # open the output h5 file:
  out_db = h5py.File(OUT_FILE,'w')
  out_db.create_group('/data')
  logging.info(colorize(Color.GREEN,'Storing the output in: '+OUT_FILE, bold=True))

  RV3 = RendererV3(DATA_PATH,max_time=SECS_PER_IMG)

  for imname in imnames[50:65]:
    # ignore if not in filetered list:
    # if imname not in filtered_imnames: continue
    t1=time.time()
    try:
      # get the colour image:
      img = Image.open(osp.join(IM_DIR, imname)).convert('RGB')
      
      # get depth:
      depth = depth_db[imname][:].T
      # depth = depth[:,:,0]

      # get segmentation info:
      seg = seg_db['mask'][imname][:].astype('float32')
      area = seg_db['mask'][imname].attrs['area']
      label = seg_db['mask'][imname].attrs['label']

      # re-size uniformly:
      sz = depth.shape[:2][::-1]
      img = np.array(img.resize(sz,Image.ANTIALIAS))
      seg = np.array(Image.fromarray(seg).resize(sz,Image.NEAREST))

      # compute text in image
      res = RV3.render_text(img,depth,seg,area,label,
                            ninstance=INSTANCE_PER_IMAGE,viz=viz)
      t2=time.time()
      
      
      for ct in range(5):
      
        if len(res) > 0:  
            # non-empty : successful in placing text:
            add_res_to_db(imname,res,out_db)
            break
        else:
            res = RV3.render_text(img,depth,seg,area,label,
                            ninstance=INSTANCE_PER_IMAGE,viz=viz)
      # visualize the output:
      logging.info('time consume in pic {}'.format(t2-t1))
      if viz:
        if 'q' in raw_input(colorize(Color.RED,'continue? (enter to continue, q to exit): ',True)):
          break
    except:
      traceback.print_exc()
      logging.info(colorize(Color.GREEN,'>>>> CONTINUING....', bold=True))
    
    RV3.reset()
    continue
  
  depth_db.close()
  seg_db.close()
  out_db.close()

if __name__=='__main__':
  import argparse
  parser = argparse.ArgumentParser(description='Genereate Synthetic Scene-Text Images')
  parser.add_argument('--viz',action='store_true',dest='viz',default=False,help='flag for turning on visualizations')
  args = parser.parse_args()

  logging.basicConfig(level=logging.DEBUG)
  main(args.viz)
