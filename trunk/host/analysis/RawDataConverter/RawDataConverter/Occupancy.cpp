#include "StdAfx.h"
#include "Occupancy.h"


Occupancy::Occupancy(void)
{
  _metaEventIndex = 0;
  _parInfo = 0;
  _lastMetaEventIndex = 0;
  allocateOccupancyArray();
  resetOccupancy();
}

Occupancy::~Occupancy(void)
{
  deleteOccupancyArray();
}

void Occupancy::addHits(unsigned int& rNhits, HitInfo*& rHitInfo)
{
  for(unsigned int i = 0; i<rNhits; i++){
    unsigned short tColumnIndex = rHitInfo[i].column-1; 
    if(tColumnIndex  > RAW_DATA_MAX_COLUMN-1)
        throw 20;
    unsigned int tRowIndex = rHitInfo[i].row-1;
    if(tRowIndex > RAW_DATA_MAX_ROW-1)
      throw 21;
    unsigned int tParIndex = getEventParameter(rHitInfo[i].eventNumber);
    if(tParIndex > Nparameters-1){
      std::cout<<"tParIndex "<<tParIndex<<"\tNparameters "<<Nparameters<<"\n";
      throw 22;
    }

    //if(i%1000 == 0)
    //  std::cout<<i<<"\t"<<tColumnIndex<<"\t"<<tRowIndex<<"\t"<<tParIndex<<"\n";

    _occupancy[tColumnIndex][tRowIndex][tParIndex] += 1;
  }
}

unsigned int Occupancy::getEventParameter(unsigned long& rEventNumber)
{
  for(unsigned int i=_lastMetaEventIndex; i<_nMetaEventIndexLength-1; ++i){
    if(_metaEventIndex[i+1] > rEventNumber || _metaEventIndex[i+1] < _metaEventIndex[i]){ // second case: meta event data not set yet (std value = 0), event number has to increase
      _lastMetaEventIndex = i;
      return _parInfo[i].pulserDAC;
    }
  }
  if(_metaEventIndex[_nMetaEventIndexLength-1] <= rEventNumber) //last read outs
    return _parInfo[_nMetaEventIndexLength-1].pulserDAC;
  std::cout<<"Correlation issues at event "<<rEventNumber<<"\n";
  std::cout<<"_metaEventIndex[_nMetaEventIndexLength-1] "<<_metaEventIndex[_nMetaEventIndexLength-1]<<"\n";
  std::cout<<"_lastMetaEventIndex "<<_lastMetaEventIndex<<"\n";
  throw 23;
  return 0;
}

void Occupancy::addScanParameter(unsigned int& rNparInfoLength, ParInfo*& rParInfo)
{
  //std::cout<<"Occupancy::addScanParameter\n";
  _nParInfoLength = rNparInfoLength;
  _parInfo = rParInfo;
  //for(unsigned int i=0; i<11; ++i)
  //   std::cout<<"read out "<<i<<"\t"<<_parInfo[i].pulserDAC<<"\n";
}

void Occupancy::addMetaEventIndex(unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex)
{
  //std::cout<<"Occupancy::addMetaEventIndex\n";
  _nMetaEventIndexLength = rNmetaEventIndexLength;
  _metaEventIndex = rMetaEventIndex;
  //for(unsigned int i=0; i<15; ++i)
  //   std::cout<<"read out "<<i<<"\t"<<_metaEventIndex[i]<<"\n";
}

void Occupancy::allocateOccupancyArray()
{
  //std::cout<<"Occupancy::allocateOccupancyArray\n";
  _occupancy = new unsigned int**[RAW_DATA_MAX_COLUMN];
  for (int i = 0; i < RAW_DATA_MAX_COLUMN; ++i) {
    _occupancy[i] = new unsigned int*[RAW_DATA_MAX_ROW];
    for (int j = 0; j < RAW_DATA_MAX_ROW; ++j)
      _occupancy[i][j] = new unsigned int[Nparameters];
  }
}

void Occupancy::deleteOccupancyArray()
{
  //std::cout<<"Occupancy::deleteOccupancyArray\n";
  for (int i = 0; i < RAW_DATA_MAX_COLUMN; ++i){
    for (int j = 0; j < RAW_DATA_MAX_ROW; ++j)
      delete [] _occupancy[i][j];
    delete [] _occupancy[i];
  }
  delete [] _occupancy;
}

void Occupancy::resetOccupancy()
{
  //std::cout<<"Occupancy::resetOccupancy\n";
  for(unsigned int i=0; i<RAW_DATA_MAX_COLUMN; ++i)
    for(unsigned int j=0; j<RAW_DATA_MAX_ROW; ++j)
      for(unsigned int k=0; k<Nparameters; ++k)
        _occupancy[i][j][k] = 0;
}

void Occupancy::test()
{
  std::cout<<"############################\n";
  /*for(unsigned int i = 0; i<1500; i += 10){
    std::cout<<"event "<<i<<"\t"<<getEventParameter((unsigned long&)i)<<"\n";
  }*/
  for(unsigned int i = 1; i<_nParInfoLength; ++i)
    if(_metaEventIndex[i-1] > _metaEventIndex[i] || _parInfo[i-1].pulserDAC > _parInfo[i].pulserDAC){
      std::cout<<i<<"AAAAAAAAAAAAAAA\t"<<_metaEventIndex[i]<<"\t"<<_parInfo[i].pulserDAC<<"\n";
      std::cout<<i-1<<"AAAAAAAAAAAAAAA\t"<<_metaEventIndex[i-1]<<"\t"<<_parInfo[i-1].pulserDAC<<"\n";
    }
}