"""
Sample code for load the 8000 pre-processed background image data.
Before running, first download the files from:
  https://github.com/ankush-me/SynthText#pre-generated-dataset
"""

import h5py
import numpy as np
from PIL import Image
import os.path as osp
import cPickle as cp

"""
im_dir = 'bg_img'
depth_db = h5py.File('depth.h5','r')
seg_db = h5py.File('seg.h5','r')
"""
#add more data into the dset
more_depth_path='data/game_dset/depth.h5'
more_seg_path='data/game_dset/seg.h5'

im_dir='data/game_dset/images'
depth_db = h5py.File(more_depth_path,'r')
seg_db = h5py.File(more_seg_path,'r')

imnames = sorted(depth_db.keys())

"""
with open('imnames.cp', 'rb') as f:
  filtered_imnames = set(cp.load(f))
"""
for imname in imnames:
  # ignore if not in filetered list:
  # if imname not in filtered_imnames: continue
  
  # get the colour image:
  img = Image.open(osp.join(im_dir, imname)).convert('RGB')
  
  # get depth:
  depth = depth_db[imname][:].T
  # depth = depth[:,:,0]

  # get segmentation info:
  seg = seg_db['mask'][imname][:].astype('float32')
  area = seg_db['mask'][imname].attrs['area']
  label = seg_db['mask'][imname].attrs['label']

  print 'seg info',seg.shape,area.shape,label.shape

  # re-size uniformly:
  sz = depth.shape[:2][::-1]
  img = np.array(img.resize(sz,Image.ANTIALIAS))
  seg = np.array(Image.fromarray(seg).resize(sz,Image.NEAREST))
  
  # see `gen.py` for how to use img, depth, seg, area, label for further processing.
  #    https://github.com/ankush-me/SynthText/blob/master/gen.py