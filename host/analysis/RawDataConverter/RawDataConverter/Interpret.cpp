#include "StdAfx.h"
#include "Interpret.h"


Interpret::Interpret(void)
{
  _NbCID = 16;
  _fEI4B = false;
  _metaDataSet = false;
  _lastMetaIndexNotSet = 0;
  _lastWordIndexSet = 0;
  _metaEventIndexLength = 0;
  resetCounters();
}


Interpret::~Interpret(void)
{
  delete[] _metaEventIndex;
}

//bool Interpret::interpretRawData(unsigned int* pDataWords, int pNdataWords)
//{
//	std::cout<<"Interpret::interpretRawData with "<<pNdataWords<<" words\n";
//
//	_nInvalidEvents = 0;
//	_nIncompleteEvents = 0;
//
//	//start in defined condition
//	resetEventVariables();
//
//	//temporary variables set according to the actual SRAM word
//	unsigned int tActualLVL1ID = 0;							//LVL1ID of the actual data header
//	unsigned int tActualBCID = 0;								//BCID of the actual data header
//	int tActualCol1 = 0;												//column position of the first hit in the actual data record
//	int tActualRow1 = 0;												//row position of the first hit in the actual data record
//	int tActualTot1 = -1;												//tot value of the first hit in the actual data record
//	int tActualCol2 = 0;												//column position of the second hit in the actual data record
//	int tActualRow2 = 0;												//row position of the second hit in the actual data record
//	int tActualTot2 = -1;												//tot value of the second hit in the actual data record
//
//  //pNdataWords = 200;
//
//	for (int iWord = 0; iWord < pNdataWords; ++iWord){			//loop over the SRAM words
//		unsigned int tActualWord = pDataWords[iWord];					//take the actual SRAM word
//		tActualTot1 = -1;												//TOT1 value stays negative if it can not be set properly in getHitsfromDataRecord()
//		tActualTot2 = -1;												//TOT2 value stays negative if it can not be set properly in getHitsfromDataRecord()
//		if (getTimefromDataHeader(tActualWord, tActualLVL1ID, tActualBCID)){	//data word is data header if true is returned
//			if (tNdataHeader > _NbCID-1){	//maximum event window is reached (tNdataHeader > BCIDs, mostly tNdataHeader > 15) and no trigger word occurred --> FE self trigger scan, so cluster data now
//				if(!tValidTriggerData)
//					_nInvalidEvents++;
//				_nEvents++;
//				resetEventVariables();
//			}
//			if (tNdataHeader == 0){								//set the BCID of the first data header
//				tStartBCID = tActualBCID;
//				tStartLVL1ID = tActualLVL1ID;
//			}
//			else{
//				tDbCID++;										//increase relative BCID counter [0:15]
//				if(_fEI4B){
//					if(tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4B-1)	//BCID counter overflow for FEI4B (10 bit BCID counter)
//						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4B;
//				}
//				else{
//					if(tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4A-1)	//BCID counter overflow for FEI4A (8 bit BCID counter)
//						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4A;
//				}
//				if (tStartBCID+tDbCID != tActualBCID) 			//check if BCID is increasing in the event window
//					tIncompleteEvent = true;					//BCID not increasing, abort event and take actual data header for the first hit of the new event
//				if (tActualLVL1ID != tStartLVL1ID)
//					tLVL1IDisConst = false;
//			}
//			std::cout<<iWord<<" DH LVL1ID/BCID "<<tActualLVL1ID<<"/"<<tActualBCID<<"\n";
//			tNdataHeader++;										//increase data header counter
//		}
//		else if (getHitsfromDataRecord(tActualWord, tActualCol1, tActualRow1, tActualTot1, tActualCol2, tActualRow2, tActualTot2)){	//data word is data record if true is returned
//			tNdataRecord++;										//increase data record counter
//			_nDataRecords++;									//increase total data record counter
//			if(tActualTot1 >= 0)								//add hit if hit info is reasonable (TOT1 >= 0)
//				addHit(_nEvents, tDbCID, tActualLVL1ID, tActualCol1, tActualRow1, tActualTot1, tActualBCID, 0);
//			if(tActualTot2 >= 0)								//add hit if hit info is reasonable and set (TOT2 >= 0)
//				addHit(_nEvents, tDbCID, tActualLVL1ID, tActualCol2, tActualRow2, tActualTot2, tActualBCID, 0);
//			//std::cout<<" DR COL1/ROW1/TOT1  COL2/ROW2/TOT2 "<<tActualCol1<<"/"<<tActualRow1<<"/"<<tActualTot1<<"  "<<tActualCol2<<"/"<<tActualRow2<<"/"<<tActualTot2<<" rBCID "<<tDbCID<<"\n";
//		}
//		else if (isTriggerWord(tActualWord)){					//data word is trigger word, is last word of the event data if external trigger is present, cluster data
//			_nTriggers++;										//increase the trigger word counter
//			int tTriggerNumber = TRIGGER_NUMBER_MACRO2(tActualWord, pDataWords[++iWord]);//actual trigger number
//			std::cout<<"Interpret::clusterRawData: TRIGGER "<<tTriggerNumber<<std::endl;
//			if(tTriggerNumber == _nTriggers && tValidTriggerData && tNdataHeader == _NbCID && tLVL1IDisConst){	//sanity check, only cluster good event data
//					_nEvents++;
//			}
//			else{
//				_nTriggers = tTriggerNumber;
//				_nInvalidEvents++;
//			}
//			resetEventVariables();
//		}
//		else{
//			if (!isOtherWord(tActualWord)){						//other for clustering uninteressting data, else data word unknown
//				tValidTriggerData = false;
//				std::cout<<"Interpret::clusterRawData: UNKNOWN WORD "<<tActualWord<<" AT "<<iWord<<"\n";
//			}
//		}
//
//		if (tIncompleteEvent){	//tIncompleteEvent is raised if BCID is not increasing by 1, most likely due to incomplete data transmission, so start new event, actual word is data header here
//			std::cout<<"INCOMPLETE EVENT DATA STRUCTURE\n";
//      std::cout<<"!!!! "<<_fEI4B<<"\n";
//			if (tNdataHeader > 2 || _NbCID < 2)
//				_nIncompleteEvents++;
//			getTimefromDataHeader(tActualWord, tActualLVL1ID, tStartBCID);
//			resetEventVariables();
//			tNdataHeader = 1;									//tNdataHeader is already 1, because actual word is first data of new event
//			tStartBCID = tActualBCID;
//			tStartLVL1ID = tActualLVL1ID;
//		}
//	}
//	return true;
//}

bool Interpret::interpretRawData(unsigned int* pDataWords, int pNdataWords)
{
	//std::cout<<"Interpret::interpretRawData with "<<pNdataWords<<" words\n";
  _hitIndex = 0;

	//temporary variables set according to the actual SRAM word
	unsigned int tActualLVL1ID = 0;							//LVL1ID of the actual data header
	unsigned int tActualBCID = 0;								//BCID of the actual data header
	int tActualCol1 = 0;												//column position of the first hit in the actual data record
	int tActualRow1 = 0;												//row position of the first hit in the actual data record
	int tActualTot1 = -1;												//tot value of the first hit in the actual data record
	int tActualCol2 = 0;												//column position of the second hit in the actual data record
	int tActualRow2 = 0;												//row position of the second hit in the actual data record
	int tActualTot2 = -1;												//tot value of the second hit in the actual data record

	for (int iWord = 0; iWord < pNdataWords; ++iWord){			//loop over the SRAM words
    correlateMetaWordIndex(_nEvents, _nDataWords);
    _nDataWords++;
		unsigned int tActualWord = pDataWords[iWord];					      //take the actual SRAM word
		tActualTot1 = -1;												//TOT1 value stays negative if it can not be set properly in getHitsfromDataRecord()
		tActualTot2 = -1;												//TOT2 value stays negative if it can not be set properly in getHitsfromDataRecord()
		if (getTimefromDataHeader(tActualWord, tActualLVL1ID, tActualBCID)){	//data word is data header if true is returned
			_nDataHeaders++;
      if (tNdataHeader > _NbCID-1){	//maximum event window is reached (tNdataHeader > BCIDs, mostly tNdataHeader > 15), so create new event
        _nEvents++;
        if(tNdataRecord==0)
          _nEmptyEvents++;
				resetEventVariables();
			}
			if (tNdataHeader == 0){								//set the BCID of the first data header
				tStartBCID = tActualBCID;
				tStartLVL1ID = tActualLVL1ID;
			}
			else{
				tDbCID++;										//increase relative BCID counter [0:15]
				if(_fEI4B){
					if(tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4B-1)	//BCID counter overflow for FEI4B (10 bit BCID counter)
						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4B;
				}
				else{
					if(tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4A-1)	//BCID counter overflow for FEI4A (8 bit BCID counter)
						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4A;
				}
				if (tStartBCID+tDbCID != tActualBCID) 			//check if BCID is increasing in the event window
					tIncompleteEvent = true;					//BCID not increasing, abort event and take actual data header for the first hit of the new event
				if (tActualLVL1ID != tStartLVL1ID)
					tLVL1IDisConst = false;
			}
			//std::cout<<iWord<<" DH LVL1ID/BCID "<<tActualLVL1ID<<"/"<<tActualBCID<<"\n";
			tNdataHeader++;										//increase data header counter
		}
		else if (getHitsfromDataRecord(tActualWord, tActualCol1, tActualRow1, tActualTot1, tActualCol2, tActualRow2, tActualTot2)){	//data word is data record if true is returned
			tNdataRecord++;										//increase data record counter for this event
			_nDataRecords++;									//increase total data record counter
			if(tActualTot1 >= 0)								//add hit if hit info is reasonable (TOT1 >= 0)
				addHit(_nEvents, tDbCID, tActualLVL1ID, tActualCol1, tActualRow1, tActualTot1, tActualBCID, 0);
			if(tActualTot2 >= 0)								//add hit if hit info is reasonable and set (TOT2 >= 0)
				addHit(_nEvents, tDbCID, tActualLVL1ID, tActualCol2, tActualRow2, tActualTot2, tActualBCID, 0);
			//std::cout<<iWord<<" DR COL1/ROW1/TOT1  COL2/ROW2/TOT2 "<<tActualCol1<<"/"<<tActualRow1<<"/"<<tActualTot1<<"  "<<tActualCol2<<"/"<<tActualRow2<<"/"<<tActualTot2<<" rBCID "<<tDbCID<<"\n";
		}
    else if (isTriggerWord(tActualWord)){					//data word is trigger word, is last word of the event data if external trigger is present, cluster data
			_nTriggers++;										//increase the trigger word counter
			int tTriggerNumber = TRIGGER_NUMBER_MACRO2(tActualWord, pDataWords[++iWord]);//actual trigger number
			//std::cout<<"Interpret:: TRIGGER "<<tTriggerNumber<<std::endl;
			if(tTriggerNumber == _nTriggers && tValidTriggerData && tNdataHeader == _NbCID && tLVL1IDisConst){	//sanity check, only cluster good event data
					_nEvents++;
			}
			else{
				_nTriggers = tTriggerNumber;
				_nInvalidEvents++;
			}
			resetEventVariables();
		}
		else{
			if (!isOtherWord(tActualWord)){						//other for hit interpreting uninteressting data, else data word unknown
				tValidTriggerData = false;
        _nUnknownWords++;
				std::cout<<"Interpret:: UNKNOWN WORD "<<tActualWord<<" AT "<<_nDataWords<<"\n";
			}
		}

		if (tIncompleteEvent){	//tIncompleteEvent is raised if BCID is not increasing by 1, most likely due to incomplete data transmission, so start new event, actual word is data header here
      //std::cout<<"INCOMPLETE EVENT DATA STRUCTURE "<<iWord<<"\n";
      //for(int index = iWord-10; index < iWord +250; ++index){
      //  unsigned int ttLVL1 = 0;
      //  unsigned int tBCID = 0;
      //  int ttcol = 0;
      //  int ttrow = 0;
      //  int tttot = 0;
      //  int ttcol2 = 0;
      //  int ttrow2 = 0;
      //  int tttot2 = 0;
      //  if(getTimefromDataHeader(pDataWords[index], ttLVL1, tBCID))
      //    std::cout<<" "<<tBCID<<" "<<ttLVL1<<"\t";
      //  if(getHitsfromDataRecord(pDataWords[index],ttcol, ttrow, tttot,ttcol2, ttrow2, tttot2))
      //    std::cout<<"     "<<ttcol<<" "<<ttrow<<" "<<tttot<<" "<<ttcol2<<" "<<ttrow2<<"  "<<tttot2<<"\t";
      //  std::cout<<index<<"\n";
      //}
      //return false;
			if (tNdataHeader > 2 || _NbCID < 2)
				_nIncompleteEvents++;
			getTimefromDataHeader(tActualWord, tActualLVL1ID, tStartBCID);
			resetEventVariables();
			tNdataHeader = 1;									//tNdataHeader is already 1, because actual word is first data of new event
			tStartBCID = tActualBCID;
			tStartLVL1ID = tActualLVL1ID;
		}
	}
	  return true;
}


void Interpret::resetEventVariables()
{
	tNdataHeader = 0;
	tNdataRecord = 0;
	tDbCID = 0;
	tValidTriggerData = true;
	tIncompleteEvent = false;
	tLVL1IDisConst = true;
}

bool Interpret::getTimefromDataHeader(unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID)
{
	if (DATA_HEADER_MACRO(pSRAMWORD)){
		if (_fEI4B){
			pLVL1ID = DATA_HEADER_LV1ID_MACRO_FEI4B(pSRAMWORD);
			pBCID = DATA_HEADER_BCID_MACRO_FEI4B(pSRAMWORD);
		}
		else{
			pLVL1ID = DATA_HEADER_LV1ID_MACRO(pSRAMWORD);
			pBCID = DATA_HEADER_BCID_MACRO(pSRAMWORD);
		}
		return true;
	}
	return false;
}

bool Interpret::getHitsfromDataRecord(unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2)
{
	if (DATA_RECORD_MACRO(pSRAMWORD)){	//SRAM word is data record
		//check if the hit values are reasonable
		if ((DATA_RECORD_TOT1_MACRO(pSRAMWORD) == 0xF) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW)
				&& (DATA_RECORD_TOT2_MACRO(pSRAMWORD) != 0xF) && ((DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW))){
				std::cout<<"Interpret::getHitsfromDataRecord: ERROR data record values out of bounds"<<std::endl;
			return false;
		}

		//set first hit values
		if (DATA_RECORD_TOT1_MACRO(pSRAMWORD) <= __MAXTOTUSED){	//ommit late/small hit and no hit TOT values for the TOT(1) hit
			pColHit1 = DATA_RECORD_COLUMN1_MACRO(pSRAMWORD);
			pRowHit1 = DATA_RECORD_ROW1_MACRO(pSRAMWORD);
			pTotHit1 = DATA_RECORD_TOT1_MACRO(pSRAMWORD);
		}

		//set second hit values
		if (DATA_RECORD_TOT2_MACRO(pSRAMWORD) <= __MAXTOTUSED){	//ommit late/small hit and no hit (15) tot values for the TOT(2) hit
			pColHit2 = DATA_RECORD_COLUMN2_MACRO(pSRAMWORD);
			pRowHit2 = DATA_RECORD_ROW2_MACRO(pSRAMWORD);
			pTotHit2 = DATA_RECORD_TOT2_MACRO(pSRAMWORD);
		}
		return true;
	}
	return false;
}

bool Interpret::isTriggerWord(unsigned int& pSRAMWORD)
{
	if (TRIGGER_WORD_MACRO(pSRAMWORD))	//data word is trigger word
		return true;
	return false;
}

bool Interpret::isOtherWord(unsigned int& pSRAMWORD)
{
	if (EMPTY_RECORD_MACRO(pSRAMWORD) || ADDRESS_RECORD_MACRO(pSRAMWORD) || VALUE_RECORD_MACRO(pSRAMWORD) || SERVICE_RECORD_MACRO(pSRAMWORD))
		return true;
	return false;
}

void Interpret::setNbCIDs(int NbCIDs)
{
	_NbCID = NbCIDs;
}

void Interpret::addHit(unsigned long pEventNumber, unsigned char pRelBCID, unsigned short int pLVLID, unsigned char pColumn, unsigned short int pRow, unsigned char pTot, unsigned short int pBCID, unsigned char pEventStatus)	//add hit with event number, column, row, relative BCID [0:15], tot, trigger ID
{
  _nHits++;
  if(_hitIndex < __MAXARRAYSIZE){
    _hitInfo[_hitIndex].eventNumber = pEventNumber;
    _hitInfo[_hitIndex].relativeBCID = pRelBCID;
    _hitInfo[_hitIndex].LVLID = pLVLID;
    _hitInfo[_hitIndex].column = pColumn;
    _hitInfo[_hitIndex].row = pRow;
    _hitInfo[_hitIndex].tot = pTot;
    _hitInfo[_hitIndex].BCID = pBCID;
    _hitInfo[_hitIndex].eventStatus = pEventStatus;
    _hitIndex++;
  }
}

void Interpret::printHits(unsigned int pNhits)
{
  if(pNhits>__MAXARRAYSIZE)
    return;
  std::cout<<"Event\tBCIDrel\tLVL1ID\tCol\tRow\tTot\tBCID\tEventStatus\n";
  for(unsigned int i = 0; i < pNhits; ++i)
    std::cout<<_hitInfo[i].eventNumber<<"\t"<<(unsigned int) _hitInfo[i].relativeBCID<<"\t"<<_hitInfo[i].LVLID<<"\t"<<(unsigned int) _hitInfo[i].column<<"\t"<<_hitInfo[i].row<<"\t"<<(unsigned int) _hitInfo[i].tot<<"\t"<<_hitInfo[i].BCID<<"\t"<<(unsigned int) _hitInfo[i].eventStatus<<"\n";
}

void Interpret::printSummary()
{
    std::cout<<"#Data Words "<<_nDataWords<<"\n";
    std::cout<<"#Data Header "<<_nDataHeaders<<"\n";
    std::cout<<"#Data Records "<<_nDataRecords<<"\n";
    std::cout<<"#Unknown words "<<_nUnknownWords<<"\n";
    std::cout<<"#Hits "<<_nHits<<"\n";

    std::cout<<"#Events "<<_nEvents<<"\n";
    std::cout<<"#Invalid Events "<<_nInvalidEvents<<"\n";
    std::cout<<"#Incomplete Events "<<_nIncompleteEvents<<"\n";
    std::cout<<"#Empty Events "<<_nEmptyEvents<<"\n";
    std::cout<<"#Trigger "<<_nTriggers<<"\n";
}

void Interpret::resetCounters()
{
  _nDataWords = 0;
  _nTriggers = 0;
	_nEvents = 0;
	_nInvalidEvents = 0;
	_nIncompleteEvents = 0;
	_nDataRecords = 0;
  _nDataHeaders = 0;
  _nUnknownWords = 0;
  _nHits = 0;
  _nEmptyEvents = 0;
}

void Interpret::getHits(unsigned int &rNhits, HitInfo* &rHitInfo)
{
  rHitInfo = _hitInfo;
  rNhits = _hitIndex;
}

void Interpret::setMetaWordIndex(unsigned int& tLength, MetaInfo* &rMetaInfo)
{
  _metaInfo = rMetaInfo;
  //sanity check
  for(unsigned int i = 0; i < tLength-1; ++i){
    if(_metaInfo[i].startIndex + _metaInfo[i].length != _metaInfo[i].stopIndex)
      throw 10;
    if(_metaInfo[i].stopIndex != _metaInfo[i+1].startIndex)
      throw 10;
  }
  if(_metaInfo[tLength-1].startIndex + _metaInfo[tLength-1].length != _metaInfo[tLength-1].stopIndex)
    throw 10;

  _metaEventIndexLength = tLength;
  _metaEventIndex = new unsigned long[_metaEventIndexLength];
  for(unsigned int i= 0; i<_metaEventIndexLength; ++i)
    _metaEventIndex[i] = 0;
  _metaDataSet = true;
}

void Interpret::correlateMetaWordIndex(unsigned long& pEventNumer, unsigned long& pDataWordIndex)
{
  if(_metaDataSet && pDataWordIndex == _lastWordIndexSet){
     _metaEventIndex[_lastMetaIndexNotSet] = pEventNumer;
     _lastWordIndexSet = _metaInfo[_lastMetaIndexNotSet].stopIndex;
     _lastMetaIndexNotSet++;
  }
}

void Interpret::getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned long*& rEventNumber)
{
  rEventNumberIndex = _metaEventIndexLength;
  rEventNumber = _metaEventIndex;
}