#include "lzss_encoder.h"

/*
static U8_t bit_buffer  = 0;
static U8_t bit_mask    = 128;
static U32_t codecount  = 0;

void putbit(U8_t value,AXIS_OUT &out_data) // 0:bit0 1:bit1 other:flush
{
	axiu o_data;
	if (value==1) // bit1
    {
        bit_buffer |= bit_mask;
		bit_mask = bit_mask >> 1;
		if (bit_mask==0)
		{
			bit_mask   = 128;
			codecount += 1;
			o_data.data = bit_buffer;
			bit_buffer = 0;
			out_data.write(o_data);
		}
    }
    else if(value==0) // bit0
    {
		bit_mask = bit_mask >> 1;
		if (bit_mask==0)
		{
			bit_mask   = 128;
			codecount += 1;
			o_data.data = bit_buffer;
			bit_buffer = 0;
			out_data.write(o_data);
		}
    }
	else // flush
	{
		if (bit_mask!=128)
		{
			codecount += 1;
		}
		out_data.write(o_data);
	}
}

void encoder(U32_t offset,U8_t length, U8_t symbol, AXIS_OUT &out_data)
{
    U32_t mask = 256;
    putbit(1,out_data);
    if (offset!=0)
    {
		while (mask>>=1)
		{
			if (symbol & mask)
			{
				putbit(1,out_data);
			}
			else
			{
				putbit(0,out_data);
			}
		}
    }
    else
    {
    	mask = SLIDE_WINDOW_SIZE;
		putbit(0,out_data);
		while (mask>>=1)
		{
			if (offset & mask)
			{
				putbit(1,out_data);
			}
			else
			{
				putbit(0,out_data);
			}
		}
		mask = (1 << LENGTH_BITWIDTH);
		while (mask>>=1)
		{
			if (length & mask)
			{
				putbit(1,out_data);
			}
			else
			{
				putbit(0,out_data);
			}
		}
    }
}
*/

void encoder(BITBUF_INF *bitbuf_t, U32_t offset,U8_t length, U8_t symbol, AXIS_OUT &out_data)
{
	axiu  o_data;
	U8_t  temp=0;
    U8_t  pos=bitbuf_t->bit_pos;
    U8_t  buf=bitbuf_t->bit_buffer;
    if(offset==0)
    {
    	if(pos==7)
    	{
    		o_data.data = buf | 1;
    		out_data.write(o_data);
    		o_data.data = symbol;
    		out_data.write(o_data);
    	    bitbuf_t->bit_buffer = 0;
    	    bitbuf_t->bit_pos    = 0;
    	    bitbuf_t->codecount += 2;
    	}
    	else
    	{
    		o_data.data = buf | (1<<(7-pos)) | symbol.range(7,pos+1);
			out_data.write(o_data);
			bitbuf_t->bit_buffer.range(7,7-pos) = symbol.range(pos,0);
			bitbuf_t->bit_buffer.range(6-pos,0) = 0;
    	    bitbuf_t->bit_pos++;
			bitbuf_t->codecount++;
    	}
    }
    else
    {
    	o_data.data = buf | offset.range(10,pos+4);
		out_data.write(o_data);
		if(pos==4)
		{
			o_data.data = offset.range(7,0);
			out_data.write(o_data);
			bitbuf_t->bit_buffer.range(7,4) = length.range(3,0);
			bitbuf_t->bit_buffer.range(3,0) = 0;
		}
		else if(pos>4)
		{
			o_data.data = offset.range(pos+3,pos-4);
			out_data.write(o_data);
			bitbuf_t->bit_buffer.range(7,12-pos)     = offset.range(pos-5,0);
			bitbuf_t->bit_buffer.range(11-pos,8-pos) = length.range(3,0);
			bitbuf_t->bit_buffer.range(7-pos,0)      = 0;
		}
		else
		{
			temp.range(7,4-pos) = offset.range(pos+3,0);
			temp.range(3-pos,0) = length.range(3,pos);
			o_data.data = temp;
			out_data.write(o_data);
			if (pos!=0)
				bitbuf_t->bit_buffer.range(7,8-pos) = length.range(pos-1,0);
			bitbuf_t->bit_buffer.range(7-pos,0) = 0;
		}
		bitbuf_t->codecount += 2;
    }
}


void flush_buffer(BITBUF_INF *bitbuf_t, AXIS_OUT &out_data)
{
	axiu o_data;
    U8_t  pos=bitbuf_t->bit_pos;
    U8_t  buf=bitbuf_t->bit_buffer;
	if(pos!=0)
	{
		o_data.data = buf;
		o_data.keep = 1;
		o_data.last = 1;
		out_data.write(o_data);
		bitbuf_t->codecount++;
	}
	else
	{
		o_data.data = 0;
		o_data.keep = 0;
		o_data.last = 1;
		out_data.write(o_data);
	}
	bitbuf_t->bit_buffer = 0;
	bitbuf_t->bit_pos    = 0;
}

void UpdateHash(U32_t	windowMask,\
				U32_t	hash_table[SYMBOL_NUM],\
				U32_t   link_table[SLIDE_WINDOW_SIZE],\
				U8_t  	current_byte,\
				U8_t    slide_window[SLIDE_WINDOW_SIZE],\
				U32_t   pos)
{
    link_table[pos&windowMask] = hash_table[current_byte];
    hash_table[current_byte] = pos;
    slide_window[(pos-1)&windowMask] = current_byte;
    //printf ("****hash_table[%02X]=%x, slide[%x]=0x%02X",current_byte,pos,pos-1,current_byte);
}

U32_t FindMatch(U32_t	windowMask,\
				U32_t	hash_table[SYMBOL_NUM],\
				U32_t   link_table[SLIDE_WINDOW_SIZE],\
				U32_t	pos2_list[SLIDE_WINDOW_SIZE],\
				U8_t	current_byte,\
				U32_t	pos)
{
    U32_t pos2      = hash_table[current_byte];
    U32_t pos2_d1   = 0;
    U32_t match_cnt = 0;
    if ((pos2!=0) && (pos2!=pos))
    {
        pos2_list[match_cnt++] = pos2;
        for(int i=1;i<SLIDE_WINDOW_SIZE;i++)
        {
            pos2_d1 = pos2;
            pos2    = link_table[pos2 & windowMask];
            if (pos2_d1==MAX_ADDR_VALUE)
            {
            	break;
            }
            else if ((pos2_d1<=pos2)&&(pos2!=MAX_ADDR_VALUE))
            {
            	break;
            }
            else
            {
            	if (pos2_d1==MAX_ADDR_VALUE)
				{
					pos2_list[match_cnt++] = pos2;
				}
				else if ((pos-pos2<SLIDE_WINDOW_SIZE) && (pos2!=0))
				{
					pos2_list[match_cnt++] = pos2;
				}
				else
				{
					break;
				}
            }
        }
    }
    return match_cnt;
}

void ExtendMatch( 	U32_t		windowMask,\
					MATCH_INFO *ret,\
					U32_t		pos2_list[SLIDE_WINDOW_SIZE],\
					U8_t    	slide_window[SLIDE_WINDOW_SIZE],\
					U8_t		current_byte,\
					U32_t		length,\
					U32_t		pos)
{
	U32_t	pos2 = 0;
	U32_t   pos2_pop  = 0;
	U32_t   match_cnt = ret->match_num;
	ret->match_num = 0;
	ret->match_pos = 0;
	int i;
	extend_loop_int:
    for(i=0;i<SLIDE_WINDOW_SIZE;i++) // in range(0,len(pos2_list)):
    {
        if(i>=match_cnt)
        {
        	break;
        }
        else
        {
        	pos2_pop = pos2_list[i];
        	if (pos2_pop!=0)
			{
				if (pos2_pop==MAX_ADDR_VALUE)
				{
					if ((current_byte==0x20)&&((pos+length)<SLIDE_WINDOW_SIZE))
					{
						pos2 = pos2_pop-length;
					}
					else
					{
						pos2 = pos2_pop+1;
					}
				}
				else
				{
					pos2 = pos2_pop;
				}

				if ((pos2_list[i]==MAX_ADDR_VALUE)&&(current_byte==0x20)&&((pos+length)<SLIDE_WINDOW_SIZE))
				{
					ret->match_pos = pos2;
					pos2_list[ret->match_num++] = pos2_pop;
				}
				else if (slide_window[(pos2+length)&windowMask]==current_byte)
				{
					pos2_list[ret->match_num++] = pos2_pop;
					if(ret->match_pos<pos2)
					{
						ret->match_pos = pos2;
					}
				}
				else
				{
					continue;
				}
			}
		}
    }
}

U32_t LZSS_encoder(AXIS_IN &in_data,U32_t in_size, AXIS_OUT &out_data)
{
	U32_t 		max_match_len = 0;
	MATCH_INFO 	match_info;
	BITBUF_INF  bitbuf;
	U8_t        length    = 0;
	U32_t       offset    = 0;
    U8_t       	symbol_d1 = 0;
    U8_t       	symbol    = 0;
    U32_t 		head_addr = 0;
    U32_t 		tail_addr = 0;
    U32_t 		match_ok  = 0;
    U32_t 		windowMask = SLIDE_WINDOW_SIZE-1;

    match_info.match_num = 0;
    match_info.match_pos = 0;
    bitbuf.bit_buffer = 0;
    bitbuf.bit_pos    = 0;
    bitbuf.codecount  = 0;
    
    U8_t 		slide_window[SLIDE_WINDOW_SIZE];
    U32_t		hash_table[SYMBOL_NUM];
    U32_t 		link_table[SLIDE_WINDOW_SIZE];
    U32_t		pos2_list[SLIDE_WINDOW_SIZE];

    init_loop:
	for(int i=0;i<SLIDE_WINDOW_SIZE;i++)
	{
		slide_window[i] 		= 0;
		hash_table[i%SYMBOL_NUM]= 0;
		link_table[i] 			= 0;
		pos2_list[i] 			= 0;
	}

    while (head_addr<in_size)
    {
        if (MAX_MATCH_LEN<=in_size-tail_addr)
        {
            max_match_len = MAX_MATCH_LEN;
        }
        else
        {
            max_match_len = in_size-tail_addr+1;
        }
        if (tail_addr==0)
        {
            symbol_d1 = 0x20;
            symbol    = in_data.read().data;
            encoder(&bitbuf,0,0,symbol,out_data);
            head_addr = 0;
            tail_addr = 1;
            UpdateHash( windowMask,\
                        hash_table,\
                        link_table,\
                        symbol_d1,\
                        slide_window,\
                        MAX_ADDR_VALUE);

            UpdateHash( windowMask,\
                        hash_table,\
                        link_table,\
                        symbol,\
                        slide_window,\
                        tail_addr);
        }
        else if ((head_addr+2==tail_addr)&&(tail_addr>=in_size))
        {
            encoder(&bitbuf,0,0,symbol,out_data);
            head_addr += 2;
        }
        else
        {
        	length = MIN_MATCH_LEN;
            if (head_addr+1>=tail_addr)
            {
                symbol    = in_data.read().data;
                symbol_d1 = symbol;
                tail_addr += 1;
            }
            match_ok = FindMatch(   windowMask,\
                                    hash_table,\
                                    link_table,\
                                    pos2_list,\
                                    symbol,\
                                    tail_addr);
            UpdateHash( windowMask,\
                        hash_table,\
                        link_table,\
                        symbol,\
                        slide_window,\
                        tail_addr);
            if (match_ok!=0)
            {
            	match_info.match_num = match_ok;
                for(int i=1;i<max_match_len;i++) //  in range(1,max_match_len)
                {
					symbol_d1  = symbol;
					symbol     = in_data.read().data;
					tail_addr += 1;
                    ExtendMatch(windowMask,\
								&match_info,\
								pos2_list,\
								slide_window,\
								symbol,\
								length-1,\
								head_addr);
                    // print ("----ExtendMatch: 0x%02X, match_num=%d, match_pos=%x" % (symbol,match_num,match_pos))
                    if (match_info.match_num==0)
                    {
                        break;
                    }
                    else
                    {
                    	length    += 1;
                    	match_info.match_pos += 1;
                        if (head_addr<SLIDE_WINDOW_SIZE)
                        {
                        	offset = match_info.match_pos+(SLIDE_WINDOW_SIZE-MAX_MATCH_LEN-2);
                        }
                        else
                        {
                        	offset = match_info.match_pos-MAX_MATCH_LEN-2;
                        }
                        UpdateHash( windowMask,\
                                    hash_table,\
                                    link_table,\
                                    symbol,\
                                    slide_window,\
                                    tail_addr);
                    }
                }
                if (length <= MIN_MATCH_LEN)
                {
                	length = 1;
                    encoder(&bitbuf,0,0,symbol_d1,out_data);
                    head_addr += 1;
                }
                else
                {
                    //print ("offset=%d (aftermask=%03X), length=%d, pos=%x" % (offset,(offset&windowMask),length,tail_addr))
                	encoder(&bitbuf,offset&windowMask, length-2,0x0,out_data);
                    head_addr += length;
                    length = MIN_MATCH_LEN;
                    //# print ("^^head = %x, tail = %x" % (head_addr,tail_addr))
                }
            }
            else
            {
            	encoder(&bitbuf,0,0,symbol,out_data);
                head_addr += 1;
            }
            if (head_addr+1==tail_addr and tail_addr>=in_size)
            {
                head_addr += 1;
            }
        }
    }
	//putbit(2,out_data);
    flush_buffer(&bitbuf,out_data);
    return bitbuf.codecount;
}
