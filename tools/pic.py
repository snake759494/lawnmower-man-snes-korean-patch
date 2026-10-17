import struct,sys,numpy as np
from lmcomp import *


def tiles(v, bpp):
    n = len(v) // (8 * bpp); a = np.frombuffer(v[:n * 8 * bpp], np.uint8).reshape(n, 8 * bpp)
    out = np.zeros((n, 8, 8), np.uint8)
    for p in range(bpp):
        plane = a[:, (p // 2) * 16 + p % 2:(p // 2) * 16 + 16:2]
        for x in range(8): out[:, :, x] |= ((plane >> (7 - x)) & 1) << p
    return out
def entry(rom,i):
    b=s2f(0x85e960)+i*32; return struct.unpack('<16H',rom[b:b+32])
def gfx(rom,i):
    e=entry(rom,i); buf=bytearray(0x8000)
    for k in range(4):
        y=e[8+k]
        if y==0: break
        o,_=decompress(rom,y&0xff,e[4+k]); buf[k*0x2000:k*0x2000+len(o)]=o
    return bytes(buf),e
def indexed(rom,i):
    g,e=gfx(rom,i); t=tiles(g,4); w,h=e[0],e[1]
    img=np.zeros((h*16,w*16),np.uint8); fa=0
    for cy in range(h):
        for cx in range(w):
            tb=(fa&7)*2 | (fa&0x3f8)<<2
            for dy in range(2):
                for dx in range(2):
                    img[cy*16+dy*8:cy*16+dy*8+8,cx*16+dx*8:cx*16+dx*8+8]=t[(tb+dy*16+dx)&1023]
            fa+=1
    return img,e
