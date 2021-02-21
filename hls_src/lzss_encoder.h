#ifndef _LZSS_ENCODER_
#define _LZSS_ENCODER_

#include <ap_int.h>
#include <hls_stream.h>
using namespace hls;

#define OFFSET_BITWIDTH     11                            /* typically 10..13 */
#define LENGTH_BITWIDTH     4                             /* typically 4..5 */
#define MIN_MATCH_LEN       1                             /* If match length <= MIN_MATCH_LEN then output one character */
#define SLIDE_WINDOW_SIZE   (1 << OFFSET_BITWIDTH)        /* buffer size */
#define MAX_MATCH_LEN       ((1 << LENGTH_BITWIDTH) + 1)  /* lookahead buffer size */
#define SYMBOL_NUM          256

#define ADDR_WIDTH          32
#define DATA_WIDTH			8
#define MAX_ADDR_VALUE      0xFFFFFFFF

typedef ap_uint<ADDR_WIDTH>  U32_t;
typedef ap_uint<DATA_WIDTH>  U8_t;

struct axiu
{
  ap_uint<DATA_WIDTH>   data;
  ap_uint<DATA_WIDTH/8> keep;
  ap_uint<1>   			last;
};

typedef hls::stream<axiu> AXIS_OUT;
typedef hls::stream<axiu> AXIS_IN;

typedef struct
{
	U32_t match_num;
	U32_t match_pos;
}MATCH_INFO;

typedef struct
{
	U8_t  bit_buffer;
	U8_t  bit_pos;
	U32_t codecount;
}BITBUF_INF;

U32_t LZSS_encoder(AXIS_IN &in_data,U32_t in_size, AXIS_OUT &out_data);

#endif
