#pragma once
//helper class to calculate histograms quickly
#include "defines.h"
#include "Basis.h"

#include <vector>
#include <cmath>
#include <algorithm>
#include <set>

#define __nMaxParameters 200

class Histogram: public Basis
{
public:
  Histogram(void);
  ~Histogram(void);

  void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy);  //returns the occupancy histogram for all hits
  void getTotHist(unsigned long*& rTotHist);           //returns the tot histogram for all hits
  void getRelBcidHist(unsigned long*& rRelBcidHist);   //returns the relative BCID histogram for all hits

  void createOccupancyHist(bool CreateOccHist = true);
  void createRelBCIDHist(bool CreateRelBCIDHist = true);
  void createTotHist(bool CreateTotHist = true);

  void addHits(const unsigned int& rNhits, HitInfo*& rHitInfo);
  void addScanParameter(const unsigned int& rNparInfoLength, ParInfo*& rParInfo);
  void setNoScanParameter();
  void addMetaEventIndex(const unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex);

  void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[]); //takes the occupancy histograms for different parameters for the threshold arrays

  unsigned int getMinParameter(); //returns the minimum parameter from _parInfo
  unsigned int getMaxParameter(); //returns the maximum parameter from _parInfo
  unsigned int getNparameters();  //returns the parameter range from _parInfo

  void test();

private:
  void allocateOccupancyArray();
  void resetOccupancyArray();
  void deleteOccupancyArray();
  void allocateTotArray();
  void resetTotArray();
  void deleteTotArray();
  void allocateRelBcidArray();
  void resetRelBcidArray();
  void deleteRelBcidArray();

  void setParameterLimits();      //sets _minParameterValue/_maxParameterValue from _parInfo
  
  unsigned int* _occupancy;       //2d hit histogram for each parameter (in total 3d, linearily sorted in memory via col, row, parameter)
  unsigned long* _tot;            //tot histogram
  unsigned long* _relBcid;        //realative BCID histogram

  unsigned int getEventParameter(unsigned long& rEventNumber);  //returns the event parameter from ParInfo for the given event number
  unsigned int getParIndex(unsigned int& rEventParameter);      //returns the event index in _parameterValues

  unsigned int _nMetaEventIndexLength;//length of the meta data event index array
  unsigned long* _metaEventIndex;     //event index of meta data array
  unsigned int _nParInfoLength;       //length of the parInfo array
  unsigned int _lastMetaEventIndex;   //for loop speed up
  
  unsigned int _minParameterValue;    //...
  unsigned int _maxParameterValue;    //...

  unsigned int _NparameterValues;     //needed for _occupancy histogram allocation

  std::vector<unsigned int> _parameterValues; //different parameter values used in ParInfo

  bool _createOccHist, _createRelBCIDhist, _createTotHist;
  
  ParInfo* _parInfo;
};

