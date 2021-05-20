# Author: Ankush Gupta
# Date: 2015

"""
Visualize the generated localization synthetic
data stored in h5 data-bases
"""
from __future__ import division
import os
import os.path as osp
import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt 
import h5py 
from common import *
import logging

def viz_textbb(text_im, charBB_list, wordBB, alpha=1.0, image_name=None):
    """
    text_im : image containing text
    charBB_list : list of 2x4xn_i bounding-box matrices
    wordBB : 2x4xm matrix of word coordinates
    """
    plt.close(1)
    plt.figure(1)
    plt.imshow(text_im)
    plt.hold(True)
    H,W = text_im.shape[:2]
    
    plot_charBB = True
    plot_wordBB = True
    hide_axis = True

    if plot_charBB:
        # plot the character-BB:
        for i in xrange(len(charBB_list)):
            bbs = charBB_list[i]
            ni = bbs.shape[-1]
            for j in xrange(ni):
                bb = bbs[:,:,j]
                bb = np.c_[bb,bb[:,0]]
                # given in the format of x=@bb[0,:], y=@bb[1,:]
                plt.plot(bb[0,:], bb[1,:], 'r', alpha=alpha/2)

    if plot_wordBB:
        # plot the word-BB:
        for i in xrange(wordBB.shape[-1]):
            bb = wordBB[:,:,i]
            bb = np.c_[bb,bb[:,0]]
            plt.plot(bb[0,:], bb[1,:], 'g', alpha=alpha)
            # visualize the indiv vertices:
            vcol = ['r','g','b','k']
            for j in xrange(4):
                plt.scatter(bb[0,j],bb[1,j],color=vcol[j])    

    plt.gca().set_xlim([0,W-1])
    plt.gca().set_ylim([H-1,0])
    plt.show(block=False)
    if hide_axis:
        plt.axis('off')
        plt.margins(0,0)
    plt.savefig("out_images/{}.png".format(image_name.encode('utf-8')))

def main(db_fname):
    db = h5py.File(db_fname, 'r')
    dsets = sorted(db['data'].keys())
    print "total number of images : ", colorize(Color.RED, len(dsets), highlight=True)
    for k in dsets:
        rgb = db['data'][k][...]
        charBB = db['data'][k].attrs['charBB']
        wordBB = db['data'][k].attrs['wordBB']
        txt = db['data'][k].attrs['txt']

        viz_textbb(rgb, [charBB], wordBB, image_name=k)
        logging.info(colorize(Color.RED, "image name        : {}".format(k.encode('utf-8')), bold=True))
        logging.info(colorize(Color.YELLOW, "  ** no. of chars : {}".format(charBB.shape[-1]) ))
        logging.info(colorize(Color.YELLOW, "  ** no. of words : {}".format(wordBB.shape[-1]) ))
        logging.info(colorize(Color.GREEN, "  ** text         : {}".format("--".join(txt)) ))
        logging.info(colorize(Color.GREEN, "  ** raw_text         : {}".format(repr("--".join(txt))) ))

        #if 'q' in raw_input("next? ('q' to exit) : "):
        #    break
    db.close()

if __name__=='__main__':
    logging.basicConfig(level=logging.DEBUG)
    #main('results/SynthText.h5')
    main('results/SynthText_game_3000.h5')

