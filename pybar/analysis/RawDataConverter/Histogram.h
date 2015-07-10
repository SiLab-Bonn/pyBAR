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

  //get histograms
  void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy, bool copy = false);  //returns the occupancy histogram for all hits
  void getTotHist(unsigned int*& rTotHist, bool copy = false);           //returns the tot histogram for all hits
  void getTdcHist(unsigned int*& rTdcHist, bool copy = false);           //returns the tdc histogram for all hits
  void getRelBcidHist(unsigned int*& rRelBcidHist, bool copy = false);   //returns the relative BCID histogram for all hits
  void getTotPixelHist(unsigned short*& rTotPixelHist, bool copy = false); //returns the tot pixel histogram
  void getTdcPixelHist(unsigned short*& rTdcPixelHist, bool copy = false); //returns the tdc pixel histogram

  //options set/get
  void createOccupancyHist(bool CreateOccHist = true);
  void createRelBCIDHist(bool CreateRelBCIDHist = true);
  void createTotHist(bool CreateTotHist = true);
  void createTdcHist(bool CreateTdcHist = true);
  void createTdcPixelHist(bool CreateTdcPixelHist = true);
  void createTotPixelHist(bool CreateTotPixelHist = true);
  void setMaxTot(const unsigned int& rMaxTot);

  void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits);
  void addClusterSeedHits(ClusterInfo*& rClusterInfo, const unsigned int& rNcluster);
  void addScanParameter(int*& rParInfo, const unsigned int& rNparInfoLength);
  void setNoScanParameter();
  void addMetaEventIndex(uint64_t*& rMetaEventIndex, const unsigned int& rNmetaEventIndexLength);

  void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[], const unsigned int& rMaxInjections, const unsigned int& min_parameter, const unsigned int& max_parameter); //takes the occupancy histograms for different parameters for the threshold arrays

  unsigned int getNparameters();  //returns the parameter range from _parInfo

  void resetOccupancyArray();
  void resetTotArray();
  void resetTdcArray();
  void resetTdcPixelArray();
  void resetTotPixelArray();
  void resetRelBcidArray();

  void reset();  // resets the histograms and keeps the settings

  void test();

private:
  void setStandardSettings();
  void allocateOccupancyArray();
  void deleteOccupancyArray();
  void allocateTotArray();
  void allocateTdcArray();
  void deleteTotArray();
  void deleteTdcArray();
  void allocateRelBcidArray();
  void deleteRelBcidArray();
  void allocateTotPixelArray();
  void allocateTdcPixelArray();
  void deleteTotPixelArray();
  void deleteTdcPixelArray();
  
  unsigned int* _occupancy;       //2d hit histogram for each parameter (in total 3d, linearly sorted via col, row, parameter)
  unsigned int* _tot;             //tot histogram
  unsigned int* _tdc;             //tdc histogram
  unsigned short* _tdcPixel;      //3d pixel tdc histogram  (in total 3d, linearly sorted via col, row, tdc value)
  unsigned short* _totPixel;      //3d pixel tot histogram  (in total 3d, linearly sorted via col, row, tot value)
  unsigned int* _relBcid;         //realative BCID histogram

  unsigned int getParIndex(int64_t& rEventNumber);      //returns the parameter index for the given event number

  unsigned int _nMetaEventIndexLength;//length of the meta data event index array
  uint64_t* _metaEventIndex;      	  //event index of meta data array
  unsigned int _nParInfoLength;       //length of the parInfo array
  uint64_t _lastMetaEventIndex;   	  //for loop speed up

  unsigned int _NparameterValues;     //needed for _occupancy histogram allocation

  std::map<int, unsigned int> _parameterValues; //different parameter values used in ParInfo, key = parameter value, value = index

  //config variables
  bool _createOccHist;
  bool _createRelBCIDhist;
  bool _createTotHist;
  bool _createTdcHist;
  bool _createTdcPixelHist;
  bool _createTotPixelHist;
  unsigned int _maxTot;               //maximum ToT value (inclusive) considered to be a hit
  
  int* _parInfo;
};

