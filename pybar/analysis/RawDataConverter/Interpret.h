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
	bool interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords); //starts to interpret the actual raw data pDataWords and saves result to _hitInfo
	bool setMetaData(MetaInfo* &rMetaInfo, const unsigned int& tLength);         	  //sets the meta words for word number/event correlation
	bool setMetaDataV2(MetaInfoV2* &rMetaInfo, const unsigned int& tLength);       	  //sets the meta words for word number/event correlation
	void getHits(HitInfo*& rHitInfo, unsigned int& rSize, bool copy = false);    	  //returns the hit histogram

	//set arrays to be filled
	void setMetaDataEventIndex(uint64_t*& rEventNumber, const unsigned int& rSize);  //set the meta event index array to be filled
	void setMetaDataWordIndex(MetaWordInfoOut*& rWordNumber, const unsigned int& rSize);  //set the meta word index array to be filled

	//array info get functions
	unsigned int getNarrayHits(){return _hitIndex;};								  // the number of hits of the actual interpreted raw data
	unsigned int getNmetaDataEvent(){return _lastMetaIndexNotSet;};				  	  // the filled length of the array storing the event number per read out
	unsigned int getNmetaDataWord(){return _actualMetaWordIndex;};

	//initializers, should be called before first call of interpretRawData() with new data file
	void resetCounters();                                     						  //reset summary counters
	void resetEventVariables();											              //resets event variables before starting new event

	//analysis options
	void setHitsArraySize(const unsigned int &rSize);   			  //set the siye of the hit array, has to be able to hold hits of one event
	void createEmptyEventHits(bool CreateEmptyEventHits = true);  //create hits that are virtual hits (not real hits) for debugging, thus event no hit events will show up in the hit table
	void createMetaDataWordIndex(bool CreateMetaDataWordIndex = true);
	void setNbCIDs(const unsigned int& NbCIDs);				  //set the number of BCIDs with hits for the actual trigger
	void setMaxTot(const unsigned int& rMaxTot);			  //sets the maximum tot code that is considered to be a hit
	void setFEI4B(bool pIsFEI4B = true){_fEI4B = pIsFEI4B;};  //set the FE flavor to be able to read the raw data correctly
	bool getFEI4B(){return _fEI4B;};                          //returns the FE flavor set
	bool getMetaTableV2(){return _isMetaTableV2;};            //returns the MetaTable flavor (V1 or V2)
	void alignAtTriggerNumber(bool alignAtTriggerNumber = true);      //new events are created if trigger number occurs
	void alignAtTdcWord(bool alignAtTdcWord = true);      			  //new events are created if tdc word occurs and event structure of event before is complete
	void useTdcTriggerTimeStamp(bool useTdcTriggerTimeStamp = true);//true: tdc time stamp is the delay between trigger/TDC leading edge, False: time stamp counter
	void setMaxTdcDelay(const unsigned int& rMaxTdcDelay);			  //sets the maximum tdc delay, only tdc words with tdc delay values < rMaxTdcDelay will be considered as fitting tdc words, otherwise it is fully ignored
	void useTriggerTimeStamp(bool useTriggerTimeStamp = true);//trigger number is giving you a clock count and not a total count
	void setMaxTriggerNumber(const unsigned int& rMaxTriggerNumber);

	void addEvent();              //increases the event counter, adds the actual hits/error/SR codes

	//get function to global counters
	void getServiceRecordsCounters(unsigned int*& rServiceRecordsCounter, unsigned int &rNserviceRecords, bool copy = false);   //returns the total service record counter array
	void getErrorCounters(unsigned int*& rErrorCounter, unsigned int &rNerrorCounters, bool copy = false);                      //returns the total errors counter array
	void getTriggerErrorCounters(unsigned int*& rTriggerErrorCounter, unsigned int &rNTriggerErrorCounters, bool copy = false); //returns the total trigger errors counter array
	void getTdcCounters(unsigned int*& rTdcCounter, unsigned int& rNtdcCounters, bool copy = false); //returns the TDC counter array
	unsigned int getNhits(){return _nHits;};                 //returns the total numbers of hits found (global counter)
	unsigned int getNwords();                                //returns the total numbers of words analyzed (global counter)
	unsigned int getNunknownWords(){return _nUnknownWords;}; //returns the total numbers of unknown words found (global counter)
	uint64_t getNevents(){return _nEvents;};             	 //returns the total numbers of events analyzed (global counter)
	unsigned int getNemptyEvents(){return _nEmptyEvents;};   //returns the total numbers of empty events found (global counter)
	unsigned int getNtriggers(){return _nTriggers;};         //returns the total numbers of trigger found (global counter)
	unsigned int getNtriggerNotInc(){return _triggerErrorCounter[1];}; //returns the total numbers of not increasing trigger (error histogram)
	unsigned int getNtriggerNotOne(){return _errorCounter[1]+_triggerErrorCounter[2];}; //returns the total numbers of events with # trigger != 1 (from error histogram)

	//print functions for info output
	void printSummary();                                      //print the interpreter summary with all global counter values (#hits, #data records,...)
	void printStatus();                                       //print the interpreter options and counter values (#hits, #data records,...)
	void printHits(const unsigned int& pNhits = 100);		  //prints the hits stored in the array
	void debugEvents(const unsigned int& rStartEvent = 0, const unsigned int& rStopEvent = 0, const bool& debugEvents = true);

	void reset();											  //resets all data but keeps the settings
	void resetMetaDataCounter();							  //resets the meta data counter, is needed if meta data was combined from different files
	unsigned int getHitSize();								  //return the size of one hit entry in the hit array, needed to check data in memory alignment

private:
	void addHit(const unsigned char& pRelBCID, const unsigned short int& pLVLID, const unsigned char& pColumn, const unsigned short int& pRow, const unsigned char& pTot, const unsigned short int& pBCID); //adds the hit to the event hits array _hitBuffer
	void storeHit(HitInfo& rHit);	//stores the hit into the output hit array _hitInfo
	void storeEventHits();          //adds the hits of the actual event to _hitInfo
	void correlateMetaWordIndex(const uint64_t& pEventNumer, const unsigned int& pDataWordIndex);  //writes the event number for the meta data

	//SRAM word check and interpreting methods
	bool getTimefromDataHeader(const unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID);	      //returns true if the SRAMword is a data header and if it is sets the BCID and LVL1
	bool isDataRecord(const unsigned int& pSRAMWORD);               //returns true if data word is a data record (no col ,row ,tot limit checks done, only check for data record header)
	bool isTdcWord(const unsigned int& pSRAMWORD);					//returns true if the data word is a tdc count word
	bool getHitsfromDataRecord(const unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2);	//returns true if the SRAMword is a data record with reasonable hit infos and if it is sets pCol,pRow,pTot
	bool getInfoFromServiceRecord(const unsigned int& pSRAMWORD, unsigned int& pSRcode, unsigned int& pSRcount); 	//returns true if the SRAMword is a service record and sets pSRcode, pSRcount
	bool isTriggerWord(const unsigned int& pSRAMWORD);						  //returns true if data word is trigger word
	bool isAddressRecord(const unsigned int& pSRAMWORD, unsigned int& rAddress, bool& isShiftRegister); //returns true if data word is a adress record
	bool isValueRecord(const unsigned int& pSRAMWORD, unsigned int& rValue);    //returns true if data word is a value record
	bool isOtherWord(const unsigned int& pSRAMWORD);							  //returns true if data word is an empty record, adress record, value record or service record

	//SR/error histogramming methods
	void addTriggerErrorCode(const unsigned char& pErrorCode);                              //adds the trigger error code to the existing error code
	void addEventErrorCode(const unsigned short int& pErrorCode);                           //adds the error code to the existing error code
	void histogramTriggerErrorCode();                                                       //adds the event trigger error code to the histogram
	void histogramErrorCode();                                                              //adds the event error code to the histogram
	void addServiceRecord(const unsigned char& pSRcode, const unsigned int& pSRcounter);    //adds the service record code to SR histogram
	void addTdcValue(const unsigned short& pTdcCode);                           			//adds the TDC count code to TDC histogram

	//memory allocation/initialization
	void setStandardSettings();
	void allocateHitArray();
	void deleteHitArray();
	void allocateHitBufferArray();
	void deleteHitBufferArray();
	void allocateTriggerErrorCounterArray();
	void resetTriggerErrorCounterArray();
	void deleteTriggerErrorCounterArray();
	void allocateErrorCounterArray();
	void resetErrorCounterArray();
	void deleteErrorCounterArray();
	void allocateTdcCounterArray();
	void resetTdcCounterArray();
	void deleteTdcCounterArray();
	void allocateServiceRecordCounterArray();
	void resetServiceRecordCounterArray();
	void deleteServiceRecordCounterArray();

	//helper function for debuging data words
	void printInterpretedWords(unsigned int* pDataWords, const unsigned int& rNsramWords, const unsigned int& rStartWordIndex, const unsigned int& rEndWordIndex);

	//array variables for interpreted information
	unsigned int _hitInfoSize;				  //size of the _hitInfo array
	unsigned int _hitIndex;                   //max index of _hitInfo filled
	HitInfo* _hitInfo;                        //holds the actual interpreted hits

	//array variables for the hit events buffer
	unsigned int tHitBufferIndex;             //index for the buffer hit info array
	HitInfo* _hitBuffer;                      //holds the actual interpreted hits of one event, needed to be able to set event error codes subsequently

	//config variables
	unsigned int _NbCID; 						//number of BCIDs for one trigger
	unsigned int _maxTot; 						//maximum Tot value considered to be a hit
	unsigned int _maxTdcDelay;				    //maximum tdc delay value to use tdc word
	bool _fEI4B;								//set to true to distinguish between FE-I4B and FE-I4A
	bool _debugEvents;                          //true if some events have to have debug output
	unsigned int _startDebugEvent;              //start event number to have debug output
	unsigned int _stopDebugEvent;               //stop event number to have debug output
	bool _alignAtTriggerNumber;						//set to true to force event recognision by trigger number
	bool _alignAtTdcWord;							//set to true to force event recognision by tdc word if event before is complete
	bool _useTdcTriggerTimeStamp;				//set to true to use the TDC trigger distance to fill the TDC time stamp otherwise use counter
	bool _useTriggerTimeStamp;					//set to true to use the trigger value as a clock count
	unsigned int _maxTriggerNumber;       		//maximum trigger trigger number

	//one event variables
	unsigned int tNdataHeader;					//number of data header per event
	unsigned int tNdataRecord;					//number of data records per event
	unsigned int tStartBCID;					//BCID value of the first hit for the event window
	unsigned int tStartLVL1ID;					//LVL1ID value of the first data header of the event window
	unsigned int tDbCID;						//relative BCID of on event window [0:15], counter
	unsigned char tTriggerError;				//event trigger error code
	unsigned short tErrorCode;					//event error code
	unsigned int tServiceRecord;				//event service records
	unsigned int tEventTriggerNumber;           //event trigger number
	unsigned int tTotalHits;                    //event hits
	bool tLVL1IDisConst;					    //is only true if a trigger is send externally, self trigger can have different LVL1IDs in one event
	bool tBCIDerror;						    //set to true if event data is incomplete to omit the actual event for clustering
	unsigned int tTriggerWord;				    //count the trigger words per event
	unsigned int _lastTriggerNumber;            //trigger number of last event
	unsigned int _startWordIndex;				//the absolute word index of the first word of the actual event
	unsigned short tTdcCount;					//the TDC count value of the actual event, if no TDC word occured this value is zero
	unsigned char tTdcTimeStamp;				//the TDC count value of the actual event, if no TDC word occured this value is zero

	//counters/flags for the total raw data processing
	unsigned int _nTriggers;					//total number of trigger words found
	uint64_t _nEvents;							//total number of valid events counted
	unsigned int _nMaxHitsPerEvent;				//number of the maximum hits per event
	unsigned int _nEmptyEvents;				  	//number of events with no records
	unsigned int _nIncompleteEvents;			//number of events with incomplete data structure (# data header != _NbCID)
	unsigned int _nTDCWords;					//number of TDC words found
	unsigned int _nUnknownWords;				//number of unknowns words found
	unsigned int _nOtherWords;					//Address or value records
	unsigned int _nServiceRecords;				//total number of service records found
	unsigned int _nDataRecords;					//total number of data records found
	unsigned int _nDataHeaders;					//total number of data headers found
	unsigned int _nHits;						//total number of hits found
	unsigned int _nDataWords;					//total number of data words
	bool _firstTriggerNrSet;                    //true if the first trigger was found
	bool _firstTdcSet;                    		//true if the first tdc word was found

	//meta data infos in/out
	MetaInfo* _metaInfo;                      //pointer to the meta info, meta data infos in
	MetaInfoV2* _metaInfoV2;                  //pointer to the meta info V2, meta data infos in

	bool _metaDataSet;                        //true if meta data is available
	unsigned int _lastMetaIndexNotSet;        //the last meta index that is not set
	unsigned int _lastWordIndexSet;           //the last word index used for the event calculation
	uint64_t* _metaEventIndex;                //pointer to the array that holds the event number for every read out (meta_data row), meta data infos out
	unsigned int _metaEventIndexLength;       //length of event number array
	MetaWordInfoOut* _metaWordIndex;		  //pointer to the structure array that holds the start/stop word number for every event
	unsigned int _metaWordIndexLength;		  //length of the word number array
	unsigned int _actualMetaWordIndex;		  //counter for the actual meta word array index
	bool _createEmptyEventHits;				  //true if empty event virtual hits are created
	bool _createMetaDataWordIndex;			  //true if word index has to be set
	bool _isMetaTableV2;                      //set to true if using MetaInfoV2 table

	//counter histograms
	unsigned int* _triggerErrorCounter;      //trigger error histogram
	unsigned int* _errorCounter;             //error code histogram
	unsigned int* _tdcCounter;             	 //tdc counter value histogram
	unsigned int* _serviceRecordCounter;     //SR histogram

	//temporary variables set according to the actual SRAM word
	unsigned int tTriggerNumber;            //trigger number of actual trigger number word
	unsigned int tActualLVL1ID;				//LVL1ID of the actual data header
	unsigned int tActualBCID;				//BCID of the actual data header
	unsigned int tActualSRcode;				//Service record code of the actual service record
	unsigned int tActualSRcounter;			//Service record counter value of the actual service record

	//counter variables for the actual raw data file
	unsigned int _dataWordIndex;			//the word index of the actual raw data file, needed for event number calculation
};

