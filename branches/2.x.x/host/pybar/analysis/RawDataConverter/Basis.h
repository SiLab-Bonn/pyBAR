#pragma once
//Base class for every raw data converter class, providing often used functions (e.g. function that
//are implemented in the C11 standard but not in C09.
//pohl@physik.uni-bonn.de
//Mar. 2012

//#pragma warning(disable: 4800) //disable 'int' : forcing value to bool 'true' or 'false' (performance warning)
#pragma warning(disable: 4996) //disable 'std::copy': Function call warning with parameters that may be unsafe; I know what I'm doing

#include <string>
#include <map>
#include <vector>
#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <limits>
#include <new>
#include <stdexcept>

// for (u)int64_t event_number
#ifdef _MSC_VER
typedef __int64 int64_t;
typedef unsigned __int64 uint64_t;
#else
#include <stdint.h>
#endif


class Basis
{
public:
	Basis(void);
	~Basis(void);

	void setSourceFileName(std::string pSourceFileName);//sets the name of every raw data converter class for info output

	//helper functions
	bool fileExists(const std::string& pFileName);		//check if a file exists
	double StrToDouble(std::string const& pValue);		//converts a std::string to a double
	int StrToInt(std::string const& pValue);			//converts a std::string to a int
	std::string IntToStr(unsigned int const& pValue);	//converts a int to a std::string
	std::string LongIntToStr(uint64_t const& pValue);		//converts a int to a std::string
	std::string DoubleToStr(double const& pValue);		//converts a double to a std::string
	std::string IntToBin(unsigned int pValue);			//converts an unsigned int to a binary string
	bool isInf(double pValue);							//checks if the value is infinite
	bool isNan(double pValue);							//checks if the value is not a number
	bool isFinite(double pValue);						//check if the value is neither NaN nor Inf
	bool getStringSeparated(std::string pLine, std::string pSeparator, std::string& pLeft, std::string& pRight);

	void setBugReport(bool pCreateReport = true);		  		//activates the trace back output
	void setBugReportFileName(std::string pBugReportFileName);	//set the file name for the trace back

	virtual void setErrorOutput(bool pToggle = true);
	virtual void setWarningOutput(bool pToggle = true);
	virtual void setInfoOutput(bool pToggle = true);
	virtual void setDebugOutput(bool pToggle = true);

  //functions needed for code speed up, creating a string and not to show it takes too long (profiled)
  bool debugSet(){return _debug;};
  bool infoSet(){return _info;};
  bool warningSet(){return _warning;};
  bool errorSet(){return _error;};

protected:
	//output debug, infos, warning, errors
	void debug(std::string pText, int pLine = -1);		//writes the pText to the console, also reports the line pLine and the file where this function was called
	void info(std::string pText, int pLine = -1);		//writes the pText to the console, also reports the line pLine and the file where this function was called
	void warning(std::string pText, int pLine = -1);	//writes the pText to the console, also reports the line pLine and the file where this function was called
	void error(std::string pText, int pLine = -1);		//writes the pText to the console, also reports the line pLine and the file where this function was called

private:
	std::string _sourceFileName;						//the file name of the cxx file
	bool _error;										//toggle error output on/off
	bool _warning;										//toggle warning output on/off
	bool _info;											//toggle info output on/off
	bool _debug;										//toggle debug output on/off
	bool _debugReport;									//toggle bug reprot on/off
	std::string _bugReportFileName;				  		//set bug report file name
};

