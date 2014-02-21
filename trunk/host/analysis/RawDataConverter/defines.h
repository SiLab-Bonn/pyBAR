#ifndef DEFINES_H
#define DEFINES_H

#pragma pack(1) //data struct in memory alignement

//structure to store the hits
typedef struct HitInfo{
  unsigned int eventNumber;  //event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
  unsigned int triggerNumber; //external trigger number for read out system
  unsigned char relativeBCID; //relative BCID value (unsigned char: 0 to 255)
  unsigned short int LVLID;   //LVL1ID (unsigned short int: 0 to 65.535)
  unsigned char column;       //column value (unsigned char: 0 to 255)
  unsigned short int row;     //row value (unsigned short int: 0 to 65.535)
  unsigned char tot;          //tot value (unsigned char: 0 to 255)
  unsigned short int BCID;    //absolute BCID value (unsigned short int: 0 to 65.535)
  unsigned short int TDC; 	  //the TDC count (12-bit value)
  unsigned char triggerStatus;//event service records
  unsigned int serviceRecord; //event service records
  unsigned short int eventStatus;  //event status value (unsigned short int: 0 to 65.535)
} HitInfo;

//structure to store the hits with cluster info
typedef struct ClusterHitInfo{
  unsigned int eventNumber;   //event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
  unsigned int triggerNumber; //external trigger number for read out system
  unsigned char relativeBCID; //relative BCID value (unsigned char: 0 to 255)
  unsigned short int LVLID;   //LVL1ID (unsigned short int: 0 to 65.535)
  unsigned char column;       //column value (unsigned char: 0 to 255)
  unsigned short int row;     //row value (unsigned short int: 0 to 65.535)
  unsigned char tot;          //tot value (unsigned char: 0 to 255)
  unsigned short int BCID;    //absolute BCID value (unsigned short int: 0 to 65.535)
  unsigned short int TDC; 	  //the TDC count (12-bit value)
  unsigned char triggerStatus;//event service records
  unsigned int serviceRecord; //event service records
  unsigned short int eventStatus;  //event status value (unsigned short int: 0 to 65.535)
  unsigned short clusterID;	  //the cluster id of the hit
  unsigned char isSeed;	  	  //flag to mark seed pixel
  unsigned short clusterSize; //the cluster size of the cluster belonging to the hit
  unsigned short nCluster;	  //the number of hits of the cluster belonging to the hit
} ClusterHitInfo;

//structure to store the cluster
typedef struct ClusterInfo{
  unsigned int eventNumber;  //event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
  unsigned short ID;	  	  //the cluster id of the cluster
  unsigned short size; 		  //sum tot of all cluster hits
  unsigned short Tot; 		  //sum tot of all cluster hits
  float charge; 		  	  //sum charge of all cluster hits
  unsigned char seed_column;  //column value (unsigned char: 0 to 255)
  unsigned short int seed_row;//row value (unsigned short int: 0 to 65.535)
  unsigned short int eventStatus;  //event status value (unsigned char: 0 to 255)
} ClusterInfo;

//structure for the input meta data
typedef struct MetaInfo{
  unsigned int startIndex;    //start index for this read out
  unsigned int stopIndex;     //stop index for this read out (exclusive!)
  unsigned int length;        //number of data word in this read out
  double timeStamp;           //time stamp of the readout
  unsigned int errorCode;     //error code for the read out (0: no error)
} MetaInfo;

//structure for the input meta data V2
typedef struct MetaInfoV2{
  unsigned int startIndex;    //start index for this read out
  unsigned int stopIndex;     //stop index for this read out (exclusive!)
  unsigned int length;        //number of data word in this read out
  double startTimeStamp;      //start time stamp of the readout
  double stopTimeStamp;       //stop time stamp of the readout
  unsigned int errorCode;     //error code for the read out (0: no error)
} MetaInfoV2;

//structures for the output meta data
typedef struct MetaInfoOut{
  unsigned int eventIndex;    //event number of the read out
  double timeStamp;           //time stamp of the readout
  unsigned int errorCode;     //error code for the read out (0: no error)
} MetaInfoOut;

typedef struct MetaWordInfoOut{
  unsigned int eventIndex;   //event number
  unsigned int startWordIdex;//start word index
  unsigned int stopWordIdex; //stop word index
} MetaWordInfoOut;

//structure to read the parameter information table
typedef struct ParInfo{
  unsigned int scanParameter;     //parameter setting
} ParInfo;

//DUT and TLU defines
#define __BCIDCOUNTERSIZE_FEI4A 256	  //BCID counter for FEI4A has 8 bit
#define __BCIDCOUNTERSIZE_FEI4B 1024  //BCID counter for FEI4B has 10 bit
#define __NSERVICERECORDS 32          //# of different service records
#define __MAXARRAYSIZE 2000000         //maximum buffer array size for the output hit array (has to be bigger than hits in one chunk)
#define __MAXHITBUFFERSIZE 4000000     //maximum buffer array size for the hit buffer array (has to be bigger than hits in one event)
#define __MAXTLUTRGNUMBER 32767       //maximum trigger logic unit trigger number (32-bit)

//event error codes
#define __N_ERROR_CODES 16            //number of event error codes
#define __NO_ERROR 0                  //no error
#define __HAS_SR 1                    //the event has service records
#define __NO_TRG_WORD 2               //the event has no trigger word, is ok for not external triggering
#define __NON_CONST_LVL1ID 4          //LVL1ID changes in one event, is ok for self triggering
#define __EVENT_INCOMPLETE 8          //BCID not increasing by 1, most likely BCID missing (incomplete data transmission)
#define __UNKNOWN_WORD 16             //event has unknown words
#define __BCID_JUMP 32                //BCID jumps, but either LVL1ID is constant or data is externally triggered with trigger word or TDC word
#define __TRG_ERROR 64                //a trigger error occured
#define __TRUNC_EVENT 128             //Event had to many hits (>__MAXHITBUFFERSIZE) and was therefore truncated
#define __TDC_WORD 256             	  //Event has a TDC word
#define __MANY_TDC_WORDS 512          //Event has more than one TDC word
#define __TDC_OVERFLOW 1024           //Event has TDC word indicating a TDC overflow

//trigger error codes
#define __TRG_N_ERROR_CODES 8         //number of trigger error codes
#define __TRG_NO_ERROR 0              //no trigger error
#define __TRG_NUMBER_INC_ERROR 1      //two consecutive triggern numbers are not increasing by exactly one (counter overflow case considered correctly)
#define __TRG_NUMBER_MORE_ONE 2       //more than one trigger per event
#define __TRG_ERROR_TRG_ACCEPT 4      //TLU error
#define __TRG_ERROR_LOW_TIMEOUT 8     //TLU error

//trigger word macros
#define TRIGGER_WORD_HEADER_MASK_NEW 0x80000000   //first bit 1 means trigger word
#define TRIGGER_NUMBER_MASK_NEW		0x0000FFFF      //trigger number is in the low word
#define TRIGGER_ERROR_TRG_ACCEPT		0x40000000    //trigger accept error
#define TRIGGER_ERROR_LOW_TIMEOUT		0x20000000    //TLU not deassert trigger signal
#define TRIGGER_WORD_MACRO_NEW(X)			(((TRIGGER_WORD_HEADER_MASK_NEW & X) == TRIGGER_WORD_HEADER_MASK_NEW) ? true : false) //true if data word is trigger word
#define TRIGGER_NUMBER_MACRO_NEW(X)	(TRIGGER_NUMBER_MASK_NEW & X)                                                           //calculates the trigger number from a trigger word

//FE number macros
#define NFE_HEADER_MASK 0xF0000000  //first bit 0 means FE number word
#define NFE_NUMBER_MASK 0x0F000000
#define NFE_WORD_MACRO(X) (((NFE_HEADER_MASK & X) == 0) ? true : false)
#define NFE_NUMBER_MACRO(X) ((NFE_NUMBER_MASK & X)  >> 24)

//TDC macros
#define __N_TDC_VALUES 4096
#define TDC_HEADER 0x40000000
#define TDC_HEADER_MASK 0xF0000000  //first bit 0 means FE number word
#define TDC_COUNT_MASK 0x00000FFF
#define TDC_WORD_MACRO(X) (((TDC_HEADER_MASK & X) == TDC_HEADER) ? true : false)
#define TDC_COUNT_MACRO(X) (TDC_COUNT_MASK & X)

// Data Header (DH)
#define DATA_HEADER						0x00E90000
#define DATA_HEADER_MASK				0xF0FF0000
#define DATA_HEADER_FLAG_MASK			0x00008000
#define DATA_HEADER_LV1ID_MASK			0x00007F00
#define DATA_HEADER_LV1ID_MASK_FEI4B	0x00007C00	// data format changed in fE-I4B. Upper LV1IDs comming in seperate SR.
#define DATA_HEADER_BCID_MASK			0x000000FF
#define DATA_HEADER_BCID_MASK_FEI4B		0x000003FF  // data format changed in FE-I4B due to increased counter size, See DATA_HEADER_LV1ID_MASK_FEI4B also.

#define DATA_HEADER_MACRO(X)			((DATA_HEADER_MASK & X) == DATA_HEADER ? true : false)
#define DATA_HEADER_FLAG_MACRO(X)		((DATA_HEADER_FLAG_MASK & X) >> 15)
#define DATA_HEADER_FLAG_SET_MACRO(X)	((DATA_HEADER_FLAG_MASK & X) == DATA_HEADER_FLAG_MASK ? true : false)
#define DATA_HEADER_LV1ID_MACRO(X)		((DATA_HEADER_LV1ID_MASK & X) >> 8)
#define DATA_HEADER_LV1ID_MACRO_FEI4B(X)		((DATA_HEADER_LV1ID_MASK_FEI4B & X) >> 10) // data format changed in fE-I4B. Upper LV1IDs comming in seperate SR.
#define DATA_HEADER_BCID_MACRO(X)		(DATA_HEADER_BCID_MASK & X)
#define DATA_HEADER_BCID_MACRO_FEI4B(X)		(DATA_HEADER_BCID_MASK_FEI4B & X) // data format changed in FE-I4B due to increased counter size, See DATA_HEADER_LV1ID_MASK_FEI4B also.

// Data Record (DR)
#define DATA_RECORD						0x00000000
#define DATA_RECORD_MASK				0xF0000000
#define DATA_RECORD_COLUMN_MASK			0x00FE0000
#define DATA_RECORD_ROW_MASK			0x0001FF00
#define DATA_RECORD_TOT1_MASK			0x000000F0
#define DATA_RECORD_TOT2_MASK			0x0000000F

#define RAW_DATA_MIN_COLUMN				0x00000001 // 1
#define RAW_DATA_MAX_COLUMN				0x00000050 // 80
#define RAW_DATA_MIN_ROW				0x00000001 // 1
#define RAW_DATA_MAX_ROW				0x00000150 // 336
#define DATA_RECORD_MIN_COLUMN			(RAW_DATA_MIN_COLUMN << 17)
#define DATA_RECORD_MAX_COLUMN			(RAW_DATA_MAX_COLUMN << 17)
#define DATA_RECORD_MIN_ROW				(RAW_DATA_MIN_ROW << 8)
#define DATA_RECORD_MAX_ROW				(RAW_DATA_MAX_ROW << 8)

#define DATA_RECORD_MACRO(X)			(((DATA_RECORD_COLUMN_MASK & X) <= DATA_RECORD_MAX_COLUMN) && ((DATA_RECORD_COLUMN_MASK & X) >= DATA_RECORD_MIN_COLUMN) && ((DATA_RECORD_ROW_MASK & X) <= DATA_RECORD_MAX_ROW) && ((DATA_RECORD_ROW_MASK & X) >= DATA_RECORD_MIN_ROW) && ((DATA_RECORD_MASK & X) == DATA_RECORD) ? true : false)
#define DATA_RECORD_COLUMN1_MACRO(X)	((DATA_RECORD_COLUMN_MASK & X) >> 17)
#define DATA_RECORD_ROW1_MACRO(X)		((DATA_RECORD_ROW_MASK & X) >> 8)
#define DATA_RECORD_TOT1_MACRO(X)		((DATA_RECORD_TOT1_MASK & X) >> 4)
#define DATA_RECORD_COLUMN2_MACRO(X)	((DATA_RECORD_COLUMN_MASK & X) >> 17)
#define DATA_RECORD_ROW2_MACRO(X)		(((DATA_RECORD_ROW_MASK & X) >> 8) + 1)
#define DATA_RECORD_TOT2_MACRO(X)		(DATA_RECORD_TOT2_MASK & X)

// Address Record (AR)
#define ADDRESS_RECORD					0x00EA0000
#define ADDRESS_RECORD_MASK				0x00FF0000
#define ADDRESS_RECORD_TYPE_MASK		0x00008000
#define ADDRESS_RECORD_ADDRESS_MASK		0x00007FFF

#define ADDRESS_RECORD_MACRO(X)			((ADDRESS_RECORD_MASK & X) == ADDRESS_RECORD ? true : false)
#define ADDRESS_RECORD_TYPE_MACRO(X)	((ADDRESS_RECORD_TYPE_MASK & X) >> 15)
#define ADDRESS_RECORD_TYPE_SET_MACRO(X)((ADDRESS_RECORD_TYPE_MASK & X) == ADDRESS_RECORD_TYPE_MASK ? true : false)
#define ADDRESS_RECORD_ADDRESS_MACRO(X)	(ADDRESS_RECORD_ADDRESS_MASK & X)

// Value Record (VR)
#define VALUE_RECORD					0x00EC0000
#define VALUE_RECORD_MASK				0x00FF0000
#define VALUE_RECORD_VALUE_MASK			0x0000FFFF

#define VALUE_RECORD_MACRO(X)			((VALUE_RECORD_MASK & X) == VALUE_RECORD ? true : false)
#define VALUE_RECORD_VALUE_MACRO(X)		(VALUE_RECORD_VALUE_MASK & X)

// Service Record (SR)
#define SERVICE_RECORD					0x00EF0000
#define SERVICE_RECORD_MASK				0x00FF0000
#define SERVICE_RECORD_CODE_MASK		0x0000FC00
#define SERVICE_RECORD_COUNTER_MASK		0x000003FF

#define SERVICE_RECORD_MACRO(X)			((SERVICE_RECORD_MASK & X) == SERVICE_RECORD ? true : false)
#define SERVICE_RECORD_CODE_MACRO(X)	((SERVICE_RECORD_CODE_MASK & X) >> 10)
#define SERVICE_RECORD_COUNTER_MACRO(X)	(SERVICE_RECORD_COUNTER_MASK & X)

//FEI4B: SR 14
#define SERVICE_RECORD_LV1ID_MASK_FEI4B	0x000003F8
#define SERVICE_RECORD_BCID_MASK_FEI4B	0x00000007
#define SERVICE_RECORD_LV1ID_MACRO_FEI4B(X)	((SERVICE_RECORD_LV1ID_MASK_FEI4B & X) >> 3)
#define SERVICE_RECORD_BCID_MACRO_FEI4B(X)	(SERVICE_RECORD_BCID_MASK_FEI4B & X)
//FEI4B: SR 16
#define SERVICE_RECORD_TF_MASK_FEI4B	0x00000200
#define SERVICE_RECORD_ETC_MASK_FEI4B	0x000001F0
#define SERVICE_RECORD_L1REQ_MASK_FEI4B	0x0000000F
#define SERVICE_RECORD_TF_MACRO_FEI4B(X)	((SERVICE_RECORD_TF_MASK_FEI4B & X) >> 9)
#define SERVICE_RECORD_ETC_MACRO_FEI4B(X)	((SERVICE_RECORD_ETC_MASK_FEI4B & X) >> 4)
#define SERVICE_RECORD_L1REQ_MACRO_FEI4B(X)	(SERVICE_RECORD_L1REQ_MASK_FEI4B & X)

//Clusterizer definitions
#define __MAXBCID 16			//maximum possible BCID window width
#define __MAXTOTBINS 128		//number of TOT bins for the cluster tot histogram (in TOT = [0:31])
#define __MAXCHARGEBINS 4096	//number of charge bins for the cluster charge histogram (in PlsrDAC)
#define __MAXCLUSTERHITSBINS 1024	//number of for the cluster size (=# hits) histogram
#define __MAXPOSXBINS 1000		//number of bins in x for the 2d hit position histogram
#define __MAXPOSYBINS 1000		//number of bins in y for the 2d hit position histogram
#define __PIXELSIZEX 250		//250 um
#define __PIXELSIZEY 50			//50 um

#define __MAXTOTLOOKUP 14

#endif // DEFINES_H
