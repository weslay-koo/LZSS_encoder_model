#include<iostream>
#include<fstream>
#include<iomanip>

using std::cerr;
using std::cout;
using std::setw;
using std::setfill;
using std::ofstream;
using std::ios;

template <int N, typename Tm, typename Tv>
void WriteFileVec(char *fp, int file_len, Tm InBuf[N])
{
    ofstream fp_strmo(fp,ios::out | ios::binary);
    if(!fp_strmo.is_open())
    {
        cerr << "Error!\nThe file is not able to open!\n";
    }
    else 
    {
    	for (int i=0;i<file_len;i++)
        {
            fp_strmo << (Tv)(InBuf[i]);
        }
    }
    fp_strmo.close();
    cout << setw(60) << setfill('-') << '-' << '\n';
    cout << "Data has been successfully stored to target file!\n";
    cout << setw(60) << setfill('-') << '-' << '\n';
}
