#include "Interpret.h"

Interpret::Interpret(void)
{
  setSourceFileName("Interpret");
  _NbCID = 16;
  _maxTot = 14;
  _fEI4B = false;
  _metaDataSet = false;
  _lastMetaIndexNotSet = 0;
  _lastWordIndexSet = 0;
  _metaEventIndexLength = 0;
  _metaEventIndex = 0;
  allocateHitInfoArray();
  allocateHitBufferArray();
  allocateTriggerErrorCounterArray();
  allocateErrorCounterArray();
  allocateServiceRecordCounterArray();
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

bool Interpret::interpretRawData(unsigned int* pDataWords, int pNdataWords)
{
	//std::cout<<"Interpret::interpretRawData with "<<pNdataWords<<" words\n";
  _hitIndex = 0;

  int nErrors = 0;

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

	for (int iWord = 0; iWord < pNdataWords; ++iWord){			//loop over the SRAM words
    //if(iWord > 530)
    //  return false;
    /*if(_nEvents>2)
      return false;*/
    correlateMetaWordIndex(_nEvents, _nDataWords);
    _nDataWords++;
		unsigned int tActualWord = pDataWords[iWord];					//take the actual SRAM word
		tActualTot1 = -1;												  //TOT1 value stays negative if it can not be set properly in getHitsfromDataRecord()
		tActualTot2 = -1;												  //TOT2 value stays negative if it can not be set properly in getHitsfromDataRecord()
		if (getTimefromDataHeader(tActualWord, tActualLVL1ID, tActualBCID)){	//data word is data header if true is returned
			_nDataHeaders++;
      if (tNdataHeader > _NbCID-1){	          //maximum event window is reached (tNdataHeader > BCIDs, mostly tNdataHeader > 15), so create new event
        if(tNdataRecord==0)
          _nEmptyEvents++;
        addEvent();
			}
			if (tNdataHeader == 0){								  //set the BCID of the first data header
				tStartBCID = tActualBCID;
				tStartLVL1ID = tActualLVL1ID;
			}
			else{
				tDbCID++;										          //increase relative BCID counter [0:15]
				if(_fEI4B){
					if(tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4B-1)	//BCID counter overflow for FEI4B (10 bit BCID counter)
						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4B;
				}
				else{
					if(tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4A-1)	//BCID counter overflow for FEI4A (8 bit BCID counter)
						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4A;
				}
				if (tStartBCID+tDbCID != tActualBCID){ //check if BCID is increasing in the event window, if not close actual event and create new with actual data header
          if(_firstTriggerNrSet && tActualLVL1ID == tStartLVL1ID) //happens sometimes, non inc. BCID, FE feature, only abort if no external trigger is used or the LVL1ID is not constant
            addEventErrorCode(__BCID_JUMP);
          else{
					  tBCIDerror = true;					         //BCID not increasing and no external triggering used, abort event and take actual data header for the first hit of the new event
            addEventErrorCode(__BCID_ERROR);
          }
        }
        if (tActualLVL1ID != tStartLVL1ID){    //LVL1ID not constant, is expected for CMOS pulse trigger/hit OR, but not for trigger word triggering
					tLVL1IDisConst = false;
          addEventErrorCode(__NON_CONST_LVL1ID);
        }
			}
      tNdataHeader++;										      //increase data header counter
      if (__DEBUG) //FIXME 
        debug(IntToStr(_nDataWords)+" DH LVL1ID/BCID "+IntToStr(tActualLVL1ID)+"/"+IntToStr(tActualBCID)+"\t"+IntToStr(_nEvents));
		}
		else if (getHitsfromDataRecord(tActualWord, tActualCol1, tActualRow1, tActualTot1, tActualCol2, tActualRow2, tActualTot2)){	//data word is data record if true is returned
			tNdataRecord++;										  //increase data record counter for this event
			_nDataRecords++;									  //increase total data record counter
			if(tActualTot1 >= 0)								//add hit if hit info is reasonable (TOT1 >= 0)
        addHit(tDbCID, tActualLVL1ID, tActualCol1, tActualRow1, tActualTot1, tActualBCID);
			if(tActualTot2 >= 0)								//add hit if hit info is reasonable and set (TOT2 >= 0)
        addHit(tDbCID, tActualLVL1ID, tActualCol2, tActualRow2, tActualTot2, tActualBCID);
      if (__DEBUG) //FIXME 
        debug(IntToStr(_nDataWords)+" DR COL1/ROW1/TOT1  COL2/ROW2/TOT2 "+IntToStr(tActualCol1)+"/"+IntToStr(tActualRow1)+"/"+IntToStr(tActualTot1)+"  "+IntToStr(tActualCol2)+"/"+IntToStr(tActualRow2)+"/"+IntToStr(tActualTot2)+" rBCID "+IntToStr(tDbCID)+"\t"+IntToStr(_nEvents));
		}
    else if (isTriggerWord(tActualWord)){ //data word is trigger word, is first word of the event data if external trigger is present
			_nTriggers++;										    //increase the total trigger number counter
      tTriggerWord++;  //trigger event counter increase
			tTriggerNumber = TRIGGER_NUMBER_MACRO_NEW(tActualWord); //actual trigger number
      if (__DEBUG)
        debug("trigger number: "+IntToStr(tTriggerNumber));

      //if(_firstTriggerNrSet && tNdataHeader != _NbCID) //if trigger comes always at the beginning this can be added
      //  addEventErrorCode(__BCID_ERROR);
      //if(tTriggerNumber == 9425){
      //  std::cout<<"!!!!!!!TRIGGER "<<tTriggerNumber<<"\n";
      //  for(int index = iWord-15; index < iWord +15; ++index){
      //      unsigned int ttLVL1 = 0;
      //      unsigned int tBCID = 0;
      //      int ttcol = 0;
      //      int ttrow = 0;
      //      int tttot = 0;
      //      int ttcol2 = 0;
      //      int ttrow2 = 0;
      //      int tttot2 = 0;
      //      int ttActualSRcode = 0;
      //      int ttActualSRcounter = 0;
      //      if(getTimefromDataHeader(pDataWords[index], ttLVL1, tBCID))
      //        std::cout<<index<<" DH "<<tBCID<<" "<<ttLVL1<<" "<<pDataWords[index]<<"\t";
      //      else if(getHitsfromDataRecord(pDataWords[index],ttcol, ttrow, tttot,ttcol2, ttrow2, tttot2))
      //        std::cout<<index<<" DR     "<<ttcol<<" "<<ttrow<<" "<<tttot<<" "<<ttcol2<<" "<<ttrow2<<"  "<<tttot2<<" "<<pDataWords[index]<<"\t";
      //      else if(isTriggerWord(pDataWords[index]))
      //        std::cout<<index<<" TRIGGER "<<TRIGGER_NUMBER_MACRO_NEW(pDataWords[index]);
      //      else if(getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter))
      //        std::cout<<index<<"\tSR "<<tActualSRcode<<" "<<pDataWords[index];
      //      else if(!isOtherWord(tActualWord))	
      //        std::cout<<index<<"\tUNKNOWN "<<tActualWord<<" "<<pDataWords[index];
      //      std::cout<<"\n";
      //    }
      //}
      //TLU error handling
      if(!_firstTriggerNrSet)
        _firstTriggerNrSet = true;
      else if(_lastTriggerNumber + 1 != tTriggerNumber && !(_lastTriggerNumber == __MAXTLUTRGNUMBER && tTriggerNumber == 0)){
        addTriggerErrorCode(__TRG_NUMBER_INC_ERROR);
        if (__DEBUG)
          warning("interpretRawData: Trigger Number not increasing by 1 (old/new): "+IntToStr(_lastTriggerNumber)+"/"+IntToStr(tTriggerNumber));

        if(Basis::debugSet()){
          for(int index = iWord-10; index < iWord +250; ++index){
            unsigned int ttLVL1 = 0;
            unsigned int tBCID = 0;
            int ttcol = 0;
            int ttrow = 0;
            int tttot = 0;
            int ttcol2 = 0;
            int ttrow2 = 0;
            int tttot2 = 0;
            int ttActualSRcode = 0;
            int ttActualSRcounter = 0;
            if(getTimefromDataHeader(pDataWords[index], ttLVL1, tBCID))
              std::cout<<index<<" DH "<<tBCID<<" "<<ttLVL1<<"\t";
            else if(getHitsfromDataRecord(pDataWords[index],ttcol, ttrow, tttot,ttcol2, ttrow2, tttot2))
              std::cout<<index<<" DR     "<<ttcol<<" "<<ttrow<<" "<<tttot<<" "<<ttcol2<<" "<<ttrow2<<"  "<<tttot2<<"\t";
            else if(isTriggerWord(pDataWords[index]))
              std::cout<<index<<" TRIGGER "<<TRIGGER_NUMBER_MACRO_NEW(pDataWords[index]);
            else if(getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter))
              std::cout<<index<<"\tSR "<<tActualSRcode;
            else if(!isOtherWord(tActualWord))	
              std::cout<<index<<"\tUNKNOWN "<<tActualWord;
            std::cout<<"\n";
          }
          counter++;
          if (counter > 1)
            return false;
        }

      }

      if ((tTriggerNumber & TRIGGER_ERROR_TRG_ACCEPT) == TRIGGER_ERROR_TRG_ACCEPT){
        addTriggerErrorCode(__TRG_ERROR_TRG_ACCEPT);
        if(Basis::warningSet())
          warning(std::string("interpretRawData: TRIGGER_ERROR_TRG_ACCEPT"));
      }
      if ((tTriggerNumber & TRIGGER_ERROR_LOW_TIMEOUT) == TRIGGER_ERROR_LOW_TIMEOUT){
        addTriggerErrorCode(__TRG_ERROR_LOW_TIMEOUT);
        if(Basis::warningSet())
          warning(std::string("interpretRawData: TRIGGER_ERROR_LOW_TIMEOUT"));
      }
      _lastTriggerNumber = tTriggerNumber;
		}
    else if (getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter)){ //data word is service record
        info(IntToStr(_nDataWords)+" SR "+IntToStr(tActualSRcode));
        addServiceRecord(tActualSRcode);
        addEventErrorCode(__HAS_SR);
        _nServiceRecords++;
		}
		else{
			if (!isOtherWord(tActualWord)){			//other for hit interpreting uninteressting data, else data word unknown
        addEventErrorCode(__UNKNOWN_WORD);
        _nUnknownWords++;
        if(Basis::warningSet())
				  warning("interpretRawData: "+IntToStr(_nDataWords)+" UNKNOWN WORD "+IntToStr(tActualWord)+" AT "+IntToStr(_nEvents));
        //std::cout<<_nDataWords<<" UNKNOWN WORD "<<tActualWord<<" AT "<<_nEvents<<"\n";
        //for(int index = iWord-10; index < iWord +250; ++index){
        //  unsigned int ttLVL1 = 0;
        //  unsigned int tBCID = 0;
        //  int ttcol = 0;
        //  int ttrow = 0;
        //  int tttot = 0;
        //  int ttcol2 = 0;
        //  int ttrow2 = 0;
        //  int tttot2 = 0;
        //  int ttActualSRcode = 0;
        //  int ttActualSRcounter = 0;
        //  if(getTimefromDataHeader(pDataWords[index], ttLVL1, tBCID))
        //    std::cout<<index<<" DH "<<tBCID<<" "<<ttLVL1<<"\t";
        //  else if(getHitsfromDataRecord(pDataWords[index],ttcol, ttrow, tttot,ttcol2, ttrow2, tttot2))
        //    std::cout<<index<<" DR     "<<ttcol<<" "<<ttrow<<" "<<tttot<<" "<<ttcol2<<" "<<ttrow2<<"  "<<tttot2<<"\t";
        //  else if(isTriggerWord(pDataWords[index]))
        //    std::cout<<index<<" TRIGGER "<<TRIGGER_NUMBER_MACRO_NEW(pDataWords[index]);
        //  else if(getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter))
        //    std::cout<<index<<"\tSR "<<tActualSRcode;
        //  else if(!isOtherWord(tActualWord))	
        //    std::cout<<index<<"\tUNKNOWN "<<tActualWord;
        //  std::cout<<"\n";
        //}
        ////nErrors++;
        ////if(nErrors>2)
        //  return false;
      }
		}

		if (tBCIDerror){	//tBCIDerror is raised if BCID is not increasing by 1, most likely due to incomplete data transmission, so start new event, actual word is data header here
      if(Basis::warningSet())
        warning("interpretRawData "+IntToStr(_nDataWords)+" BCID ERROR, event "+IntToStr(_nEvents));
      //for(int index = iWord-50; index < iWord +50; ++index){
      //    unsigned int ttLVL1 = 0;
      //    unsigned int tBCID = 0;
      //    int ttcol = 0;
      //    int ttrow = 0;
      //    int tttot = 0;
      //    int ttcol2 = 0;
      //    int ttrow2 = 0;
      //    int tttot2 = 0;
      //    int ttActualSRcode = 0;
      //    int ttActualSRcounter = 0;
      //    if(getTimefromDataHeader(pDataWords[index], ttLVL1, tBCID))
      //      std::cout<<index<<" DH "<<tBCID<<" "<<ttLVL1<<"\t";
      //    else if(getHitsfromDataRecord(pDataWords[index],ttcol, ttrow, tttot,ttcol2, ttrow2, tttot2))
      //      std::cout<<index<<" DR     "<<ttcol<<" "<<ttrow<<" "<<tttot<<" "<<ttcol2<<" "<<ttrow2<<"  "<<tttot2<<"\t";
      //    else if(isTriggerWord(pDataWords[index]))
      //      std::cout<<index<<" TRIGGER "<<TRIGGER_NUMBER_MACRO_NEW(pDataWords[index]);
      //    else if(getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter))
      //      std::cout<<index<<"\tSR "<<tActualSRcode;
      //    else if(!isOtherWord(tActualWord))	
      //      std::cout<<index<<"\tUNKNOWN "<<tActualWord;
      //    std::cout<<"\n";
      //  }
      //  //nErrors++;
      //  //if(nErrors>2)
      //    return false;
			//if (tNdataHeader > 2 || _NbCID < 2){ //only count as incomplete event if at least to consecutive data headers are there
            //}
      addEvent();
			_nIncompleteEvents++;
      getTimefromDataHeader(tActualWord, tActualLVL1ID, tStartBCID);
			tNdataHeader = 1;									//tNdataHeader is already 1, because actual word is first data of new event
			tStartBCID = tActualBCID;
			tStartLVL1ID = tActualLVL1ID;
		}
	}
  //save last incomplete event, otherwise maybe hit buffer/hit array overflow in next chunk
  storeEventHits();
  tHitBufferIndex = 0;
	return true;
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

void Interpret::getHits(unsigned int &rNhits, HitInfo* &rHitInfo)
{
  rHitInfo = _hitInfo;
  rNhits = _hitIndex;
}

void Interpret::resetCounters()
{
  _nDataWords = 0;
  _nTriggers = 0;
	_nEvents = 0;
	_nIncompleteEvents = 0;
	_nDataRecords = 0;
  _nDataHeaders = 0;
  _nServiceRecords = 0;
  _nUnknownWords = 0;
  _nHits = 0;
  _nEmptyEvents = 0;
  _nMaxHitsPerEvent = 0;
  _firstTriggerNrSet = false;
  _lastTriggerNumber = 0;
  resetTriggerErrorCounterArray();
  resetErrorCounterArray();
  resetServiceRecordCounterArray();
}

void Interpret::resetEventVariables()
{
	tNdataHeader = 0;
	tNdataRecord = 0;
	tDbCID = 0;
  tTriggerError = 0;
  tErrorCode = 0;
  tServiceRecord = 0;		
	tBCIDerror = false;
	tLVL1IDisConst = true;
  tTriggerWord = 0;
  tTriggerNumber = 0;
  tStartBCID = 0;
  tStartLVL1ID = 0;
  tHitBufferIndex = 0;
  tTotalHits = 0;
}

void Interpret::setNbCIDs(unsigned int& NbCIDs)
{
	_NbCID = NbCIDs;
}

void Interpret::setMaxTot(unsigned int& rMaxTot)
{
	_maxTot = rMaxTot;
}

void Interpret::getServiceRecordsCounters(unsigned int &rNserviceRecords, unsigned long*& rServiceRecordsCounter)
{
  rServiceRecordsCounter = _serviceRecordCounter;
  rNserviceRecords = __NSERVICERECORDS;
}

void Interpret::getErrorCounters(unsigned int &rNerrorCounters, unsigned long*& rErrorCounter)
{
  rErrorCounter = _errorCounter;
  rNerrorCounters = __N_ERROR_CODES;
}

void Interpret::getTriggerErrorCounters(unsigned int &rNTriggerErrorCounters, unsigned long*& rTriggerErrorCounter)
{
  rTriggerErrorCounter = _triggerErrorCounter;
  rNTriggerErrorCounters = __TRG_N_ERROR_CODES;
}

unsigned long Interpret::getNwords()
{
  return _nDataWords;
}

void Interpret::printSummary()
{
    std::cout<<"#Data Words "<<_nDataWords<<"\n";
    std::cout<<"#Data Header "<<_nDataHeaders<<"\n";
    std::cout<<"#Data Records "<<_nDataRecords<<"\n";
    std::cout<<"#Service Records "<<_nServiceRecords<<"\n";
    std::cout<<"#Unknown words "<<_nUnknownWords<<"\n\n";

    std::cout<<"#Hits "<<_nHits<<"\n";
    std::cout<<"MaxHitsPerEvent "<<_nMaxHitsPerEvent<<"\n";
    std::cout<<"#Events "<<_nEvents<<"\n";
    std::cout<<"#Trigger "<<_nTriggers<<"\n\n";
    std::cout<<"#Empty Events "<<_nEmptyEvents<<"\n";
    std::cout<<"#Incomplete Events "<<_nIncompleteEvents<<"\n\n";

    std::cout<<"#ErrorCounters \n";
    std::cout<<"\t0\t"<<_errorCounter[0]<<"\tEvents with SR\n";
    std::cout<<"\t1\t"<<_errorCounter[1]<<"\tEvents with no trigger word\n";
    std::cout<<"\t2\t"<<_errorCounter[2]<<"\tEvents with LVLID non const.\n";
    std::cout<<"\t3\t"<<_errorCounter[3]<<"\tEvents with wrong number of BCIDs\n";
    std::cout<<"\t4\t"<<_errorCounter[4]<<"\tEvents with unknown words\n";
    std::cout<<"\t5\t"<<_errorCounter[5]<<"\tEvents with jumping BCIDs\n";
    std::cout<<"\t6\t"<<_errorCounter[6]<<"\tEvents with TLU trigger error\n";

    std::cout<<"#TriggerErrorCounters \n";
    std::cout<<"\t0\t"<<_triggerErrorCounter[0]<<"\tTrigger number does not increase by 1\n";
    std::cout<<"\t1\t"<<_triggerErrorCounter[1]<<"\t# Trigger per event > 1\n";
    std::cout<<"\t2\t"<<_triggerErrorCounter[2]<<"\tTLU trigger accept error\n";
    std::cout<<"\t3\t"<<_triggerErrorCounter[3]<<"\tTLU low time out error\n";

    std::cout<<"#ServiceRecords \n";
    for(unsigned int i = 0; i<__NSERVICERECORDS; ++i)
      std::cout<<"\t"<<i<<"\t"<<_serviceRecordCounter[i]<<"\n";
}

void Interpret::printHits(unsigned int pNhits)
{
  if(pNhits>__MAXARRAYSIZE)
    return;
  std::cout<<"Event\tRelBCID\tTrigger\tLVL1ID\tCol\tRow\tTot\tBCID\tSR\tEventStatus\n";
  for(unsigned int i = 0; i < pNhits; ++i)
    std::cout<<_hitInfo[i].eventNumber<<"\t"<<(unsigned int) _hitInfo[i].relativeBCID<<"\t"<<(unsigned int) _hitInfo[i].triggerNumber<<"\t"<<_hitInfo[i].LVLID<<"\t"<<(unsigned int) _hitInfo[i].column<<"\t"<<_hitInfo[i].row<<"\t"<<(unsigned int) _hitInfo[i].tot<<"\t"<<_hitInfo[i].BCID<<"\t"<<(unsigned int) _hitInfo[i].serviceRecord<<"\t"<<(unsigned int) _hitInfo[i].eventStatus<<"\n";
}

//private

void Interpret::addHit(unsigned char pRelBCID, unsigned short int pLVLID, unsigned char pColumn, unsigned short int pRow, unsigned char pTot, unsigned short int pBCID)	//add hit with event number, column, row, relative BCID [0:15], tot, trigger ID
{
  tTotalHits++;
  if(tHitBufferIndex < __MAXHITBUFFERSIZE){
    _hitBuffer[tHitBufferIndex].eventNumber = _nEvents;
    _hitBuffer[tHitBufferIndex].triggerNumber = tTriggerNumber;
    _hitBuffer[tHitBufferIndex].relativeBCID = pRelBCID;
    _hitBuffer[tHitBufferIndex].LVLID = pLVLID;
    _hitBuffer[tHitBufferIndex].column = pColumn;
    _hitBuffer[tHitBufferIndex].row = pRow;
    _hitBuffer[tHitBufferIndex].tot = pTot;
    _hitBuffer[tHitBufferIndex].BCID = pBCID;
    _hitBuffer[tHitBufferIndex].serviceRecord = tServiceRecord;
    _hitBuffer[tHitBufferIndex].eventStatus = tErrorCode;
    tHitBufferIndex++;
  }
  else{
    if(Basis::errorSet())
      error("addHit: tHitBufferIndex = "+IntToStr(tHitBufferIndex), __LINE__);
    throw 12;
  }
}

void Interpret::storeHit(unsigned char pRelBCID, unsigned int pTriggerNumber, unsigned short int pLVLID, unsigned char pColumn, unsigned short int pRow, unsigned char pTot, unsigned short int pBCID, unsigned int pServiceRecord,  unsigned char pErrorCode)	//add hit with event number, column, row, relative BCID [0:15], tot, trigger ID
{
  _nHits++;
  if(_hitIndex < __MAXARRAYSIZE){
    _hitInfo[_hitIndex].eventNumber = _nEvents;
    _hitInfo[_hitIndex].triggerNumber = tTriggerNumber;
    _hitInfo[_hitIndex].relativeBCID = pRelBCID;
    _hitInfo[_hitIndex].LVLID = pLVLID;
    _hitInfo[_hitIndex].column = pColumn;
    _hitInfo[_hitIndex].row = pRow;
    _hitInfo[_hitIndex].tot = pTot;
    _hitInfo[_hitIndex].BCID = pBCID;
    _hitInfo[_hitIndex].serviceRecord = tServiceRecord;
    _hitInfo[_hitIndex].eventStatus = tErrorCode;
    _hitIndex++;
  }
  else{
    if(Basis::errorSet())
      error("storeHit: _hitIndex = "+IntToStr(_hitIndex), __LINE__);
    throw 11;
  }
}

void Interpret::addEvent()
{
  /*std::cout<<"!! EVENT "<<_nEvents<<"\n";
  for(unsigned int i = 0; i < _hitIndex; ++i)
    std::cout<<_hitInfo[i].eventNumber<<"\t"<<(unsigned int) _hitInfo[i].relativeBCID<<"\t"<<(unsigned int) _hitInfo[i].triggerNumber<<"\t"<<_hitInfo[i].LVLID<<"\t"<<(unsigned int) _hitInfo[i].column<<"\t"<<_hitInfo[i].row<<"\t"<<(unsigned int) _hitInfo[i].tot<<"\t"<<_hitInfo[i].BCID<<"\t"<<(unsigned int) _hitInfo[i].serviceRecord<<"\t"<<(unsigned int) _hitInfo[i].eventStatus<<"\n";*/

  if(tTriggerWord == 0){
    addEventErrorCode(__NO_TRG_WORD);
    if(Basis::infoSet())
      info(std::string("addEvent: no trigger word"));
  }
  if(tTriggerWord > 1){
    addEventErrorCode(__TRG_NUMBER_MORE_ONE);
    if(Basis::warningSet())
      warning(std::string("addEvent: # trigger words > 1"));
  }
  storeEventHits();
  if(tTotalHits > _nMaxHitsPerEvent)
    _nMaxHitsPerEvent = tTotalHits;
  histogramTriggerErrorCode();
  histogramErrorCode();
  _nEvents++;
	resetEventVariables();
}

void Interpret::storeEventHits()
{
  for (unsigned int i = 0; i<tHitBufferIndex; ++i){
    //_hitBuffer[i].triggerNumber = tTriggerNumber; not needed if trigger number is at the beginning
    //_hitBuffer[i].serviceRecord = tServiceRecord; not used if you want to see the position when the 
    _hitBuffer[i].triggerStatus = tTriggerError;
    _hitBuffer[i].eventStatus = tErrorCode;
  }

  for (unsigned int i = 0; i<tHitBufferIndex; ++i)
    storeHit(_hitBuffer[i].relativeBCID,_hitBuffer[i].triggerNumber,_hitBuffer[i].LVLID,_hitBuffer[i].column,_hitBuffer[i].row,_hitBuffer[i].tot,_hitBuffer[i].BCID,_hitBuffer[i].serviceRecord,_hitBuffer[i].eventStatus);
}

void Interpret::correlateMetaWordIndex(unsigned long& pEventNumer, unsigned long& pDataWordIndex)
{
  if(_metaDataSet && pDataWordIndex == _lastWordIndexSet){
     _metaEventIndex[_lastMetaIndexNotSet] = pEventNumer;
     _lastWordIndexSet = _metaInfo[_lastMetaIndexNotSet].stopIndex;
     _lastMetaIndexNotSet++;
  }
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
		if ((DATA_RECORD_TOT1_MACRO(pSRAMWORD) == 0xF) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW)){
      //std::cout<<"Interpret::getHitsfromDataRecord: ERROR data record values (1. Hit) out of bounds"<<std::endl;
			return false;			
		}
    if ((DATA_RECORD_TOT2_MACRO(pSRAMWORD) != 0xF) && ((DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW))){
      //std::cout<<"Interpret::getHitsfromDataRecord: ERROR data record values (2. Hit) out of bounds"<<std::endl;
			return false;	
    }

		//set first hit values
		if (DATA_RECORD_TOT1_MACRO(pSRAMWORD) <= _maxTot){	//ommit late/small hit and no hit TOT values for the TOT(1) hit
			pColHit1 = DATA_RECORD_COLUMN1_MACRO(pSRAMWORD);
			pRowHit1 = DATA_RECORD_ROW1_MACRO(pSRAMWORD);
			pTotHit1 = DATA_RECORD_TOT1_MACRO(pSRAMWORD);
		}

		//set second hit values
		if (DATA_RECORD_TOT2_MACRO(pSRAMWORD) <= _maxTot){	//ommit late/small hit and no hit (15) tot values for the TOT(2) hit
			pColHit2 = DATA_RECORD_COLUMN2_MACRO(pSRAMWORD);
			pRowHit2 = DATA_RECORD_ROW2_MACRO(pSRAMWORD);
			pTotHit2 = DATA_RECORD_TOT2_MACRO(pSRAMWORD);
		}
		return true;
	}
	return false;
}

bool Interpret::getInfoFromServiceRecord(unsigned int& pSRAMWORD, unsigned int& pSRcode, unsigned int& pSRcount)
{
  if(SERVICE_RECORD_MACRO(pSRAMWORD)){
		pSRcode = SERVICE_RECORD_CODE_MACRO(pSRAMWORD);
		pSRcount = SERVICE_RECORD_COUNTER_MACRO(pSRAMWORD);
    return true;
  }
  return false;
}

bool Interpret::isTriggerWord(unsigned int& pSRAMWORD)
{
	if (TRIGGER_WORD_MACRO_NEW(pSRAMWORD))	//data word is trigger word
		return true;
	return false;
}

bool Interpret::isOtherWord(unsigned int& pSRAMWORD)
{
	if (EMPTY_RECORD_MACRO(pSRAMWORD) || ADDRESS_RECORD_MACRO(pSRAMWORD) || VALUE_RECORD_MACRO(pSRAMWORD))
		return true;
	return false;
}

void Interpret::addTriggerErrorCode(unsigned char pErrorCode)
{
  std::cout<<"addTriggerErrorCode\n";
    tTriggerError |= pErrorCode;
}

void Interpret::addEventErrorCode(unsigned char pErrorCode)
{
  tErrorCode |= pErrorCode;
}

void Interpret::histogramTriggerErrorCode()
{
  unsigned int tBitPosition = 0;
  for(unsigned char iErrorCode = tTriggerError; iErrorCode != 0; iErrorCode = iErrorCode>>1){
    if(iErrorCode & 0x1)
      _triggerErrorCounter[tBitPosition]+=1;
    tBitPosition++;
  }
}

void Interpret::histogramErrorCode()
{
  unsigned int tBitPosition = 0;
  for(unsigned char iErrorCode = tErrorCode; iErrorCode != 0; iErrorCode = iErrorCode>>1){
    if(iErrorCode & 0x1)
      _errorCounter[tBitPosition]+=1;
    tBitPosition++;
  }
}

void Interpret::addServiceRecord(unsigned char pSRcode)
{
  tServiceRecord |= pSRcode;
  if(pSRcode<__NSERVICERECORDS)
    _serviceRecordCounter[pSRcode]+=1;
}

void Interpret::allocateHitInfoArray()
{
  _hitInfo = new HitInfo[__MAXARRAYSIZE];
}

void Interpret::deleteHitInfoArray()
{
  if (_hitInfo == 0)
    return;
  delete[] _hitInfo;
  _hitInfo = 0;
}

void Interpret::allocateHitBufferArray()
{
  _hitBuffer = new HitInfo[__MAXHITBUFFERSIZE];
}

void Interpret::deleteHitBufferArray()
{
  if (_hitBuffer == 0)
    return;
  delete[] _hitBuffer;
  _hitBuffer = 0;
}

void Interpret::allocateMetaEventIndexArray()
{
  _metaEventIndex = new unsigned long[_metaEventIndexLength];
}

void Interpret::deleteMetaEventIndexArray()
{
  if (_metaEventIndex == 0)
    return;
  delete[] _metaEventIndex;
  _metaEventIndex = 0;
}

void Interpret::allocateTriggerErrorCounterArray()
{
  _triggerErrorCounter = new unsigned long[__TRG_N_ERROR_CODES];
}

void Interpret::resetTriggerErrorCounterArray()
{
  for(unsigned int i = 0; i<__TRG_N_ERROR_CODES; ++i)
    _triggerErrorCounter[i] = 0;
}

void Interpret::deleteTriggerErrorCounterArray()
{
  if (_triggerErrorCounter == 0)
    return;
  delete[] _triggerErrorCounter;
  _triggerErrorCounter = 0;
}

void Interpret::allocateErrorCounterArray()
{
  _errorCounter = new unsigned long[__N_ERROR_CODES];
}

void Interpret::resetErrorCounterArray()
{
  for(unsigned int i = 0; i<__N_ERROR_CODES; ++i)
    _errorCounter[i] = 0;
}

void Interpret::deleteErrorCounterArray()
{
  if (_errorCounter == 0)
    return;
  delete[] _errorCounter;
  _errorCounter = 0;
}

void Interpret::allocateServiceRecordCounterArray()
{
  _serviceRecordCounter = new unsigned long[__NSERVICERECORDS];
}

void Interpret::resetServiceRecordCounterArray()
{
  for(unsigned int i = 0; i<__NSERVICERECORDS; ++i)
    _serviceRecordCounter[i] = 0;
}

void Interpret::deleteServiceRecordCounterArray()
{
  if (_serviceRecordCounter == 0)
    return;
  delete[] _serviceRecordCounter;
  _serviceRecordCounter = 0;
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
//					tBCIDerror = true;					//BCID not increasing, abort event and take actual data header for the first hit of the new event
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
//		if (tBCIDerror){	//tBCIDerror is raised if BCID is not increasing by 1, most likely due to incomplete data transmission, so start new event, actual word is data header here
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