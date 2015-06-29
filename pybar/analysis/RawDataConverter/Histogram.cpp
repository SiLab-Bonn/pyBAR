#include "Histogram.h"

Histogram::Histogram(void)
{
  setSourceFileName("Histogram");
//  setDebugOutput(true);
  setStandardSettings();
}

Histogram::~Histogram(void)
{
  debug("~Histogram(void): destructor called");
  deleteOccupancyArray();
  deleteTotArray();
  deleteTdcArray();
  deleteRelBcidArray();
  deleteTotPixelArray();
  deleteTdcPixelArray();
}

void Histogram::setStandardSettings()
{
	info("setStandardSettings()");
    _metaEventIndex = 0;
	_parInfo = 0;
	_lastMetaEventIndex = 0;
	_metaEventIndex = 0;
	_occupancy = 0;
	_relBcid = 0;
	_tot = 0;
	_tdc = 0;
	_totPixel = 0;
	_tdcPixel = 0;
	_NparameterValues = 1;
	_createOccHist = false;
	_createRelBCIDhist = false;
	_createTotHist = false;
	_createTdcHist = false;
	_createTdcPixelHist = false;
	_createTotPixelHist = false;
	_maxTot = 13;
}

void Histogram::createOccupancyHist(bool CreateOccHist)
{
	_createOccHist = CreateOccHist;
}

void Histogram::createRelBCIDHist(bool CreateRelBCIDHist)
{
	_createRelBCIDhist = CreateRelBCIDHist;
	if (_createRelBCIDhist){
		allocateRelBcidArray();
		resetRelBcidArray();
	}
	else
		deleteRelBcidArray();
}

void Histogram::createTotHist(bool CreateTotHist)
{
	_createTotHist = CreateTotHist;
	if (_createTotHist){
		allocateTotArray();
		resetTotArray();
	}
	else
		deleteTotArray();
}

void Histogram::createTdcHist(bool CreateTdcHist)
{
	_createTdcHist = CreateTdcHist;
	if (_createTdcHist){
		allocateTdcArray();
		resetTdcArray();
	}
	else
		deleteTdcArray();
}

void Histogram::createTdcPixelHist(bool CreateTdcPixelHist)
{
	_createTdcPixelHist = CreateTdcPixelHist;
	if (_createTdcPixelHist){
		allocateTdcPixelArray();
		resetTdcPixelArray();
	}
	else
		deleteTdcPixelArray();
}

void Histogram::createTotPixelHist(bool CreateTotPixelHist)
{
	_createTotPixelHist = CreateTotPixelHist;
	if (_createTotPixelHist){
		allocateTotPixelArray();
		resetTotPixelArray();
	}
	else
		deleteTotPixelArray();
}

void Histogram::setMaxTot(const unsigned int& rMaxTot)
{
	_maxTot = rMaxTot;
}

void Histogram::addHits(HitInfo*& rHitInfo, const unsigned int& rNhits)
{
	debug("addHits()");
	for(unsigned int i = 0; i<rNhits; ++i){
		if ((rHitInfo[i].eventStatus & __NO_HIT) == __NO_HIT) // ignore virtual hits
			continue;
		unsigned short tColumnIndex = rHitInfo[i].column-1;
		if(tColumnIndex > RAW_DATA_MAX_COLUMN-1)
			throw std::out_of_range("Column index out of range.");
		unsigned int tRowIndex = rHitInfo[i].row-1;
		if(tRowIndex > RAW_DATA_MAX_ROW-1)
			throw std::out_of_range("Row index out of range.");
		unsigned int tTot = rHitInfo[i].tot;
		if(tTot > 15)
			throw std::out_of_range("Tot index out of range.");
		unsigned int tTdc = rHitInfo[i].TDC;
		if(tTdc >= __N_TDC_VALUES)
			throw std::out_of_range("TDC counter " + IntToStr(tTdc) + " index out of range.");
		unsigned int tRelBcid = rHitInfo[i].relativeBCID;
		if(tRelBcid >= __MAXBCID)
			throw std::out_of_range("Relative BCID index out of range.");

		unsigned int tParIndex = getParIndex(rHitInfo[i].eventNumber);
//		std::cout<<i<<" tParIndex "<<tParIndex<<" rHitInfo[i].eventNumber "<<rHitInfo[i].eventNumber<<"\n";

		if(tParIndex < 0 || tParIndex > getNparameters()-1){
			error("addHits: tParIndex "+IntToStr(tParIndex)+"\t> "+IntToStr(_NparameterValues));
			throw std::out_of_range("Parameter index out of range.");
		}
		if(_createOccHist)
			if(tTot <= _maxTot){
				if(_occupancy!=0)
					_occupancy[(size_t)tColumnIndex + (size_t)tRowIndex * (size_t)RAW_DATA_MAX_COLUMN + (size_t)tParIndex * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] += 1;
				else
					throw std::runtime_error("Occupancy array not intitialized. Set scan parameter first!.");
			}
		if(_createRelBCIDhist)
			if(tTot <= _maxTot)
				_relBcid[tRelBcid] += 1;
		if(_createTotHist)
			if(tTot <= _maxTot) //not sure if cut on ToT histogram is unwanted here
				_tot[tTot] += 1;
		if(_createTdcHist)
			_tdc[tTdc] += 1;
		if(_createTdcPixelHist){
			if (_tdcPixel != 0){
				 if(tTdc >= __N_TDC_PIXEL_VALUES){
					info("TDC value out of range:" + IntToStr(tTdc) + ">" + IntToStr(__N_TDC_PIXEL_VALUES));
					tTdc = 0;
				}
				_tdcPixel[(size_t)tColumnIndex + (size_t)tRowIndex * (size_t)RAW_DATA_MAX_COLUMN + (size_t)tTdc * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] += 1;
			}
			else
				throw std::runtime_error("Output TDC pixel array array not set.");
		}
		if(_createTotPixelHist){
			if (tTot <= _maxTot)
				_totPixel[(size_t)tColumnIndex + (size_t)tRowIndex * (size_t)RAW_DATA_MAX_COLUMN + (size_t)tTot * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] += 1;
		}
	}
	//std::cout<<"addHits done"<<std::endl;
}

void Histogram::addClusterSeedHits(ClusterInfo*& rClusterInfo, const unsigned int& rNcluster)
{
	if(Basis::debugSet())
		debug("addClusterSeedHits(...,rNcluster="+IntToStr(rNcluster)+")");
	for(unsigned int i = 0; i<rNcluster; ++i){
		unsigned short tColumnIndex = rClusterInfo[i].seed_column-1;
		if(tColumnIndex > RAW_DATA_MAX_COLUMN-1)
			throw std::out_of_range("Column index out of range.");
		unsigned int tRowIndex = rClusterInfo[i].seed_row-1;
		if(tRowIndex > RAW_DATA_MAX_ROW-1)
			throw std::out_of_range("Row index out of range.");

		unsigned int tParIndex = getParIndex(rClusterInfo[i].eventNumber);

		if(tParIndex < 0 || tParIndex > getNparameters()-1){
			error("addHits: tParIndex "+IntToStr(tParIndex)+"\t> "+IntToStr(_NparameterValues));
			throw std::out_of_range("Parameter index out of range.");
		}
		if(_createOccHist){
			if(_occupancy!=0)
				_occupancy[(size_t)tColumnIndex + (size_t)tRowIndex * (size_t)RAW_DATA_MAX_COLUMN + (size_t)tParIndex * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] += 1;
			else
				throw std::runtime_error("Occupancy array not intitialized. Set scan parameter first!.");
		}
	}
}

unsigned int Histogram::getParIndex(int64_t& rEventNumber)
{
  if(_parInfo == 0)
    return 0;
  for(uint64_t i=_lastMetaEventIndex; i<_nMetaEventIndexLength-1; ++i){
    if(_metaEventIndex[i+1] > (uint64_t) rEventNumber || _metaEventIndex[i+1] < _metaEventIndex[i]){ // second case: meta event data not set yet (std value = 0), event number has to increase
      _lastMetaEventIndex = i;
      if (i < _nParInfoLength)
      	return _parInfo[i];
      else{
    	  error("Scan parameter index " + LongIntToStr(i) + " out of range");
    	  throw std::out_of_range("Scan parameter index out of range.");
      }
    }
  }
  if(_metaEventIndex[_nMetaEventIndexLength-1] <= (uint64_t) rEventNumber) //last read outs
    return _parInfo[_nMetaEventIndexLength-1];
  error("getScanParameter: Correlation issues at event "+LongIntToStr(rEventNumber)+"\n_metaEventIndex[_nMetaEventIndexLength-1] "+LongIntToStr(_metaEventIndex[_nMetaEventIndexLength-1])+"\n_lastMetaEventIndex "+LongIntToStr(_lastMetaEventIndex));
  throw std::logic_error("Event parameter correlation issues.");
  return 0;
}

void Histogram::addScanParameter(int*& rParInfo, const unsigned int& rNparInfoLength)
{
	debug("addScanParameter");
	_nParInfoLength = rNparInfoLength;
	_parInfo = rParInfo;

	std::vector<unsigned int> tParameterValues;

	for(unsigned int i = 0; i < _nParInfoLength; ++i)
	  tParameterValues.push_back(_parInfo[i]);

	std::sort(tParameterValues.begin(), tParameterValues.end());  //sort from lowest to highest value
	std::set<unsigned int> tSet(tParameterValues.begin(), tParameterValues.end());  // delete duplicates
	tParameterValues.assign(tSet.begin(), tSet.end() );

	for(unsigned int i = 0; i < tParameterValues.size(); ++i)
		_parameterValues[tParameterValues[i]] = i;

	_NparameterValues = (unsigned int) tSet.size();

	if (_createOccHist){
		allocateOccupancyArray();
		resetOccupancyArray();
	}
	if (Basis::debugSet()){
	  for(unsigned int i=0; i<_nParInfoLength; ++i)
		 std::cout<<"index "<<i<<"\t parameter index "<<_parInfo[i]<<"\n";
	}
}

void Histogram::addMetaEventIndex(uint64_t*& rMetaEventIndex, const unsigned int& rNmetaEventIndexLength)
{
  debug("addMetaEventIndex()");
  _nMetaEventIndexLength = rNmetaEventIndexLength;
  _metaEventIndex = rMetaEventIndex;
  if (Basis::debugSet())
	  for(unsigned int i=0; i<_nMetaEventIndexLength; ++i)
		 std::cout<<"index "<<i<<"\t event number "<<_metaEventIndex[i]<<"\n";
}

void Histogram::allocateOccupancyArray()
{
  debug("allocateOccupancyArray() with "+IntToStr(getNparameters())+" parameters");
  deleteOccupancyArray();
  try{
    _occupancy = new unsigned int[(size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW * (size_t)getNparameters()];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateOccupancyArray: ")+std::string(exception.what()));
  }
}

void Histogram::deleteOccupancyArray()
{
  debug("deleteOccupancyArray()");
  if (_occupancy != 0)
    delete[] _occupancy;
  _occupancy = 0;
}

void Histogram::resetOccupancyArray()
{
  info("resetOccupancyArray()");
  if (_occupancy != 0){
	  for (unsigned int i = 0; i < RAW_DATA_MAX_COLUMN; i++)
		for (unsigned int j = 0; j < RAW_DATA_MAX_ROW; j++)
		  for(unsigned int k = 0; k < getNparameters();k++)
			  _occupancy[(size_t)i + (size_t)j * (size_t)RAW_DATA_MAX_COLUMN + (size_t)k * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] = 0;
  }
}

void Histogram::resetTdcPixelArray()
{
  info("resetTdcPixelArray()");
  if (_createTdcPixelHist){
	  if (_tdcPixel != 0){
		  for (unsigned int i = 0; i < RAW_DATA_MAX_COLUMN; i++)
			for (unsigned int j = 0; j < RAW_DATA_MAX_ROW; j++)
			  for(unsigned int k = 0; k < __N_TDC_PIXEL_VALUES;k++)
				  _tdcPixel[(size_t)i + (size_t)j * (size_t)RAW_DATA_MAX_COLUMN + (size_t)k * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] = 0;
	  }
	  else
		  throw std::runtime_error("Output TDC pixel array array not set.");
  }
}

void Histogram::resetTotPixelArray()
{
  info("resetTotPixelArray()");
  if (_createTotPixelHist){
	  if (_totPixel != 0){
		  for (unsigned int i = 0; i < RAW_DATA_MAX_COLUMN; i++)
			for (unsigned int j = 0; j < RAW_DATA_MAX_ROW; j++)
			  for(unsigned int k = 0; k < 16;k++)
				  _totPixel[(size_t)i + (size_t)j * (size_t)RAW_DATA_MAX_COLUMN + (size_t)k * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW] = 0;
	  }
	  else
		  throw std::runtime_error("Output TOT pixel array array not set.");
  }
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

void Histogram::allocateTdcArray()
{
  debug("allocateTdcArray()");
  deleteTdcArray();
  try{
    _tdc = new unsigned int[__N_TDC_VALUES];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateTotArray: ")+std::string(exception.what()));
  }
}

void Histogram::resetTotArray()
{
  info("resetTotArray()");
  if (_createTotHist){
	  if (_tot != 0){
		  for (unsigned int i = 0; i < 16; i++)
			_tot[(size_t)i] = 0;
	  }
  }
}

void Histogram::resetTdcArray()
{
  info("resetTdcArray()");
  if (_createTdcHist){
	  if (_tdc != 0){
		  for (unsigned int i = 0; i < __N_TDC_VALUES; i++)
			_tdc[(size_t)i] = 0;
	  }
  }
}
  
void Histogram::deleteTotArray()
{
  debug("deleteTotArray()");
  if (_tot != 0)
    delete[] _tot;
  _tot = 0;
}

void Histogram::deleteTdcArray()
{
  debug("deleteTdcArray()");
  if (_tdc != 0)
    delete[] _tdc;
  _tdc = 0;
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
  info("resetRelBcidArray()");
  if (_createRelBCIDhist){
	  if (_relBcid != 0){
		  for (unsigned int i = 0; i < __MAXBCID; i++)
			_relBcid[(size_t)i] = 0;
	  }
  }
}
  
void Histogram::deleteRelBcidArray()
{
  debug("deleteRelBcidArray");
  if (_relBcid != 0)
    delete[] _relBcid;
  _relBcid = 0;
}

void Histogram::allocateTotPixelArray()
{
  debug("allocateTotPixelArray()");
  deleteTotPixelArray();
  try{
	  _totPixel = new unsigned short[(size_t)RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW * 16];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateTotPixelArray: ")+std::string(exception.what()));
  }
}

void Histogram::allocateTdcPixelArray()
{
  debug("allocateTdcPixelArray()");
  deleteTdcPixelArray();
  try{
	  _tdcPixel = new unsigned short[(size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW * (size_t)__N_TDC_VALUES];
  }
  catch(std::bad_alloc& exception){
    error(std::string("allocateTdcPixelArray: ")+std::string(exception.what()));
  }
}

void Histogram::deleteTotPixelArray()
{
  debug("deleteTotPixelArray");
  if (_totPixel != 0)
    delete[] _totPixel;
  _totPixel = 0;
}

void Histogram::deleteTdcPixelArray()
{
  debug("deleteTdcPixelArray");
  if (_tdcPixel != 0)
    delete[] _tdcPixel;
  _tdcPixel = 0;
}

void Histogram::test()
{
  debug("test()");
  int64_t one = 0;
  int64_t two = 19537531;
  int64_t three = 39086851;
  int64_t four = 273752263;
  std::cout<<one<<"\t"<<getParIndex(one)<<"\n";
  std::cout<<two<<"\t"<<getParIndex(two)<<"\n";
  std::cout<<three<<"\t"<<getParIndex(three)<<"\n";
  std::cout<<four<<"\t"<<getParIndex(four)<<"\n";
//  for (unsigned int i; i < _nParInfoLength; ++i){
//	  std::cout<<_parInfo[i]<<"\n";
//	  std::cout<<_metaEventIndex[i]<<"\n";
//  }
}

unsigned int Histogram::getNparameters()
{
 return _NparameterValues;
}

void Histogram::getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy, bool copy)
{
  debug("getOccupancy(...)");
  if(copy){
	  unsigned int tArrayLength = (size_t)(RAW_DATA_MAX_COLUMN-1) + (size_t)(RAW_DATA_MAX_ROW-1) * (size_t)RAW_DATA_MAX_COLUMN + (size_t)(_NparameterValues-1) * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW+1;
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

void Histogram::getTdcHist(unsigned int*& rTdcHist, bool copy)
{
  debug("getTdcHist(...)");
  if(copy)
 	  std::copy(_tdc, _tdc+__N_TDC_VALUES, rTdcHist);
  else
	  rTdcHist = _tdc;
}

void Histogram::getRelBcidHist(unsigned int*& rRelBcidHist, bool copy)
{
  debug("getRelBcidHist(...)");
  if(copy)
   	  std::copy(_relBcid, _relBcid+__MAXBCID, rRelBcidHist);
  else
	 rRelBcidHist = _relBcid;
}

void Histogram::getTotPixelHist(unsigned short*& rTotPixelHist, bool copy)
{
  debug("getTotPixelHist(...)");
  if(copy)
   	  std::copy(_totPixel, _totPixel+16, rTotPixelHist);
  else
	  rTotPixelHist = _totPixel;
}

void Histogram::getTdcPixelHist(unsigned short*& rTdcPixelHist, bool copy)
{
  debug("getTdcPixelHist(...)");
  if(copy)
   	  std::copy(_tdcPixel, _tdcPixel+__N_TDC_VALUES, rTdcPixelHist);
  else
	  rTdcPixelHist = _tdcPixel;
}

void Histogram::calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[], const unsigned int& rMaxInjections, const unsigned int& min_parameter, const unsigned int& max_parameter)
{
  debug("calculateThresholdScanArrays(...)");
  //quick algorithm from M. Mertens, phd thesis, Juelich 2010

  if(_occupancy==0)
	  throw std::runtime_error("Occupancy array not intitialized. Set scan parameter first!.");

  if (_NparameterValues<2)  //a minimum number of different scans is needed
    return;

  unsigned int q_min = min_parameter;
  unsigned int q_max = max_parameter;
  unsigned int n = getNparameters();
  unsigned int A = rMaxInjections;
  unsigned int d = (int) ( ((double) q_max - (double) q_min)/(double) (n-1));

  for(unsigned int i=0; i<RAW_DATA_MAX_COLUMN; ++i){
    for(unsigned int j=0; j<RAW_DATA_MAX_ROW; ++j){
      unsigned int M = 0;
        
      for(unsigned int k=0; k<getNparameters(); ++k){
        M += _occupancy[(size_t)i + (size_t)j * (size_t)RAW_DATA_MAX_COLUMN  + (size_t)k * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW];
      }
      double threshold = (double) q_max - d*(double)M/(double)A;
      rMuArray[i+j*RAW_DATA_MAX_COLUMN] = threshold;

      unsigned int mu1 = 0;
      unsigned int mu2 = 0;
      for(unsigned int k=0; k<getNparameters(); ++k){
        if((double) k*d < threshold)
          mu1 += _occupancy[(size_t)i + (size_t)j * (size_t)RAW_DATA_MAX_COLUMN  + (size_t)k * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW];
        else
          mu2 += (A-_occupancy[(size_t)i + (size_t)j * (size_t)RAW_DATA_MAX_COLUMN  + (size_t)k * (size_t)RAW_DATA_MAX_COLUMN * (size_t)RAW_DATA_MAX_ROW]);
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

void Histogram::reset()
{
	info("reset()");
	resetOccupancyArray();
	resetTotArray();
	resetTdcArray();
	resetTotPixelArray();
	resetTdcPixelArray();
	resetRelBcidArray();
	_parInfo = 0;
}

