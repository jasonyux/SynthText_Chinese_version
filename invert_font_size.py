# Author: Ankush Gupta
# Date: 2015
"Script to generate font-models."

import pygame
from pygame import freetype
from text_utils import FontState
import numpy as np 
import matplotlib.pyplot as plt 
import cPickle as cp
import os.path as osp
import os


def populate_fontlist(path, out_file):
	my_fontlist = []
	for filename in os.listdir(path):
		if filename.endswith('.ttf') or filename.endswith('.TTF'):
			fontfile = filename.decode('utf-8')
			parent_dir = os.path.basename(os.path.normpath(path))
			print(osp.join(parent_dir, fontfile))
			my_fontlist.append(osp.join(parent_dir, fontfile))

	with open(out_file, 'w') as open_file:
		for font in my_fontlist:
			open_file.write('{}\n'.format(font.encode('utf-8')))


pygame.init()


ys = np.arange(8,200)
A = np.c_[ys,np.ones_like(ys)]

xs = []
models = {} #linear model

# this function only needs to be run once
# populate_fontlist("data/fonts/more_font", "data/fonts/fontlist.txt")

FS = FontState()
#plt.figure()
#plt.hold(True)
for i in xrange(len(FS.fonts)):
	print i, FS.fonts[i]
	font = freetype.Font(FS.fonts[i], size=12)
	h = []
	for y in ys:
		h.append(font.get_sized_glyph_height(y))
	h = np.array(h)
	m,_,_,_ = np.linalg.lstsq(A,h)
	models[font.name] = m
	xs.append(h)
	print font.name

font_model_path = osp.join('data', 'models/font_px2pt.cp')
with open(font_model_path,'w') as f:
	cp.dump(models,f)
#plt.plot(xs,ys[i])
#plt.show()
