#include "ReadFileVec.h"
#include "WriteFileVec.h"
#include "lzss_encoder.h"

#define  MAX_FILE_LEN  (1024*1024)

using namespace std;

int main()
{
	U8_t     *in_data;
	U8_t     *out_data;

	AXIS_IN  in_stream;
	AXIS_OUT out_stream;
    U32_t    in_size,out_size;
    axiu     in_st,out_st;
    
    in_data  = (U8_t *)malloc(MAX_FILE_LEN*sizeof(U8_t));
    out_data = (U8_t *)malloc(MAX_FILE_LEN*sizeof(U8_t));

    int ErrCnt   = 0;
    char *fp_in  = (char*)"xargs.1";
    char *fp_out = (char*)"../../../src/data_out";

    // Read input file to AXIS
    in_size = (U32_t)ReadFileVec<MAX_FILE_LEN,U8_t,char>(fp_in, in_data);
    cerr << "In_size = "<<in_size<<"\n";
    for(int i=0;i<in_size;i++)
    {
    	in_st.data = in_data[i];
    	in_st.keep = 1;
    	if (i<in_size-1)
    		in_st.last = 0;
    	else
    		in_st.last = 1;
    	in_stream.write(in_st);
    }

    /////////////////// DUT  Stimulus Start //////////////////////////
    out_size = LZSS_encoder(in_stream,in_size,out_stream);
    /////////////////// DUT  Stimulus End   //////////////////////////

    // Write AXIS to output file
    int j = 0;
    while(!out_stream.empty())
    {
    	out_st = in_stream.read();
		out_data[j++] = out_st.data;
    	if(out_st.last==1)
    		break;
    }

    WriteFileVec<MAX_FILE_LEN,U8_t,char>(fp_out, in_size, out_data);
    free(in_data);
    free(out_data);
    return 0;

    /*
    out_size = LZSS_encoder(in_data,in_size,out_data);

    WriteFileVec<AXIS_OUT,unsigned char>(fp_out, out_data);

    ///////////////////////////////////////
    ////        Score Board            ////
    ///////////////////////////////////////
    ErrCnt = system("diff -w R_out.txt Golden_R.txt");
    cerr << " done." << endl << endl;
    if (ErrCnt == 0)
    {
        cerr << "*** Test Passed ***" << endl << endl;
        return 0;
    }
    else
    {
        cerr << "!!! TEST FAILED -- " << ErrCnt << " mismatches detected !!!";
        cerr << endl << endl;
        return -1;
    }
    */
}
