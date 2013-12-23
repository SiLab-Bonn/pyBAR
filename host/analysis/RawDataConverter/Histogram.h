#pragma once
//helper class to calculate histograms quickly
#include <vector>
#include <cmath>
#include <algorithm>
#include <iterator>
#include <set>

#include "defines.h"
#include "Basis.h"

class Histogram: public Basis
{
public:
  Histogram(void);
  ~Histogram(void);

  void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy, bool copy = true);  //returns the occupancy histogram for all hits
  void getTotHist(unsigned int*& rTotHist, bool copy = true);           //returns the tot histogram for all hits
  void getRelBcidHist(unsigned int*& rRelBcidHist, bool copy = true);   //returns the relative BCID histogram for all hits

  //options set/get
  void createOccupancyHist(bool CreateOccHist = true);
  void createRelBCIDHist(bool CreateRelBCIDHist = true);
  void createTotHist(bool CreateTotHist = true);
  void setMaxTot(const unsigned int& rMaxTot);

  void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits);
  void addScanParameter(const unsigned int& rNparInfoLength, ParInfo*& rParInfo);
  void setNoScanParameter();
  void addMetaEventIndex(const unsigned int& rNmetaEventIndexLength, unsigned int*& rMetaEventIndex);

  void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[], const unsigned int& rMaxInjections); //takes the occupancy histograms for different parameters for the threshold arrays

  unsigned int getMinParameter(); //returns the minimum parameter from _parInfo
  unsigned int getMaxParameter(); //returns the maximum parameter from _parInfo
  unsigned int getNparameters();  //returns the parameter range from _parInfo

  void resetOccupancyArray();
  void resetTotArray();
  void resetRelBcidArray();

  void reset();  // resets the histograms and keeps the settings

  void test();

private:
  void setStandardSettings();
  void allocateOccupancyArray();
  void deleteOccupancyArray();
  void allocateTotArray();
  void deleteTotArray();
  void allocateRelBcidArray();
  void deleteRelBcidArray();
  void setParameterLimits();      //sets _minParameterValue/_maxParameterValue from _parInfo
  
  unsigned int* _occupancy;       //2d hit histogram for each parameter (in total 3d, linearly sorted via col, row, parameter)
  unsigned int* _tot;            //tot histogram
  unsigned int* _relBcid;        //realative BCID histogram

  unsigned int getScanParameter(unsigned int& rEventNumber);  //returns the event parameter from ParInfo for the given event number
  unsigned int getParIndex(unsigned int& rScanParameter);      //returns the event index in _parameterValues

  unsigned int _nMetaEventIndexLength;//length of the meta data event index array
  unsigned int* _metaEventIndex;      //event index of meta data array
  unsigned int _nParInfoLength;       //length of the parInfo array
  unsigned int _lastMetaEventIndex;   //for loop speed up
  
  unsigned int _minParameterValue;    //...
  unsigned int _maxParameterValue;    //...

  unsigned int _NparameterValues;     //needed for _occupancy histogram allocation

  std::map<unsigned int, unsigned int> _parameterValues; //different parameter values used in ParInfo, key = parameter value, value = index

  //config variables
  bool _createOccHist;
  bool _createRelBCIDhist;
  bool _createTotHist;
  unsigned int _maxTot;               //maximum ToT value (inclusive) considered to be a hit
  
  ParInfo* _parInfo;
};

