#pragma once

#include <iostream>
#include <map>
#include <vector>
#include <string>
#include <ctime>

//#include <stdint.h> //for 1 byte unsigned ints

#include "defines.h"

#define __BCIDCOUNTERSIZE_FEI4A 256	//BCID counter for FEI4A has 8 bit
#define __BCIDCOUNTERSIZE_FEI4B 1024//BCID counter for FEI4B has 10 bit
#define __MAXTOTUSED 13
#define __MAXARRAYSIZE 32768

//#define TRIGGER_WORD_HEADER_MASK_NEW
//#define TRIGGER_WORD_MACRO_NEW(X)			((((TRIGGER_WORD_HEADER_MASK_NEW & X) == TRIGGER_WORD_HEADER_MASK_NEW) || ((TRIGGER_WORD_HEADER_MASK_V10 & X) == TRIGGER_WORD_HEADER_V10))? true : false)

typedef struct HitInfo{
  unsigned long eventNumber;   //event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
  unsigned char relativeBCID;       //relative BCID value (unsigned char: 0 to 255)
  unsigned short int LVLID;         //LVL1ID (unsigned short int: 0 to 65.535)
  unsigned char column;             //column value (unsigned char: 0 to 255)
  unsigned short int row;           //row value (unsigned short int: 0 to 65.535)
  unsigned char tot;                //tot value (unsigned char: 0 to 255)
  unsigned short int BCID;          //absolute BCID value (unsigned short int: 0 to 65.535)
  unsigned char eventStatus;        //event status value (unsigned char: 0 to 255)
} HitInfo;

typedef struct MetaInfo{
  unsigned int startIndex;   //start index for this read out
  unsigned int stopIndex;    //stop index for this read out (exclusive!)
  unsigned int length;       //number of data word in this read out
  double timeStamp;          //time stamp of the readout         
  unsigned int errorCode;    //error code for the read out (0: no error)
} MetaInfo;

typedef struct ParInfo{
  unsigned int pulserDAC;   //pulser DAC setting
} ParInfo;

class Interpret
{
public:
  Interpret(void);
  ~Interpret(void);
  bool interpretRawData(unsigned int* pDataWords, int size);
  void setNbCIDs(int NbCIDs);											//set the number of BCIDs with hits for the actual trigger to save cluster time
  void setFEI4B(bool pIsFEI4B = true){_fEI4B = pIsFEI4B;};						//set the FE flavor to be able to read the raw data correctly
  bool getFEI4B(){return _fEI4B;};
  void resetCounters();                           //reset summary counters
  void resetEventVariables();											//resets event variables before starting new event

  void printSummary();
  void printHits(unsigned int pNhits = 100);						//prints the hits stored in the array

  void getHits(unsigned int &rNhits, HitInfo* &rHitInfo);
  
  void getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned long*& rEventNumber);
  void setMetaWordIndex(unsigned int& tLength, MetaInfo* &rMetaInfo);

private:
  void addHit(unsigned long pEventNumber, unsigned char pRelBCID, unsigned short int pLVLID, unsigned char pColumn, unsigned short int pRow, unsigned char pTot, unsigned short int pBCID, unsigned char pEventStatus);	//add hit with event number, column, row, relative BCID [0:15], tot, trigger ID

  bool getTimefromDataHeader(unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID);	//returns true if the SRAMword is a data header and if it is sets the BCID and LVL1
	bool getHitsfromDataRecord(unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2);	//returns true if the SRAMword is a data record with reasonable hit infos and if it is sets pCol,pRow,pTot
	bool isTriggerWord(unsigned int& pSRAMWORD);						//returns true if data word is trigger word
	bool isOtherWord(unsigned int& pSRAMWORD);							//returns true if data word is an empty record, adress record, value record or service record

  void correlateMetaWordIndex(unsigned long& pEventNumer, unsigned long& pDataWordIndex);  //writes the event number for the meta data 

  //config variables
  int _NbCID; 														  //number of BCIDs for one trigger
  bool _fEI4B;														  //set to true to distinguish between FE-I4B and FE-I4A

  //event variables
  int tNdataHeader;													//number of data header per event
	int tNdataRecord;													//number of data records per event
	unsigned int tStartBCID;									//BCID value of the first hit for the event window
	unsigned int tStartLVL1ID;								//LVL1ID value of the first data header of the event window
	unsigned int tDbCID;											//relative BCID of on event window [0:15], counter
	bool tLVL1IDisConst;											//is only true if a trigger is send externally, self trigger can have different LVL1IDs in one event
  bool tValidTriggerData;										//set to false if event data structure is strange to avoid clustering of invalid data
	bool tIncompleteEvent;										//set to true if event data is incomplete to omit the actual event for clustering

  //counters for the total raw data processing
	unsigned long _nTriggers;								  //stores the total number of trigger words counted
	unsigned long _nEvents;									  //stores the total number of valid events counted
	unsigned long _nInvalidEvents;						//number of events with wrong data structure
  unsigned long _nEmptyEvents;				  		//number of events with wrong data structure
	unsigned long _nIncompleteEvents;				  //number of events with incomplete data structure
  unsigned long _nUnknownWords;						  //number of unknowns words found
	unsigned long _nDataRecords;							//the total number of data records found
  unsigned long _nDataHeaders;							//the total number of data headers found
  unsigned long _nHits;							        //the total number of hits found
  unsigned long _nDataWords;							  //the total number of data words

  //arrays for interpreted information
  unsigned int _hitIndex;                   //index for the interpreted info array
  HitInfo _hitInfo[__MAXARRAYSIZE];

  //meta data infos
  bool _metaDataSet;                        //true if meta data is available
  unsigned long* _metaEventIndex;           //pointer to the array that holds the event number for every read out (meta_data row)
  unsigned int _metaEventIndexLength;      //length of event number array
  MetaInfo* _metaInfo;                      //pointer to the meta info
  unsigned long _lastMetaIndexNotSet;       //the last meta index that is not set
  unsigned long _lastWordIndexSet;          //the last word index used for the event calculation
};

