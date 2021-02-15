# -*- coding: utf-8 -*-
"""
Created on Fri Feb 12 15:19:23 2021

@author: weslay
"""
import numpy as np
import struct
import os,filecmp ## Only For Test!!

OFFSET_BITWIDTH     = 11                            # /* typically 10..13 */
LENGTH_BITWIDTH     = 4                             # /* typically 4..5 */
MIN_MATCH_LEN       = 1                             # /* If match length <= MIN_MATCH_LEN then output one character */
SLIDE_WINDOW_SIZE   = (1 << OFFSET_BITWIDTH)        # /* buffer size */
MAX_MATCH_LEN       = ((1 << LENGTH_BITWIDTH) + 1)  # /* lookahead buffer size */

bit_buffer = 0
bit_mask   = 128
codecount  = 0
textcount  = 0

out_data   = []

def putbit(value):
    global bit_buffer,bit_mask,codecount,out_data
    if (value!=0):
        bit_buffer |= bit_mask
    bit_mask = bit_mask >> 1
    if (bit_mask==0):
        bit_mask   = 128
        codecount += 1
        out_data.append(bit_buffer)
        bit_buffer = 0


def flush_bit_buffer():
    global bit_buffer,bit_mask,codecount,out_data
    if (bit_mask!=128):
        codecount += 1
    out_data.append(bit_buffer)

def output1(symbol):
    print ("symbol=0x%02X" % (symbol))
    mask = 256
    putbit(1)
    mask = mask>>1
    while (mask!=0):
        if (symbol & mask):
            putbit(1)
        else:
            putbit(0)
        mask = mask>>1

def output2(offset,length):
    mask = SLIDE_WINDOW_SIZE
    putbit(0)
    mask = mask>>1
    while (mask!=0):
        if (offset & mask):
            putbit(1)
        else:
            putbit(0)
        mask = mask>>1
    mask = (1 << LENGTH_BITWIDTH)
    mask = mask>>1
    while (mask!=0):
        if (length & mask):
            putbit(1)
        else:
            putbit(0)
        mask = mask>>1

def UpdateHash( windowMask,
                hash_table,
                link_table,
                current_byte,
                slide_window,
                pos):
    link_table[pos&windowMask] = hash_table[current_byte]
    hash_table[current_byte] = pos
    slide_window[(pos-1)&windowMask] = current_byte
    # print ("****hash_table[%02X]=%x, slide[%x]=0x%02X" % (current_byte,pos,pos-1,current_byte))

def FindMatch(  windowMask,
                hash_table,
                link_table,
                pos2_list,
                current_byte,
                pos):
    # if current_byte == 0x52:
    #     posx = hash_table[current_byte]
    #     print (hex(posx),end='')
    #     while (posx!=0):
    #         posx = link_table[posx]
    #         print ("->",hex(posx),end='')
    #     print ("\n")
    pos2    = hash_table[current_byte]
    pos2_d1 = 0
    pos2_done = 0
    match_cnt = 0
    # print ("################ current_byte=0x%02X, pos=%x, pos2=%x" % (current_byte,pos,pos2))
    if (pos2!=0 and pos2!=pos):
        match_cnt += 1
        pos2_list[0] = pos2
        for i in range(1,len(pos2_list)):
            pos2_d1 = pos2
            pos2    = link_table[pos2 & windowMask]
            if (pos2_d1<=pos2): # 防止hash链混叠
                pos2_done = 1
            if (pos-pos2<SLIDE_WINDOW_SIZE and pos2!=0 and pos2_done!=1):
                pos2_list[i] = pos2
                match_cnt   += 1
            else:
                pos2_list[i] = 0
    # print ("pos_num = %d" % match_cnt)
    return match_cnt

def ExtendMatch(windowMask,
                pos2_list,
                slide_window,
                current_byte,
                length,
                pos):
    match_num = 0
    match_pos = 0
    pos2      = 0
    # if current_byte == 0x20:
    #     print (pos2_list[0:100])
    for i in range(0,len(pos2_list)):
        if (pos2_list[i]!=0):
            if (pos2_list[i]==-1):
                if (current_byte==0x20 and (pos+length)<SLIDE_WINDOW_SIZE):
                    pos2 = pos2_list[i]-length
                    # print ("(((current_byte==0x20, pos2=%x" % (pos2))
                else:
                    pos2 = pos2_list[i]+1
            else:
                pos2 = pos2_list[i]
            
            if (pos2_list[i]==-1 and current_byte==0x20 and (pos+length)<SLIDE_WINDOW_SIZE):
                print ("&"*80)
                match_num += 1
                match_pos = pos2
            elif (slide_window[(pos2+length)&windowMask]!=current_byte):
                pos2_list[i] = 0
            else:
                # print ("^"*80)
                match_num += 1
                if (match_pos<pos2):
                    match_pos = pos2
    # print ("----slide_window[%x]==0x%02X current=0x%02X,match_pos[%d]=%x" % (pos2+length,
    #                                                     slide_window[(pos2+length)&windowMask],
    #                                                     current_byte,
    #                                                     match_num,match_pos))
    return match_num,match_pos
            
                
def LZSS_encoder(in_data,in_size):
    max_match_len = 0
    offset = 0
    length = 0
    symbol_d1 = 0
    symbol    = 0
    head_addr = 0
    tail_addr = 0
    match_ok  = 0
    match_num = 0
    match_pos = 0
    windowMask = SLIDE_WINDOW_SIZE-1
    
    slide_window = np.zeros(SLIDE_WINDOW_SIZE,dtype=np.uint8)
    link_table   = np.zeros(SLIDE_WINDOW_SIZE,dtype=int)
    pos2_list    = np.zeros(SLIDE_WINDOW_SIZE,dtype=int)
    hash_table   = np.zeros(256,dtype=int)
    
    while (head_addr < in_size):
        if (MAX_MATCH_LEN<=in_size-tail_addr):
            max_match_len = MAX_MATCH_LEN
        else:
            max_match_len = in_size-tail_addr+1
            
        if (tail_addr==0):
            symbol_d1 = 0x20
            symbol    = in_data.pop(0)
            output1(symbol)
            head_addr = 0
            tail_addr = 1
            UpdateHash( windowMask,
                        hash_table,
                        link_table,
                        symbol_d1,
                        slide_window,
                        -1)
            UpdateHash( windowMask,
                        hash_table,
                        link_table,
                        symbol,
                        slide_window,
                        tail_addr)
        elif (head_addr+2==tail_addr and tail_addr>=in_size):
            print ("#"*80)
            # print ("head = %x, tail = %x" % (head_addr,tail_addr))
            output1(symbol)
            head_addr += 2
        else: # 尝试匹配
            length = MIN_MATCH_LEN
            if (head_addr+1>=tail_addr):
                print ("*"*80)
                # print ("head = %x, tail = %x" % (head_addr,tail_addr))
                symbol    = in_data.pop(0)
                symbol_d1 = symbol
                tail_addr += 1
            match_ok = FindMatch(   windowMask,
                                    hash_table,
                                    link_table,
                                    pos2_list,
                                    symbol,
                                    tail_addr)
            UpdateHash( windowMask,
                        hash_table,
                        link_table,
                        symbol,
                        slide_window,
                        tail_addr)
            if (match_ok!=0):
                # print ("FindMatch: pos=%x, symbol_d1=0x%02X, symbol=0x%02X(%x|%x)" % (tail_addr,symbol_d1,symbol,head_addr,tail_addr))
                # print (pos2_list[0:20])
                for i in range(1,max_match_len): # 扩展匹配
                    if (in_data!=[]):
                        symbol_d1  = symbol
                        symbol     = in_data.pop(0)
                        tail_addr += 1
                    match_num,match_pos = ExtendMatch(  windowMask,
                                                        pos2_list,
                                                        slide_window,
                                                        symbol,
                                                        length-1,
                                                        head_addr)
                    # print ("----ExtendMatch: 0x%02X, match_num=%d, match_pos=%x" % (symbol,match_num,match_pos))
                    if (match_num==0):
                        break
                    else:
                        length    += 1
                        match_pos += 1
                        # print ("match_pos=%x" % match_pos)
                        # print (pos2_list[0:20])
                        if (head_addr<SLIDE_WINDOW_SIZE): # !!!Unnecessnary
                            offset = match_pos+(SLIDE_WINDOW_SIZE-MAX_MATCH_LEN-2)
                        else:
                            offset = match_pos-MAX_MATCH_LEN-2
                        UpdateHash( windowMask,
                                    hash_table,
                                    link_table,
                                    symbol,
                                    slide_window,
                                    tail_addr)
                if (length <= MIN_MATCH_LEN):
                    length = 1
                    output1(symbol_d1)
                    head_addr += 1
                else:
                    print ("offset=%d (aftermask=%03X), length=%d, pos=%x" % (offset,(offset&windowMask),length,tail_addr))
                    output2(offset&windowMask, length-2)
                    head_addr += length
                    length = MIN_MATCH_LEN
                    # print ("^^head = %x, tail = %x" % (head_addr,tail_addr))
            else:
                output1(symbol)
                head_addr += 1
            if (head_addr+1==tail_addr and tail_addr>=in_size):
                head_addr += 1
    flush_bit_buffer()
    return out_data,len(out_data)

if __name__=="__main__":
    SRC_PATH  = "./"
    DST_PATH  = "./"
    file_list = ["xargs.1"]
    # file_list = ["tt"]
    error_list = []
    
    for file in file_list:
        fp_src = open(SRC_PATH+file,'rb')
        fp_dst = open(DST_PATH+file+'.hwlzss','wb')
        in_data = fp_src.read()
        in_stream = []
        for d in in_data:
            in_stream.append(d)
        print (len(in_stream),type(in_stream))
        
        out_data,out_size = LZSS_encoder(in_stream,len(in_stream))
    
        for i in range(0,out_size):
            fp_dst.write(struct.pack("B",out_data[i] & 0xFF))
        print ("Src Size: %d ====> Dst Size: %d Bytes\n" % (len(in_data),out_size))
        
        fp_src.close()
        fp_dst.close()
        
        #比较解压后的文件
        if os.path.exists(DST_PATH+file+".hwdecomp"):
            os.remove(DST_PATH+file+".hwdecomp")
        os.system("lzss d %s %s" % (DST_PATH+file+".hwlzss",DST_PATH+file+".hwdecomp"))
        
        if filecmp.cmp(file,DST_PATH+file+".hwdecomp"):
            print ("%s file compress OK\n" % file)
        else:
            print ("%s file compress error!!\n" % file)
            error_list.append(file)
        
    print (error_list)