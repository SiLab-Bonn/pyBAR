#include "Interpret.h"

Interpret::Interpret(void)
{
  setSourceFileName("Interpret");
  _metaDataSet = false;
  _debugEvents = false;
  _lastMetaIndexNotSet = 0;
  _lastWordIndexSet = 0;
  _metaEventIndexLength = 0;
  _metaEventIndex = 0;
  _NbCID[0] = 16;
  _maxTot[0] = 13;
  _fEI4B[0] = false;
  resetCounters();
}

Interpret::~Interpret(void)
{
  deleteMetaEventIndexArray();
  deleteHitInfoArray();
  deleteHitBufferArray();
  deleteTriggerErrorCounterArray();
  deleteErrorCounterArray();
  deleteServiceRecordCounterArray();
}

bool Interpret::interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords)
{
  if(Basis::debugSet()){
    std::stringstream tDebug;
    tDebug<<"interpretRawData with "<<pNdataWords<<" words";
    debug(tDebug.str());
  }
  for(std::map<unsigned int, unsigned int>::iterator it = _hitIndex.begin(); it != _hitIndex.end(); ++it)
    it->second = 0;

  //temporary variables set according to the actual SRAM word
	unsigned int tActualLVL1ID = 0;							//LVL1ID of the actual data header
	unsigned int tActualBCID = 0;								//BCID of the actual data header
  unsigned int tActualSRcode = 0;							//Service record code of the actual service record
  unsigned int tActualSRcounter = 0;					//Service record counter value of the actual service record
	int tActualCol1 = 0;												//column position of the first hit in the actual data record
	int tActualRow1 = 0;												//row position of the first hit in the actual data record
	int tActualTot1 = -1;												//tot value of the first hit in the actual data record
	int tActualCol2 = 0;												//column position of the second hit in the actual data record
	int tActualRow2 = 0;												//row position of the second hit in the actual data record
	int tActualTot2 = -1;												//tot value of the second hit in the actual data record

  int counter = 0;

	for (unsigned int iWord = 0; iWord < pNdataWords; ++iWord){	//loop over the SRAM words
		unsigned int tActualWord = pDataWords[iWord];			//take the actual SRAM word
    unsigned int tFEindex = getFeIndexFromWord(tActualWord);  //sets the actual FE index
		tActualTot1 = -1;												          //TOT1 value stays negative if it can not be set properly in getHitsfromDataRecord()
		tActualTot2 = -1;												          //TOT2 value stays negative if it can not be set properly in getHitsfromDataRecord() 

    correlateMetaWordIndex(_nEvents[tFEindex], _nDataWords);

    _nDataWords++;

    if(isNewFeIndex(tFEindex))
      setOptionsNewFe(tFEindex);

    if(_debugEvents){                                 //show debug output for selected events
      if(_nEvents[tFEindex] >= _startDebugEvent && _nEvents[tFEindex] <= _stopDebugEvent)
        setDebugOutput();
      else
        setDebugOutput(false);
    }

		if (getTimefromDataHeader(tFEindex, tActualWord, tActualLVL1ID, tActualBCID)){	//data word is data header if true is returned
			_nDataHeaders[tFEindex]++;
      if (tNdataHeader[tFEindex] > _NbCID[tFEindex]-1){	                  //maximum event window is reached (tNdataHeader > BCIDs, mostly tNdataHeader > 15), so create new event
        if(tNdataRecord[tFEindex]==0)
          _nEmptyEvents[tFEindex]++;
        addEvent(tFEindex);
			}
			if (tNdataHeader[tFEindex] == 0){								          //set the BCID of the first data header
				tStartBCID[tFEindex] = tActualBCID;
				tStartLVL1ID[tFEindex] = tActualLVL1ID;
			}
			else{
				tDbCID[tFEindex]++;										                  //increase relative BCID counter [0:15]
				if(_fEI4B[tFEindex]){
					if(tStartBCID[tFEindex] + tDbCID[tFEindex] > __BCIDCOUNTERSIZE_FEI4B-1)	//BCID counter overflow for FEI4B (10 bit BCID counter)
						tStartBCID[tFEindex] = tStartBCID[tFEindex] - __BCIDCOUNTERSIZE_FEI4B;
        }
				else{
					if(tStartBCID[tFEindex] + tDbCID[tFEindex] > __BCIDCOUNTERSIZE_FEI4A-1)	//BCID counter overflow for FEI4A (8 bit BCID counter)
						tStartBCID[tFEindex] = tStartBCID[tFEindex] - __BCIDCOUNTERSIZE_FEI4A;
        }

				if(tStartBCID[tFEindex]+tDbCID[tFEindex] != tActualBCID){  //check if BCID is increasing by 1s in the event window, if not close actual event and create new event with actual data header
          if(_firstTriggerNrSet && tActualLVL1ID == tStartLVL1ID[tFEindex]) //happens sometimes, non inc. BCID, FE feature, only abort if no external trigger is used or the LVL1ID is not constant
            addEventErrorCode(tFEindex, __BCID_JUMP);
          else{
					  tBCIDerror[tFEindex] = true;					       //BCID number wrong, abort event and take actual data header for the first hit of the new event
            addEventErrorCode(tFEindex, __EVENT_INCOMPLETE);
          }
        }
        if (!tBCIDerror[tFEindex] && tActualLVL1ID != tStartLVL1ID[tFEindex]){    //LVL1ID not constant, is expected for CMOS pulse trigger/hit OR, but not for trigger word triggering
					tLVL1IDisConst[tFEindex] = false;
          addEventErrorCode(tFEindex, __NON_CONST_LVL1ID);
        }
			}
      tNdataHeader[tFEindex]++;										       //increase data header counter
      if (Basis::debugSet())
        debug(std::string(" ")+IntToStr(_nDataWords)+" FE"+IntToStr(tFEindex)+" DH LVL1ID/BCID "+IntToStr(tActualLVL1ID)+"/"+IntToStr(tActualBCID)+"\t"+IntToStr(_nEvents[tFEindex]));
		}
    else if (isTriggerWord(tActualWord)){ //data word is trigger word, is first word of the event data if external trigger is present
			_nTriggers++;										    //increase the total trigger number counter
      if (tNdataHeader[tFEindex] > _NbCID[tFEindex]-1){	      //special case: first word is trigger word
        if(tNdataRecord[tFEindex]==0)
          _nEmptyEvents[tFEindex]++;
        addEvent(tFEindex);
			}
      tTriggerWord[tFEindex]++;                     //trigger event counter increase
			tTriggerNumber[tFEindex] = TRIGGER_NUMBER_MACRO_NEW(tActualWord); //actual trigger number
      if (Basis::debugSet())
        debug(std::string(" ")+IntToStr(_nDataWords)+" FE"+IntToStr(tFEindex)+" TR NUMBER "+IntToStr(tTriggerNumber[tFEindex]));

      //TLU error handling
      if(!_firstTriggerNrSet)
        _firstTriggerNrSet = true;
      else if(_lastTriggerNumber[tFEindex] + 1 != tTriggerNumber[tFEindex] && !(_lastTriggerNumber[tFEindex] == __MAXTLUTRGNUMBER && tTriggerNumber[tFEindex] == 0)){
        addTriggerErrorCode(tFEindex, __TRG_NUMBER_INC_ERROR);
        if (Basis::warningSet())
          warning("interpretRawData: Trigger Number not increasing by 1 (old/new): "+IntToStr(_lastTriggerNumber[tFEindex])+"/"+IntToStr(tTriggerNumber[tFEindex]));
        if (Basis::debugSet())
          printInterpretedWords(pDataWords, pNdataWords, iWord-10, iWord+250);
      }

      if ((tTriggerNumber[tFEindex] & TRIGGER_ERROR_TRG_ACCEPT) == TRIGGER_ERROR_TRG_ACCEPT){
        addTriggerErrorCode(tFEindex, __TRG_ERROR_TRG_ACCEPT);
        if(Basis::warningSet())
          warning(std::string("interpretRawData: TRIGGER_ERROR_TRG_ACCEPT"));
      }
      if ((tTriggerNumber[tFEindex] & TRIGGER_ERROR_LOW_TIMEOUT) == TRIGGER_ERROR_LOW_TIMEOUT){
        addTriggerErrorCode(tFEindex, __TRG_ERROR_LOW_TIMEOUT);
        if(Basis::warningSet())
          warning(std::string("interpretRawData: TRIGGER_ERROR_LOW_TIMEOUT"));
      }
      _lastTriggerNumber[tFEindex] = tTriggerNumber[tFEindex];
		}
    else if (getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter)){ //data word is service record
        info(IntToStr(_nDataWords)+" FE"+IntToStr(tFEindex)+" SR "+IntToStr(tActualSRcode));
        addServiceRecord(tFEindex, tActualSRcode);
        addEventErrorCode(tFEindex, __HAS_SR);
        _nServiceRecords[tFEindex]++;
		}
		else if (getHitsfromDataRecord(tFEindex, tActualWord, tActualCol1, tActualRow1, tActualTot1, tActualCol2, tActualRow2, tActualTot2)){	//data word is data record if true is returned
        tNdataRecord[tFEindex]++;										  //increase data record counter for this event
			  _nDataRecords[tFEindex]++;									  //increase total data record counter
			  if(tActualTot1 >= 0)								//add hit if hit info is reasonable (TOT1 >= 0)
          addHit(tFEindex, tDbCID[tFEindex], tActualLVL1ID, tActualCol1, tActualRow1, tActualTot1, tActualBCID);
			  if(tActualTot2 >= 0)								//add hit if hit info is reasonable and set (TOT2 >= 0)
          addHit(tFEindex, tDbCID[tFEindex], tActualLVL1ID, tActualCol2, tActualRow2, tActualTot2, tActualBCID);
        if (Basis::debugSet()) 
          debug(std::string(" ")+IntToStr(_nDataWords)+" FE"+IntToStr(tFEindex)+" DR COL1/ROW1/TOT1  COL2/ROW2/TOT2 "+IntToStr(tActualCol1)+"/"+IntToStr(tActualRow1)+"/"+IntToStr(tActualTot1)+"  "+IntToStr(tActualCol2)+"/"+IntToStr(tActualRow2)+"/"+IntToStr(tActualTot2)+" rBCID "+IntToStr(tDbCID[tFEindex])+"\t"+IntToStr(_nEvents[tFEindex]));
    }
		else{
			if (!isOtherWord(tActualWord)){			//other for hit interpreting uninteressting data, else data word unknown
        addEventErrorCode(tFEindex, __UNKNOWN_WORD);
        _nUnknownWords++;
        if(Basis::warningSet())
				  warning("interpretRawData: "+IntToStr(_nDataWords)+" FE"+IntToStr(tFEindex)+" UNKNOWN WORD "+IntToStr(tActualWord)+" AT "+IntToStr(_nEvents[tFEindex]));
        if (Basis::debugSet())
          printInterpretedWords(pDataWords, pNdataWords, iWord-10, iWord+250);
      }
		}

		if (tBCIDerror[tFEindex]){	//tBCIDerror is raised if BCID is not increasing by 1, most likely due to incomplete data transmission, so start new event, actual word is data header here
      if(Basis::warningSet())
        warning("interpretRawData "+IntToStr(_nDataWords)+" FE"+IntToStr(tFEindex)+" BCID ERROR, event "+IntToStr(_nEvents[tFEindex]));
      if (Basis::debugSet())
          printInterpretedWords(pDataWords, pNdataWords, iWord-50, iWord+50);
      addEvent(tFEindex);
			_nIncompleteEvents[tFEindex]++;
      getTimefromDataHeader(tFEindex, tActualWord, tActualLVL1ID, tStartBCID[tFEindex]);
			tNdataHeader[tFEindex] = 1;									//tNdataHeader is already 1, because actual word is first data of new event
			tStartBCID[tFEindex] = tActualBCID;
			tStartLVL1ID[tFEindex] = tActualLVL1ID;
		}
	}
  ////save last incomplete event, otherwise maybe hit buffer/hit array overflow in next chunk
  //storeEventHits();
  //tHitBufferIndex = 0;
	return true;
}

void Interpret::setMetaWordIndex(const unsigned int& tLength, MetaInfo* &rMetaInfo)
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
  allocateMetaEventIndexArray();
  for(unsigned int i= 0; i<_metaEventIndexLength; ++i)
    _metaEventIndex[i] = 0;
  _metaDataSet = true;
}

void Interpret::getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned long*& rEventNumber)
{
  rEventNumberIndex = _metaEventIndexLength;
  rEventNumber = _metaEventIndex;
}

void Interpret::getHits(const unsigned int& pFEindex, unsigned int &rNhits, HitInfo* &rHitInfo)
{
  rHitInfo = _hitInfo[pFEindex];
  rNhits = _hitIndex[pFEindex];
}

void Interpret::resetCounters()
{
  _nDataWords = 0;
  _nTriggers = 0;
	_nEvents.clear();
	_nIncompleteEvents.clear();
	_nDataRecords.clear();
  _nDataHeaders.clear();
  _nServiceRecords.clear();
  _nUnknownWords = 0;
  _nHits.clear();
  _nEmptyEvents.clear();
  _nMaxHitsPerEvent.clear();
  _firstTriggerNrSet = false;
  for(std::map<unsigned int, unsigned int>::iterator it = _lastTriggerNumber.begin(); it != _lastTriggerNumber.end(); ++it)
    it->second = 0;
  resetTriggerErrorCounterArray();
  resetErrorCounterArray();
  resetServiceRecordCounterArray();
}

void Interpret::setNbCIDs(const unsigned int& NbCIDs, const unsigned int& pFEindex)
{
    _NbCID[pFEindex] = NbCIDs;
}

void Interpret::setMaxTot(const unsigned int& rMaxTot, const unsigned int& pFEindex)
{
    _maxTot[pFEindex] = rMaxTot;
}

void Interpret::setFEI4B(bool pIsFEI4B, const unsigned int& pFEindex)
{
    _fEI4B[pFEindex] = pIsFEI4B;
};

bool Interpret::getFEI4B(const unsigned int pFEindex)
{
  return _fEI4B[pFEindex];
}

unsigned int Interpret::getNfe()
{
  return _hitInfo.size();
}

void Interpret::getServiceRecordsCounters(const unsigned int& pFEindex, unsigned int& rNserviceRecords, unsigned long*& rServiceRecordsCounter)
{
  rServiceRecordsCounter = _serviceRecordCounter[pFEindex];
  rNserviceRecords = __NSERVICERECORDS;
}

void Interpret::getErrorCounters(const unsigned int& pFEindex, unsigned int& rNerrorCounters, unsigned long*& rErrorCounter)
{
  rErrorCounter = _errorCounter[pFEindex];
  rNerrorCounters = __N_ERROR_CODES;
}

void Interpret::getTriggerErrorCounters(const unsigned int& pFEindex, unsigned int& rNTriggerErrorCounters, unsigned long*& rTriggerErrorCounter)
{
  rTriggerErrorCounter = _triggerErrorCounter[pFEindex];
  rNTriggerErrorCounters = __TRG_N_ERROR_CODES;
}

unsigned long Interpret::getNwords()
{
  return _nDataWords;
}

unsigned int Interpret::getFeIndex(const unsigned int& pNfE)
{
  unsigned int tFeCounter = 0;
  for(std::map<unsigned int, HitInfo*>::iterator it = _hitInfo.begin(); it != _hitInfo.end(); ++it){
    if (tFeCounter == pNfE)
      return it->first;
    tFeCounter++;
  }
  warning(std::string("getFeIndex: FE number not found"));
  return 0;
}

void Interpret::printSummary()
{
    std::cout<<"#Data Words "<<_nDataWords<<"\n";
    std::cout<<"#Unknown words "<<_nUnknownWords<<"\n";
    std::cout<<"#Trigger "<<_nTriggers<<"\n\n";

    for(unsigned int iFe = 0; iFe < getNfe(); ++iFe){
      unsigned int tFeIndex = getFeIndex(iFe);
      std::cout<<"#Data Header "<<_nDataHeaders[tFeIndex]<<" (FE"<<tFeIndex<<")\n";
      std::cout<<"#Data Records "<<_nDataRecords[tFeIndex]<<" (FE"<<tFeIndex<<")\n";
      std::cout<<"#Service Records "<<_nServiceRecords[tFeIndex]<<" (FE"<<tFeIndex<<")\n";
      std::cout<<"#Hits "<<_nHits[tFeIndex]<<" (FE"<<getFeIndex(iFe)<<")\n";
      std::cout<<"MaxHitsPerEvent "<<_nMaxHitsPerEvent[tFeIndex]<<" (FE"<<tFeIndex<<")\n";
      std::cout<<"#Events "<<_nEvents[tFeIndex]<<" (FE"<<tFeIndex<<")\n";
      std::cout<<"#Empty Events "<<_nEmptyEvents[tFeIndex]<<" (FE"<<tFeIndex<<")\n";
      std::cout<<"#Incomplete Events "<<_nIncompleteEvents[tFeIndex]<<" (FE"<<tFeIndex<<")\n\n";

      std::cout<<"#ErrorCounters \n";
      std::cout<<"\t0\t"<<_errorCounter[tFeIndex][0]<<"\tEvents with SR (FE"<<tFeIndex<<")\n";
      std::cout<<"\t1\t"<<_errorCounter[tFeIndex][1]<<"\tEvents with no trigger word (FE"<<tFeIndex<<")\n";
      std::cout<<"\t2\t"<<_errorCounter[tFeIndex][2]<<"\tEvents with LVLID non const. (FE"<<tFeIndex<<")\n";
      std::cout<<"\t3\t"<<_errorCounter[tFeIndex][3]<<"\tEvents that are incomplete (# BCIDs wrong) (FE"<<tFeIndex<<")\n";
      std::cout<<"\t4\t"<<_errorCounter[tFeIndex][4]<<"\tEvents with unknown words (FE"<<tFeIndex<<")\n";
      std::cout<<"\t5\t"<<_errorCounter[tFeIndex][5]<<"\tEvents with jumping BCIDs (FE"<<tFeIndex<<")\n";
      std::cout<<"\t6\t"<<_errorCounter[tFeIndex][6]<<"\tEvents with TLU trigger error (FE"<<tFeIndex<<")\n\n";

      std::cout<<"#TriggerErrorCounters \n";
      std::cout<<"\t0\t"<<_triggerErrorCounter[tFeIndex][0]<<"\tTrigger number does not increase by 1 (FE"<<tFeIndex<<")\n";
      std::cout<<"\t1\t"<<_triggerErrorCounter[tFeIndex][1]<<"\t# Trigger per event > 1 (FE"<<tFeIndex<<")\n";
      std::cout<<"\t2\t"<<_triggerErrorCounter[tFeIndex][2]<<"\tTLU trigger accept error (FE"<<tFeIndex<<")\n";
      std::cout<<"\t3\t"<<_triggerErrorCounter[tFeIndex][3]<<"\tTLU low time out error (FE"<<tFeIndex<<")\n\n";

      std::cout<<"#ServiceRecords \n";
      for(unsigned int i = 0; i<__NSERVICERECORDS; ++i)
        std::cout<<"\t"<<i<<"\t"<<_serviceRecordCounter[tFeIndex][i]<<" (FE"<<tFeIndex<<")\n";
    }
}

void Interpret::printHits(const unsigned int& pFEindex, const unsigned int& pNhits)
{
  if(pNhits>__MAXARRAYSIZE)
    return;
  std::cout<<"Event\tRelBCID\tTrigger\tLVL1ID\tCol\tRow\tTot\tBCID\tSR\tEventStatus\n";
  unsigned int tNfe = 0;
  if(_hitInfo[pFEindex] != 0){
    for(unsigned int i = 0; i < pNhits; ++i)
      std::cout<<_hitInfo[pFEindex][i].eventNumber<<"\t"<<(unsigned int) _hitInfo[pFEindex][i].relativeBCID<<"\t"<<(unsigned int) _hitInfo[pFEindex][i].triggerNumber<<"\t"<<_hitInfo[pFEindex][i].LVLID<<"\t"<<(unsigned int) _hitInfo[pFEindex][i].column<<"\t"<<_hitInfo[pFEindex][i].row<<"\t"<<(unsigned int) _hitInfo[pFEindex][i].tot<<"\t"<<_hitInfo[pFEindex][i].BCID<<"\t"<<(unsigned int) _hitInfo[pFEindex][i].serviceRecord<<"\t"<<(unsigned int) _hitInfo[pFEindex][i].eventStatus<<"\n";
  }
  else
    warning("printHits: Index "+IntToStr(pFEindex)+std::string(" does not exist"));
}

void Interpret::debugEvents(const unsigned long& rStartEvent, const unsigned long& rStopEvent, const bool& debugEvents)
{
  _debugEvents = debugEvents;
  _startDebugEvent = rStartEvent;
  _stopDebugEvent = rStopEvent;
}

void Interpret::printOptions()
{
  std::cout<<"\n\n##### Interpreter options\n";
  std::cout<<"Standard settings\n";
  std::cout<<"_NbCID[0] "<<_NbCID[0]<<"\n";
  std::cout<<"_maxTot[0]  "<<_maxTot[0] <<"\n";
  std::cout<<"_fEI4B[0] "<<_fEI4B[0]<<"\n";
  std::cout<<"Fe settings\n";
  for(unsigned int iFe = 0; iFe < getNfe(); ++iFe){
    std::cout<<"_NbCID["<<getFeIndex(iFe)<<"] "<<_NbCID[getFeIndex(iFe)]<<"\n";
    std::cout<<"_maxTot["<<getFeIndex(iFe)<<"] "<<_maxTot[getFeIndex(iFe)]<<"\n";
    std::cout<<"_fEI4B["<<getFeIndex(iFe)<<"] "<<_fEI4B[getFeIndex(iFe)]<<"\n";
  }
}

//private

void Interpret::addHit(const unsigned int& pNfE, const unsigned char& pRelBCID, const unsigned short int& pLVLID, const unsigned char& pColumn, const unsigned short int& pRow, const unsigned char& pTot, const unsigned short int& pBCID)	//add hit with event number, column, row, relative BCID [0:15], tot, trigger ID
{
  tTotalHits[pNfE]++;
  unsigned int ttHitBufferIndex = tHitBufferIndex[pNfE];
    
  if(ttHitBufferIndex < __MAXHITBUFFERSIZE){
    _hitBuffer[pNfE][ttHitBufferIndex].eventNumber = _nEvents[pNfE];
    _hitBuffer[pNfE][ttHitBufferIndex].triggerNumber = tTriggerNumber[pNfE];
    _hitBuffer[pNfE][ttHitBufferIndex].relativeBCID = pRelBCID;
    _hitBuffer[pNfE][ttHitBufferIndex].LVLID = pLVLID;
    _hitBuffer[pNfE][ttHitBufferIndex].column = pColumn;
    _hitBuffer[pNfE][ttHitBufferIndex].row = pRow;
    _hitBuffer[pNfE][ttHitBufferIndex].tot = pTot;
    _hitBuffer[pNfE][ttHitBufferIndex].BCID = pBCID;
    _hitBuffer[pNfE][ttHitBufferIndex].serviceRecord = tServiceRecord[pNfE];
    _hitBuffer[pNfE][ttHitBufferIndex].triggerStatus = tTriggerError[pNfE];
    _hitBuffer[pNfE][ttHitBufferIndex].eventStatus = tErrorCode[pNfE];
    tHitBufferIndex[pNfE]++;
  }
  else{
    if(Basis::errorSet())
      error("addHit: tHitBufferIndex = "+IntToStr(tHitBufferIndex[pNfE]), __LINE__);
    throw 12;
  }
}

void Interpret::storeHit(const unsigned int& pNfE, HitInfo& rHit)
{
  _nHits[pNfE]++;
  unsigned int ttHitIndex = _hitIndex[pNfE];  //code speed up, reduce map look ups
  if(ttHitIndex < __MAXARRAYSIZE){
    _hitInfo[pNfE][ttHitIndex] = rHit;
    _hitIndex[pNfE]++;
  }
  else{
    if(Basis::errorSet())
      error("storeHit: _hitIndex = "+IntToStr(_hitIndex[pNfE]), __LINE__);
    throw 11;
  }
}

void Interpret::addEvent(const unsigned int& pNfE)
{
  if(Basis::debugSet()){
    std::stringstream tDebug;
    tDebug<<"addEvent() "<<_nEvents[pNfE];
    debug(tDebug.str());
  }
  if(tTriggerWord[pNfE] == 0){
    addEventErrorCode(pNfE, __NO_TRG_WORD);
    debug(std::string("addEvent: no trigger word"));
  }
  if(tTriggerWord[pNfE] > 1){
    addTriggerErrorCode(pNfE, __TRG_NUMBER_MORE_ONE);
    if(Basis::warningSet())
      warning(std::string("addEvent: # trigger words > 1"));
  }
  storeEventHits(pNfE);
  if(tTotalHits[pNfE] > _nMaxHitsPerEvent[pNfE])
    _nMaxHitsPerEvent[pNfE] = tTotalHits[pNfE];
  histogramTriggerErrorCode(pNfE);
  histogramErrorCode(pNfE);
  _nEvents[pNfE]++;
	resetEventVariables(pNfE);
}

void Interpret::storeEventHits(const unsigned int& pNfE)
{
  for (unsigned int i = 0; i<tHitBufferIndex[pNfE]; ++i){
    _hitBuffer[pNfE][i].triggerNumber = tTriggerNumber[pNfE]; //not needed if trigger number is at the beginning
    _hitBuffer[pNfE][i].triggerStatus = tTriggerError[pNfE];
    _hitBuffer[pNfE][i].eventStatus = tErrorCode[pNfE];
    storeHit(pNfE, _hitBuffer[pNfE][i]);
  }
}

void Interpret::correlateMetaWordIndex(const unsigned long& pEventNumer, const unsigned long& pDataWordIndex)
{
  if(_metaDataSet && pDataWordIndex == _lastWordIndexSet){
     _metaEventIndex[_lastMetaIndexNotSet] = pEventNumer;
     _lastWordIndexSet = _metaInfo[_lastMetaIndexNotSet].stopIndex;
     _lastMetaIndexNotSet++;
  }
}

void Interpret::resetEventVariables(const unsigned int& pFEindex)
{
	tNdataHeader[pFEindex] = 0;
	tNdataRecord[pFEindex] = 0;
	tDbCID[pFEindex] = 0;
  tTriggerError[pFEindex] = 0;
  tErrorCode[pFEindex] = 0;
  tServiceRecord[pFEindex] = 0;	
	tBCIDerror[pFEindex] = false;
  tTriggerWord[pFEindex] = 0;
  tTriggerNumber[pFEindex] = 0;
  tStartBCID[pFEindex] = 0;
  tStartLVL1ID[pFEindex] = 0;
  tHitBufferIndex[pFEindex] = 0;
  tTotalHits[pFEindex] = 0;
  tLVL1IDisConst[pFEindex] = true;
}

bool Interpret::isNewFeIndex(const unsigned int& pFEindex)
{
	if (_hitInfo.find(pFEindex) == _hitInfo.end())
		return true;
	return false;
}

void Interpret::setOptionsNewFe(const unsigned int& pFEindex)
{
  resetEventVariables(pFEindex);
  allocateHitInfoArray(pFEindex);
  allocateHitBufferArray(pFEindex);

  allocateTriggerErrorCounterArray(pFEindex);
  resetTriggerErrorCounterArray(pFEindex);
  allocateErrorCounterArray(pFEindex);
  resetErrorCounterArray(pFEindex);
  allocateServiceRecordCounterArray(pFEindex);
  resetServiceRecordCounterArray(pFEindex);

  resetTriggerErrorCounterArray();
  if (_NbCID.find(pFEindex) == _NbCID.end())    //set std. value if option is not set
    _NbCID[pFEindex] = _NbCID[0];
  if (_maxTot.find(pFEindex) == _maxTot.end())  //set std. value if option is not set
    _maxTot[pFEindex] = _maxTot[0];
  if (_fEI4B.find(pFEindex) == _fEI4B.end())    //set std. value if option is not set
    _fEI4B[pFEindex] = _fEI4B[0];
}

unsigned int Interpret::getFeIndexFromWord(const unsigned int& pSRAMWORD)
{
  if(NFE_WORD_MACRO(pSRAMWORD))
      return NFE_NUMBER_MACRO(pSRAMWORD);
  return 0;
}

bool Interpret::getTimefromDataHeader(const unsigned int& pNfE, const unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID)
{
	if (DATA_HEADER_MACRO(pSRAMWORD)){
		if (_fEI4B[pNfE]){
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

bool Interpret::getHitsfromDataRecord(const unsigned int& pNfE, const unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2)
{
	if (DATA_RECORD_MACRO(pSRAMWORD)){	//SRAM word is data record
		//check if the hit values are reasonable
		if ((DATA_RECORD_TOT1_MACRO(pSRAMWORD) == 0xF) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW)){
      warning(std::string("getHitsfromDataRecord: data record values (1. Hit) out of bounds"));
			return false;			
		}
    if ((DATA_RECORD_TOT2_MACRO(pSRAMWORD) != 0xF) && ((DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW))){
      warning(std::string("getHitsfromDataRecord: data record values (2. Hit) out of bounds"));
			return false;	
    }

		//set first hit values
		if (DATA_RECORD_TOT1_MACRO(pSRAMWORD) <= _maxTot[pNfE]){	//ommit late/small hit and no hit TOT values for the TOT(1) hit
			pColHit1 = DATA_RECORD_COLUMN1_MACRO(pSRAMWORD);
			pRowHit1 = DATA_RECORD_ROW1_MACRO(pSRAMWORD);
			pTotHit1 = DATA_RECORD_TOT1_MACRO(pSRAMWORD);
		}

		//set second hit values
		if (DATA_RECORD_TOT2_MACRO(pSRAMWORD) <= _maxTot[pNfE]){	//ommit late/small hit and no hit (15) tot values for the TOT(2) hit
			pColHit2 = DATA_RECORD_COLUMN2_MACRO(pSRAMWORD);
			pRowHit2 = DATA_RECORD_ROW2_MACRO(pSRAMWORD);
			pTotHit2 = DATA_RECORD_TOT2_MACRO(pSRAMWORD);
		}
		return true;
	}
	return false;
}

bool Interpret::getInfoFromServiceRecord(const unsigned int& pSRAMWORD, unsigned int& pSRcode, unsigned int& pSRcount)
{
  if(SERVICE_RECORD_MACRO(pSRAMWORD)){
		pSRcode = SERVICE_RECORD_CODE_MACRO(pSRAMWORD);
		pSRcount = SERVICE_RECORD_COUNTER_MACRO(pSRAMWORD);
    return true;
  }
  return false;
}

bool Interpret::isTriggerWord(const unsigned int& pSRAMWORD)
{
	if (TRIGGER_WORD_MACRO_NEW(pSRAMWORD))	//data word is trigger word
		return true;
	return false;
}

bool Interpret::isOtherWord(const unsigned int& pSRAMWORD)
{
	if (ADDRESS_RECORD_MACRO(pSRAMWORD) || VALUE_RECORD_MACRO(pSRAMWORD))
		return true;
	return false;
}

void Interpret::addTriggerErrorCode(const unsigned int& pNfE, const unsigned char& pErrorCode)
{
  if(Basis::debugSet()){
    std::stringstream tDebug;
    tDebug<<"addTriggerErrorCode: "<<(unsigned int) pErrorCode<<"\n";
    debug(tDebug.str());
  }
  addEventErrorCode(pNfE, __TRG_ERROR);
  tTriggerError[pNfE] |= pErrorCode;
}

void Interpret::addEventErrorCode(const unsigned int& pNfE, const unsigned char& pErrorCode)
{
  if(Basis::debugSet()){
    std::stringstream tDebug;
    tDebug<<"addEventErrorCode: "<<(unsigned int) pErrorCode<<"\n";
    debug(tDebug.str());
  }
  tErrorCode[pNfE] |= pErrorCode;
}

void Interpret::addServiceRecord(const unsigned int& pNfE, const unsigned char& pSRcode)
{
  tServiceRecord[pNfE] |= pSRcode;
  if(pSRcode<__NSERVICERECORDS)
    _serviceRecordCounter[pNfE][pSRcode]+=1;
}

void Interpret::histogramTriggerErrorCode(const unsigned int& pNfE)
{
  unsigned int tBitPosition = 0;
  for(unsigned char iErrorCode = tTriggerError[pNfE]; iErrorCode != 0; iErrorCode = iErrorCode>>1){
    if(iErrorCode & 0x1)
      _triggerErrorCounter[pNfE][tBitPosition]+=1;
    tBitPosition++;
  }
}

void Interpret::histogramErrorCode(const unsigned int& pNfE)
{
  unsigned int tBitPosition = 0;
  for(unsigned char iErrorCode = tErrorCode[pNfE]; iErrorCode != 0; iErrorCode = iErrorCode>>1){
    if(iErrorCode & 0x1)
      _errorCounter[pNfE][tBitPosition]+=1;
    tBitPosition++;
  }
}

void Interpret::allocateHitInfoArray(const unsigned int& pIfE)
{
  debug(std::string("allocateHitInfoArray")+IntToStr(pIfE));
  _hitInfo[pIfE] = new HitInfo[__MAXARRAYSIZE];
}

void Interpret::deleteHitInfoArray()
{
  for(std::map<unsigned int, HitInfo*>::iterator it = _hitInfo.begin(); it != _hitInfo.end(); ++it){
    if (it->second != 0){
      delete[] it->second;
      it->second = 0;
    }
  }
}

void Interpret::allocateHitBufferArray(const unsigned int& pIfE)
{
  debug(std::string("allocateHitBufferArray for FE ")+IntToStr(pIfE));
  _hitBuffer[pIfE] = new HitInfo[__MAXHITBUFFERSIZE];
}

void Interpret::deleteHitBufferArray()
{
  for(std::map<unsigned int, HitInfo*>::iterator it = _hitBuffer.begin(); it != _hitBuffer.end(); ++it){
    if (it->second != 0){
      delete[] it->second;
      it->second = 0;
    }
  }
}

void Interpret::allocateMetaEventIndexArray()
{
  debug(std::string("allocateMetaEventIndexArray"));
  _metaEventIndex = new unsigned long[_metaEventIndexLength];
}

void Interpret::deleteMetaEventIndexArray()
{
  if (_metaEventIndex == 0)
    return;
  delete[] _metaEventIndex;
  _metaEventIndex = 0;
}

void Interpret::allocateTriggerErrorCounterArray(const unsigned int& pIfE)
{
  debug(std::string("allocateTriggerErrorCounterArray for FE ")+IntToStr(pIfE));
  _triggerErrorCounter[pIfE] = new unsigned long[__TRG_N_ERROR_CODES];
}

void Interpret::resetTriggerErrorCounterArray(const unsigned int pIfE)
{
  if(pIfE == 0) // reset all histograms
    for(std::map<unsigned int, unsigned long*>::iterator it = _triggerErrorCounter.begin(); it != _triggerErrorCounter.end(); ++it)
      for(unsigned int i = 0; i<__TRG_N_ERROR_CODES; ++i)
        it->second[i] = 0;
  else
    for(unsigned int iCode = 0; iCode < __TRG_N_ERROR_CODES; ++iCode)
      _triggerErrorCounter[pIfE][iCode] = 0;
}

void Interpret::deleteTriggerErrorCounterArray()
{
  for(std::map<unsigned int, unsigned long*>::iterator it = _triggerErrorCounter.begin(); it != _triggerErrorCounter.end(); ++it){
    if (it->second != 0){
      delete[] it->second;
      it->second = 0;
    }
  }
}

void Interpret::allocateErrorCounterArray(const unsigned int& pIfE)
{
  debug(std::string("allocateErrorCounterArray for FE ")+IntToStr(pIfE));
  _errorCounter[pIfE] = new unsigned long[__N_ERROR_CODES];
}

void Interpret::resetErrorCounterArray(const unsigned int pIfE)
{
  if(pIfE == 0) // reset all histograms
    for(std::map<unsigned int, unsigned long*>::iterator it = _errorCounter.begin(); it != _errorCounter.end(); ++it)
      for(unsigned int i = 0; i<__N_ERROR_CODES; ++i)
        it->second[i] = 0;
  else
    for(unsigned int iCode = 0; iCode < __N_ERROR_CODES; ++iCode)
      _errorCounter[pIfE][iCode] = 0;
}

void Interpret::deleteErrorCounterArray()
{
  for(std::map<unsigned int, unsigned long*>::iterator it = _errorCounter.begin(); it != _errorCounter.end(); ++it){
    if (it->second != 0){
      delete[] it->second;
      it->second = 0;
    }
  }
}

void Interpret::allocateServiceRecordCounterArray(const unsigned int& pIfE)
{
  debug(std::string("allocateServiceRecordCounterArray for FE ")+IntToStr(pIfE));
  _serviceRecordCounter[pIfE] = new unsigned long[__NSERVICERECORDS];
}

void Interpret::resetServiceRecordCounterArray(const unsigned int pIfE)
{
  if(pIfE == 0) // reset all histograms
    for(std::map<unsigned int, unsigned long*>::iterator it = _serviceRecordCounter.begin(); it != _serviceRecordCounter.end(); ++it)
      for(unsigned int i = 0; i<__NSERVICERECORDS; ++i)
        it->second[i] = 0;
  else
    for(unsigned int iRecord = 0; iRecord < __NSERVICERECORDS; ++iRecord)
      _serviceRecordCounter[pIfE][iRecord] = 0;
}

void Interpret::deleteServiceRecordCounterArray()
{
  for(std::map<unsigned int, unsigned long*>::iterator it = _serviceRecordCounter.begin(); it != _serviceRecordCounter.end(); ++it){
    if (it->second != 0){
      delete[] it->second;
      it->second = 0;
    }
  }
}

void Interpret::printInterpretedWords(unsigned int* pDataWords, const unsigned int& rNsramWords, const unsigned int& rStartWordIndex, const unsigned int& rEndWordIndex)
{
  std::cout<<"Interpret::printInterpretedWords\n";
  std::cout<<"rStartWordIndex "<<rStartWordIndex<<"\n";
  std::cout<<"rEndWordIndex "<<rEndWordIndex<<"\n";
  unsigned int tStartWordIndex = 0;
  unsigned int tStopWordIndex = rNsramWords;
  if(rStartWordIndex > 0 && rStartWordIndex < rEndWordIndex)
    tStartWordIndex = rStartWordIndex;
  if(rEndWordIndex < rNsramWords)
    tStopWordIndex = rEndWordIndex;
  for(unsigned int iWord = tStartWordIndex; iWord <= tStopWordIndex; ++iWord){
    unsigned int tActualWord = pDataWords[iWord];
    unsigned int tLVL1 = 0;
    unsigned int tBCID = 0;
    int tcol = 0;
    int trow = 0;
    int ttot = 0;
    int tcol2 = 0;
    int trow2 = 0;
    int ttot2 = 0;
    unsigned int tActualSRcode = 0;
    unsigned int tActualSRcounter = 0;
    unsigned int tFEindex = getFeIndexFromWord(tActualWord);  //sets the actual FE index
    if(getTimefromDataHeader(0, tActualWord, tLVL1, tBCID))
      std::cout<<iWord<<" FE"<<IntToStr(tFEindex)<<" DH "<<tBCID<<" "<<tLVL1<<"\t";
    else if(isTriggerWord(tActualWord))
      std::cout<<iWord<<" FE"<<IntToStr(tFEindex)<<" TRIGGER "<<TRIGGER_NUMBER_MACRO_NEW(tActualWord);
    else if(getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter))
      std::cout<<iWord<<" FE"<<IntToStr(tFEindex)<<" SR "<<tActualSRcode;
    else if(getHitsfromDataRecord(tFEindex, tActualWord,tcol, trow, ttot,tcol2, trow2, ttot2))
      std::cout<<iWord<<" FE"<<IntToStr(tFEindex)<<" DR     "<<tcol<<" "<<trow<<" "<<ttot<<" "<<tcol2<<" "<<trow2<<"  "<<ttot2<<"\t";
    else if(!isOtherWord(tActualWord))	
      std::cout<<iWord<<" FE"<<IntToStr(tFEindex)<<"\tUNKNOWN "<<tActualWord;
    std::cout<<"\n";
  }
}