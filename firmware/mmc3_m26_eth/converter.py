# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#
import tables
import numpy as np
from numba import njit 

def m26_decode(raw,fout,start=0,end=-1):
  debug=0
  n=10000
  idx=np.zeros(6)
  mframe=[0]*8
  dlen=[-1]*6
  idx=[-1]*6
  numstatus=[0]*6
  row=[-1]*6
  dat=np.empty(n,dtype=[('plane', '<u2'),('mframe', '<u4'),('x', '<u2'), ('y', '<u2'),('tlu','<u2')])
  with open("hit.npy","wb") as f:
      pass
  raw_i=start
  if end>0:
      end=min(len(raw),end)
  else:
      end=len(raw)
  hit=0
  while raw_i < end:
    raw_d=raw[raw_i]
    if hit+4>=n:
       print "raw_i",raw_i,"hit", hit, float(raw_i)/end*100,"% done"
       with open(fout,"ab") as f:
               np.save(f,dat[:hit])
               f.flush()
       hit=0
    if (0xF0000000 & raw_d==0x20000000):
        if debug:
            print hex(raw_d),
        plane=((raw_d>>20) & 0xF)
        mid=plane-1
        if (0x000FFFFF & raw_d==0x15555):
            if debug:
                print "start %d"%mid
            idx[mid]=0
        elif idx[mid]==-1:
            if debug:
                print "trash"
        else:
            idx[mid]=idx[mid]+1
            if debug:
                print mid, idx[mid],
            if idx[mid]==1:
                if debug:
                    print "header"
                if (0x0000FFFF & raw_d)!=(0x5550 | plane):
                    print "header ERROR",hex(raw_d)
            elif idx[mid]==2:
                if debug:
                    print "frame lsb"
                mframe[mid+1]= (0x0000FFFF & raw_d)
            elif idx[mid]==3:
                mframe[plane]= (0x0000FFFF & raw_d)<<16 | mframe[plane]
                if mid==0:
                    mframe[0]=mframe[plane]
                if debug:
                    print "frame",mframe[plane]          
            elif idx[mid]==4:
                dlen[mid] = (raw_d & 0xFFFF)*2
                if debug:
                    print "length",dlen[mid]
            elif idx[mid]==5:
                if debug:
                    print "length check" 
                if dlen[mid] != (raw_d & 0xFFFF)*2:
                    print "dlen ERROR", hex(raw_d)
            elif idx[mid]== 6+dlen[mid]:
                if debug:
                    print "tailer"
                if raw_d &0xFFFF!=0xaa50:
                    print "tailer ERROR",hex(raw_d)
            elif idx[mid]== 7+dlen[mid]:
                dlen[mid]=-1
                numstatus[mid]=0
                if debug:
                    print "frame end"
                if (raw_d & 0xFFFF)!= (0xaa50 | plane):
                    print "tailer ERROR",hex(raw_d)
            else:
                if numstatus[mid]==0:
                   if idx[mid]==6+dlen[mid]-1:
                       if debug:
                           print "pass"
                       pass
                   else:
                       numstatus[mid]=(raw_d)& 0xF
                       row[mid]=(raw_d>>4)& 0x7FF
                       if debug:
                           print "sts",numstatus[mid],"row",row[mid]
                       if raw_d & 0x00008000 !=0:
                            print "overflow",hex(raw_d)
                            break
                else:
                    numstatus[mid]=numstatus[mid]-1
                    num=(raw_d)& 0x3
                    col=(raw_d>>2)& 0x7FF
                    if debug:
                        print "col",col,"num",num
                    for k in range(num+1):
                        dat[hit]=(plane,mframe[plane],col+k,row[mid],0)
                        hit=hit+1
    elif(0x80000000 & raw_d==0x80000000):
        tlu= raw_d & 0xFFFF
        if debug:
            print hex(raw_d)
        dat[hit]=(7,mframe[0],0,0,tlu)
        hit=hit+1
    raw_i=raw_i+1
  if debug:
     print "raw_i",raw_i
  if hit==n:
     with open(fout,"ab") as f:
           np.save(f,dat[:hit])
           f.flush()

if __name__=="__main__":
    import tables
    import os
    tb=tables.open_file("50_module_test_ext_trigger_scan.h5")
    dat=m26_decode(tb.root.raw_data,0,-1)
    tb.close()
