#include "Histogram.h"

Histogram::Histogram(void)
{
  setSourceFileName("Histogram");
  _metaEventIndex = 0;
  _parInfo = 0;
  _lastMetaEventIndex = 0;
  _parInfo = 0;
  _metaEventIndex = 0;
  _maxParameterValue = 1;
  _occupancy = 0;
  _relBcid = 0;
  _tot = 0;
  _NparameterValues = 1;
  _minParameterValue = 0;
  _maxParameterValue = 0;
  _createOccHist = false;
  _createRelBCIDhist = false;
  _createTotHist = false;
}

Histogram::~Histogram(void)
{
  deleteOccupancyArray();
  deleteTotArray();
  deleteRelBcidArray();
}

void Histogram::createOccupancyHist(bool CreateOccHist)
{
  _createOccHist = CreateOccHist;
}

void Histogram::createRelBCIDHist(bool CreateRelBCIDHist)
{
  _createRelBCIDhist = CreateRelBCIDHist;
  allocateRelBcidArray();
  resetRelBcidArray();
}

void Histogram::createTotHist(bool CreateTotHist)
{
  _createTotHist = CreateTotHist;
  allocateTotArray();
  resetTotArray();
}

void Histogram::addHits(const unsigned int& rNhits, HitInfo*& rHitInfo)
{
  debug(std::string("addHits()"));
  for(unsigned int i = 0; i<rNhits; i++){
    unsigned short tColumnIndex = rHitInfo[i].column-1;
    if(tColumnIndex > RAW_DATA_MAX_COLUMN-1)
        throw std::out_of_range("column index out of range");
    unsigned int tRowIndex = rHitInfo[i].row-1;
    if(tRowIndex > RAW_DATA_MAX_ROW-1)
      throw std::out_of_range("row index out of range");
    unsigned int tTot = rHitInfo[i].tot;
    if(tTot > 15)
      throw std::out_of_range("tot index out of range");
    unsigned int tRelBcid = rHitInfo[i].relativeBCID;
    if(tRelBcid > 15)
      throw std::out_of_range("relative BCID index out of range");

    unsigned int tEventParameter = getEventParameter(rHitInfo[i].eventNumber);
    unsigned int tParIndex = getParIndex(tEventParameter);

    if(tParIndex < 0 || tParIndex > getNparameters()-1){
      error("addHits: tParIndex "+IntToStr(tParIndex)+"\t_minParameterValue "+IntToStr(_minParameterValue)+"\t_maxParameterValue "+IntToStr(_maxParameterValue));
      throw std::out_of_range("parameter index out of range");
    }
    if(_createOccHist)
      _occupancy[(long)tColumnIndex + (long)tRowIndex * (long)RAW_DATA_MAX_COLUMN + (long)tParIndex * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW] += 1;
    if(_createRelBCIDhist)
      _relBcid[tRelBcid] += 1;
    if(_createTotHist)
      _tot[tTot] += 1;
  }
  //std::cout<<"addHits done"<<std::endl;
}

unsigned int Histogram::getEventParameter(unsigned long& rEventNumber)
{
  if(_parInfo == 0)
    return 0;
  for(unsigned int i=_lastMetaEventIndex; i<_nMetaEventIndexLength-1; ++i){
    if(_metaEventIndex[i+1] > rEventNumber || _metaEventIndex[i+1] < _metaEventIndex[i]){ // second case: meta event data not set yet (std value = 0), event number has to increase
      _lastMetaEventIndex = i;
      return _parInfo[i].scanParameter;
    }
  }
  if(_metaEventIndex[_nMetaEventIndexLength-1] <= rEventNumber) //last read outs
    return _parInfo[_nMetaEventIndexLength-1].scanParameter;
  error("getEventParameter: Correlation issues at event "+IntToStr(rEventNumber)+"\n_metaEventIndex[_nMetaEventIndexLength-1] "+IntToStr(_metaEventIndex[_nMetaEventIndexLength-1])+"\n_lastMetaEventIndex "+IntToStr(_lastMetaEventIndex));
  throw std::logic_error("Event parameter correlation issues");
  return 0;
}

unsigned int Histogram::getParIndex(unsigned int& rEventParameter)
{
  for(unsigned int i = 0; i<_parameterValues.size(); ++i)
    if(_parameterValues[i] == rEventParameter) 
      return i;
  return 0;
}

void Histogram::addScanParameter(const unsigned int& rNparInfoLength, ParInfo*& rParInfo)
{
  debug(std::string("addScanParameter"));
  _nParInfoLength = rNparInfoLength;
  _parInfo = rParInfo;
  setParameterLimits();
  allocateOccupancyArray();
  resetOccupancyArray();
  //for(unsigned int i=0; i<11; ++i)
  //   std::cout<<"read out "<<i<<"\t"<<_parInfo[i].scanParameter<<"\n";
}

void Histogram::addMetaEventIndex(const unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex)
{
  debug(std::string("addMetaEventIndex()"));
  _nMetaEventIndexLength = rNmetaEventIndexLength;
  _metaEventIndex = rMetaEventIndex;
  //for(unsigned int i=0; i<15; ++i)
  //   std::cout<<"read out "<<i<<"\t"<<_metaEventIndex[i]<<"\n";
}

void Histogram::allocateOccupancyArray()
{
  debug("allocateOccupancyArray() with "+IntToStr(getNparameters())+" parameters");
  deleteOccupancyArray();
  try{
    _occupancy = new unsigned int[(long)(RAW_DATA_MAX_COLUMN-1) + ((long)RAW_DATA_MAX_ROW-1)*(long)RAW_DATA_MAX_COLUMN + ((long)getNparameters()-1) * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW +1];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateOccupancyArray: ")+std::string(exception.what()));
  }
}

void Histogram::deleteOccupancyArray()
{
  debug(std::string("deleteOccupancyArray()"));
  if (_occupancy != 0)
    delete _occupancy;
  _occupancy = 0;
}

void Histogram::resetOccupancyArray()
{
  debug(std::string("resetOccupancyArray()"));
  for (unsigned int i = 0; i < RAW_DATA_MAX_COLUMN; i++)
    for (unsigned int j = 0; j < RAW_DATA_MAX_ROW; j++)
      for(unsigned int k = 0; k < getNparameters();k++)
	      _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW] = 0;
}

void Histogram::allocateTotArray()
{
  debug(std::string("allocateTotArray()"));
  deleteTotArray();
  try{
    _tot = new unsigned long[16];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateTotArray: ")+std::string(exception.what()));
  }
}

void Histogram::resetTotArray()
{
  debug(std::string("resetTotArray()"));
  for (unsigned int i = 0; i < 16; i++)
    _tot[(long)i] = 0;
}
  
void Histogram::deleteTotArray()
{
  debug(std::string("deleteTotArray()"));
  if (_tot != 0)
    delete _tot;
  _tot = 0;
}

void Histogram::allocateRelBcidArray()
{
  debug(std::string("allocateRelBcidArray"));
  deleteRelBcidArray();
  try{
     _relBcid = new unsigned long[16];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateRelBcidArray: ")+std::string(exception.what()));
  }
}

void Histogram::resetRelBcidArray()
{
  debug(std::string("resetRelBcidArray()"));
  for (unsigned int i = 0; i < 16; i++)
    _relBcid[(long)i] = 0;
}
  
void Histogram::deleteRelBcidArray()
{
  debug(std::string("deleteRelBcidArray"));
  if (_relBcid != 0)
    delete _relBcid;
  _relBcid = 0;
}

void Histogram::test()
{
  debug(std::string("test()"));
  //std::cout<<"\n##########Histogram::test()########\n";
  /*for(unsigned int i = 0; i<1500; i += 10){
    std::cout<<"event "<<i<<"\t"<<getEventParameter((unsigned long&)i)<<"\n";
  }*/
 /* for(unsigned int i = 1; i<_nParInfoLength; ++i)
    if(_metaEventIndex[i-1] > _metaEventIndex[i] || _parInfo[i-1].scanParameter > _parInfo[i].scanParameter){
      std::cout<<i<<"AAAAAAAAAAAAAAA\t"<<_metaEventIndex[i]<<"\t"<<_parInfo[i].scanParameter<<"\n";
      std::cout<<i-1<<"AAAAAAAAAAAAAAA\t"<<_metaEventIndex[i-1]<<"\t"<<_parInfo[i-1].scanParameter<<"\n";
    }*/

  //unsigned int q_min = getMinParameter();
  //unsigned int q_max = getMaxParameter();
  //unsigned int n = getNparameters();
  //unsigned int A = 100;
  //unsigned int d = (int) ( ((double) getMaxParameter() - (double) getMinParameter())/(n-1));

  //std::cout<<"q_min "<<q_min;
  //std::cout<<"\nq_max "<<q_max;
  //std::cout<<"\nA "<<A;
  //std::cout<<"\nd "<<d<<"\n";

  for(unsigned int tColumnIndex=0; tColumnIndex<RAW_DATA_MAX_COLUMN; ++tColumnIndex){
    for(unsigned int tRowIndex=0; tRowIndex<RAW_DATA_MAX_ROW; ++tRowIndex){
      unsigned int M = 0;
      for(unsigned int tParIndex=0; tParIndex<getNparameters(); ++tParIndex){
    	  _occupancy[(long)tColumnIndex + (long)tRowIndex * (long)RAW_DATA_MAX_COLUMN + (long)tParIndex * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW] = tColumnIndex*RAW_DATA_MAX_ROW + tRowIndex;
    	  //std::cout<<tColumnIndex<<"/"<<tRowIndex<<"/"<<tParIndex<<" "<<(unsigned int) _occupancy[(long)tColumnIndex + (long)tRowIndex * (long)RAW_DATA_MAX_COLUMN + (long)tParIndex * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]<<"\n";
      }
//      double threshold = (double) q_max - d*(double)M/(double)A;
//      std::cout<<"threshold "<<threshold<<"\n";  //threshold
//      unsigned int mu1 = 0;
//      unsigned int mu2 = 0;
//      for(unsigned int k=0; k<getNparameters(); ++k){
//        if((double) k < threshold)
//          mu1 += _occupancy[(long)i * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW + (long)j * (long)getNparameters() + (long)k];
//        if((double) k > threshold)
//          mu2 += (A-_occupancy[(long)i * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW + (long)j * (long)getNparameters() + (long)k]);
//      }
//      double noise = d*(double)(mu1+mu2)/(double)A*sqrt(3.141592653589893238462643383/2);
//      std::cout<<noise<<"\t";
      //std::cout<<d*(double)M/(double)A<<"other\n";
      //std::cout<<d*(double) M/ (double) A;  //threshold
    }
  }
  std::cout<<"\nHistogram::getMinParameter() "<<getMinParameter();
  std::cout<<"\nHistogram::getMaxParameter() "<<getMaxParameter();
  std::cout<<"\nHistogram::getNparameters() "<<getNparameters()<<"\n";
}

void Histogram::setParameterLimits()
{
  debug(std::string("setParameterLimits()"));
  std::vector<unsigned int> tParameterValues;

  for(unsigned int i = 0; i < _nParInfoLength; ++i)
    tParameterValues.push_back(_parInfo[i].scanParameter);

  std::sort(tParameterValues.begin(), tParameterValues.end());  //sort from lowest to highest value
  std::set<int> tSet(tParameterValues.begin(), tParameterValues.end());
  _parameterValues.assign(tSet.begin(), tSet.end() );
  std::unique(_parameterValues.begin(), _parameterValues.end());  //remove all duplicates

  //for(unsigned int i = 0; i<_parameterValues.size(); ++i)
  //  std::cout<<_parameterValues[i]<<"\n";
  
  _minParameterValue = tParameterValues.front();
  _maxParameterValue = tParameterValues.back();
  _NparameterValues = std::unique(tParameterValues.begin(), tParameterValues.end()) - tParameterValues.begin();
  //std::cout<<" setting: _minParameterValue "<<_minParameterValue<<"\n";
  //std::cout<<" setting: _maxParameterValue "<<_maxParameterValue<<"\n";
  //std::cout<<" setting: _NparameterValues "<<_NparameterValues<<"\n";
}

unsigned int Histogram::getMaxParameter()
{
  return _maxParameterValue;
}

unsigned int Histogram::getMinParameter()
{
 return _minParameterValue;
}

unsigned int Histogram::getNparameters()
{
 return _NparameterValues;
}

void Histogram::getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy)
{
  debug(std::string("getOccupancy(...)"));
  rNparameterValues = _NparameterValues;
  rOccupancy = _occupancy;
}

void Histogram::getTotHist(unsigned long*& rTotHist)
{
  debug(std::string("getTotHist(...)"));
  rTotHist = _tot;
}

void Histogram::getRelBcidHist(unsigned long*& rRelBcidHist)
{
  debug(std::string("getRelBcidHist(...)"));
  rRelBcidHist = _relBcid;
}

void Histogram::calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[])
{
  debug(std::string("calculateThresholdScanArrays(...)"));
  //quick algorithm from M. Mertens, phd thesis, J�lich 2010
  if (_NparameterValues<2)  //a minimum number of different scans is needed
    return;

  unsigned int q_min = getMinParameter();
  unsigned int q_max = getMaxParameter();
  unsigned int n = getNparameters();
  unsigned int A = 100;
  unsigned int d = (int) ( ((double) getMaxParameter() - (double) getMinParameter())/(n-1));

  //std::cout<<"q_min "<<q_min<<"\n";
  //std::cout<<"q_max "<<q_max<<"\n";
  //std::cout<<"n "<<n<<"\n";
  //std::cout<<"A "<<A<<"\n";
  //std::cout<<"d "<<d<<"\n";

  for(unsigned int i=0; i<RAW_DATA_MAX_COLUMN; ++i){
    for(unsigned int j=0; j<RAW_DATA_MAX_ROW; ++j){
      unsigned int M = 0;
      unsigned int tMinOccupancy = _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN];
      unsigned int tMaxOccupancy = _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + ((long)getNparameters()-1) * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW];
      if(i == 3 && j == 15){
        //std::cout<<"col/row "<<i<<"/"<<j<<"\n";
        //std::cout<<"tMinOccupancy "<<tMinOccupancy<<"\n";
        //std::cout<<"tMaxOccupancy "<<tMaxOccupancy<<"\n";
        for(unsigned int k=0; k<getNparameters(); ++k)
          std::cout<<_occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]<<"\t";
      }
      //if(tMinOccupancy != 0 || tMaxOccupancy != A){ //error check
      //  //std::cout<<"col/row="<<i<<"/"<<j<<"\n";
      //  rMuArray[i+j*RAW_DATA_MAX_COLUMN] = 0;
      //  rSigmaArray[i+j*RAW_DATA_MAX_COLUMN] = 0;
      //  continue;
      //  //return;
      //}
        
      for(unsigned int k=0; k<getNparameters(); ++k){
        M += _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]; 
        //std::cout<<_occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]<<"\t";
      }
      double threshold = (double) q_max - d*(double)M/(double)A;
      rMuArray[i+j*RAW_DATA_MAX_COLUMN] = threshold;
      //std::cout<<"t "<<threshold<<"\tn ";  //threshold
      unsigned int mu1 = 0;
      unsigned int mu2 = 0;
      for(unsigned int k=0; k<getNparameters(); ++k){
        if((double) k < threshold)
          mu1 += _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW];
        if((double) k > threshold)
          mu2 += (A-_occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]);
      }
      double noise = d*(double)(mu1+mu2)/(double)A*sqrt(3.141592653589893238462643383/2);
      rSigmaArray[i+j*RAW_DATA_MAX_COLUMN] = noise;
      //std::cout<<noise<<"\tM "<<M<<"\tmu1 "<<mu1<<"\tmu2 "<<mu2<<"\n";
      //if(threshold<0){
      //  for(unsigned int k=0; k<getNparameters(); ++k)
      //    std::cout<<_occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]<<"\t";
      //  //return;
      //}
      //std::cout<<d*(double)M/(double)A<<"other\n";
      //std::cout<<d*(double) M/ (double) A;  //threshold
      //std::cout<<"COL "<<i<<"\tROW "<<j<<"\t threshold "<<threshold<<"\tnoise "<<noise<<"\n";
    }
  }
}

void Histogram::setNoScanParameter()
{
  debug(std::string("setNoScanParameter()"));
  deleteOccupancyArray();
  _NparameterValues = 1;
  allocateOccupancyArray();
  resetOccupancyArray();
}

