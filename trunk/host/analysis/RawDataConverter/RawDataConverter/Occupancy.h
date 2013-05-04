#pragma once
//helper class to determine the occupancy and the threshold quickly
#include <map>
#include "Interpret.h"
#include "defines.h"

#define Nparameters 200

class Occupancy
{
public:
  Occupancy(void);
  ~Occupancy(void);

  void getOccupancy(unsigned int*& tOccupancy);

  void addHits(unsigned int& rNhits, HitInfo*& rHitInfo);
  void addScanParameter(unsigned int& rNparInfoLength, ParInfo*& rParInfo);
  void addMetaEventIndex(unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex);

  void resetOccupancy();

  void test();

private:
  void allocateOccupancyArray();
  void deleteOccupancyArray();

  unsigned int*** _occupancy; //col, row, parameter, #hits; will have fixed size [Nparameters][RAW_DATA_MAX_COLUMN][RAW_DATA_MAX_ROW]
  unsigned int getEventParameter(unsigned long& rEventNumber);  //returns the event parameter from ParInfo for the given event number

  unsigned int _nMetaEventIndexLength;
  unsigned long* _metaEventIndex;
  unsigned int _nParInfoLength;
  unsigned int _lastMetaEventIndex; //for loop speed up
  ParInfo* _parInfo;
};

