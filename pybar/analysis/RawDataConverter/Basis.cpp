#include "Basis.h"

Basis::Basis(void)
{
	_error = true;
	_warning = true;
	_info = false;
	_debug = false;
	_debugReport = false;
	_bugReportFileName = "BugReport";
}

Basis::~Basis(void)
{
	;
}

void Basis::setSourceFileName(std::string pSourceFileName){
	//pSourceFileName.replace(0,2,"");	//get rid of the .\ in the file name
	pSourceFileName = pSourceFileName.substr(0,pSourceFileName.find_last_of("."));		//get rid of the .cxx in the file name
	_sourceFileName = pSourceFileName;
}

void Basis::setErrorOutput(bool pToggle)
{
	_error = pToggle;
}
void Basis::setWarningOutput(bool pToggle)
{
	if (pToggle){
			_warning = true;
			_error = true;
	}
	else
		_warning = false;
}
void Basis::setInfoOutput(bool pToggle)
{
	if (pToggle){
			_info = true;
			_warning = true;
			_error = true;
	}
	else
		_info = false;
}
void Basis::setDebugOutput(bool pToggle)
{
	if (pToggle){
		_debug = true;
		_info = true;
		_warning = true;
		_error = true;
	}
	else
		_debug = false;
}

void Basis::debug(std::string pText, int pLine)
{
  if(_debug){
	  std::stringstream tOutString;
	  if (pLine == -1)
		  tOutString<<"DEBUG "<<_sourceFileName<<"::"<<pText;
	  else
		  tOutString<<"DEBUG "<<_sourceFileName<<"("<<pLine<<")::";
	  std::cout<<tOutString.str()<<"\n";
	  if (_debugReport){
		  std::ofstream tBugReport;
		  tBugReport.open(_bugReportFileName.c_str(), std::ios::out | std::ios::app);
		  tBugReport<<tOutString.str()<<std::endl;
		  tBugReport.close();
	  }
  }
}

void Basis::info(std::string pText, int pLine)
{
  if(_info){
	  std::stringstream tOutString;
	  if (pLine == -1)
		  tOutString<<"INFO "<<_sourceFileName<<"::"<<pText;
	  else
		  tOutString<<"INFO "<<_sourceFileName<<"("<<pLine<<")::"<<pText;
	  std::cout<<tOutString.str()<<"\n";
	  if (_debugReport){
		  std::ofstream tBugReport;
		  tBugReport.open(_bugReportFileName.c_str(), std::ios::out | std::ios::app);
		  tBugReport<<tOutString.str()<<std::endl;
		  tBugReport.close();
	  }
  }
}

void Basis::warning(std::string pText, int pLine)
{
	if(_warning){
		std::stringstream tOutString;
		if (pLine == -1)
			tOutString<<"WARNING "<<_sourceFileName<<"::"<<pText;
		else
			tOutString<<"WARNING "<<_sourceFileName<<"("<<pLine<<")::"<<pText;
		std::cout<<tOutString.str()<<"\n";
		if (_debugReport){
			std::ofstream tBugReport;
			tBugReport.open(_bugReportFileName.c_str(), std::ios::out | std::ios::app);
			tBugReport<<tOutString.str()<<std::endl;
			tBugReport.close();
		}
	}
}

void Basis::error(std::string pText, int pLine)
{
	if(_error){
		std::stringstream tOutString;
		if (pLine == -1)
			tOutString<<"ERROR "<<_sourceFileName<<"::"<<pText;
		else
			tOutString<<"ERROR "<<_sourceFileName<<"("<<pLine<<")::"<<pText;
		std::cout<<tOutString.str()<<"\n";
		if (_debugReport){
			std::ofstream tBugReport;
			tBugReport.open(_bugReportFileName.c_str(), std::ios::out | std::ios::app);
			tBugReport<<tOutString.str()<<std::endl;
			tBugReport.close();
		}
	}
}
bool Basis::getStringSeparated(std::string pLine, std::string pSeparator, std::string& pLeft, std::string& pRight)
{
	size_t tFound = 0;
	tFound = pLine.find_first_of(pSeparator);
	if(tFound != pLine.npos){ //abort if no seperator found
		pLeft = pLine.substr(0, tFound);
		pRight = pLine.substr(tFound+pSeparator.size(), pLine.npos);
		return true;
	}
	return false;
}

bool Basis::isInf(double pValue)
{
	return std::numeric_limits<double>::has_infinity && pValue == std::numeric_limits<double>::infinity();
}

bool Basis::isNan(double pValue)
{
	return pValue != pValue;
}
bool Basis::isFinite(double pValue)
{
	return !isInf(pValue) &&  !isNan(pValue);
}

bool Basis::fileExists(const std::string& pFileName)
{
	std::ifstream tFile(pFileName.c_str());
	return (tFile != 0);
}

double Basis::StrToDouble(std::string const& pValue)
{
	std::istringstream tValue(pValue);
	double tDoubleValue;
	if (!(tValue>>tDoubleValue)){
		error(std::string("StrToDouble(std::string const& pValue): Not a valid double value set: ").append(pValue));
		return -1;
	}
	return tDoubleValue;
}

int Basis::StrToInt(std::string const& pValue)
{
	std::istringstream tValue(pValue);
	int tIntValue;
	if (!(tValue>>tIntValue)){
		error(std::string("StrToInt(std::string const& pValue): Not a valid integer value set: ").append(pValue));
		return 0;
	}
	return tIntValue;
}

std::string Basis::IntToStr(unsigned int const& pValue)
{
	std::stringstream tStream;
	tStream << pValue;
	return tStream.str();
}

std::string Basis::LongIntToStr(uint64_t const& pValue)
{
	std::stringstream tStream;
	tStream << pValue;
	return tStream.str();
}

std::string Basis::DoubleToStr(double const& pValue)
{
	std::stringstream tValue;
	tValue << pValue;
	return tValue.str();
}

std::string Basis::IntToBin(unsigned int pValue)
{
	std::string tResult = "";
	do
	{
		if ( (pValue & 1) == 0 )
			tResult += "0";
		else
			tResult += "1";
		pValue >>= 1;
	} while (pValue);

	std::reverse(tResult.begin(), tResult.end());
	return tResult;
}

void Basis::setBugReport(bool pCreateReport)
{
	_debugReport = pCreateReport;
}
