#include "lzss_encoder.h"

static U8_t bit_buffer = 0;
static U8_t bit_mask   = 128;
static U32_t codecount  = 0;
//static U32_t textcount  = 0;

//out_data   = []

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
    U8_t  pos2_done = 0;
    U32_t match_cnt = 0;
    // printf ("################ current_byte=0x%02X, pos=%x, pos2=%x",current_byte,pos,pos2);
    if ((pos2!=0) && (pos2!=pos))
    {
        match_cnt++;
        pos2_list[0] = pos2;
        for(int i=0;i<SLIDE_WINDOW_SIZE;i++) // in range(1,len(pos2_list)):
        {
            pos2_d1 = pos2;
            pos2    = link_table[pos2 & windowMask];
            if (pos2_d1<=pos2)
            {
                pos2_done = 1;
            }
            if ((pos-pos2<SLIDE_WINDOW_SIZE) && (pos2!=0) && (pos2_done!=1))
            {
                pos2_list[i] = pos2;
                match_cnt++;
            }
            else
            {
                pos2_list[i] = 0;
            }
        }
    }
    return match_cnt;
}

MATCH_INFO ExtendMatch( U32_t	windowMask,\
						U32_t	pos2_list[SLIDE_WINDOW_SIZE],\
						U8_t    slide_window[SLIDE_WINDOW_SIZE],\
						U8_t	current_byte,\
						U32_t	length,\
						U32_t	pos)
{
	U32_t	pos2 = 0;
	int     i;
	MATCH_INFO ret;
    for(i=0;i<SLIDE_WINDOW_SIZE;i++) // in range(0,len(pos2_list)):
    {
        if (pos2_list[i]!=0)
        {
            if (pos2_list[i]==-1)
            {
                if ((current_byte==0x20)&&((pos+length)<SLIDE_WINDOW_SIZE))
                {
                    pos2 = pos2_list[i]-length;
                    // print ("(((current_byte==0x20, pos2=%x" % (pos2))
                }
                else
                {
                    pos2 = pos2_list[i]+1;
                }
            }
            else
			{
                pos2 = pos2_list[i];
			}

            if ((pos2_list[i]==-1)&&(current_byte==0x20)&&((pos+length)<SLIDE_WINDOW_SIZE))
            {
                ret.match_num += 1;
                ret.match_pos = pos2;
            }
            else if (slide_window[(pos2+length)&windowMask]!=current_byte)
            {
                pos2_list[i] = 0;
            }
            else
            {
            	ret.match_num += 1;
                if (ret.match_pos<pos2)
                {
                	ret.match_pos = pos2;
                }
            }
        }
    }
    /* print ("----slide_window[%x]==0x%02X current=0x%02X,match_pos[%d]=%x" % (pos2+length,
                                                         slide_window[(pos2+length)&windowMask],
                                                         current_byte,
                                                         match_num,match_pos))*/
    return ret;
}

U32_t LZSS_encoder(AXIS_IN &in_data,U32_t in_size, AXIS_OUT &out_data)
{
	U32_t 		max_match_len = 0;
	MATCH_INFO 	match_info;
	U8_t        length    = 0;
	U32_t       offset    = 0;
    U8_t       	symbol_d1 = 0;
    U8_t       	symbol    = 0;
    U32_t 		head_addr = 0;
    U32_t 		tail_addr = 0;
    U8_t 		match_ok  = 0;
    U32_t 		match_num = 0;
    U32_t 		match_pos = 0;
    U32_t 		windowMask = SLIDE_WINDOW_SIZE-1;

    U8_t 		slide_window[SLIDE_WINDOW_SIZE]={0};
    U32_t		hash_table[SYMBOL_NUM] = {0};
    U32_t 		link_table[SLIDE_WINDOW_SIZE] = {0};
    U32_t		pos2_list[SLIDE_WINDOW_SIZE] = {0};
    
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
            encoder(0,0,symbol,out_data);
            head_addr = 0;
            tail_addr = 1;
            UpdateHash( windowMask,\
                        hash_table,\
                        link_table,\
                        symbol_d1,\
                        slide_window,\
                        -1);

            UpdateHash( windowMask,\
                        hash_table,\
                        link_table,\
                        symbol,\
                        slide_window,\
                        tail_addr);
        }
        else if ((head_addr+2==tail_addr)&&(tail_addr>=in_size))
        {
            encoder(0,0,symbol,out_data);
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
                for(int i=1;i<max_match_len;i++) //  in range(1,max_match_len)
                {
					symbol_d1  = symbol;
					symbol     = in_data.read().data;
					tail_addr += 1;
                    match_info = ExtendMatch(   windowMask,\
												pos2_list,\
												slide_window,\
												symbol,\
												length-1,\
												head_addr);
                    // print ("----ExtendMatch: 0x%02X, match_num=%d, match_pos=%x" % (symbol,match_num,match_pos))
                    if (match_num==0)
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
                    encoder(0,0,symbol_d1,out_data);
                    head_addr += 1;
                }
                else
                {
                    //print ("offset=%d (aftermask=%03X), length=%d, pos=%x" % (offset,(offset&windowMask),length,tail_addr))
                	encoder(offset&windowMask, length-2,0x0,out_data);
                    head_addr += length;
                    length = MIN_MATCH_LEN;
                    //# print ("^^head = %x, tail = %x" % (head_addr,tail_addr))
                }
            }
            else
            {
            	encoder(0,0,symbol,out_data);
                head_addr += 1;
            }
            if (head_addr+1==tail_addr and tail_addr>=in_size)
            {
                head_addr += 1;
            }
        }
    }
    putbit(2,out_data);
    return codecount;
}
