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
MAX_ADDR_VALUE      = -1
PARALLEL_NUM        = 8

out_data   = []

def bit_range(value,h,l):
    bitbuf = value
    bitbuf = (bitbuf & ((1<<h+1)-1))>>l
    return bitbuf

def encoder(bitbuf_t,offset,length,symbol):
    global out_data
    o_data = 0
    pos = bitbuf_t['bit_pos']
    buf = bitbuf_t['bit_buffer']
    if (offset==MAX_ADDR_VALUE):
        # print ("symbol=0x%02X" % symbol)
        if (pos==7):
            o_data = buf | 1
            out_data.append(o_data)
            o_data = symbol
            out_data.append(o_data)
            bitbuf_t['bit_buffer'] = 0
            bitbuf_t['bit_pos']    = 0
            bitbuf_t['codecount'] += 2
        else:
            o_data = buf | (1<<(7-pos)) | bit_range(symbol,7,pos+1)
            out_data.append(o_data)
            o_data = bit_range(symbol,pos,0)<<(7-pos)
            bitbuf_t['bit_buffer'] = o_data
            bitbuf_t['bit_pos']   += 1
            bitbuf_t['codecount'] += 1
    else:
        if (pos==0):
            o_data = bit_range(offset,10,4)
            out_data.append(o_data)
            o_data = (bit_range(offset,3,0)<<4) | bit_range(length,3,0)
            out_data.append(o_data)
            bitbuf_t['bit_buffer'] = 0
        elif (pos==7):
            o_data = buf
            out_data.append(o_data)
            o_data = bit_range(offset,10,3)
            out_data.append(o_data)
            bitbuf_t['bit_buffer'] = (bit_range(offset,2,0)<<5) | (bit_range(length,3,0)<<1)
        else:
            o_data = buf | bit_range(offset,10,pos+4)
            out_data.append(o_data)
            if (pos==4):
                o_data = bit_range(offset,7,0)
                out_data.append(o_data)
                bitbuf_t['bit_buffer'] = bit_range(length,3,0)<<4
            elif (pos>4):
                o_data = bit_range(offset,pos+3,pos-4)
                out_data.append(o_data)
                bitbuf_t['bit_buffer'] = (bit_range(offset,pos-5,0)<<(12-pos)) | (bit_range(length,3,0)<<(8-pos))
            else:
                o_data = (bit_range(offset,pos+3,0)<<(4-pos)) | bit_range(length,3,pos)
                out_data.append(o_data)
                bitbuf_t['bit_buffer'] = bit_range(length,pos-1,0)<<(8-pos)
        bitbuf_t['codecount'] += 2

def flush_buffer(bitbuf_t):
    global out_data
    pos = bitbuf_t['bit_pos']
    buf = bitbuf_t['bit_buffer']
    if (pos!=0):
        out_data.append(buf)
        bitbuf_t['codecount'] += 1
    bitbuf_t['bit_buffer'] = 0
    bitbuf_t['bit_pos']    = 0
    

def UpdateHash( windowMask,
                fill_table,
                hash_table,
                current_byte,
                slide_window,
                pos):
    match_num = fill_table[current_byte]
    hash_table[(match_num%SLIDE_WINDOW_SIZE)%PARALLEL_NUM][int((match_num%SLIDE_WINDOW_SIZE)/PARALLEL_NUM)*256+current_byte] = pos
    fill_table[current_byte] += 1
    slide_window[(pos-1)&windowMask] = current_byte

def FindMatch(  windowMask,
                fill_table,
                hash_table,
                pos2_list,
                current_byte,
                pos):
    total_match_num = fill_table[current_byte]
    last_num  = 0
    match_cnt = 0
    if (total_match_num>SLIDE_WINDOW_SIZE):
        last_num = total_match_num-SLIDE_WINDOW_SIZE
    else:
        last_num = 0
    if (total_match_num==0):
        match_cnt = 0
    else:
        for k in range(total_match_num,last_num,-1):
            i = k-1
            pos2 = hash_table[i%PARALLEL_NUM][(int(i/PARALLEL_NUM)*256+current_byte)%int(SLIDE_WINDOW_SIZE*256/PARALLEL_NUM)]
            if (pos2==MAX_ADDR_VALUE and pos<SLIDE_WINDOW_SIZE):
                pos2_list.append(pos2)
                match_cnt += 1
            elif (pos-pos2<(SLIDE_WINDOW_SIZE-MAX_MATCH_LEN+1) and pos2!=0):
                pos2_list.append(pos2)
                match_cnt += 1
            else:
                break
    return match_cnt

def ExtendMatch(windowMask,
                pos2_list,
                slide_window,
                current_byte,
                length,
                run_length,
                run_length_done,
                match_cnt,
                pos):
    match_num = 0
    match_pos = 0
    pos2      = 0
    pos2_pop  = 0
    # if current_byte == 0x20:
    #     print (pos2_list[0:100])
    for i in range(0,match_cnt):
        pos2_pop = pos2_list.pop(0)
        if (pos2_pop==MAX_ADDR_VALUE):
            if (current_byte==0x20 and (pos+length)<SLIDE_WINDOW_SIZE and run_length_done!=1):
                pos2 = pos2_pop-length
                match_num += 1
                if (match_pos==MAX_ADDR_VALUE or match_pos==0):
                    match_pos = pos2
                pos2_list.append(pos2_pop)
            else:
                pos2 = pos2_pop+length-run_length+1
                if (slide_window[pos2&windowMask]==current_byte):
                    match_num += 1
                    if (match_pos==MAX_ADDR_VALUE or match_pos==0):
                        match_pos = 0-run_length
                    pos2_list.append(pos2_pop)
        else:
            pos2 = pos2_pop+length
            if (slide_window[pos2&windowMask]==current_byte):
                match_num += 1
                pos2_list.append(pos2_pop)
                if (match_pos<pos2_pop):
                    match_pos = pos2_pop
    # print ("----slide_window[%x]==0x%02X current=0x%02X,match_pos[%d]=%x" % (pos2+length,
    #                                                     slide_window[(pos2+length)&windowMask],
    #                                                     current_byte,
    #                                                     match_num,match_pos))
    return match_num,match_pos
            
                
def LZSS_encoder(in_data,in_size):
    global out_data
    out_data = []
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
    
    run_length      = 0
    run_length_done = 0
    bitbuf = {}
    bitbuf['bit_buffer'] = 0
    bitbuf['bit_pos']    = 0
    bitbuf['codecount']  = 0
    
    
    slide_window = np.zeros(SLIDE_WINDOW_SIZE,dtype=np.uint8)
    fill_table   = np.zeros(256,dtype=int)
    hash_table   = np.zeros((PARALLEL_NUM,int(SLIDE_WINDOW_SIZE*256/PARALLEL_NUM)),dtype=int)
    pos2_list    = []
    
    while (head_addr < in_size):
        if (MAX_MATCH_LEN<=in_size-tail_addr):
            max_match_len = MAX_MATCH_LEN
        else:
            max_match_len = in_size-tail_addr+1
        if (in_size==1):
            symbol = in_data.pop(0)
            encoder(bitbuf,MAX_ADDR_VALUE,0,symbol)
            head_addr += 1
            tail_addr += 1
            break
        elif (tail_addr==0):
            symbol_d1 = 0x20
            symbol    = in_data.pop(0)
            encoder(bitbuf,MAX_ADDR_VALUE,0,symbol)
            head_addr = 0
            tail_addr = 1
            UpdateHash( windowMask,
                        fill_table,
                        hash_table,
                        symbol_d1,
                        slide_window,
                        MAX_ADDR_VALUE)
            UpdateHash( windowMask,
                        fill_table,
                        hash_table,
                        symbol,
                        slide_window,
                        tail_addr)
        elif (head_addr+2==tail_addr and tail_addr>=in_size):
            # print ("#"*80)
            # print ("head = %x, tail = %x" % (head_addr,tail_addr))
            encoder(bitbuf,MAX_ADDR_VALUE,0,symbol)
            head_addr += 2
        else: # 尝试匹配
            length = MIN_MATCH_LEN
            if (head_addr+1>=tail_addr):
                symbol_d1 = symbol
                symbol    = in_data.pop(0)
                tail_addr += 1
            pos2_list = []
            match_ok = FindMatch(   windowMask,
                                    fill_table,
                                    hash_table,
                                    pos2_list,
                                    symbol,
                                    tail_addr)
            UpdateHash( windowMask,
                        fill_table,
                        hash_table,
                        symbol,
                        slide_window,
                        tail_addr)
            if (match_ok!=0 and head_addr<in_size-2):
                # print ("FindMatch: pos=%x, symbol_d1=0x%02X, symbol=0x%02X(%x|%x)" % (tail_addr,symbol_d1,symbol,head_addr,tail_addr))
                # print (pos2_list[0:20])
                match_num       = match_ok
                run_length      = 0
                run_length_done = 0
                for i in range(1,max_match_len): # 扩展匹配
                    if (in_data!=[]):
                        symbol_d1  = symbol
                        symbol     = in_data.pop(0)
                        tail_addr += 1
                    else:
                        if (tail_addr>=in_size):
                            break
                    if (symbol==0x20 and run_length_done!=1):
                        run_length = length
                    else:
                        run_length_done = 1
                    match_num,match_pos = ExtendMatch(  windowMask,
                                                        pos2_list,
                                                        slide_window,
                                                        symbol,
                                                        length-1,
                                                        run_length,
                                                        run_length_done,
                                                        match_num,
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
                                    fill_table,
                                    hash_table,
                                    symbol,
                                    slide_window,
                                    tail_addr)
                if (length <= MIN_MATCH_LEN):
                    length = 1
                    encoder(bitbuf,MAX_ADDR_VALUE,0,symbol_d1)
                    head_addr += 1
                else:
                    # print ("offset=%d (aftermask=%03X), length=%d, pos=%x" % (offset,(offset&windowMask),length,tail_addr))
                    encoder(bitbuf,offset&windowMask, length-2,symbol)
                    head_addr += length
                    length = MIN_MATCH_LEN
                    # print ("^^head = %x, tail = %x" % (head_addr,tail_addr))
            else:
                encoder(bitbuf,MAX_ADDR_VALUE,0,symbol)
                head_addr += 1
            if (head_addr+1==tail_addr and tail_addr>=in_size):
                head_addr += 1
    flush_buffer(bitbuf)
    return out_data,len(out_data)

if __name__=="__main__":
    SRC_PATH = "../test_corpus/calgary/"
    DST_PATH = "../test_out/"
    file_list = os.listdir(SRC_PATH)
    print (file_list)
    # SRC_PATH  = "./"
    # DST_PATH  = "./"
    # file_list = ["xargs.1"]
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
        
        #比较压缩后的文件
        if os.path.exists(DST_PATH+file+".swlzss"):
            os.remove(DST_PATH+file+".swlzss")
        os.system("lzss e %s %s" % (SRC_PATH+file,DST_PATH+file+".swlzss"))
        if filecmp.cmp(DST_PATH+file+".swlzss",DST_PATH+file+".hwlzss"):
            print ("%s file compress is same" % file)
        else:
            print ("%s file compress different!!" % file)
            
        #比较解压后的文件
        if os.path.exists(DST_PATH+file+".hwdecomp"):
            os.remove(DST_PATH+file+".hwdecomp")
        os.system("lzss d %s %s" % (DST_PATH+file+".hwlzss",DST_PATH+file+".hwdecomp"))
        if filecmp.cmp(SRC_PATH+file,DST_PATH+file+".hwdecomp"):
            print ("%s file decompress OK\n" % file)
        else:
            print ("%s file decompress error!!\n" % file)
            error_list.append(file)
        
    print (error_list)