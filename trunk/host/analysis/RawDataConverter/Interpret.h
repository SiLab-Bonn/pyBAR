#pragma once

#include <iostream>
#include <string>
#include <ctime>
#include <cmath>

#include "Basis.h"
#include "defines.h"

#define __DEBUG false
#define __DEBUG2 false

//DUT and TLU defines
#define __BCIDCOUNTERSIZE_FEI4A 256	  //BCID counter for FEI4A has 8 bit
#define __BCIDCOUNTERSIZE_FEI4B 1024  //BCID counter for FEI4B has 10 bit
#define __NSERVICERECORDS 32          //# of different service records
#define __MAXARRAYSIZE 32768          //maximum buffer array size for the output hit array (has to be bigger than hits in one chunk)
#define __MAXHITBUFFERSIZE 30000      //maximum buffer array size for the hit buffer array (has to be bigger than hits in one event)
#define __MAXTLUTRGNUMBER 32767       //maximum trigger logic unit trigger number (32-bit)

//event error codes
#define __N_ERROR_CODES 8             //number of event error codes
#define __NO_ERROR 0                  //no error
#define __HAS_SR 1                    //the event has service records
#define __NO_TRG_WORD 2               //the event has no trigger word, is ok for not external triggering
#define __NON_CONST_LVL1ID 4          //LVL1ID changes in one event, is ok for self triggering
#define __EVENT_INCOMPLETE 8          //BCID not increasing by 1, most likely BCID missing (incomplete data transmission)
#define __UNKNOWN_WORD 16             //event has unknown words
#define __BCID_JUMP 32                //BCID jumps, but LVL1ID is constant and data is externally triggered
#define __TRG_ERROR 64                //a trigger error occured

//trigger error codes
#define __TRG_N_ERROR_CODES 8         //number of trigger error codes
#define __TRG_NO_ERROR 0              //no trigger error
#define __TRG_NUMBER_INC_ERROR 1      //two consecutive triggern numbers are not increasing by exactly one (counter overflow case considered correctly)
#define __TRG_NUMBER_MORE_ONE 2       //more than one trigger per event
#define __TRG_ERROR_TRG_ACCEPT 4      //TLU error
#define __TRG_ERROR_LOW_TIMEOUT 8     //TLU error

//trigger word macros
//#define TRIGGER_WORD_HEADER_MASK_NEW 0x00000000 //first bit 1 means trigger word
#define TRIGGER_WORD_HEADER_MASK_NEW 0x80000000   //first bit 1 means trigger word
#define TRIGGER_NUMBER_MASK_NEW		0x0000FFFF      //trigger number is in the low word
#define TRIGGER_ERROR_TRG_ACCEPT		0x40000000    //trigger accept error
#define TRIGGER_ERROR_LOW_TIMEOUT		0x20000000    //TLU not deassert trigger signal
#define TRIGGER_WORD_MACRO_NEW(X)			(((TRIGGER_WORD_HEADER_MASK_NEW & X) == TRIGGER_WORD_HEADER_MASK_NEW) ? true : false) //true if data word is trigger word
#define TRIGGER_NUMBER_MACRO_NEW(X)	(TRIGGER_NUMBER_MASK_NEW & X)                                                           //calculates the trigger number from a trigger word

//structure to store the hits
typedef struct HitInfo{
  unsigned long eventNumber;  //event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
  unsigned int triggerNumber; //external trigger number for read out system
  unsigned char relativeBCID; //relative BCID value (unsigned char: 0 to 255)
  unsigned short int LVLID;   //LVL1ID (unsigned short int: 0 to 65.535)
  unsigned char column;       //column value (unsigned char: 0 to 255)
  unsigned short int row;     //row value (unsigned short int: 0 to 65.535)
  unsigned char tot;          //tot value (unsigned char: 0 to 255)
  unsigned short int BCID;    //absolute BCID value (unsigned short int: 0 to 65.535)
  unsigned char triggerStatus;//event service records
  unsigned int serviceRecord; //event service records
  unsigned char eventStatus;  //event status value (unsigned char: 0 to 255)
} HitInfo;

//structure for the input meta data
typedef struct MetaInfo{
  unsigned int startIndex;    //start index for this read out
  unsigned int stopIndex;     //stop index for this read out (exclusive!)
  unsigned int length;        //number of data word in this read out
  double timeStamp;           //time stamp of the readout         
  unsigned int errorCode;     //error code for the read out (0: no error)
} MetaInfo;

//structure for the output meta data
typedef struct MetaInfoOut{
  unsigned long eventIndex;   //event number of the read out
  double timeStamp;           //time stamp of the readout         
  unsigned int errorCode;     //error code for the read out (0: no error)
} MetaInfoOut;

//structure to read the parameter information table
typedef struct ParInfo{
  unsigned int pulserDAC;     //pulser DAC setting
} ParInfo;

class Interpret: public Basis
{
public:
  Interpret(void);
  ~Interpret(void);

  //main functions
  bool interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords); //starts to interpret the actual raw data pDataWords and saves result to _hitInfo
  void setMetaWordIndex(const unsigned int& tLength, MetaInfo* &rMetaInfo);         //sets the meta word index for word number/event correlation
  void getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned long*& rEventNumber);  //returns the meta event index filled upto the actual interpreted hits
  void getHits(unsigned int &rNhits, HitInfo* &rHitInfo);   //returns the actual interpreted hits

  //initializers, should be called before first call of interpretRawData() with new data file
  void resetCounters();                                     //reset summary counters
  void resetEventVariables();											          //resets event variables before starting new event

  //options set/get
  void setNbCIDs(const unsigned int& NbCIDs);								//set the number of BCIDs with hits for the actual trigger to save cluster time
  void setMaxTot(const unsigned int& rMaxTot);							//sets the maximum tot code that is considered to be a hit
  void setFEI4B(bool pIsFEI4B = true){_fEI4B = pIsFEI4B;};  //set the FE flavor to be able to read the raw data correctly
  bool getFEI4B(){return _fEI4B;};                          //returns the FE flavor set

  //get function to global counters
  void getServiceRecordsCounters(unsigned int &rNserviceRecords, unsigned long*& rServiceRecordsCounter);   //returns the total service record counter array
  void getErrorCounters(unsigned int &rNerrorCounters, unsigned long*& rErrorCounter);                      //returns the total errors counter array
  void getTriggerErrorCounters(unsigned int &rNTriggerErrorCounters, unsigned long*& rTriggerErrorCounter); //returns the total trigger errors counter array
  unsigned long getNwords();                                //returns the total numbers of words analyzed (global counter)
  unsigned long getNunknownWords(){return _nUnknownWords;}; //returns the total numbers of unknown words found (global counter)
  unsigned long getNevents(){return _nEvents;};             //returns the total numbers of events analyzed (global counter)
  unsigned long getNemptyEvents(){return _nEmptyEvents;};   //returns the total numbers of empty events found (global counter)
  unsigned long getNtriggers(){return _nTriggers;};         //returns the total numbers of trigger found (global counter)
  unsigned long getNhits(){return _nHits;};                 //returns the total numbers of hits found (global counter)
  unsigned long getNtriggerNotInc(){return _triggerErrorCounter[1];}; //returns the total numbers of not increasing trigger (error histogram)
  unsigned long getNtriggerNotOne(){return _errorCounter[1]+_triggerErrorCounter[2];}; //returns the total numbers of events with # trigger != 1 (from error histogram)

  //print functions for info output
  void printSummary();                                      //print the interpreter summary with all global counter values (#hits, #data records,...)
  void printHits(const unsigned int& pNhits = 100);			    //prints the hits stored in the array
  void debugEvents(const unsigned long& rStartEvent = 0, const unsigned long& rStopEvent = 0, const bool& debugEvents = true);

private:
  void addHit(const unsigned char& pRelBCID, const unsigned short int& pLVLID, const unsigned char& pColumn, const unsigned short int& pRow, const unsigned char& pTot, const unsigned short int& pBCID); //adds the hit to the event hits array _hitBuffer
  void storeHit(HitInfo& rHit);	//stores the hit into the output hit array _hitInfo
  void addEvent();              //increases the event counter, adds the actual hits/error/SR codes
  void storeEventHits();        //adds the hits of the actual event to _hitInfo
  void correlateMetaWordIndex(const unsigned long& pEventNumer, const unsigned long& pDataWordIndex);  //writes the event number for the meta data 
  
  //SRAM word check and interpreting methods
  bool getTimefromDataHeader(const unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID);	      //returns true if the SRAMword is a data header and if it is sets the BCID and LVL1
  bool isDataRecord(const unsigned int& pSRAMWORD);               //returns true if data word is a data record (no col ,row ,tot limit checks done, only check for data record header)
	bool getHitsfromDataRecord(const unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2);	//returns true if the SRAMword is a data record with reasonable hit infos and if it is sets pCol,pRow,pTot
	bool getInfoFromServiceRecord(const unsigned int& pSRAMWORD, unsigned int& pSRcode, unsigned int& pSRcount); 	//returns true if the SRAMword is a service record and sets pSRcode,pSRcount
  bool isTriggerWord(const unsigned int& pSRAMWORD);						  //returns true if data word is trigger word
	bool isOtherWord(const unsigned int& pSRAMWORD);							  //returns true if data word is an empty record, adress record, value record or service record

  //SR/error histogramming methods
  void addTriggerErrorCode(const unsigned char& pErrorCode);      //adds the trigger error code to the existing error code
  void addEventErrorCode(const unsigned char& pErrorCode);        //adds the error code to the existing error code
  void histogramTriggerErrorCode();                               //adds the event trigger error code to the histogram
  void histogramErrorCode();                                      //adds the event error code to the histogram
  void addServiceRecord(const unsigned char& pSRcode);            //adds the service record code to SR histogram

  //memory allocation/initialization
  void allocateHitInfoArray();
  void deleteHitInfoArray();
  void allocateHitBufferArray();
  void deleteHitBufferArray();
  void allocateMetaEventIndexArray();
  void deleteMetaEventIndexArray();
  void allocateTriggerErrorCounterArray();
  void resetTriggerErrorCounterArray();
  void deleteTriggerErrorCounterArray();
  void allocateErrorCounterArray();
  void resetErrorCounterArray();
  void deleteErrorCounterArray();
  void allocateServiceRecordCounterArray();
  void resetServiceRecordCounterArray();
  void deleteServiceRecordCounterArray();

  //helper function for debuging data words
  void printInterpretedWords(unsigned int* pDataWords, const unsigned int& rNsramWords, const unsigned int& rStartWordIndex, const unsigned int& rEndWordIndex);

  //arrays for interpreted information
  unsigned int _hitIndex;                   //index for the interpreted info array, taken by converter class to write it in one chunk
  HitInfo* _hitInfo;                        //holds the actual interpreted hits

  unsigned int tHitBufferIndex;             //index for the buffer hit info array
  HitInfo* _hitBuffer;                      //holds the actual interpreted hits of one event, needed to be able to set event error codes subsequently

  //config variables
  unsigned int _NbCID; 											//number of BCIDs for one trigger
  unsigned int _maxTot; 									  //maximum Tot value considered to be a hit
  bool _fEI4B;														  //set to true to distinguish between FE-I4B and FE-I4A
  bool _debugEvents;                        //true if some events have to have debug output
  unsigned long _startDebugEvent;           //start event number to have debug output
  unsigned long _stopDebugEvent;            //stop event number to have debug output

  //one event variables
  unsigned int tNdataHeader;								//number of data header per event
	unsigned int tNdataRecord;								//number of data records per event
	unsigned int tStartBCID;									//BCID value of the first hit for the event window
	unsigned int tStartLVL1ID;								//LVL1ID value of the first data header of the event window
	unsigned int tDbCID;											//relative BCID of on event window [0:15], counter
  unsigned char tTriggerError;						  //event trigger error code
  unsigned char tErrorCode;						      //event error code
  unsigned int tServiceRecord;						  //event service records
  unsigned int tTriggerNumber;              //event trigger number
  unsigned int tTotalHits;                  //event hits
	bool tLVL1IDisConst;											//is only true if a trigger is send externally, self trigger can have different LVL1IDs in one event
	bool tBCIDerror;										      //set to true if event data is incomplete to omit the actual event for clustering
  unsigned int tTriggerWord;								//count the trigger words per event
  unsigned int _lastTriggerNumber;          //trigger number of last event

  //counters/flags for the total raw data processing
	unsigned long _nTriggers;								  //total number of trigger words found
	unsigned long _nEvents;									  //total number of valid events counted
	unsigned long _nMaxHitsPerEvent;					//number of the maximum hits per event
  unsigned long _nEmptyEvents;				  		//number of events with no records
	unsigned long _nIncompleteEvents;				  //number of events with incomplete data structure (# data header != _NbCID)
  unsigned long _nUnknownWords;						  //number of unknowns words found
  unsigned long _nServiceRecords;						//total number of service records found
	unsigned long _nDataRecords;							//total number of data records found
  unsigned long _nDataHeaders;							//total number of data headers found
  unsigned long _nHits;							        //total number of hits found
  unsigned long _nDataWords;							  //total number of data words
  bool _firstTriggerNrSet;                  //true if the first trigger was found
 
  //meta data infos in/out
  MetaInfo* _metaInfo;                      //pointer to the meta info, meta data infos in
  bool _metaDataSet;                        //true if meta data is available
  unsigned long _lastMetaIndexNotSet;       //the last meta index that is not set
  unsigned long _lastWordIndexSet;          //the last word index used for the event calculation
  unsigned long* _metaEventIndex;           //pointer to the array that holds the event number for every read out (meta_data row), meta data infos out
  unsigned int _metaEventIndexLength;       //length of event number array

  //counter histograms
  unsigned long* _triggerErrorCounter;      //trigger error histogram
  unsigned long* _errorCounter;             //error code histogram
  unsigned long* _serviceRecordCounter;     //SR histogram
};

