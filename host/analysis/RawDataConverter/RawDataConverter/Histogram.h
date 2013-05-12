#pragma once
//helper class to calculate histograms quickly
#include "Interpret.h"

#define Nparameters 200

class Histogram
{
public:
  Histogram(void);
  ~Histogram(void);

  void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy);

  void addHits(unsigned int& rNhits, HitInfo*& rHitInfo);
  void addScanParameter(unsigned int& rNparInfoLength, ParInfo*& rParInfo);
  void setNoScanParameter();
  void addMetaEventIndex(unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex);

  void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[]);

  void test();

private:
  void allocateOccupancyArray();
  void resetOccupancy();
  void deleteOccupancyArray();

  void setParameterLimits();      //sets _minParameterValue/_maxParameterValue from _parInfo

  unsigned int getMinParameter(); //returns the minimum parameter from _parInfo
  unsigned int getMaxParameter(); //returns the maximum parameter from _parInfo
  unsigned int getNparameters();  //returns the parameter range from _parInfo
  
  unsigned int* _occupancy;       //histogram sorted in memory via col, row, parameter
  unsigned int getEventParameter(unsigned long& rEventNumber);  //returns the event parameter from ParInfo for the given event number

  unsigned int _nMetaEventIndexLength;//length of the meta data event index array
  unsigned long* _metaEventIndex;     //event index of meta data array
  unsigned int _nParInfoLength;       //length of the parInfo array
  unsigned int _lastMetaEventIndex;   //for loop speed up
  unsigned int _minParameterValue;    //needed for _occupancy histogram allocation
  unsigned int _maxParameterValue;    //needed for _occupancy histogram allocation
  unsigned int _NparameterValues;     //needed for _occupancy histogram allocation
  
  ParInfo* _parInfo;
};

