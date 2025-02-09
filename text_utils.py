from __future__ import division
import numpy as np
import matplotlib.pyplot as plt 
import scipy.io as sio
import os.path as osp
import random, os
import cv2
import cPickle as cp
import scipy.signal as ssig
import scipy.stats as sstat
import pygame, pygame.locals
from pygame import freetype
import logging
from PIL import Image
import math
from common import *

def is_chinese(ch):    
    #uc=ch.decode('utf-8')     
    if u'\u4e00' <= ch<=u'\u9fff':
        return True
    else:
        return False

def sample_weighted(p_dict):
    ps = p_dict.keys()
    return p_dict[np.random.choice(ps,p=ps)]

def move_bb(bbs, t):
    """
    Translate the bounding-boxes in by t_x,t_y.
    BB : 2x4xn
    T  : 2-long np.array
    """
    return bbs + t[:,None,None]

def crop_safe(arr, rect, bbs=[], pad=0, rotated=False):
    """
    ARR : arr to crop
    RECT: (x,y,w,h) : area to crop to
    BBS : nx4 xywh format bounding-boxes
    PAD : percentage to pad

    Does safe cropping. Returns the cropped rectangle and
    the adjusted bounding-boxes
    """
    rect = np.array(rect)
    if rotated:
        # if rotated, increase x and decrease y
        rect[0] += pad
        rect[0] -= pad
        rect[2:] += 2*pad
    else:
        rect[:2] -= pad
        rect[2:] += 2*pad
    v0 = [max(0,rect[0]), max(0,rect[1])]
    v1 = [min(arr.shape[0], rect[0]+rect[2]), min(arr.shape[1], rect[1]+rect[3])]
    arr = arr[v0[0]:v1[0],v0[1]:v1[1],...]
    if len(bbs) > 0:
        for i in xrange(len(bbs)):
            bbs[i,0] -= v0[0]
            bbs[i,1] -= v0[1]
        return arr, bbs
    else:
        return arr


class BaselineState(object):
    curve = lambda this, a: lambda x: a*x*x
    differential = lambda this, a: lambda x: 2*a*x
    a = [0.50, 0.05]

    # TODO: attempt to do no curve1
    """
    curve = lambda this, a: lambda x: a*x
    differential = lambda this, a: lambda x: a
    """
    def get_sample(self):
        """
        Returns the functions for the curve and differential for a and b
        """
        sgn = 1.0
        if np.random.rand() < 0.5:
            sgn = -1
        a = self.a[1]*np.random.randn() + sgn*self.a[0]
        return {
            'curve': self.curve(a),
            'diff': self.differential(a),
        }

class RenderFont(object):
    """
    Outputs a rasterized font sample.
        Output is a binary mask matrix cropped closesly with the font.
        Also, outputs ground-truth bounding boxes and text string
    """

    def __init__(self, data_dir='data'):
        # distribution over the type of text:
        # whether to get a single word, paragraph or a line:
        self.p_text = {0.0 : 'WORD',
                       0.0 : 'LINE',
                       1.0 : 'PARA'}

        ## TEXT PLACEMENT PARAMETERS:
        self.f_shrink = 0.90
        self.max_shrink_trials = 5 # 0.9^5 ~= 0.6
        # the minimum number of characters that should fit in a mask
        # to define the maximum font height.
        self.min_nchar = 1
        self.min_font_h = 16 #px : 0.6*12 ~ 7px <= actual minimum height
        self.max_font_h = 120 #px
        self.p_flat = 0.10

        # curved baseline:
        #self.p_curved = 1.0
        # either it is curved, or not
        self.p_curved = 0.1
        self.baselinestate = BaselineState()

        # not curved but rotated
        self.p_rotated = 0.2

        # vertical alignmnent vs horizontal alignment
        self.p_vertical = 0.2
        """
        # rotation only / vertical
        self.p_rotated = 0.4
        self.p_vertical = 0.3
        """
        

        # text-source : gets english text:
        # now this folder modified to contain only chinese texts
        self.text_source = TextSource(min_nchar=self.min_nchar,
                                      fn=osp.join(data_dir,'game_texts/camp/'))

        # get font-state object:
        self.font_state = FontState(data_dir)

        pygame.init()

    # configures the distribution
    def configure(self, conf_args):
        if conf_args.vertical >= 0 and conf_args.vertical <= 1:
            self.p_vertical = conf_args.vertical
        if conf_args.rotated >= 0 and conf_args.rotated <= 1:
            self.p_rotated = conf_args.rotated
        if conf_args.curved >= 0 and conf_args.curved <= 1:
            self.p_curved = conf_args.curved
        logging.info(colorize(Color.BLUE, "configured p_vert={} p_rot={} p_curved={}".format(self.p_vertical, self.p_rotated, self.p_curved)))


    def render_multiline(self,font,text):
        """
        renders multiline TEXT on the pygame surface SURF with the
        font style FONT.
        A new line in text is denoted by \n, no other characters are 
        escaped. Other forms of white-spaces should be converted to space.

        returns the updated surface, words and the character bounding boxes.
        """
        # get the number of lines
        lines = text.split('\n')
        lengths = [len(l) for l in lines]

        # font parameters:
        line_spacing = font.get_sized_height() + 1
        
        # initialize the surface to proper size:
        line_bounds = font.get_rect(lines[np.argmax(lengths)])
        fsize = (round(2.0*line_bounds.width), round(1.25*line_spacing*len(lines)))
        surf = pygame.Surface(fsize, pygame.locals.SRCALPHA, 32)

        bbs = []
        space = font.get_rect('o')
        x, y = 0, 0
        #TODO: enable rotation for multiline texts as well
        for l in lines:
            x = 0 # carriage-return
            y += line_spacing # line-feed

            for ch in l: # render each character
                if ch.isspace(): # just shift
                    x += space.width
                else:
                    # render the character
                    ch_bounds = font.render_to(surf, (x,y), ch)
                    ch_bounds.x = x + ch_bounds.x
                    ch_bounds.y = y - ch_bounds.y
                    x += ch_bounds.width
                    bbs.append(np.array(ch_bounds))

        # get the union of characters for cropping:
        r0 = pygame.Rect(bbs[0])
        rect_union = r0.unionall(bbs)

        # get the words:
        words = ' '.join(text.split())
        # words=words.decode('utf-8')
        # print words
        # crop the surface to fit the text:
        bbs = np.array(bbs)
        surf_arr, bbs = crop_safe(pygame.surfarray.pixels_alpha(surf), rect_union, bbs, pad=5)
        surf_arr = surf_arr.swapaxes(0,1)
        #self.visualize_bb(surf_arr,bbs)
        return surf_arr, words, bbs


    def render_vertical(self, font, word_text):
        wl = len(word_text)
        isword = len(word_text.split())==1
        lspace = font.get_sized_height() + 1
        lbound = font.get_rect(word_text)
        fsize = (round(2.0*lbound.width), round(wl*lspace))
        surf = pygame.Surface(fsize, pygame.locals.SRCALPHA, 32)
        
        bbs = []
        space = font.get_rect(' ')
        x, y = 0, 0

        # y needs to be offsetted for correct rendering
        # ch_bounds = font.render_to(surf, (x,y), word_text[0])
        ch_bounds = font.get_rect(word_text[0])
        y += ch_bounds.height + 2 #for padding
        first_width = ch_bounds.width

        for ch in word_text: # render each character
            if ch.isspace(): # just shift
                y += space.width
            else:
                temp = font.get_rect(ch)
                # render the character
                x_diff = (first_width - temp.width)/2.0
                ch_bounds = font.render_to(surf, (x+x_diff,y), ch)
                # center align it
                ch_bounds.y = y - ch_bounds.y
                #x += ch_bounds.width
                y += ch_bounds.height + 2
                bbs.append(np.array(ch_bounds))

        # get the union of characters for cropping:
        r0 = pygame.Rect(bbs[0])
        rect_union = r0.unionall(bbs)
        logging.debug("vertical union rect{}".format(rect_union))

        # crop the surface to fit the text:
        bbs = np.array(bbs)
        surf_arr, bbs = crop_safe(pygame.surfarray.pixels_alpha(surf), rect_union, bbs, pad=5)
        surf_arr = surf_arr.swapaxes(0,1)
        return surf_arr, word_text, bbs


    def render_rotated(self, font, word_text, vertical=False):
        wl = len(word_text)
        isword = len(word_text.split())==1
        lspace = font.get_sized_height() + 1
        lbound = font.get_rect(word_text)
        fsize = (round(2.0*lbound.width), round(3*lspace))
        surf = pygame.Surface(fsize, pygame.locals.SRCALPHA, 32)

        angle = np.random.randint(low=-89, high=89)
        logging.debug("angle={}".format(angle))
        surf = pygame.transform.rotate(surf, angle)

        # baseline state
        mid_idx = wl//2
        
        BS = self.baselinestate.get_sample()
        curve = [BS['curve'](i-mid_idx) for i in xrange(wl)]
        rots = []
        if vertical:
            rots  = [angle for i in xrange(wl)]
        else:
            rots  = [-angle for i in xrange(wl)]
        
        bbs = []
        # place middle char
        rect = font.get_rect(word_text[mid_idx])
        rect.centerx = surf.get_rect().centerx
        rect.centery = surf.get_rect().centery + rect.height
        rect.centery +=  curve[mid_idx]
        ch_bounds = font.render_to(surf, rect, word_text[mid_idx], rotation=rots[mid_idx])
        ch_bounds.x = rect.x + ch_bounds.x
        ch_bounds.y = rect.y - ch_bounds.y
        mid_ch_bb = np.array(ch_bounds)

        logging.debug(colorize(Color.RED, "[{}]th=mid char {} with y at {}".format(mid_idx, word_text[mid_idx].encode('utf-8'), rect.y)))
        logging.debug(colorize(Color.RED, "newrect at {}".format(rect)))

        # render chars to the left and right:
        last_rect = rect
        ch_idx = []
        # do rotation without curving
        # verical x angle cc is same as horizontal 90-x angle c
        if vertical:
            if angle < 0:
                angle = -90 - angle
            else:
                angle = 90 - angle

        for i in xrange(wl):
            #skip the middle character
            if i==mid_idx: 
                bbs.append(mid_ch_bb)
                ch_idx.append(i)
                continue

            if i < mid_idx: #left-chars
                i = mid_idx-1-i
            elif i==mid_idx+1: #right-chars begin
                last_rect = rect

            ch_idx.append(i)
            ch = word_text[i]

            newrect = font.get_rect(ch)
            newrect.y = last_rect.y

            logging.debug("{} top={} left={}, x={}, y={}, topleft={}, bottomright={}".format(
            type(newrect), newrect.top, newrect.left, newrect.x, newrect.y, newrect.topleft, newrect.bottomright))

            if i > mid_idx:
                newrect.topleft = (last_rect.topright[0]+2, newrect.topleft[1])
            else:
                newrect.topright = (last_rect.topleft[0]-2, newrect.topleft[1])

            if abs(angle) <= 45:
                y_dist = math.tan(math.radians(angle)) * ((last_rect.width + newrect.width)/2.0)
                logging.debug("grad={}, y_dist={}".format(math.tan(math.radians(angle)), y_dist))
                if i > mid_idx:
                    newrect.centery += y_dist
                else:
                    newrect.centery -= y_dist
            else: # now, instead of shifting y, I shift x
                y_dist = ((last_rect.height + newrect.height)/2.0) + 2 # no y-overlap
                x_dist = ((last_rect.width + newrect.width)/2.0) - (y_dist / math.tan(math.radians(angle)))
                logging.debug("grad={}, y_dist={}, x_dist={}".format(math.tan(math.radians(angle)), y_dist, x_dist))
                if i > mid_idx:
                    newrect.centery += y_dist
                    newrect.centerx -= x_dist
                else:
                    newrect.centery -= y_dist
                    newrect.centerx += x_dist
                
            logging.debug(colorize(Color.RED, "[{}]th char {} with y at {}".format(i, ch.encode('utf-8'), newrect.y)))
            logging.debug(colorize(Color.RED, "moved newrect at {}".format(newrect)))
            try:
                bbrect = font.render_to(surf, newrect, ch, rotation=rots[i])
            except ValueError:
                bbrect = font.render_to(surf, newrect, ch)
            bbrect.x = newrect.x + bbrect.x
            bbrect.y = newrect.y - bbrect.y
            bbs.append(np.array(bbrect))
            last_rect = newrect
        
        # correct the bounding-box order:
        bbs_sequence_order = [None for i in ch_idx]
        for idx,i in enumerate(ch_idx):
            bbs_sequence_order[i] = bbs[idx]
        bbs = bbs_sequence_order

        # get the union of characters for cropping:
        r0 = pygame.Rect(bbs[0])
        rect_union = r0.unionall(bbs)

        # crop the surface to fit the text:
        bbs = np.array(bbs)
        surf_arr, bbs = crop_safe(pygame.surfarray.pixels_alpha(surf), rect_union, bbs, pad=5, rotated=True)
        surf_arr = surf_arr.swapaxes(0,1)
        return surf_arr, word_text, bbs

    def render_curved(self, font, word_text):
        """
        use curved baseline for rendering word
        """
        wl = len(word_text)
        isword = len(word_text.split())==1

        # do curved iff, the length of the word <= 10
        #if not isword or wl > 10 or np.random.rand() > self.p_curved:
        rand = np.random.rand()
        rotation = True if np.random.rand() < self.p_rotated else False
        vertical = True if np.random.rand() < self.p_vertical else False
        # TODO: this branching could be improved
        if not isword or wl > 10 or (not rotation and not vertical):
            # horizontal not rotated
            logging.debug("going multiline")
            return self.render_multiline(font, word_text)
        elif rand < self.p_curved or wl <= 2:
            # curved, continue
            logging.debug("going curved")
            pass
        elif vertical and not rotation: #vertical not rotated
            logging.debug("going vertical")
            return self.render_vertical(font, word_text)
        else: # rotated
            logging.debug("going rotated")
            return self.render_rotated(font, word_text, vertical=vertical)

        # create the surface:
        lspace = font.get_sized_height() + 1
        lbound = font.get_rect(word_text)
        fsize = (round(2.0*lbound.width), round(3*lspace))
        surf = pygame.Surface(fsize, pygame.locals.SRCALPHA, 32)

        # baseline state
        mid_idx = wl//2
        BS = self.baselinestate.get_sample()
        
        # this is the original one, rotation and curve
        curve = [BS['curve'](i-mid_idx) for i in xrange(wl)]
        curve[mid_idx] = -np.sum(curve) / (wl-1)
        rots  = [-int(math.degrees(math.atan(BS['diff'](i-mid_idx)/(font.size/2)))) for i in xrange(wl)]

        bbs = []
        # place middle char
        rect = font.get_rect(word_text[mid_idx])
        rect.centerx = surf.get_rect().centerx
        rect.centery = surf.get_rect().centery + rect.height
        rect.centery +=  curve[mid_idx]
        ch_bounds = font.render_to(surf, rect, word_text[mid_idx], rotation=rots[mid_idx])
        ch_bounds.x = rect.x + ch_bounds.x
        ch_bounds.y = rect.y - ch_bounds.y
        mid_ch_bb = np.array(ch_bounds)

        # render chars to the left and right:
        last_rect = rect
        ch_idx = []
        for i in xrange(wl):
            #skip the middle character
            if i==mid_idx: 
                bbs.append(mid_ch_bb)
                ch_idx.append(i)
                continue

            if i < mid_idx: #left-chars
                i = mid_idx-1-i
            elif i==mid_idx+1: #right-chars begin
                last_rect = rect

            ch_idx.append(i)
            ch = word_text[i]

            newrect = font.get_rect(ch)
            newrect.y = last_rect.y

            logging.debug("{} top={} left={}, x={}, y={}, topleft={}, bottomright={}".format(
            type(newrect), newrect.top, newrect.left, newrect.x, newrect.y, newrect.topleft, newrect.bottomright))

            if i > mid_idx:
                newrect.topleft = (last_rect.topright[0]+2, newrect.topleft[1])
            else:
                newrect.topright = (last_rect.topleft[0]-2, newrect.topleft[1])
            newrect.centery = max(newrect.height, min(fsize[1] - newrect.height, newrect.centery + curve[i]))
                
            try:
                bbrect = font.render_to(surf, newrect, ch, rotation=rots[i])
            except ValueError:
                bbrect = font.render_to(surf, newrect, ch)
            bbrect.x = newrect.x + bbrect.x
            bbrect.y = newrect.y - bbrect.y
            bbs.append(np.array(bbrect))
            last_rect = newrect
        
        # correct the bounding-box order:
        bbs_sequence_order = [None for i in ch_idx]
        for idx,i in enumerate(ch_idx):
            bbs_sequence_order[i] = bbs[idx]
        bbs = bbs_sequence_order

        # get the union of characters for cropping:
        r0 = pygame.Rect(bbs[0])
        rect_union = r0.unionall(bbs)
        # logging.debug("working union {}".format(bbs))

        # crop the surface to fit the text:
        bbs = np.array(bbs)
        surf_arr, bbs = crop_safe(pygame.surfarray.pixels_alpha(surf), rect_union, bbs, pad=5)
        logging.debug("cropped union {}".format(bbs))
        surf_arr = surf_arr.swapaxes(0,1)
        return surf_arr, word_text, bbs


    def get_nline_nchar(self,mask_size,font_height,font_width):
        """
        Returns the maximum number of lines and characters which can fit
        in the MASK_SIZED image.
        """
        H,W = mask_size
        nline = int(np.ceil(H/(2*font_height)))
        nchar = int(np.floor(W/font_width))
        return nline,nchar

    def place_text(self, text_arrs, back_arr, bbs):
        areas = [-np.prod(ta.shape) for ta in text_arrs]
        order = np.argsort(areas)

        locs = [None for i in range(len(text_arrs))]
        out_arr = np.zeros_like(back_arr)
        for i in order:            
            ba = np.clip(back_arr.copy().astype(np.float), 0, 255)
            ta = np.clip(text_arrs[i].copy().astype(np.float), 0, 255)
            ba[ba > 127] = 1e8
            intersect = ssig.fftconvolve(ba,ta[::-1,::-1],mode='valid')
            safemask = intersect < 1e8

            if not np.any(safemask): # no collision-free position:
                #warn("COLLISION!!!")
                return back_arr,locs[:i],bbs[:i],order[:i]

            minloc = np.transpose(np.nonzero(safemask))
            loc = minloc[np.random.choice(minloc.shape[0]),:]
            locs[i] = loc

            # update the bounding-boxes:
            bbs[i] = move_bb(bbs[i],loc[::-1])

            # blit the text onto the canvas
            w,h = text_arrs[i].shape
            out_arr[loc[0]:loc[0]+w,loc[1]:loc[1]+h] += text_arrs[i]

        return out_arr, locs, bbs, order

    def robust_HW(self,mask):
        m = mask.copy()
        m = (~mask).astype('float')/255
        rH = np.median(np.sum(m,axis=0))
        rW = np.median(np.sum(m,axis=1))
        return rH,rW

    def sample_font_height_px(self,h_min,h_max):
        if np.random.rand() < self.p_flat:
            rnd = np.random.rand()
        else:
            rnd = np.random.beta(2.0,2.0)

        h_range = h_max - h_min
        f_h = np.floor(h_min + h_range*rnd)
        return f_h

    def bb_xywh2coords(self,bbs):
        """
        Takes an nx4 bounding-box matrix specified in x,y,w,h
        format and outputs a 2x4xn bb-matrix, (4 vertices per bb).
        """
        n,_ = bbs.shape
        coords = np.zeros((2,4,n))
        for i in xrange(n):
            coords[:,:,i] = bbs[i,:2][:,None]
            coords[0,1,i] += bbs[i,2]
            coords[:,2,i] += bbs[i,2:4]
            coords[1,3,i] += bbs[i,3]
        return coords


    def render_sample(self,font,mask):
        """
        Places text in the "collision-free" region as indicated
        in the mask -- 255 for unsafe, 0 for safe.
        The text is rendered using FONT, the text content is TEXT.
        """
        #H,W = mask.shape
        H,W = self.robust_HW(mask)
        f_asp = self.font_state.get_aspect_ratio(font)

        # find the maximum height in pixels:
        max_font_h = min(0.9*H, (1/f_asp)*W/(self.min_nchar+1))
        max_font_h = min(max_font_h, self.max_font_h)
        if max_font_h < self.min_font_h: # not possible to place any text here
            return #None

        # let's just place one text-instance for now
        ## TODO : change this to allow multiple text instances?
        i = 0
        while i < self.max_shrink_trials and max_font_h > self.min_font_h:
            # if i > 0:
            #     print colorize(Color.BLUE, "shrinkage trial : %d"%i, True)

            # sample a random font-height:
            f_h_px = self.sample_font_height_px(self.min_font_h, max_font_h)
            #print "font-height : %.2f (min: %.2f, max: %.2f)"%(f_h_px, self.min_font_h,max_font_h)
            # convert from pixel-height to font-point-size:
            f_h = self.font_state.get_font_size(font, f_h_px)

            # update for the loop
            max_font_h = f_h_px 
            i += 1

            font.size = f_h # set the font-size

            # compute the max-number of lines/chars-per-line:
            nline,nchar = self.get_nline_nchar(mask.shape[:2],f_h,f_h*f_asp)
            #print "  > nline = %d, nchar = %d"%(nline, nchar)

            assert nline >= 1 and nchar >= self.min_nchar

            # sample text:
            text_type = sample_weighted(self.p_text)
            text = self.text_source.sample(nline,nchar,kind=text_type,font=font)
            #text = self.text_source.sample(nline,nchar,'PARA')
            #text = self.text_source.sample(nline,nchar,'WORD')
            
            #print 'before the if judge',text.encode('utf-8') #TODO: it could be a paragraph as well
            if len(text)==0:
                logging.debug(colorize(Color.GREEN, ' didn\'t pass because of len(text)==0'))
                continue
            if np.any([len(line)==0 for line in text]):
                logging.debug(colorize(Color.GREEN, ' didn\'t pass because of np.any'))
                continue
            logging.info(colorize(Color.GREEN, 'pass the text filter'))
            #print colorize(Color.GREEN, text)

            # render the text:
            txt_arr,txt,bb = self.render_curved(font, text)
            bb = self.bb_xywh2coords(bb)

            # make sure that the text-array is not bigger than mask array:
            if np.any(np.r_[txt_arr.shape[:2]] > np.r_[mask.shape[:2]]):
                #warn("text-array is bigger than mask")
                logging.info(colorize(Color.GREEN, 'fail in mask array size'))
                continue
            logging.info(colorize(Color.GREEN, 'pass in mask array size'))
            
            # position the text within the mask:
            text_mask,loc,bb, _ = self.place_text([txt_arr], mask, [bb])
            if len(loc) > 0:#successful in placing the text collision-free:
                return text_mask,loc[0],bb[0],text
        return #None


    def visualize_bb(self, text_arr, bbs):
        ta = text_arr.copy()
        for r in bbs:
            cv.rectangle(ta, (r[0],r[1]), (r[0]+r[2],r[1]+r[3]), color=128, thickness=1)
        plt.imshow(ta,cmap='gray')
        plt.show()


class FontState(object):
    """
    Defines the random state of the font rendering  
    """
    size = [50, 10]  # normal dist mean, std
    underline = 0.00 # disabled underline
    strong = 0.5
    oblique = 0.2
    wide = 0.5
    strength = [0.05, 0.1]  # uniform dist in this interval
    underline_adjustment = [1.0, 2.0]  # normal dist mean, std
    kerning = [2, 5, 0, 20]  # beta distribution alpha, beta, offset, range (mean is a/(a+b))
    border = 0.5 # increased for visual effects
    random_caps = -1 ## don't recapitalize : retain the capitalization of the lexicon
    capsmode = [str.lower, str.upper, str.capitalize]  # lower case, upper case, proper noun
    curved = 0.2
    random_kerning = 0.2
    random_kerning_amount = 0.1

    def __init__(self, data_dir='data'):

        char_freq_path = osp.join(data_dir, 'models/char_freq.cp')        
        font_model_path = osp.join(data_dir, 'models/font_px2pt.cp')

        # get character-frequencies in the English language:
        with open(char_freq_path,'r') as f:
            self.char_freq = cp.load(f)

        # get the model to convert from pixel to font pt size:
        with open(font_model_path,'r') as f:
            self.font_model = cp.load(f)

        # get the names of fonts to use:
        self.FONT_LIST = osp.join(data_dir, 'fonts/fontlist.txt')
        self.fonts = [os.path.join(data_dir,'fonts',f.strip()) for f in open(self.FONT_LIST)]


    def get_aspect_ratio(self, font, size=None):
        """
        Returns the median aspect ratio of each character of the font.
        """
        if size is None:
            size = 12 # doesn't matter as we take the RATIO
        chars = ''.join(self.char_freq.keys())
        w = np.array(self.char_freq.values())

        # get the [height,width] of each character:
        try:
            sizes = font.get_metrics(chars,size)
            good_idx = [i for i in xrange(len(sizes)) if sizes[i] is not None]
            sizes,w = [sizes[i] for i in good_idx], w[good_idx]
            sizes = np.array(sizes).astype('float')[:,[3,4]]        
            r = np.abs(sizes[:,1]/sizes[:,0]) # width/height
            good = np.isfinite(r)
            r = r[good]
            w = w[good]
            w /= np.sum(w)
            r_avg = np.sum(w*r)
            return r_avg
        except:
            return 1.0

    def get_font_size(self, font, font_size_px):
        """
        Returns the font-size which corresponds to FONT_SIZE_PX pixels font height.
        """
        m = self.font_model[font.name]
        return m[0]*font_size_px + m[1] #linear model


    def sample(self):
        """
        Samples from the font state distribution
        """
        return {
            'font': self.fonts[int(np.random.randint(0, len(self.fonts)))],
            'size': self.size[1]*np.random.randn() + self.size[0],
            'underline': np.random.rand() < self.underline,
            'underline_adjustment': max(2.0, min(-2.0, self.underline_adjustment[1]*np.random.randn() + self.underline_adjustment[0])),
            'strong': np.random.rand() < self.strong,
            'oblique': np.random.rand() < self.oblique,
            'strength': (self.strength[1] - self.strength[0])*np.random.rand() + self.strength[0],
            'char_spacing': int(self.kerning[3]*(np.random.beta(self.kerning[0], self.kerning[1])) + self.kerning[2]),
            'border': np.random.rand() < self.border,
            'random_caps': np.random.rand() < self.random_caps,
            'capsmode': random.choice(self.capsmode),
            'curved': np.random.rand() < self.curved,
            'random_kerning': np.random.rand() < self.random_kerning,
            'random_kerning_amount': self.random_kerning_amount,
        }

    def init_font(self,fs):
        """
        Initializes a pygame font.
        FS : font-state sample
        """
        font = freetype.Font(fs['font'], size=fs['size'])
        font.underline = fs['underline']
        font.underline_adjustment = fs['underline_adjustment']
        font.strong = fs['strong']
        font.oblique = fs['oblique']
        font.strength = fs['strength']
        char_spacing = fs['char_spacing']
        font.antialiased = True
        font.origin = True
        return font


class TextSource(object):
    """
    Provides text for words, paragraphs, sentences.
    """
    def __init__(self, min_nchar, fn):
        """
        TXT_FN : path to file containing text data.
        """
        self.min_nchar = min_nchar
        self.fdict = {'WORD':self.sample_word,
                      'LINE':self.sample_line,
                      'PARA':self.sample_para}
        files= os.listdir(fn)
        files=files[0:-1]
        # print files
        random.shuffle(files)
        filecnt=10
        self.txt=[]
        for filename in files: #TODO: add distribution here for text sources
            filecnt-=1
            if filecnt==0:
                break            
            print filename
            fc=filename.decode('utf-8')
            fc=fn+fc
            print fc
            with open(fc,'r') as f:
                for l in f.readlines():
                    line=l.strip()
                    # add the file contents
                    #"""
                    try:
                        line=line.decode('utf-8')
                    except:
                        print colorize(Color.RED, 'cannot decode', line)
                        pass
                        # print 'failed to decode:', line
                    #"""
                    self.txt.append(line)
        random.shuffle(self.txt)          
        print len(self.txt)
            #self.txt = [l.strip() for l in f.readlines()]
            #self.txt=self.txt.decode('utf-8')
        
        # distribution over line/words for LINE/PARA:
        self.p_line_nline = np.array([0.85, 0.10, 0.05])
        self.p_line_nword = [4,3,12]  # normal: (mu, std)
        self.p_para_nline = [1.0,1.0]#[1.7,3.0] # beta: (a, b), max_nline
        self.p_para_nword = [1.7,3.0,10] # beta: (a,b), max_nword

        # probability to center-align a paragraph:
        self.center_para = 0.5


    def check_symb_frac(self, txt, f=0.35):
        """
        T/F return : T iff fraction of symbol/special-charcters in
                     txt is less than or equal to f (default=0.25).
        """
        chcnt=0
        line=txt#.decode('utf-8')
        for ch in line:
            if ch.isalnum() or is_chinese(ch):
                chcnt+=1
        return float(chcnt)/(len(txt)+0.0)>f
        #return np.sum([not ch.isalnum() for ch in txt])/(len(txt)+0.0) <= f

    def is_good(self, txt, f=0.35):
        """
        T/F return : T iff the lines in txt (a list of txt lines)
                     are "valid".
                     A given line l is valid iff:
                         1. It is not empty.
                         2. symbol_fraction > f
                         3. Has at-least self.min_nchar characters
                         4. Not all characters are i,x,0,O,-
        """
        def is_txt(l):
            char_ex = ['i','I','o','O','0','-']
            chs = [ch in char_ex for ch in l]
            return not np.all(chs)

        return [ (len(l)> self.min_nchar
                 and self.check_symb_frac(l,f)
                 and is_txt(l)) for l in txt ]

    def center_align(self, lines):
        """
        PADS lines with space to center align them
        lines : list of text-lines.
        """
        ls = [len(l) for l in lines]
        max_l = max(ls)
        for i in xrange(len(lines)):
            l = lines[i].strip()
            dl = max_l-ls[i]
            lspace = dl//2
            rspace = dl-lspace
            lines[i] = ' '*lspace+l+' '*rspace
        return lines

    def get_lines(self, nline, nword, nchar_max, f=0.35, niter=100):
        def h_lines(niter=100):
            lines = ['']
            iter = 0
            while not np.all(self.is_good(lines,f)) and iter < niter:
                iter += 1
                line_start = np.random.choice(len(self.txt)-nline)
                lines = [self.txt[line_start+i] for i in range(nline)]
            return lines

        lines = ['']
        iter = 0
        while not np.all(self.is_good(lines,f)) and iter < niter:
            iter += 1
            lines = h_lines(niter=100)
            # get words per line:
            nline = len(lines)
            for i in range(nline):
                words = lines[i].split()
                dw = len(words)-nword[i]
                if dw > 0:
                    first_word_index = random.choice(range(dw+1))
                    lines[i] = ' '.join(words[first_word_index:first_word_index+nword[i]])

                while len(lines[i]) > nchar_max: #chop-off characters from end:
                    if not np.any([ch.isspace() for ch in lines[i]]):
                        lines[i] = ''
                    else:
                        lines[i] = lines[i][:len(lines[i])-lines[i][::-1].find(' ')].strip()
        
        if not np.all(self.is_good(lines,f)):
            return #None
        else:
            return lines

    def valid_ch_range(self):
        # use it inclusively
        regular_range = (u'\U00000021', u'\U0000007F')
        chj_ideo_range = (u'\u4e00', u'\u9fff')
        chj_ideo_ext_a_range = (u'\u3400', u'\u4dbf')
        chj_ideo_ext_b_range = (u'\U00020000', u'\U0002A6DF')
        chj_ideo_ext_c_range = (u'\U0002A700', u'\U0002B73F')
        chj_ideo_ext_d_range = (u'\U0002B740', u'\U0002B81F')
        chj_ideo_ext_e_range = (u'\U0002B820', u'\U0002CEAF')
        chj_punctuations_range = (u'\uFE50', u'\uFF65')
        chj_punctuations_range_a = (u'\u3001', u'\u3002')
        chj_punctuations_range_b = (u'\u201c', u'\u2027')
        return [regular_range, chj_ideo_range, 
                chj_ideo_ext_a_range, chj_ideo_ext_b_range, chj_ideo_ext_c_range, chj_ideo_ext_d_range, chj_ideo_ext_e_range, 
                chj_punctuations_range, chj_punctuations_range_a, chj_punctuations_range_b]

    def cannot_render(self, ch, font):
        # this does not check for the case when @ch renders to a box
        if ch.isspace():
            return False
        x,y=0,0
        fsize = (10,10)
        surf = pygame.Surface(fsize, pygame.locals.SRCALPHA, 32)

        ch_bounds = font.render_to(surf, (x,y), ch)
        return ch_bounds.width == 0


    def is_emoji(self, ch, font):
        # prevents rendering boxes instead of text
        valid_ranges = self.valid_ch_range()
        for valid_range in valid_ranges:
            start = valid_range[0]
            end = valid_range[1]
            if ch >= start and ch <= end:
                #logging.debug("{} is valid for start={}".format(repr(ch.encode('utf-8')), start))
                return self.cannot_render(ch, font)
        #emoji_start = u'\U0001f600'
        return True


    def strip_emoji_from_word(self, word, font):
        word = list(word)
        result = []
        for char in word:
            if not self.is_emoji(char, font):
                result.append(char)
            else:
                logging.debug(colorize(Color.RED, "stripped {}".format(char.encode('utf-8'))))
        return "".join(result)

    def sample(self, nline_max,nchar_max,font=None,kind='WORD'):
        #print 'sample_output',self.fdict[kind](nline_max,nchar_max)
        return self.fdict[kind](nline_max,nchar_max,font)
        """
        print 'is type:', type(self.fdict[kind](nline_max,nchar_max))
        encoded = [t.encode('utf-8') for t in self.fdict[kind](nline_max,nchar_max)]
        # print('sample output {}'.format(encoded))
        return encoded
        """
        
        
    def sample_word(self,nline_max,nchar_max,font=None,niter=100):
        rand_line = self.txt[np.random.choice(len(self.txt))]                
        words = rand_line.split()
        rand_word = random.choice(words)

        iter = 0
        while iter < niter and (not self.is_good([rand_word])[0] or len(rand_word)>nchar_max):
            rand_line = self.txt[np.random.choice(len(self.txt))]                
            words = rand_line.split()
            rand_word = random.choice(words)
            iter += 1
        #print colorize(Color.GREEN, rand_word)
        print 'sample_word_output',rand_word
        rand_word = self.strip_emoji_from_word(rand_word, font)
        if not self.is_good([rand_word])[0] or len(rand_word)>nchar_max:
            return []
        else:
            return rand_word


    def sample_line(self,nline_max,nchar_max,font=None):
        nline = nline_max+1
        while nline > nline_max:
            nline = np.random.choice([1,2,3], p=self.p_line_nline)

        # get number of words:
        nword = [self.p_line_nword[2]*sstat.beta.rvs(a=self.p_line_nword[0], b=self.p_line_nword[1])
                 for _ in xrange(nline)]
        nword = [max(1,int(np.ceil(n))) for n in nword]

        lines = self.get_lines(nline, nword, nchar_max, f=0.35)
        print 'sample_line_output',lines
        if lines is not None:
            return '\n'.join(lines)
        else:
            return []

    def sample_para(self,nline_max,nchar_max,font=None):
        # get number of lines in the paragraph:
        nline = nline_max*sstat.beta.rvs(a=self.p_para_nline[0], b=self.p_para_nline[1])
        nline = max(1, int(np.ceil(nline)))

        # get number of words:
        nword = [self.p_para_nword[2]*sstat.beta.rvs(a=self.p_para_nword[0], b=self.p_para_nword[1])
                 for _ in xrange(nline)]
        nword = [max(1,int(np.ceil(n))) for n in nword]

        lines = self.get_lines(nline, nword, nchar_max, f=0.35)
        logging.debug('sample_para_output {}'.format(lines))
        if lines is not None:
            temp = []
            for word in lines:
                temp.append(self.strip_emoji_from_word(word, font))
            lines = temp
            # if the text is too long, it might cause segmentation error
            if len(lines) > 5:
                lines = lines[:5]
            # center align the paragraph-text:
            if np.random.rand() < self.center_para:
                lines = self.center_align(lines)
            return '\n'.join(lines)
        else:
            return []
