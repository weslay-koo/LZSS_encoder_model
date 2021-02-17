#include<iostream>
#include<fstream>
#include<iomanip>

using std::cerr;
using std::cout;
using std::setw;
using std::setfill;
using std::ifstream;
using std::ios;

template <int N, typename Tm, typename Tv>
unsigned int ReadFileVec(char *fp, Tm OutBuf[N])
{
    Tv val;
    unsigned int in_size = 0;
    ifstream fp_strmi(fp,ios::in | ios::binary);
    fp_strmi.unsetf(ios::skipws);
    if(!fp_strmi.is_open())
    {
        cerr << "Error!\nThe file is not able to open!\n";
    }
    else 
    {
        while(!fp_strmi.eof())
        {
			fp_strmi >> val;
			OutBuf[in_size] = Tm(val);
			in_size++;
			if (in_size>=N)
				return -1;
        }
    }
    fp_strmi.close();
    cout << setw(60) << setfill('-') << '-' << '\n';
    cout << "Read file successful! Length = " << in_size << "\n";
    cout << setw(60) << setfill('-') << '-' << '\n';
    return in_size;
}
