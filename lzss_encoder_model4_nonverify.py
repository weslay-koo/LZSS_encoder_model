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
MIN_MATCH_LEN       = 2                             # /* If match length <= MIN_MATCH_LEN then output one character */
SLIDE_WINDOW_SIZE   = (1 << OFFSET_BITWIDTH)        # /* buffer size */
MAX_MATCH_LEN       = ((1 << LENGTH_BITWIDTH) + 1)  # /* lookahead buffer size */
MAX_ADDR_VALUE      = -1
PARALLEL_NUM        = 8
LOOKAHEAD_SIZE      = (1 << (LENGTH_BITWIDTH+1))

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
        # print ("offset=0x%03X, length=%d" % (offset,length+2))
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
                head_table,
                next_table,
                current_byte,
                next_byte,
                pos):
    hash_value = (current_byte<<8) | next_byte
    next_table[pos&windowMask] = head_table[hash_value]
    head_table[hash_value]     = pos
    # print ("*** Hash[0x%04X] = %x" % (hash_value,pos))

def FindMatch(  windowMask,
                head_table,
                next_table,
                pos2_list,
                current_byte,
                next_byte,
                first_hash,
                pos,in_size):
    hash_value = (current_byte<<8) | next_byte
    pos2 = head_table[hash_value]
    match_cnt = 0
    for i in range(0,SLIDE_WINDOW_SIZE):
        if (hash_value==first_hash and pos-pos2<(SLIDE_WINDOW_SIZE-MAX_MATCH_LEN+1)):
            pos2_list[match_cnt] = 0
            match_cnt += 1
        elif (pos-pos2<(SLIDE_WINDOW_SIZE-MAX_MATCH_LEN+1) and pos2!=0):
            pos2_list[match_cnt] = pos2
            match_cnt += 1
        else:
            break
        pos2 = next_table[pos2&windowMask]
        
    # if match_cnt!=0:
    #     print ("---- Find Match 0x%04X at %x (match_cnt=%d)" % (hash_value,pos,match_cnt))
    return match_cnt

def ExtendMatch(windowMask,
                lookaheadMask,
                pos2_list,
                match_num,
                slide_window,
                lookahead_buf,
                lookahead_cnt,
                pos,in_size):
    match_pos = 0
    match_len = 2
    for i in range(0,match_num):
        m_pos = pos2_list[i]
        m_len = 0
        for m_len in range(0,MAX_MATCH_LEN-MIN_MATCH_LEN+1):
            # print ("==== Extend Match sl[%x]=0x%02X lb[%x]=0x%02X mpos=%x" % (m_pos+m_len+1,slide_window[(m_pos+m_len+1)&windowMask],\
            #                                                           pos+m_len+MIN_MATCH_LEN,lookahead_buf[(pos+m_len+MIN_MATCH_LEN)&lookaheadMask],m_pos))
            if (slide_window[(m_pos+m_len+1)&windowMask] != lookahead_buf[(pos+m_len+MIN_MATCH_LEN)&lookaheadMask]):
                break
        if (m_len+MIN_MATCH_LEN==MAX_MATCH_LEN):
            match_pos = m_pos
            match_len = m_len+MIN_MATCH_LEN
            break
        elif (match_len<m_len+MIN_MATCH_LEN) or (match_pos==0):
            match_pos = m_pos
            match_len = m_len+MIN_MATCH_LEN
        else:
            m_len = 0
    return match_pos,match_len
            
                
def LZSS_encoder(in_data,in_size):
    global out_data
    out_data = []
    offset = 0
    length = 0
    first_hash = 0
    symbol_d2 = 0
    symbol_d1 = 0
    symbol    = 0
    head_addr = 0
    lookahead_cnt = 0
    match_num = 0
    match_pos = 0
    windowMask = SLIDE_WINDOW_SIZE-1
    lookaheadMask = LOOKAHEAD_SIZE-1
    
    bitbuf = {}
    bitbuf['bit_buffer'] = 0
    bitbuf['bit_pos']    = 0
    bitbuf['codecount']  = 0
    
    
    slide_window  = np.zeros(SLIDE_WINDOW_SIZE,dtype=np.uint8)
    lookahead_buf = np.zeros(LOOKAHEAD_SIZE,dtype=np.uint8)
    pos2_list    = np.zeros(SLIDE_WINDOW_SIZE,dtype=int)
    head_table   = np.zeros(65536,dtype=int)
    next_table   = np.zeros(SLIDE_WINDOW_SIZE,dtype=int)
    
    # Initial Loop
    for i in range(0,SLIDE_WINDOW_SIZE):
        slide_window[i] = 0x20
        pos2_list[i] = 0
        UpdateHash( windowMask,
                    head_table,
                    next_table,
                    0x20,
                    0x20,
                    i-SLIDE_WINDOW_SIZE)
    for i in range(0,LOOKAHEAD_SIZE):
        lookahead_buf[i] = 0
        
    # Find Match Loop
    while (head_addr < in_size):
        if (in_size<=2):
            for i in range(0,in_size):
                symbol = in_data.pop(0)
                encoder(bitbuf,MAX_ADDR_VALUE,0,symbol)
                head_addr += 1
            break
        elif (head_addr==0):
            symbol_d2 = 0x20
            symbol_d1 = in_data.pop(0)
            symbol    = in_data.pop(0)
            slide_window[0] = symbol_d1
            slide_window[1] = symbol
            lookahead_buf[0] = symbol_d1
            lookahead_buf[1] = symbol
            encoder(bitbuf,MAX_ADDR_VALUE,0,symbol_d1)
            head_addr = 1
            lookahead_cnt = 2
            UpdateHash( windowMask,
                        head_table,
                        next_table,
                        symbol_d2,
                        symbol_d1,
                        0)
            UpdateHash( windowMask,
                        head_table,
                        next_table,
                        symbol_d1,
                        symbol,
                        1)
            first_hash = (0x20<<8) | symbol_d1
        else: # 尝试匹配
            if (head_addr+1>=lookahead_cnt):
                symbol_d1 = symbol
                symbol    = in_data.pop(0)
                lookahead_buf[lookahead_cnt&lookaheadMask] = symbol
                slide_window[lookahead_cnt&windowMask] = symbol
                lookahead_cnt += 1
            symbol_d1 = lookahead_buf[(head_addr)&lookaheadMask]
            symbol    = lookahead_buf[(head_addr+1)&lookaheadMask]
            match_num = FindMatch(  windowMask,
                                    head_table,
                                    next_table,
                                    pos2_list,
                                    symbol_d1,
                                    symbol,
                                    first_hash,
                                    head_addr,in_size)
            
            if (match_num!=0):
                for i in range(0,MAX_MATCH_LEN-1): # 扩展匹配
                    if (lookahead_cnt<in_size) and (lookahead_cnt-head_addr<MAX_MATCH_LEN+1):
                        symbol = in_data.pop(0)
                        lookahead_buf[lookahead_cnt&lookaheadMask] = symbol
                        slide_window[lookahead_cnt&windowMask] = symbol
                        lookahead_cnt += 1
                    else:
                        break
                match_pos,length = ExtendMatch( windowMask,
                                                lookaheadMask,
                                                pos2_list,
                                                match_num,
                                                slide_window,
                                                lookahead_buf,
                                                lookahead_cnt,
                                                head_addr,in_size)
                if (head_addr<SLIDE_WINDOW_SIZE): # !!!Unnecessnary
                    offset = match_pos+(SLIDE_WINDOW_SIZE-MAX_MATCH_LEN-1)
                else:
                    offset = match_pos-MAX_MATCH_LEN-1
                    
                encoder(bitbuf,offset&windowMask, length-2,symbol)
                for i in range(0,length):
                    symbol_d1 = lookahead_buf[(head_addr)&lookaheadMask]
                    symbol    = lookahead_buf[(head_addr+1)&lookaheadMask]
                    head_addr += 1
                    UpdateHash( windowMask,
                                head_table,
                                next_table,
                                symbol_d1,
                                symbol,
                                head_addr)
                # print ("head_addr=%x, lookahead_cnt=%x" % (head_addr,lookahead_cnt))
            else:
                symbol_d1 = lookahead_buf[(head_addr)&lookaheadMask]
                symbol    = lookahead_buf[(head_addr+1)&lookaheadMask]
                encoder(bitbuf,MAX_ADDR_VALUE,0,symbol_d1)
                head_addr += 1
                UpdateHash( windowMask,
                            head_table,
                            next_table,
                            symbol_d1,
                            symbol,
                            head_addr)
                # print (slide_window[0:20])
    flush_buffer(bitbuf)
    return out_data,len(out_data)

if __name__=="__main__":
    SRC_PATH = "../test_corpus/calgary/"
    DST_PATH = "../test_out/"
    # file_list = os.listdir(SRC_PATH)
    # print (file_list)
    # SRC_PATH  = "./"
    # DST_PATH  = "./"
    file_list = ["obj2"]
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
            error_list.append(file)
            
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