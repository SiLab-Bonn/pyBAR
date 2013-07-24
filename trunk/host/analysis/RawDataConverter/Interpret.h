#pragma once

#include <iostream>
#include <string>
#include <ctime>
#include <cmath>

#include "Basis.h"
#include "defines.h"

#define __DEBUG false
#define __DEBUG2 false

class Interpret: public Basis
{
public:
  Interpret(void);
  ~Interpret(void);

  //main functions
  bool interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords);       //starts to interpret the actual raw data pDataWords and saves result to _hitInfo
  bool setMetaWordIndex(const unsigned int& tLength, MetaInfo* &rMetaInfo);               //sets the meta word index for word number/readout info correlation
  void getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned long*& rEventNumber);  //returns the meta event index filled upto the actual interpreted hits
  void getHits(const unsigned int& pFEindex, unsigned int &rNhits, HitInfo* &rHitInfo);   //returns the actual interpreted hits

  //initializers, should be called before first call of interpretRawData() with new data file
  void resetCounters();                                     //reset summary counters

  //options set/get
  void setNbCIDs(const unsigned int& NbCIDs, const unsigned int& pFEindex);  //set the number of BCIDs with hits for the actual trigger
  void setMaxTot(const unsigned int& rMaxTot, const unsigned int& pFEindex); //sets the maximum tot code that is considered to be a hit
  void setFEI4B(bool pIsFEI4B, const unsigned int& pFEindex);         //set the FE flavor to be able to read the raw data correctly
  bool getFEI4B(const unsigned int pFEindex = 0); //returns the FE flavor set
  unsigned int getNfe();                       //returns the total number of FEs analyzed

  //get function to global counters
  void getServiceRecordsCounters(const unsigned int& pFEindex, unsigned int &rNserviceRecords, unsigned long*& rServiceRecordsCounter);   //returns the total service record counter array
  void getErrorCounters(const unsigned int& pFEindex, unsigned int &rNerrorCounters, unsigned long*& rErrorCounter);                      //returns the total errors counter array
  void getTriggerErrorCounters(const unsigned int& pFEindex, unsigned int &rNTriggerErrorCounters, unsigned long*& rTriggerErrorCounter); //returns the total trigger errors counter array
  unsigned long getNwords();                                      //returns the total numbers of words analyzed (global counter)
  unsigned long getNunknownWords(){return _nUnknownWords;};       //returns the total numbers of unknown words found (global counter)
  unsigned long getNevents(const unsigned int& pFEindex){return _nEvents[pFEindex];};                   //returns the total numbers of events analyzed (global counter)
  unsigned long getNemptyEvents(const unsigned int& pFEindex){return _nEmptyEvents[pFEindex];};         //returns the total numbers of empty events found (global counter)
  unsigned long getNtriggers(){return _nTriggers;};               //returns the total numbers of trigger found (global counter)
  unsigned long getNhits(const unsigned int& pFEindex){return _nHits[pFEindex];};                       //returns the total numbers of hits found (global counter)
  unsigned long getNtriggerNotInc(const unsigned int& pNfE){return _triggerErrorCounter[pNfE][1];}; //returns the total numbers of not increasing trigger (error histogram)
  unsigned long getNtriggerNotOne(const unsigned int& pNfE){return _errorCounter[pNfE][1]+_triggerErrorCounter[pNfE][2];}; //returns the total numbers of events with # trigger != 1 (from error histogram)
  unsigned int getFeIndex(const unsigned int& pNfE);

  //print functions for info output
  void printSummary();                                                        //print the interpreter summary with all global counter values (#hits, #data records,...)
  void printHits(const unsigned int& pFEindex, const unsigned int& pNhits = 100); //prints the hits stored in the array
  void debugEvents(const unsigned long& rStartEvent = 0, const unsigned long& rStopEvent = 0, const bool& debugEvents = true); //activates the debug mode for selected events
  void printOptions();  //prints the standard options and the options for each FE

  void printInterpretedWords(unsigned int* pDataWords, const unsigned int& rNsramWords, const unsigned int& rStartWordIndex, const unsigned int& rEndWordIndex);


private:
  void addHit(const unsigned int& pNfE, const unsigned char& pRelBCID, const unsigned short int& pLVLID, const unsigned char& pColumn, const unsigned short int& pRow, const unsigned char& pTot, const unsigned short int& pBCID); //adds the hit to the event hits array _hitBuffer
  void storeHit(const unsigned int& pNfE, HitInfo& rHit);	//stores the hit into the output hit array _hitInfo
  void addEvent(const unsigned int& pNfE);                //increases the event counter, adds the actual hits/error/SR codes
  void storeEventHits(const unsigned int& pNfE);          //adds the hits of the actual event to _hitInfo
  void correlateMetaWordIndex(const unsigned long& pEventNumer, const unsigned long& pDataWordIndex);  //writes the event number for the meta data
  void resetEventVariables(const unsigned int& pFEindex);	//resets event variables before starting new event
  bool isNewFeIndex(const unsigned int& pFEindex);  //returns true if the Fe index is unknown
  void setOptionsNewFe(const unsigned int& pFEindex); //is called when a new FE is detected and sets the options to the std. values if they are not set already
  
  //SRAM word check and interpreting methods
  unsigned int getFeIndexFromWord(const unsigned int& pSRAMWORD); //returns the FE number of the actual word, std. value is 0
  bool getTimefromDataHeader(const unsigned int& pNfE, const unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID);	      //returns true if the SRAMword is a data header and if it is sets the BCID and LVL1
	bool getHitsfromDataRecord(const unsigned int& pNfE, const unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2);	//returns true if the SRAMword is a data record with reasonable hit infos and if it is sets pCol,pRow,pTot
	bool getInfoFromServiceRecord(const unsigned int& pSRAMWORD, unsigned int& pSRcode, unsigned int& pSRcount); 	//returns true if the SRAMword is a service record and sets pSRcode,pSRcount
  bool isTriggerWord(const unsigned int& pSRAMWORD);						  //returns true if data word is trigger word
	bool isOtherWord(const unsigned int& pSRAMWORD);							  //returns true if data word is an empty record, adress record, value record or service record

  //SR/error histogramming methods
  void histogramTriggerErrorCode(const unsigned int& pNfE);                                 //adds the event trigger error code to the histogram
  void histogramErrorCode(const unsigned int& pNfE);                                        //adds the event error code to the histogram
  void addTriggerErrorCode(const unsigned int& pNfE, const unsigned char& pErrorCode);      //adds the trigger error code to the existing error code
  void addEventErrorCode(const unsigned int& pNfE, const unsigned char& pErrorCode);        //adds the error code to the existing error code
  void addServiceRecord(const unsigned int& pNfE, const unsigned char& pSRcode);            //adds the service record code to SR histogram

  //memory allocation/initialization
  void allocateHitInfoArray(const unsigned int& pIfE); 
  void deleteHitInfoArray();
  void allocateHitBufferArray(const unsigned int& pIfE);
  void deleteHitBufferArray();

  void allocateMetaEventIndexArray();
  void deleteMetaEventIndexArray();

  void allocateTriggerErrorCounterArray(const unsigned int& pIfE);
  void resetTriggerErrorCounterArray(const unsigned int pIfE = 0); //reset to all entries = 0
  void deleteTriggerErrorCounterArray();
  void allocateErrorCounterArray(const unsigned int& pIfE);
  void resetErrorCounterArray(const unsigned int pIfE = 0); //reset to all entries = 0
  void deleteErrorCounterArray();
  void allocateServiceRecordCounterArray(const unsigned int& pIfE);
  void resetServiceRecordCounterArray(const unsigned int pIfE = 0); //reset to all entries = 0
  void deleteServiceRecordCounterArray();

  //helper function for debuging data words
  

  //arrays for interpreted information
  std::map<unsigned int, unsigned int> _hitIndex;                   //index for the interpreted info array, taken by converter class to write it in one chunk
  std::map<unsigned int, HitInfo*> _hitInfo;                        //holds the actual interpreted hits

  std::map<unsigned int, unsigned int> tHitBufferIndex;             //index for the buffer hit info array
  std::map<unsigned int, HitInfo*> _hitBuffer;                      //holds the actual interpreted hits of one event, needed to be able to set event error codes subsequently

  //config variables for each Fe
  std::map<unsigned int, unsigned int> _NbCID;  //number of BCIDs for one trigger
  std::map<unsigned int, unsigned int> _maxTot; //maximum Tot value considered to be a hit
  std::map<unsigned int, bool> _fEI4B;			    //set to true to distinguish between FE-I4B and FE-I4A

  //debug config variables
  bool _debugEvents;                        //true if some events have to have debug output
  unsigned long _startDebugEvent;           //start event number to have debug output
  unsigned long _stopDebugEvent;            //stop event number to have debug output

  //one event variables for each FE
  std::map<unsigned int, unsigned int> tNdataHeader;								//number of data header per event
	std::map<unsigned int, unsigned int> tNdataRecord;								//number of data records per event
	std::map<unsigned int, unsigned int> tStartBCID;									//BCID value of the first hit for the event window
	std::map<unsigned int, unsigned int> tStartLVL1ID;								//LVL1ID value of the first data header of the event window
	std::map<unsigned int, unsigned int> tDbCID;											//relative BCID of on event window [0:15], counter
  std::map<unsigned int, unsigned char> tTriggerError;						  //event trigger error code
  std::map<unsigned int, unsigned char> tErrorCode;						      //event error code
  std::map<unsigned int, unsigned int> tServiceRecord;						  //event service records
  std::map<unsigned int, unsigned int> tTriggerNumber;              //event trigger number
  std::map<unsigned int, unsigned int> tTotalHits;                  //event hits
	std::map<unsigned int, bool> tLVL1IDisConst;											//is only true if a trigger is send externally, self trigger can have different LVL1IDs in one event
	std::map<unsigned int, bool> tBCIDerror;										      //set to true if event data is incomplete to omit the actual event for clustering
  std::map<unsigned int, unsigned int> tTriggerWord;								//count the trigger words per event
  std::map<unsigned int, unsigned int> _lastTriggerNumber;          //trigger number of last event

  //counters/flags for the total raw data processing for each Fe
	std::map<unsigned int, unsigned long> _nEvents;									  //total number of valid events counted
	std::map<unsigned int, unsigned long> _nMaxHitsPerEvent;					//number of the maximum hits per event
  std::map<unsigned int, unsigned long> _nEmptyEvents;				  		//number of events with no records
	std::map<unsigned int, unsigned long> _nIncompleteEvents;				  //number of events with incomplete data structure (# data header != _NbCID)
  std::map<unsigned int, unsigned long> _nServiceRecords;						//total number of service records found
  std::map<unsigned int, unsigned long> _nDataRecords;							//total number of data records found
  std::map<unsigned int, unsigned long> _nDataHeaders;							//total number of data headers found
  std::map<unsigned int, unsigned long> _nHits;							        //total number of hits found

  //counters/flags for the total raw data processing
  unsigned long _nTriggers;								  //total number of trigger words found
  unsigned long _nUnknownWords;						  //number of unknowns words found
  unsigned long _nDataWords;							  //total number of data words
  bool _firstTriggerNrSet;                  //true if the first trigger was found
 
  //meta data infos in/out
  MetaInfo* _metaInfo;                      //pointer to the meta info, meta data infos in
  bool _metaDataSet;                        //true if meta data is available
  unsigned long _lastMetaIndexNotSet;       //the last meta index that is not set
  unsigned long _lastWordIndexSet;          //the last word index used for the event calculation
  unsigned long* _metaEventIndex;           //pointer to the array that holds the event number for every read out (meta_data row), meta data infos out
  unsigned int _metaEventIndexLength;       //length of event number array

  //counter histograms for each Fe
  std::map<unsigned int, unsigned long*> _triggerErrorCounter;      //trigger error histogram
  std::map<unsigned int, unsigned long*> _errorCounter;             //error code histogram
  std::map<unsigned int, unsigned long*> _serviceRecordCounter;     //SR histogram
};

