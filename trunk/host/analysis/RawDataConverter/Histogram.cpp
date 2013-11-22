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
	debug("~Histogram(void): destructor called");
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

void Histogram::addHits(HitInfo*& rHitInfo, const unsigned int& rNhits)
{
  debug("addHits()");
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

    unsigned int tEventParameter = getScanParameter(rHitInfo[i].eventNumber);
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

unsigned int Histogram::getScanParameter(unsigned int& rEventNumber)
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
  error("getScanParameter: Correlation issues at event "+IntToStr(rEventNumber)+"\n_metaEventIndex[_nMetaEventIndexLength-1] "+IntToStr(_metaEventIndex[_nMetaEventIndexLength-1])+"\n_lastMetaEventIndex "+IntToStr(_lastMetaEventIndex));
  throw std::logic_error("Event parameter correlation issues");
  return 0;
}

unsigned int Histogram::getParIndex(unsigned int& rScanParameter)
{
  return _parameterValues[rScanParameter];
}

void Histogram::addScanParameter(const unsigned int& rNparInfoLength, ParInfo*& rParInfo)
{
  debug("addScanParameter");
  _nParInfoLength = rNparInfoLength;
  _parInfo = rParInfo;
  setParameterLimits();
  allocateOccupancyArray();
  resetOccupancyArray();
  //for(unsigned int i=0; i<11; ++i)
  //   std::cout<<"read out "<<i<<"\t"<<_parInfo[i].scanParameter<<"\n";
}

void Histogram::addMetaEventIndex(const unsigned int& rNmetaEventIndexLength, unsigned int*& rMetaEventIndex)
{
  debug("addMetaEventIndex()");
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
  debug("deleteOccupancyArray()");
  if (_occupancy != 0)
    delete _occupancy;
  _occupancy = 0;
}

void Histogram::resetOccupancyArray()
{
  debug("resetOccupancyArray()");
  for (unsigned int i = 0; i < RAW_DATA_MAX_COLUMN; i++)
    for (unsigned int j = 0; j < RAW_DATA_MAX_ROW; j++)
      for(unsigned int k = 0; k < getNparameters();k++)
	      _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW] = 0;
}

void Histogram::allocateTotArray()
{
  debug("allocateTotArray()");
  deleteTotArray();
  try{
    _tot = new unsigned int[16];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateTotArray: ")+std::string(exception.what()));
  }
}

void Histogram::resetTotArray()
{
  debug("resetTotArray()");
  for (unsigned int i = 0; i < 16; i++)
    _tot[(long)i] = 0;
}
  
void Histogram::deleteTotArray()
{
  debug("deleteTotArray()");
  if (_tot != 0)
    delete _tot;
  _tot = 0;
}

void Histogram::allocateRelBcidArray()
{
  debug("allocateRelBcidArray");
  deleteRelBcidArray();
  try{
     _relBcid = new unsigned int[__MAXBCID];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateRelBcidArray: ")+std::string(exception.what()));
  }
}

void Histogram::resetRelBcidArray()
{
  debug("resetRelBcidArray()");
  for (unsigned int i = 0; i < __MAXBCID; i++)
    _relBcid[(long)i] = 0;
}
  
void Histogram::deleteRelBcidArray()
{
  debug("deleteRelBcidArray");
  if (_relBcid != 0)
    delete _relBcid;
  _relBcid = 0;
}

void Histogram::test()
{
  debug("test()");
  setParameterLimits();
}

void Histogram::setParameterLimits()
{
  debug("setParameterLimits()");
  std::vector<unsigned int> tParameterValues;

  for(unsigned int i = 0; i < _nParInfoLength; ++i)
    tParameterValues.push_back(_parInfo[i].scanParameter);

  std::sort(tParameterValues.begin(), tParameterValues.end());  //sort from lowest to highest value
  std::set<unsigned int> tSet(tParameterValues.begin(), tParameterValues.end());
  tParameterValues.assign(tSet.begin(), tSet.end() );

  for(unsigned int i = 0; i < tParameterValues.size(); ++i)
      _parameterValues[tParameterValues[i]] = i;

  _minParameterValue = tParameterValues.front();
  _maxParameterValue = tParameterValues.back();
  _NparameterValues = std::unique(tParameterValues.begin(), tParameterValues.end()) - tParameterValues.begin();
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

void Histogram::getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy, bool copy)
{
  debug("getOccupancy(...)");
  if(copy){
	  unsigned int tArrayLength = (long)(RAW_DATA_MAX_COLUMN-1) + (long)(RAW_DATA_MAX_ROW-1) * (long)RAW_DATA_MAX_COLUMN + (long)(_NparameterValues-1) * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW+1;
	  std::copy(_occupancy, _occupancy+tArrayLength, rOccupancy);
  }
  else
	  rOccupancy = _occupancy;

  rNparameterValues = _NparameterValues;
}

void Histogram::getTotHist(unsigned int*& rTotHist, bool copy)
{
  debug("getTotHist(...)");
  if(copy)
 	  std::copy(_tot, _tot+16, rTotHist);
  else
	  rTotHist = _tot;
}

void Histogram::getRelBcidHist(unsigned int*& rRelBcidHist, bool copy)
{
  debug("getRelBcidHist(...)");
  if(copy)
   	  std::copy(_relBcid, _relBcid+__MAXBCID, rRelBcidHist);
  else
	 rRelBcidHist = _relBcid;
}

void Histogram::calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[])
{
  debug("calculateThresholdScanArrays(...)");
  //quick algorithm from M. Mertens, phd thesis, Juelich 2010

  if (_NparameterValues<2)  //a minimum number of different scans is needed
    return;

  unsigned int q_min = getMinParameter();
  unsigned int q_max = getMaxParameter();
  unsigned int n = getNparameters();
  unsigned int A = 100;
  unsigned int d = (int) ( ((double) getMaxParameter() - (double) getMinParameter())/(double) (n-1));

  for(unsigned int i=0; i<RAW_DATA_MAX_COLUMN; ++i){
    for(unsigned int j=0; j<RAW_DATA_MAX_ROW; ++j){
      unsigned int M = 0;
      unsigned int tMinOccupancy = _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN];
      unsigned int tMaxOccupancy = _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + ((long)getNparameters()-1) * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW];
        
      for(unsigned int k=0; k<getNparameters(); ++k){
        M += _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]; 
      }
      double threshold = (double) q_max - d*(double)M/(double)A;
      rMuArray[i+j*RAW_DATA_MAX_COLUMN] = threshold;

      unsigned int mu1 = 0;
      unsigned int mu2 = 0;
      for(unsigned int k=0; k<getNparameters(); ++k){
        if((double) k*d < threshold)
          mu1 += _occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW];
        if((double) k*d > threshold)
          mu2 += (A-_occupancy[(long)i + (long)j * (long)RAW_DATA_MAX_COLUMN  + (long)k * (long)RAW_DATA_MAX_COLUMN * (long)RAW_DATA_MAX_ROW]);
      }
      double noise = (double)d*(double)(mu1+mu2)/(double)A*sqrt(3.141592653589893238462643383/2);
      rSigmaArray[i+j*RAW_DATA_MAX_COLUMN] = noise;
    }
  }
}

void Histogram::setNoScanParameter()
{
  debug("setNoScanParameter()");
  deleteOccupancyArray();
  _NparameterValues = 1;
  allocateOccupancyArray();
  resetOccupancyArray();
}

