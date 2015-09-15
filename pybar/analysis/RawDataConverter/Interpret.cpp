#include "Interpret.h"

Interpret::Interpret(void)
{
	setSourceFileName("Interpret");
	setStandardSettings();
	allocateHitArray();
	allocateHitBufferArray();
	allocateTriggerErrorCounterArray();
	allocateErrorCounterArray();
	allocateTdcCounterArray();
	allocateServiceRecordCounterArray();
	reset();
}

Interpret::~Interpret(void)
{
	debug("~Interpret(void): destructor called");
	deleteHitArray();
	deleteHitBufferArray();
	deleteTriggerErrorCounterArray();
	deleteErrorCounterArray();
	deleteTdcCounterArray();
	deleteServiceRecordCounterArray();
}

void Interpret::setStandardSettings()
{
	info("setStandardSettings()");
	_hitInfoSize = 1000000;
	_hitInfo = 0;
	_hitIndex = 0;
	_startDebugEvent = 0;
	_stopDebugEvent = 0;
	_NbCID = 16;
	_maxTot = 13;
	_fEI4B = false;
	_metaDataSet = false;
	_debugEvents = false;
	_lastMetaIndexNotSet = 0;
	_lastWordIndexSet = 0;
	_metaEventIndexLength = 0;
	_metaEventIndex = 0;
	_startWordIndex = 0;
	_createMetaDataWordIndex = false;
	_createEmptyEventHits = false;
	_isMetaTableV2 = false;
	_alignAtTriggerNumber = false;
	_useTriggerTimeStamp = false;
	_useTdcTriggerTimeStamp = false;
	_maxTdcDelay = 255;
	_alignAtTdcWord = false;
	_dataWordIndex = 0;
	_maxTriggerNumber = 2 ^ 31 - 1;
}

bool Interpret::interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords)
{
	if (Basis::debugSet()) {
		std::stringstream tDebug;
		tDebug << "interpretRawData with " << pNdataWords << " words at total word " << _nDataWords;
		debug(tDebug.str());
	}
	_hitIndex = 0;
	_actualMetaWordIndex = 0;

	int tActualCol1 = 0;				//column position of the first hit in the actual data record
	int tActualRow1 = 0;				//row position of the first hit in the actual data record
	int tActualTot1 = -1;				//tot value of the first hit in the actual data record
	int tActualCol2 = 0;				//column position of the second hit in the actual data record
	int tActualRow2 = 0;				//row position of the second hit in the actual data record
	int tActualTot2 = -1;				//tot value of the second hit in the actual data record

	for (unsigned int iWord = 0; iWord < pNdataWords; ++iWord) {	//loop over the SRAM words
		if (_debugEvents) {
			if (_nEvents >= _startDebugEvent && _nEvents <= _stopDebugEvent)
				setDebugOutput();
			else
				setDebugOutput(false);
			setInfoOutput(false);
			setWarningOutput(false);  // FIXME: do not unset this always
		}

		correlateMetaWordIndex(_nEvents, _dataWordIndex);
		_nDataWords++;
		_dataWordIndex++;
		unsigned int tActualWord = pDataWords[iWord];			//take the actual SRAM word
		tActualTot1 = -1;												          //TOT1 value stays negative if it can not be set properly in getHitsfromDataRecord()
		tActualTot2 = -1;												          //TOT2 value stays negative if it can not be set properly in getHitsfromDataRecord()
		if (getTimefromDataHeader(tActualWord, tActualLVL1ID, tActualBCID)) {	//data word is data header if true is returned
			_nDataHeaders++;
			if (tNdataHeader > _NbCID - 1) {	                //maximum event window is reached (tNdataHeader > BCIDs, mostly tNdataHeader > 15), so create new event
				if (_alignAtTriggerNumber) {
					addEventErrorCode(__TRUNC_EVENT); //too many data header in the event, abort this event, add truncated flag
					if (Basis::warningSet())
						warning(std::string("addHit: Hit buffer overflow prevented by splitting events at event " + LongIntToStr(_nEvents)), __LINE__);
				}
				addEvent();
			}
			if (tNdataHeader == 0) {								        //set the BCID of the first data header
				tStartBCID = tActualBCID;
				tStartLVL1ID = tActualLVL1ID;
			}
			else {
				tDbCID++;										        //increase relative BCID counter [0:15]
				if (_fEI4B) {
					if (tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4B - 1)	//BCID counter overflow for FEI4B (10 bit BCID counter)
						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4B;
				}
				else {
					if (tStartBCID + tDbCID > __BCIDCOUNTERSIZE_FEI4A - 1)	//BCID counter overflow for FEI4A (8 bit BCID counter)
						tStartBCID = tStartBCID - __BCIDCOUNTERSIZE_FEI4A;
				}

				if (tStartBCID + tDbCID != tActualBCID) {  //check if BCID is increasing by 1s in the event window, if not close actual event and create new event with actual data header
					if (tActualLVL1ID == tStartLVL1ID) //happens sometimes, non inc. BCID, FE feature, only abort if the LVL1ID is not constant (if no external trigger is used or)
						addEventErrorCode(__BCID_JUMP);
					else if (_alignAtTriggerNumber || _alignAtTdcWord)  //rely here on the trigger number or TDC word and do not start a new event
						addEventErrorCode(__BCID_JUMP);
					else {
						tBCIDerror = true;					       //BCID number wrong, abort event and take actual data header for the first hit of the new event
						addEventErrorCode(__EVENT_INCOMPLETE);
					}
				}
				if (!tBCIDerror && tActualLVL1ID != tStartLVL1ID) {    //LVL1ID not constant, is expected for CMOS pulse trigger/hit OR, but not for trigger word triggering
					addEventErrorCode(__NON_CONST_LVL1ID);
					if (Basis::infoSet())
						info("interpretRawData: LVL1 is not constant: " + IntToStr(tActualLVL1ID) + "!=" + IntToStr(tStartLVL1ID) + " at event " + LongIntToStr(_nEvents));
				}
			}
			tNdataHeader++;										       //increase data header counter
			if (Basis::debugSet())
				debug(std::string(" ") + IntToStr(_nDataWords) + " DH LVL1ID/BCID " + IntToStr(tActualLVL1ID) + "/" + IntToStr(tActualBCID) + "\t" + LongIntToStr(_nEvents));
		}
		else if (isTriggerWord(tActualWord)) { //data word is trigger word, is first word of the event data if external trigger is present
			_nTriggers++;						//increase the total trigger number counter
			if (!_alignAtTriggerNumber) {			// first word is not always the trigger number
				if (tNdataHeader > _NbCID - 1)
					addEvent();
			}
			else {		// use trigger number for event building, first word is trigger word in event data stream
				if (_firstTriggerNrSet)  // do not build new event after first trigger; maybe comment for old data where trigger number is not first event word
					addEvent();
			}
			tTriggerWord++;                     //trigger event counter increase

			if (!_useTriggerTimeStamp)
				tTriggerNumber = TRIGGER_NUMBER_MACRO_NEW(tActualWord); //actual trigger number
			else
				tTriggerNumber = TRIGGER_TIME_STAMP_MACRO(tActualWord); //actual trigger number is a time stamp

			if (Basis::debugSet()) {
				if (!_useTriggerTimeStamp)
					debug(std::string(" ") + IntToStr(_nDataWords) + " TR NUMBER " + IntToStr(tTriggerNumber) + "\t WORD " + IntToStr(tActualWord) + "\t" + LongIntToStr(_nEvents));
				else
					debug(std::string(" ") + IntToStr(_nDataWords) + " TR TIME STAMP " + IntToStr(tTriggerNumber) + "\t WORD " + IntToStr(tActualWord) + "\t" + LongIntToStr(_nEvents));
			}

			//TLU error handling
			if (!_firstTriggerNrSet)
				_firstTriggerNrSet = true;
			else if (!_useTriggerTimeStamp && (_lastTriggerNumber + 1 != tTriggerNumber) && !(_lastTriggerNumber == _maxTriggerNumber && tTriggerNumber == 0)) {
				addTriggerErrorCode(__TRG_NUMBER_INC_ERROR);
				if (Basis::warningSet())
					warning("interpretRawData: Trigger Number not increasing by 1 (old/new): " + IntToStr(_lastTriggerNumber) + "/" + IntToStr(tTriggerNumber) + " at event " + LongIntToStr(_nEvents));
			}

			if (tTriggerWord == 1)  			// event trigger number is trigger number of first trigger word within the event
				tEventTriggerNumber = tTriggerNumber;

			_lastTriggerNumber = tTriggerNumber;
		}
		else if (getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter)) { //data word is service record
			if (Basis::debugSet())
				debug(std::string(" ") + IntToStr(_nDataWords) + " SR " + IntToStr(tActualSRcode) + " (" + IntToStr(tActualSRcounter) + ") at event " + LongIntToStr(_nEvents));
			addServiceRecord(tActualSRcode, tActualSRcounter);
			addEventErrorCode(__HAS_SR);
			_nServiceRecords++;
		}
		else if (isTdcWord(tActualWord)) {	//data word is a tdc word
			addTdcValue(TDC_COUNT_MACRO(tActualWord));
			_nTDCWords++;
			if (_useTdcTriggerTimeStamp && (TDC_TRIG_DIST_MACRO(tActualWord) > _maxTdcDelay)){  // of the trigger distance if > _maxTdcDelay the TDC word does not belong to this event, thus ignore it
				if (Basis::debugSet())
					debug(std::string(" ") + IntToStr(_nDataWords) + " TDC COUNT " + IntToStr(TDC_COUNT_MACRO(tActualWord)) + "\t" + LongIntToStr(_nEvents) + "\t TRG DIST TIME STAMP " + IntToStr(TDC_TRIG_DIST_MACRO(tActualWord)) + "\t WORD " + IntToStr(tActualWord));
				continue;
			}

			//create new event if the option to align at TDC words is active AND the previous event has seen already all needed data headers OR the previous event was not aligned at a TDC word
			if (_alignAtTdcWord && _firstTdcSet && ( (tNdataHeader > _NbCID - 1) || ((tErrorCode & __TDC_WORD) != __TDC_WORD) )) {
				addEvent();
			}

			_firstTdcSet = true;

			if ((tErrorCode & __TDC_WORD) == __TDC_WORD) {  //if the event has already a TDC word set __MANY_TDC_WORDS
				if (!_useTdcTriggerTimeStamp)  // the first TDC word defines the event TDC value
					addEventErrorCode(__MANY_TDC_WORDS);
				else if (TDC_TRIG_DIST_MACRO(tActualWord) != 255) {  // in trigger time measurement mode the valid TDC word (tTdcTimeStamp != 255) defines the event TDC value
					if (tTdcTimeStamp != 255)  // there is already a valid TDC word for this event
						addEventErrorCode(__MANY_TDC_WORDS);
					else {
						tTdcTimeStamp = TDC_TRIG_DIST_MACRO(tActualWord);
						tTdcCount = TDC_COUNT_MACRO(tActualWord);
					}
				}
			}
			else {
				addEventErrorCode(__TDC_WORD);
				tTdcCount = TDC_COUNT_MACRO(tActualWord);
				if (!_useTdcTriggerTimeStamp)
					tTdcTimeStamp = TDC_TIME_STAMP_MACRO(tActualWord);
				else
					tTdcTimeStamp = TDC_TRIG_DIST_MACRO(tActualWord);
			}
			if (tTdcCount == 0)
				addEventErrorCode(__TDC_OVERFLOW);
			if (Basis::debugSet()) {
				if (_useTdcTriggerTimeStamp)
					debug(std::string(" ") + IntToStr(_nDataWords) + " TDC COUNT " + IntToStr(TDC_COUNT_MACRO(tActualWord)) + "\t" + LongIntToStr(_nEvents) + "\t TRG DIST TIME STAMP " + IntToStr(TDC_TRIG_DIST_MACRO(tActualWord)) + "\t WORD " + IntToStr(tActualWord));
				else
					debug(std::string(" ") + IntToStr(_nDataWords) + " TDC COUNT " + IntToStr(TDC_COUNT_MACRO(tActualWord)) + "\t" + LongIntToStr(_nEvents) + "\t TIME STAMP " + IntToStr(TDC_TIME_STAMP_MACRO(tActualWord)) + "\t WORD " + IntToStr(tActualWord));
			}
		}
		else if (isDataRecord(tActualWord)) {	//data word is data record if true is returned
			if (getHitsfromDataRecord(tActualWord, tActualCol1, tActualRow1, tActualTot1, tActualCol2, tActualRow2, tActualTot2)) {
				tNdataRecord++;										  //increase data record counter for this event
				_nDataRecords++;									  //increase total data record counter
				if (tActualTot1 >= 0)								//add hit if hit info is reasonable (TOT1 >= 0)
					addHit(tDbCID, tActualLVL1ID, tActualCol1, tActualRow1, tActualTot1, tActualBCID);
				if (tActualTot2 >= 0)								//add hit if hit info is reasonable and set (TOT2 >= 0)
					addHit(tDbCID, tActualLVL1ID, tActualCol2, tActualRow2, tActualTot2, tActualBCID);
				if (Basis::debugSet()) {
					std::stringstream tDebug;
					tDebug << " " << _nDataWords << " DR COL1/ROW1/TOT1  COL2/ROW2/TOT2 " << tActualCol1 << "/" << tActualRow1 << "/" << tActualTot1 << "  " << tActualCol2 << "/" << tActualRow2 << "/" << tActualTot2 << " rBCID " << tDbCID << "\t" << _nEvents;
					debug(tDebug.str());
				}
			}
		}
		else {
			if (isOtherWord(tActualWord)) {			//other for hit interpreting uninteressting data, else data word unknown
				_nOtherWords++;
				if (Basis::debugSet()) {
					unsigned int tAddress = 0;
					bool isShiftRegister = false;
					unsigned int tValue = 0;
					if (isAddressRecord(tActualWord, tAddress, isShiftRegister)) {
						if (isShiftRegister)
							debug(std::string(" ") + IntToStr(_nDataWords) + " ADDRESS RECORD SHIFT REG. " + IntToStr(tAddress) + " WORD " + IntToStr(tActualWord) + "\t" + LongIntToStr(_nEvents));
						else
							debug(std::string(" ") + IntToStr(_nDataWords) + " ADDRESS RECORD GLOBAL REG. " + IntToStr(tAddress) + " WORD " + IntToStr(tActualWord) + "\t" + LongIntToStr(_nEvents));
					}
					if (isValueRecord(tActualWord, tValue)) {
						debug(std::string(" ") + IntToStr(_nDataWords) + " VALUE RECORD " + IntToStr(tValue) + "\t" + LongIntToStr(_nEvents));
					}
				}
			}
			else {
				addEventErrorCode(__UNKNOWN_WORD);
				_nUnknownWords++;
				if (Basis::warningSet())
					warning("interpretRawData: " + IntToStr(_nDataWords) + " UNKNOWN WORD " + IntToStr(tActualWord) + " at event " + LongIntToStr(_nEvents));
				if (Basis::debugSet())
					debug(std::string(" ") + IntToStr(_nDataWords) + " UNKNOWN WORD " + IntToStr(tActualWord) + " at event " + LongIntToStr(_nEvents));
			}
		}

		if (tBCIDerror) {	//tBCIDerror is raised if BCID is not increasing by 1, most likely due to incomplete data transmission, so start new event, actual word is data header here
			if (Basis::warningSet())
				warning("interpretRawData " + IntToStr(_nDataWords) + " BCID ERROR at event " + LongIntToStr(_nEvents));
			addEvent();
			_nIncompleteEvents++;
			getTimefromDataHeader(tActualWord, tActualLVL1ID, tStartBCID);
			tNdataHeader = 1;									//tNdataHeader is already 1, because actual word is first data of new event
			tStartBCID = tActualBCID;
			tStartLVL1ID = tActualLVL1ID;
		}
	}
	return true;
}

bool Interpret::setMetaData(MetaInfo* &rMetaInfo, const unsigned int& tLength)
{
	info("setMetaData with " + IntToStr(tLength) + " entries");
	_isMetaTableV2 = false;
	_metaInfo = rMetaInfo;
	if (tLength == 0) {
		warning("setMetaWordIndex: data is empty");
		return false;
	}
	//sanity check
	for (unsigned int i = 0; i < tLength - 1; ++i) {
		if (_metaInfo[i].startIndex + _metaInfo[i].length != _metaInfo[i].stopIndex)
			throw std::out_of_range("Meta word index out of range.");
		if (_metaInfo[i].stopIndex != _metaInfo[i + 1].startIndex && _metaInfoV2[i + 1].startIndex != 0)
			throw std::out_of_range("Meta word index out of range.");
	}
	if (_metaInfo[tLength - 1].startIndex + _metaInfo[tLength - 1].length != _metaInfo[tLength - 1].stopIndex)
		throw std::out_of_range("Meta word index out of range.");

	_metaEventIndexLength = tLength;
	_metaDataSet = true;

	return true;
}

bool Interpret::setMetaDataV2(MetaInfoV2* &rMetaInfo, const unsigned int& tLength)
{
	info("setMetaDataV2 with " + IntToStr(tLength) + " entries");
	_isMetaTableV2 = true;
	_metaInfoV2 = rMetaInfo;
	if (tLength == 0) {
		warning(std::string("setMetaWordIndex: data is empty"));
		return false;
	}
	//sanity check
	for (unsigned int i = 0; i < tLength - 1; ++i) {
		if (_metaInfoV2[i].startIndex + _metaInfoV2[i].length != _metaInfoV2[i].stopIndex)
			throw std::out_of_range("Meta word index out of range.");
		if (_metaInfoV2[i].stopIndex != _metaInfoV2[i + 1].startIndex && _metaInfoV2[i + 1].startIndex != 0)
			throw std::out_of_range("Meta word index out of range.");
	}
	if (_metaInfoV2[tLength - 1].startIndex + _metaInfoV2[tLength - 1].length != _metaInfoV2[tLength - 1].stopIndex)
		throw std::out_of_range("Meta word index out of range.");

	_metaEventIndexLength = tLength;
	_metaDataSet = true;

	return true;
}

void Interpret::getHits(HitInfo*& rHitInfo, unsigned int& rSize, bool copy)
{
	debug("getHits(...)");
	if (copy)
		std::copy(_hitInfo, _hitInfo + _hitInfoSize, rHitInfo);
	else
		rHitInfo = _hitInfo;
	rSize = _hitIndex;
}

void Interpret::setHitsArraySize(const unsigned int &rSize)
{
	info("setHitsArraySize(...) with size " + IntToStr(rSize));
	deleteHitArray();
	_hitInfoSize = rSize;
	allocateHitArray();
}

void Interpret::setMetaDataEventIndex(uint64_t*& rEventNumber, const unsigned int& rSize)
{
	info("setMetaDataEventIndex(...) with length " + IntToStr(rSize));
	_metaEventIndex = rEventNumber;
	_metaEventIndexLength = rSize;
}

void Interpret::setMetaDataWordIndex(MetaWordInfoOut*& rWordNumber, const unsigned int& rSize)
{
	info("setMetaDataWordIndex(...) with length " + IntToStr(rSize));
	_metaWordIndex = rWordNumber;
	_metaWordIndexLength = rSize;
}

void Interpret::resetCounters()
{
	info("resetCounters()");
	_nDataWords = 0;
	_nTriggers = 0;
	_nEvents = 0;
	_nIncompleteEvents = 0;
	_nDataRecords = 0;
	_nDataHeaders = 0;
	_nServiceRecords = 0;
	_nUnknownWords = 0;
	_nTDCWords = 0;
	_nOtherWords = 0;
	_nHits = 0;
	_nEmptyEvents = 0;
	_nMaxHitsPerEvent = 0;
	_firstTriggerNrSet = false;
	_firstTdcSet = false;
	_lastTriggerNumber = 0;
	_dataWordIndex = 0;
	resetTriggerErrorCounterArray();
	resetErrorCounterArray();
	resetTdcCounterArray();
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
//	tLVL1IDisConst = true;
	tTriggerWord = 0;
	tTdcCount = 0;
	tTdcTimeStamp = 0;
	tTriggerNumber = 0;
	tEventTriggerNumber = 0;
	tStartBCID = 0;
	tStartLVL1ID = 0;
	tHitBufferIndex = 0;
	tTotalHits = 0;
}

void Interpret::createMetaDataWordIndex(bool CreateMetaDataWordIndex)
{
	debug("createMetaDataWordIndex");
	_createMetaDataWordIndex = CreateMetaDataWordIndex;
}

void Interpret::createEmptyEventHits(bool CreateEmptyEventHits)
{
	debug("createEmptyEventHits");
	_createEmptyEventHits = CreateEmptyEventHits;
}

void Interpret::setNbCIDs(const unsigned int& NbCIDs)
{
	_NbCID = NbCIDs;
}

void Interpret::setMaxTot(const unsigned int& rMaxTot)
{
	_maxTot = rMaxTot;
}

void Interpret::setMaxTdcDelay(const unsigned int& rtMaxTdcDelay)
{
	_maxTdcDelay = rtMaxTdcDelay;
}

void Interpret::alignAtTriggerNumber(bool alignAtTriggerNumber)
{
	info("alignAtTriggerNumber()");
	_alignAtTriggerNumber = alignAtTriggerNumber;
}

void Interpret::setMaxTriggerNumber(const unsigned int& rMaxTriggerNumber)
{
	_maxTriggerNumber = rMaxTriggerNumber;
}

void Interpret::alignAtTdcWord(bool alignAtTdcWord)
{
	info("alignAtTdcWord()");
	_alignAtTdcWord = alignAtTdcWord;
}

void Interpret::useTriggerTimeStamp(bool useTriggerTimeStamp)
{
	info("useTriggerTimeStamp()");
	_useTriggerTimeStamp = useTriggerTimeStamp;
}

void Interpret::useTdcTriggerTimeStamp(bool useTdcTriggerTimeStamp)
{
	info("useTdcTriggerTimeStamp()");
	_useTdcTriggerTimeStamp = useTdcTriggerTimeStamp;
}

void Interpret::getServiceRecordsCounters(unsigned int*& rServiceRecordsCounter, unsigned int& rNserviceRecords, bool copy)
{
	debug("getServiceRecordsCounters(...)");
	if (copy)
		std::copy(_serviceRecordCounter, _serviceRecordCounter + __NSERVICERECORDS, rServiceRecordsCounter);
	else
		rServiceRecordsCounter = _serviceRecordCounter;

	rNserviceRecords = __NSERVICERECORDS;
}

void Interpret::getErrorCounters(unsigned int*& rErrorCounter, unsigned int& rNerrorCounters, bool copy)
{
	debug("getErrorCounters(...)");
	if (copy)
		std::copy(_errorCounter, _errorCounter + __N_ERROR_CODES, rErrorCounter);
	else
		rErrorCounter = _errorCounter;

	rNerrorCounters = __N_ERROR_CODES;
}

void Interpret::getTdcCounters(unsigned int*& rTdcCounter, unsigned int& rNtdcCounters, bool copy)
{
	debug("getErrorCounters(...)");
	if (copy)
		std::copy(_tdcCounter, _tdcCounter + __N_TDC_VALUES, rTdcCounter);
	else
		rTdcCounter = _tdcCounter;

	rNtdcCounters = __N_TDC_VALUES;
}

void Interpret::getTriggerErrorCounters(unsigned int*& rTriggerErrorCounter, unsigned int& rNTriggerErrorCounters, bool copy)
{
	debug(std::string("getTriggerErrorCounters(...)"));
	if (copy)
		std::copy(_triggerErrorCounter, _triggerErrorCounter + __TRG_N_ERROR_CODES, rTriggerErrorCounter);
	else
		rTriggerErrorCounter = _triggerErrorCounter;

	rNTriggerErrorCounters = __TRG_N_ERROR_CODES;
}

unsigned int Interpret::getNwords()
{
	return _nDataWords;
}

void Interpret::printSummary()
{
	std::cout << "#Data Words " << _nDataWords << "\n";
	std::cout << "#Data Header " << _nDataHeaders << "\n";
	std::cout << "#Data Records " << _nDataRecords << "\n";
	std::cout << "#Service Records " << _nServiceRecords << "\n";
	std::cout << "#Other Words " << _nOtherWords << "\n";
	std::cout << "#Unknown words " << _nUnknownWords << "\n";
	std::cout << "#TDC words " << _nTDCWords << "\n\n";

	std::cout << "#Hits " << _nHits << "\n";
	std::cout << "MaxHitsPerEvent " << _nMaxHitsPerEvent << "\n";
	std::cout << "#Events " << _nEvents << "\n";
	std::cout << "#Trigger " << _nTriggers << "\n\n";
	std::cout << "#Empty Events " << _nEmptyEvents << "\n";
	std::cout << "#Incomplete Events " << _nIncompleteEvents << "\n\n";

	std::cout << "#ErrorCounters \n";
	std::cout << "\t0\t" << _errorCounter[0] << "\tEvents with SR\n";
	std::cout << "\t1\t" << _errorCounter[1] << "\tEvents with no trigger word\n";
	std::cout << "\t2\t" << _errorCounter[2] << "\tEvents with LVL1ID not const.\n";
	std::cout << "\t3\t" << _errorCounter[3] << "\tEvents that were incomplete (# BCIDs wrong)\n";
	std::cout << "\t4\t" << _errorCounter[4] << "\tEvents with unknown words\n";
	std::cout << "\t5\t" << _errorCounter[5] << "\tEvents with jumping BCIDs\n";
	std::cout << "\t6\t" << _errorCounter[6] << "\tEvents with TLU trigger error\n";
	std::cout << "\t7\t" << _errorCounter[7] << "\tEvents that were truncated due to too many data headers or data records\n";
	std::cout << "\t8\t" << _errorCounter[8] << "\tEvents with TDC words\n";
	std::cout << "\t9\t" << _errorCounter[9] << "\tEvents with > 1 TDC words\n";
	std::cout << "\t10\t" << _errorCounter[10] << "\tEvents with TDC overflow\n";
	std::cout << "\t11\t" << _errorCounter[11] << "\tEvents with no hits\n";

	std::cout << "#TriggerErrorCounters \n";
	std::cout << "\t0\t" << _triggerErrorCounter[0] << "\tTrigger number not increasing by 1\n";
	std::cout << "\t1\t" << _triggerErrorCounter[1] << "\t# Trigger per event > 1\n";

	std::cout << "#ServiceRecords \n";
	for (unsigned int i = 0; i < __NSERVICERECORDS; ++i)
		std::cout << "\t" << i << "\t" << _serviceRecordCounter[i] << "\n";
}

void Interpret::printStatus()
{
	std::cout << "config variables\n";
	std::cout << "_NbCID " << _NbCID << "\n";
	std::cout << "_maxTot " << _maxTot << "\n";
	std::cout << "_fEI4B " << _fEI4B << "\n";
	std::cout << "_debugEvents " << _debugEvents << "\n";
	std::cout << "_startDebugEvent " << _startDebugEvent << "\n";
	std::cout << "_stopDebugEvent " << _stopDebugEvent << "\n";
	std::cout << "_alignAtTriggerNumber " << _alignAtTriggerNumber << "\n";
	std::cout << "_alignAtTdcWord " << _alignAtTdcWord << "\n";
	std::cout << "_useTriggerTimeStamp " << _useTriggerTimeStamp << "\n";
	std::cout << "_useTdcTriggerTimeStamp " << _useTdcTriggerTimeStamp << "\n";
	std::cout << "_maxTdcDelay " << _maxTdcDelay << "\n";

	std::cout << "\none event variables\n";
	std::cout << "tNdataHeader " << tNdataHeader << "\n";
	std::cout << "tNdataRecord " << tNdataRecord << "\n";
	std::cout << "tStartBCID " << tStartBCID << "\n";
	std::cout << "tStartLVL1ID " << tStartLVL1ID << "\n";
	std::cout << "tDbCID " << tDbCID << "\n";
	std::cout << "tTriggerError " << tTriggerError << "\n";
	std::cout << "tErrorCode " << tErrorCode << "\n";
	std::cout << "tServiceRecord " << tServiceRecord << "\n";
	std::cout << "tTriggerNumber " << tTriggerNumber << "\n";
	std::cout << "tTotalHits " << tTotalHits << "\n";
//	std::cout << "tLVL1IDisConst "<<tLVL1IDisConst<<"\n";
	std::cout << "tBCIDerror " << tBCIDerror << "\n";
	std::cout << "tTriggerWord " << tTriggerWord << "\n";
	std::cout << "tTdcCount " << tTdcCount << "\n";
	std::cout << "tTdcTimeStamp" << tTdcTimeStamp << "\n";
	std::cout << "_lastTriggerNumber " << _lastTriggerNumber << "\n";

	std::cout << "\ncounters/flags for the total raw data processing\n";
	std::cout << "_nTriggers " << _nTriggers << "\n";
	std::cout << "_nEvents " << _nEvents << "\n";
	std::cout << "_nMaxHitsPerEvent " << _nMaxHitsPerEvent << "\n";
	std::cout << "_nEmptyEvents " << _nEmptyEvents << "\n";
	std::cout << "_nIncompleteEvents " << _nIncompleteEvents << "\n";
	std::cout << "_nOtherWords " << _nOtherWords << "\n";
	std::cout << "_nUnknownWords " << _nUnknownWords << "\n";
	std::cout << "_nTDCWords " << _nTDCWords << "\n\n";
	std::cout << "_nServiceRecords " << _nServiceRecords << "\n";
	std::cout << "_nDataRecords " << _nDataRecords << "\n";
	std::cout << "_nDataHeaders " << _nDataHeaders << "\n";
	std::cout << "_nHits " << _nHits << "\n";
	std::cout << "_nDataWords " << _nDataWords << "\n";
	std::cout << "_firstTriggerNrSet " << _firstTriggerNrSet << "\n";
	std::cout << "_firstTdcSet " << _firstTdcSet << "\n";
}

void Interpret::printHits(const unsigned int& pNhits)
{
	if (pNhits > _hitInfoSize)
		return;
	std::cout << "Event\tRelBCID\tTrigger\tLVL1ID\tCol\tRow\tTot\tBCID\tSR\tEventStatus\n";
	for (unsigned int i = 0; i < pNhits; ++i)
		std::cout << _hitInfo[i].eventNumber << "\t" << (unsigned int) _hitInfo[i].relativeBCID << "\t" << (unsigned int) _hitInfo[i].triggerNumber << "\t" << _hitInfo[i].LVLID << "\t" << (unsigned int) _hitInfo[i].column << "\t" << _hitInfo[i].row << "\t" << (unsigned int) _hitInfo[i].tot << "\t" << _hitInfo[i].BCID << "\t" << (unsigned int) _hitInfo[i].serviceRecord << "\t" << (unsigned int) _hitInfo[i].eventStatus << "\n";
}

void Interpret::debugEvents(const unsigned int& rStartEvent, const unsigned int& rStopEvent, const bool& debugEvents)
{
	_debugEvents = debugEvents;
	_startDebugEvent = rStartEvent;
	_stopDebugEvent = rStopEvent;
}

unsigned int Interpret::getHitSize()
{
	return sizeof(HitInfo);
}

void Interpret::reset()
{
	info("reset()");
	resetCounters();
	resetEventVariables();
	_lastMetaIndexNotSet = 0;
	_lastWordIndexSet = 0;
	_metaEventIndexLength = 0;
	_metaEventIndex = 0;
	_startWordIndex = 0;
	// initialize SRAM variables to 0
	tTriggerNumber = 0;
	tActualLVL1ID = 0;
	tActualBCID = 0;
	tActualSRcode= 0;
	tActualSRcounter = 0;
}

void Interpret::resetMetaDataCounter()
{
	_lastWordIndexSet = 0;
	_dataWordIndex = 0;
}

//private

void Interpret::addHit(const unsigned char& pRelBCID, const unsigned short int& pLVLID, const unsigned char& pColumn, const unsigned short int& pRow, const unsigned char& pTot, const unsigned short int& pBCID)	//add hit with event number, column, row, relative BCID [0:15], tot, trigger ID
{
	if (tHitBufferIndex < __MAXHITBUFFERSIZE) {
		_hitBuffer[tHitBufferIndex].eventNumber = _nEvents;
		_hitBuffer[tHitBufferIndex].triggerNumber = tEventTriggerNumber;
		_hitBuffer[tHitBufferIndex].relativeBCID = pRelBCID;
		_hitBuffer[tHitBufferIndex].LVLID = pLVLID;
		_hitBuffer[tHitBufferIndex].column = pColumn;
		_hitBuffer[tHitBufferIndex].row = pRow;
		_hitBuffer[tHitBufferIndex].tot = pTot;
		_hitBuffer[tHitBufferIndex].BCID = pBCID;
		_hitBuffer[tHitBufferIndex].TDC = tTdcCount;
		_hitBuffer[tHitBufferIndex].TDCtimeStamp = tTdcTimeStamp;
		_hitBuffer[tHitBufferIndex].serviceRecord = tServiceRecord;
		_hitBuffer[tHitBufferIndex].triggerStatus = tTriggerError;
		_hitBuffer[tHitBufferIndex].eventStatus = tErrorCode;
		if ((tErrorCode & __NO_HIT) != __NO_HIT)  //only count not virtual hits
			tTotalHits++;
		tHitBufferIndex++;
	}
	else {
		addEventErrorCode(__TRUNC_EVENT); //too many hits in the event, abort this event, add truncated flac
		addEvent();
		if (Basis::warningSet())
			warning(std::string("addHit: Hit buffer overflow prevented by splitting events at event " + LongIntToStr(_nEvents)), __LINE__);
	}
}

void Interpret::storeHit(HitInfo& rHit)
{
	_nHits++;
	if (_hitIndex < _hitInfoSize) {
		if (_hitInfo != 0) {
			_hitInfo[_hitIndex] = rHit;
			_hitIndex++;
		}
		else {
			throw std::runtime_error("Output hit array not set.");
		}
	}
	else {
		if (Basis::errorSet())
			error("storeHit: _hitIndex = " + IntToStr(_hitIndex), __LINE__);
		throw std::out_of_range("Hit index out of range.");
	}
}

void Interpret::addEvent()
{
	if (Basis::debugSet()) {
		std::stringstream tDebug;
		tDebug << "addEvent() " << _nEvents;
		debug(tDebug.str());
	}
	if (tTotalHits == 0) {
		_nEmptyEvents++;
		if (_createEmptyEventHits) {
			addEventErrorCode(__NO_HIT);
			addHit(0, 0, 0, 0, 0, 0);
		}
	}
	if (tTriggerWord == 0) {
		addEventErrorCode(__NO_TRG_WORD);
		if (_firstTriggerNrSet)  // set the last existing trigger number for events without trigger number if trigger numbers exist
			tEventTriggerNumber = _lastTriggerNumber;
	}
	if (tTriggerWord > 1) {
		addTriggerErrorCode(__TRG_NUMBER_MORE_ONE);
		if (Basis::warningSet())
			warning(std::string("addEvent: # trigger words > 1 at event " + LongIntToStr(_nEvents)));
	}
	if (_useTdcTriggerTimeStamp && tTdcTimeStamp >= 254)
		addEventErrorCode(__TDC_OVERFLOW);

	storeEventHits();
	if (tTotalHits > _nMaxHitsPerEvent)
		_nMaxHitsPerEvent = tTotalHits;
	histogramTriggerErrorCode();
	histogramErrorCode();
	if (_createMetaDataWordIndex) {
		if (_actualMetaWordIndex < _metaWordIndexLength) {
			_metaWordIndex[_actualMetaWordIndex].eventIndex = _nEvents;
			_metaWordIndex[_actualMetaWordIndex].startWordIdex = _startWordIndex;
			_metaWordIndex[_actualMetaWordIndex].stopWordIdex = _nDataWords - 1;
			_startWordIndex = _nDataWords - 1;
			_actualMetaWordIndex++;
		}
		else {
			std::stringstream tInfo;
			tInfo << "Interpret::addEvent(): meta word index array is too small " << _actualMetaWordIndex << ">=" << _metaWordIndexLength;
			throw std::out_of_range(tInfo.str());
		}
	}
	_nEvents++;
	resetEventVariables();
}

void Interpret::storeEventHits()
{
	for (unsigned int i = 0; i < tHitBufferIndex; ++i) {
		_hitBuffer[i].triggerNumber = tEventTriggerNumber; //not needed if trigger number is at the beginning
		_hitBuffer[i].triggerStatus = tTriggerError;
		_hitBuffer[i].eventStatus = tErrorCode;
		storeHit(_hitBuffer[i]);
	}
}

void Interpret::correlateMetaWordIndex(const uint64_t& pEventNumer, const unsigned int& pDataWordIndex)
{
	if (_metaDataSet && pDataWordIndex == _lastWordIndexSet) { // this check is to speed up the _metaEventIndex access by using the fact that the index has to increase for consecutive events
//		std::cout<<"_lastMetaIndexNotSet "<<_lastMetaIndexNotSet<<"\n";
		_metaEventIndex[_lastMetaIndexNotSet] = pEventNumer;
		if (_isMetaTableV2 == true) {
			_lastWordIndexSet = _metaInfoV2[_lastMetaIndexNotSet].stopIndex;
			_lastMetaIndexNotSet++;
			while (_metaInfoV2[_lastMetaIndexNotSet - 1].length == 0 && _lastMetaIndexNotSet < _metaEventIndexLength) {
				info("correlateMetaWordIndex: more than one readout during one event, correcting meta info");
//				std::cout<<"correlateMetaWordIndex: pEventNumer "<<pEventNumer<<" _lastWordIndexSet "<<_lastWordIndexSet<<" _lastMetaIndexNotSet "<<_lastMetaIndexNotSet<<"\n";
				_metaEventIndex[_lastMetaIndexNotSet] = pEventNumer;
				_lastWordIndexSet = _metaInfoV2[_lastMetaIndexNotSet].stopIndex;
				_lastMetaIndexNotSet++;
//				std::cout<<"correlateMetaWordIndex: pEventNumer "<<pEventNumer<<" _lastWordIndexSet "<<_lastWordIndexSet<<" _lastMetaIndexNotSet "<<_lastMetaIndexNotSet<<"\n";
//				std::cout<<" finished\n";
			}
		}
		else {
			_lastWordIndexSet = _metaInfo[_lastMetaIndexNotSet].stopIndex;
			_lastMetaIndexNotSet++;
			while (_metaInfo[_lastMetaIndexNotSet - 1].length == 0 && _lastMetaIndexNotSet < _metaEventIndexLength) {
				info("correlateMetaWordIndex: more than one readout during one event, correcting meta info");
//				std::cout<<"correlateMetaWordIndex: pEventNumer "<<pEventNumer<<" _lastWordIndexSet "<<_lastWordIndexSet<<" _lastMetaIndexNotSet "<<_lastMetaIndexNotSet<<"\n";
				_metaEventIndex[_lastMetaIndexNotSet] = pEventNumer;
				_lastWordIndexSet = _metaInfo[_lastMetaIndexNotSet].stopIndex;
				_lastMetaIndexNotSet++;
//				std::cout<<"correlateMetaWordIndex: pEventNumer "<<pEventNumer<<" _lastWordIndexSet "<<_lastWordIndexSet<<" _lastMetaIndexNotSet "<<_lastMetaIndexNotSet<<"\n";
//				std::cout<<" finished\n";
			}
		}
	}
}

bool Interpret::getTimefromDataHeader(const unsigned int& pSRAMWORD, unsigned int& pLVL1ID, unsigned int& pBCID)
{
	if (DATA_HEADER_MACRO(pSRAMWORD)) {
		if (_fEI4B) {
			pLVL1ID = DATA_HEADER_LV1ID_MACRO_FEI4B(pSRAMWORD);
			pBCID = DATA_HEADER_BCID_MACRO_FEI4B(pSRAMWORD);
		}
		else {
			pLVL1ID = DATA_HEADER_LV1ID_MACRO(pSRAMWORD);
			pBCID = DATA_HEADER_BCID_MACRO(pSRAMWORD);
		}
		return true;
	}
	return false;
}

bool Interpret::isDataRecord(const unsigned int& pSRAMWORD)
{
	if (DATA_RECORD_MACRO(pSRAMWORD)) {
		return true;
	}
	return false;
}

bool Interpret::isTdcWord(const unsigned int& pSRAMWORD)
{
	if (TDC_WORD_MACRO(pSRAMWORD))
		return true;
	return false;
}

bool Interpret::getHitsfromDataRecord(const unsigned int& pSRAMWORD, int& pColHit1, int& pRowHit1, int& pTotHit1, int& pColHit2, int& pRowHit2, int& pTotHit2)
{
	//if (DATA_RECORD_MACRO(pSRAMWORD)){	//SRAM word is data record
	//check if the hit values are reasonable
	if ((DATA_RECORD_TOT1_MACRO(pSRAMWORD) == 0xF) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN1_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW1_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW)) {
		warning(std::string("getHitsfromDataRecord: data record values (1. Hit) out of bounds at event " + LongIntToStr(_nEvents)));
		return false;
	}
	if ((DATA_RECORD_TOT2_MACRO(pSRAMWORD) != 0xF) && ((DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) < RAW_DATA_MIN_COLUMN) || (DATA_RECORD_COLUMN2_MACRO(pSRAMWORD) > RAW_DATA_MAX_COLUMN) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) < RAW_DATA_MIN_ROW) || (DATA_RECORD_ROW2_MACRO(pSRAMWORD) > RAW_DATA_MAX_ROW))) {
		warning(std::string("getHitsfromDataRecord: data record values (2. Hit) out of bounds at event " + LongIntToStr(_nEvents)));
		return false;
	}

	//set first hit values
	if (DATA_RECORD_TOT1_MACRO(pSRAMWORD) <= _maxTot) {	//ommit late/small hit and no hit TOT values for the TOT(1) hit
		pColHit1 = DATA_RECORD_COLUMN1_MACRO(pSRAMWORD);
		pRowHit1 = DATA_RECORD_ROW1_MACRO(pSRAMWORD);
		pTotHit1 = DATA_RECORD_TOT1_MACRO(pSRAMWORD);
	}

	//set second hit values
	if (DATA_RECORD_TOT2_MACRO(pSRAMWORD) <= _maxTot) {	//ommit late/small hit and no hit (15) tot values for the TOT(2) hit
		pColHit2 = DATA_RECORD_COLUMN2_MACRO(pSRAMWORD);
		pRowHit2 = DATA_RECORD_ROW2_MACRO(pSRAMWORD);
		pTotHit2 = DATA_RECORD_TOT2_MACRO(pSRAMWORD);
	}
	return true;
	//}
	//return false;
}

bool Interpret::getInfoFromServiceRecord(const unsigned int& pSRAMWORD, unsigned int& pSRcode, unsigned int& pSRcount)
{
	if (SERVICE_RECORD_MACRO(pSRAMWORD)) {
		pSRcode = SERVICE_RECORD_CODE_MACRO(pSRAMWORD);
		if (_fEI4B) {
			if (pSRcode == 14)
				pSRcount = 1;
			else if (pSRcode == 16)
				pSRcount = SERVICE_RECORD_ETC_MACRO_FEI4B(pSRAMWORD);
			else
				pSRcount = SERVICE_RECORD_COUNTER_MACRO(pSRAMWORD);
		}
		else {
			pSRcount = SERVICE_RECORD_COUNTER_MACRO(pSRAMWORD);
		}
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

bool Interpret::isAddressRecord(const unsigned int& pSRAMWORD, unsigned int& rAddress, bool& isShiftRegister)
{
	if (ADDRESS_RECORD_MACRO(pSRAMWORD)) {
		if (ADDRESS_RECORD_TYPE_SET_MACRO(pSRAMWORD))
			isShiftRegister = true;
		rAddress = ADDRESS_RECORD_ADDRESS_MACRO(pSRAMWORD);
		return true;
	}
	return false;
}

bool Interpret::isValueRecord(const unsigned int& pSRAMWORD, unsigned int& rValue)
{
	if (VALUE_RECORD_MACRO(pSRAMWORD)) {
		rValue = VALUE_RECORD_VALUE_MACRO(pSRAMWORD);
		return true;
	}
	return false;
}

bool Interpret::isOtherWord(const unsigned int& pSRAMWORD)
{
	if (ADDRESS_RECORD_MACRO(pSRAMWORD) || VALUE_RECORD_MACRO(pSRAMWORD))
		return true;
	return false;
}

void Interpret::addTriggerErrorCode(const unsigned char& pErrorCode)
{
	if (Basis::debugSet()) {
		std::stringstream tDebug;
		tDebug << "addTriggerErrorCode: " << (unsigned int) pErrorCode << "\n";
		debug(tDebug.str());
	}
	addEventErrorCode(__TRG_ERROR);
	tTriggerError |= pErrorCode;
}

void Interpret::addEventErrorCode(const unsigned short& pErrorCode)
{
	if ((tErrorCode & pErrorCode) != pErrorCode) {  //only add event error code if its not already set
		if (Basis::debugSet()) {
			std::stringstream tDebug;
			tDebug << "addEventErrorCode: " << (unsigned int) pErrorCode << " ";
			switch ((unsigned int) pErrorCode) {
			case __NO_ERROR:
			{
				tDebug << "NO ERROR";
				break;
			}
			case __HAS_SR:
			{
				tDebug << "EVENT HAS SERVICE RECORD";
				break;
			}
			case __NO_TRG_WORD:
			{
				tDebug << "EVENT HAS NO TRIGGER NUMBER";
				break;
			}
			case __NON_CONST_LVL1ID:
			{
				tDebug << "EVENT HAS NON CONST LVL1ID";
				break;
			}
			case __EVENT_INCOMPLETE:
			{
				tDebug << "EVENT HAS TOO LESS DATA HEADER";
				break;
			}
			case __UNKNOWN_WORD:
			{
				tDebug << "EVENT HAS UNKNOWN WORDS";
				break;
			}
			case __BCID_JUMP:
			{
				tDebug << "EVENT HAS JUMPING BCID NUMBERS";
				break;
			}
			case __TRG_ERROR:
			{
				tDebug << "EVENT HAS AN EXTERNAL TRIGGER ERROR";
				break;
			}
			case __TRUNC_EVENT:
			{
				tDebug << "EVENT HAS TOO MANY DATA HEADERS/RECORDS AND WAS TRUNCATED";
				break;
			}
			case __TDC_WORD:
			{
				tDebug << "EVENT HAS TDC WORD";
				break;
			}
			case __MANY_TDC_WORDS:
			{
				tDebug << "EVENT HAS MORE THAN ONE VALID TDC WORD";
				break;
			}
			case __TDC_OVERFLOW:
			{
				tDebug << "EVENT HAS TDC OVERFLOW";
				break;
			}
			}
			debug(tDebug.str() + "\t" + LongIntToStr(_nEvents));
		}
		tErrorCode |= pErrorCode;
	}
}

void Interpret::histogramTriggerErrorCode()
{
	unsigned int tBitPosition = 0;
	for (unsigned char iErrorCode = tTriggerError; iErrorCode != 0; iErrorCode = iErrorCode >> 1) {
		if (iErrorCode & 0x1)
			_triggerErrorCounter[tBitPosition] += 1;
		tBitPosition++;
	}
}

void Interpret::histogramErrorCode()
{
	unsigned int tBitPosition = 0;
	for (unsigned short int iErrorCode = tErrorCode; iErrorCode != 0; iErrorCode = iErrorCode >> 1) {
		if (iErrorCode & 0x1)
			_errorCounter[tBitPosition] += 1;
		tBitPosition++;
	}
}

void Interpret::addServiceRecord(const unsigned char& pSRcode, const unsigned int& pSRcounter)
{
	tServiceRecord |= pSRcode;
	if (pSRcode < __NSERVICERECORDS)
		_serviceRecordCounter[pSRcode] += pSRcounter;
}

void Interpret::addTdcValue(const unsigned short& pTdcCode)
{
	if (pTdcCode < __N_TDC_VALUES)
		_tdcCounter[pTdcCode] += 1;
}

void Interpret::allocateHitArray()
{
	debug(std::string("allocateHitArray()"));
	try {
		_hitInfo = new HitInfo[_hitInfoSize];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateHitArray(): ") + std::string(exception.what()));
		throw;
	}
}

void Interpret::deleteHitArray()
{
	debug(std::string("deleteHitArray()"));
	if (_hitInfo == 0)
		return;
	delete[] _hitInfo;
	_hitInfo = 0;
}

void Interpret::allocateHitBufferArray()
{
	debug(std::string("allocateHitBufferArray()"));
	try {
		_hitBuffer = new HitInfo[__MAXHITBUFFERSIZE];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateHitBufferArray(): ") + std::string(exception.what()));
		throw;
	}
}

void Interpret::deleteHitBufferArray()
{
	debug(std::string("deleteHitBufferArray()"));
	if (_hitBuffer == 0)
		return;
	delete[] _hitBuffer;
	_hitBuffer = 0;
}

void Interpret::allocateTriggerErrorCounterArray()
{
	debug(std::string("allocateTriggerErrorCounterArray()"));
	try {
		_triggerErrorCounter = new unsigned int[__TRG_N_ERROR_CODES];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateTriggerErrorCounterArray(): ") + std::string(exception.what()));
	}
}

void Interpret::resetTriggerErrorCounterArray()
{
	for (unsigned int i = 0; i < __TRG_N_ERROR_CODES; ++i)
		_triggerErrorCounter[i] = 0;
}

void Interpret::deleteTriggerErrorCounterArray()
{
	debug(std::string("deleteTriggerErrorCounterArray()"));
	if (_triggerErrorCounter == 0)
		return;
	delete[] _triggerErrorCounter;
	_triggerErrorCounter = 0;
}

void Interpret::allocateErrorCounterArray()
{
	debug(std::string("allocateErrorCounterArray()"));
	try {
		_errorCounter = new unsigned int[__N_ERROR_CODES];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateErrorCounterArray(): ") + std::string(exception.what()));
	}
}

void Interpret::allocateTdcCounterArray()
{
	debug(std::string("allocateTdcCounterArray()"));
	try {
		_tdcCounter = new unsigned int[__N_TDC_VALUES];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateTdcCounterArray(): ") + std::string(exception.what()));
	}
}

void Interpret::resetErrorCounterArray()
{
	for (unsigned int i = 0; i < __N_ERROR_CODES; ++i)
		_errorCounter[i] = 0;
}

void Interpret::resetTdcCounterArray()
{
	for (unsigned int i = 0; i < __N_TDC_VALUES; ++i)
		_tdcCounter[i] = 0;
}

void Interpret::deleteErrorCounterArray()
{
	debug(std::string("deleteErrorCounterArray()"));
	if (_errorCounter == 0)
		return;
	delete[] _errorCounter;
	_errorCounter = 0;
}

void Interpret::deleteTdcCounterArray()
{
	debug(std::string("deleteTdcCounterArray()"));
	if (_tdcCounter == 0)
		return;
	delete[] _tdcCounter;
	_tdcCounter = 0;
}

void Interpret::allocateServiceRecordCounterArray()
{
	debug(std::string("allocateServiceRecordCounterArray()"));
	try {
		_serviceRecordCounter = new unsigned int[__NSERVICERECORDS];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateServiceRecordCounterArray(): ") + std::string(exception.what()));
	}
}

void Interpret::resetServiceRecordCounterArray()
{
	for (unsigned int i = 0; i < __NSERVICERECORDS; ++i)
		_serviceRecordCounter[i] = 0;
}

void Interpret::deleteServiceRecordCounterArray()
{
	debug(std::string("deleteServiceRecordCounterArray()"));
	if (_serviceRecordCounter == 0)
		return;
	delete[] _serviceRecordCounter;
	_serviceRecordCounter = 0;
}

void Interpret::printInterpretedWords(unsigned int* pDataWords, const unsigned int& rNsramWords, const unsigned int& rStartWordIndex, const unsigned int& rEndWordIndex)
{
	std::cout << "Interpret::printInterpretedWords\n";
	std::cout << "rStartWordIndex " << rStartWordIndex << "\n";
	std::cout << "rEndWordIndex " << rEndWordIndex << "\n";
	unsigned int tStartWordIndex = 0;
	unsigned int tStopWordIndex = rNsramWords;
	if (rStartWordIndex > 0 && rStartWordIndex < rEndWordIndex)
		tStartWordIndex = rStartWordIndex;
	if (rEndWordIndex < rNsramWords)
		tStopWordIndex = rEndWordIndex;
	for (unsigned int iWord = tStartWordIndex; iWord <= tStopWordIndex; ++iWord) {
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
		unsigned int tActualValueRecord = 0;
		unsigned int tActualAddressRecord = 0;
		bool tActualAddressRecordType = 0;
		std::cout << iWord;
		if (getTimefromDataHeader(tActualWord, tLVL1, tBCID))
			std::cout << " DH " << tBCID << " " << tLVL1 << "\t";
		else if (isDataRecord(tActualWord) && getHitsfromDataRecord(tActualWord, tcol, trow, ttot, tcol2, trow2, ttot2))
			std::cout << " DR     " << tcol << " " << trow << " " << ttot << " " << tcol2 << " " << trow2 << "  " << ttot2 << "\t";
		else if (isTriggerWord(tActualWord))
			std::cout << " TRIGGER " << TRIGGER_NUMBER_MACRO_NEW(tActualWord);
		else if (getInfoFromServiceRecord(tActualWord, tActualSRcode, tActualSRcounter))
			std::cout << " SR " << tActualSRcode;
		else if (isAddressRecord(tActualWord, tActualAddressRecord, tActualAddressRecordType))
			if (tActualAddressRecordType)
				std::cout << " AR SHIFT REG " << tActualAddressRecord;
			else
				std::cout << " AR GLOBAL REG " << tActualAddressRecord;
		else if (isValueRecord(tActualWord, tActualValueRecord))
			std::cout << " VR " << tActualValueRecord;
		else
			std::cout << " UNKNOWN " << tActualWord;
		std::cout << "\n";
	}
}
