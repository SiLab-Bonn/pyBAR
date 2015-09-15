#include "Clusterizer.h"

const int maxHitsPerEvent = 1000;  // maximum hits per event to start the clustering for this event, otherwise omit event

Clusterizer::Clusterizer(void)
{
	setSourceFileName("Clusterizer");
	setStandardSettings();
	allocateClusterHitArray();
	allocateClusterInfoArray();
	allocateHitMap();
	allocateHitIndexMap();
	allocateChargeMap();
	allocateResultHistograms();
	initChargeCalibMap();
	reset();
}

Clusterizer::~Clusterizer(void)
{
	debug("~Clusterizer(void): destructor called");
	deleteClusterHitArray();
	deleteClusterInfoArray();
	deleteHitMap();
	deleteHitIndexMap();
	deleteChargeMap();
	deleteResultHistograms();
}

void Clusterizer::setStandardSettings()
{
	info("setStandardSettings()");
	_clusterHitInfo = 0;
	_clusterInfo = 0;
	_clusterHitInfoSize = 1000000;
	_clusterInfoSize = 1000000;
	_hitMap = 0;
	_hitIndexMap = 0;
	_chargeMap = 0;
	_clusterTots = 0;
	_clusterCharges = 0;
	_clusterHits = 0;
	_clusterPosition = 0;
	_nEventHits = 0;
	_dx = 1; // column
	_dy = 2; // row
	_DbCID = 4; // timewalk
	_minClusterHits = 1;
	_maxClusterHits = 30;	//std. setting for maximum hits per cluster allowed
	_runTime = 0;
	_nHits = 0;
	_maxClusterHitTot = 13;
	_createClusterHitInfoArray = false;
	_createClusterInfoArray = true;
	_minColHitPos = RAW_DATA_MAX_COLUMN - 1;
	_maxColHitPos = 0;
	_minRowHitPos = RAW_DATA_MAX_ROW - 1;
	_maxRowHitPos = 0;
	_maxHitTot = 13;
}

void Clusterizer::setClusterHitInfoArraySize(const unsigned int& rSize)
{
	info("setClusterHitInfoArraySize()");
	deleteClusterHitArray();
	_clusterHitInfoSize = rSize;
	_NclustersHits = 0;
	allocateClusterHitArray();
}

void Clusterizer::setClusterInfoArraySize(const unsigned int& rSize)
{
	info("setClusterInfoArraySize()");
	deleteClusterInfoArray();
	_clusterInfoSize = rSize;
	_Nclusters = 0;
	allocateClusterInfoArray();
}

void Clusterizer::getClusterSizeHist(unsigned int& rNparameterValues, unsigned int*& rClusterSize, bool copy)
{
	info("getClusterSizeHist(...)");
	if (copy) {
		std::copy(_clusterHits, _clusterHits + __MAXCLUSTERHITSBINS, rClusterSize);
	}
	else
		rClusterSize = _clusterHits;

	rNparameterValues = __MAXCLUSTERHITSBINS;
}

void Clusterizer::getClusterTotHist(unsigned int& rNparameterValues, unsigned int*& rClusterTot, bool copy)
{
	info("getClusterTotHist(...)");
	unsigned int tArrayLength = (size_t)(__MAXTOTBINS - 1) + (size_t)(__MAXCLUSTERHITSBINS - 1) * (size_t) __MAXTOTBINS + 1;
	if (copy) {
		std::copy(_clusterTots, _clusterTots + tArrayLength, rClusterTot);
	}
	else
		rClusterTot = _clusterTots;

	rNparameterValues = tArrayLength;
}

void Clusterizer::getClusterChargeHist(unsigned int& rNparameterValues, unsigned int*& rClusterCharge, bool copy)
{
	info("getClusterChargeHist(...)");
	unsigned int tArrayLength = (size_t)(__MAXCHARGEBINS - 1) + (size_t)(__MAXCLUSTERHITSBINS - 1) * (size_t) __MAXCHARGEBINS + 1;
	if (copy) {
		std::copy(_clusterCharges, _clusterCharges + tArrayLength, rClusterCharge);
	}
	else
		rClusterCharge = _clusterCharges;

	rNparameterValues = tArrayLength;
}
void Clusterizer::getClusterPositionHist(unsigned int& rNparameterValues, unsigned int*& rClusterPosition, bool copy)
{
	info("getClusterPositionHist(...)");
	unsigned int tArrayLength = (size_t)(__MAXPOSXBINS - 1) + (size_t)(__MAXPOSYBINS - 1) * (size_t) __MAXPOSXBINS + 1;
	if (copy) {
		std::copy(_clusterPosition, _clusterPosition + tArrayLength, rClusterPosition);
	}
	else
		rClusterPosition = _clusterPosition;

	rNparameterValues = tArrayLength;
}

void Clusterizer::setXclusterDistance(const unsigned int& pDx)
{
	info("setXclusterDistance: " + IntToStr(pDx));
	if (pDx > 1 && pDx < RAW_DATA_MAX_COLUMN - 1)
		_dx = pDx;
}

void Clusterizer::setYclusterDistance(const unsigned int& pDy)
{
	info("setYclusterDistance: " + IntToStr(pDy));
	if (pDy > 1 && pDy < RAW_DATA_MAX_ROW - 1)
		_dy = pDy;
}

void Clusterizer::setBCIDclusterDistance(const unsigned int& pDbCID)
{
	info("setBCIDclusterDistance: " + IntToStr(pDbCID));
	if (pDbCID < __MAXBCID - 1)
		_DbCID = pDbCID;
}

void Clusterizer::setMinClusterHits(const unsigned int& pMinNclusterHits)
{
	info("setMinClusterHits: " + IntToStr(pMinNclusterHits));
	_minClusterHits = pMinNclusterHits;
}

void Clusterizer::setMaxClusterHits(const unsigned int& pMaxNclusterHits)
{
	info("setMaxClusterHits: " + IntToStr(pMaxNclusterHits));
	_maxClusterHits = pMaxNclusterHits;
}

void Clusterizer::setMaxClusterHitTot(const unsigned int& pMaxClusterHitTot)
{
	info("setMaxClusterHitTot: " + IntToStr(pMaxClusterHitTot));
	_maxClusterHitTot = pMaxClusterHitTot;
}

void Clusterizer::setMaxHitTot(const unsigned int& pMaxHitTot)
{
	info("setMaxHitTot: " + IntToStr(pMaxHitTot));
	_maxHitTot = pMaxHitTot;
}

unsigned int Clusterizer::getNclusters()
{
	info("getNclusters:");
	return _Nclusters;
}

void Clusterizer::reset()
{
	info("reset()");
	initHitMap();
	clearResultHistograms();
	clearActualClusterData();
	clearActualEventVariables();
}

void Clusterizer::addHits(HitInfo*& rHitInfo, const unsigned int& rNhits)
{
	if (Basis::debugSet())
		debug("addHits(...,rNhits=" + IntToStr(rNhits) + ")");

	_hitInfo = rHitInfo;
	_Nclusters = 0;
	_NclustersHits = 0;

	if (rNhits > 0 && _actualEventNumber != 0 && rHitInfo[0].eventNumber == _actualEventNumber)
		warning("addHits: Hit chunks not aligned at events. Clusterizer will not work properly");

	for (unsigned int i = 0; i < rNhits; i++) {
		if (_actualEventNumber != rHitInfo[i].eventNumber) {
			if (_nHits > maxHitsPerEvent){
				warning("addHits: event " + LongIntToStr(_actualEventNumber) + ", too many hits(" + IntToStr(_nHits) + ">" + IntToStr(maxHitsPerEvent) + ") omit this event!");
				clearHitMap();
			}
			clusterize();
			addHitClusterInfo(i);
			clearActualEventVariables();
		}
		_actualEventNumber = rHitInfo[i].eventNumber;
		addHit(i);
	}
	//manually add remaining hit data
	clusterize();
	addHitClusterInfo(rNhits);
}

void Clusterizer::getHitCluster(ClusterHitInfo*& rClusterHitInfo, unsigned int& rSize, bool copy)
{
	debug("getHitCluster(...)");
	if (copy)
		std::copy(_clusterHitInfo, _clusterHitInfo + _clusterHitInfoSize, rClusterHitInfo);
	else
		rClusterHitInfo = _clusterHitInfo;
	rSize = _NclustersHits;
}

void Clusterizer::getCluster(ClusterInfo*& rClusterInfo, unsigned int& rSize, bool copy)
{
	debug("getCluster(...)");
	if (copy)
		std::copy(_clusterInfo, _clusterInfo + _clusterInfoSize, rClusterInfo);
	else
		rClusterInfo = _clusterInfo;
	rSize = _Nclusters;
}

bool Clusterizer::clusterize()
{
	if (Basis::debugSet()) {
		std::cout << "Clusterizer::clusterize(): Status:\n";
		std::cout << "  _nHits " << _nHits << std::endl;
		std::cout << "  _bCIDfirstHit " << _bCIDfirstHit << "\n";
		std::cout << "  _bCIDlastHit " << _bCIDlastHit << "\n";
		std::cout << "  _minColHitPos " << _minColHitPos << "\n";
		std::cout << "  _maxColHitPos " << _maxColHitPos << "\n";
		std::cout << "  _minRowHitPos " << _minRowHitPos << "\n";
		std::cout << "  _maxRowHitPos " << _maxRowHitPos << "\n";
	}

	_runTime = 0;

	for (int iBCID = _bCIDfirstHit; iBCID <= _bCIDlastHit; ++iBCID) {			//loop over the hit array starting from the first hit BCID to the last hit BCID
		for (int iCol = _minColHitPos; iCol <= _maxColHitPos; ++iCol) {		//loop over the hit array from the minimum to the maximum column with a hit
			for (int iRow = _minRowHitPos; iRow <= _maxRowHitPos; ++iRow) {	//loop over the hit array from the minimum to the maximum row with a hit
				if (hitExists(iCol, iRow, iBCID)) {								//if a hit in iCol,iRow,iBCID exists take this as a first hit of a cluster and do:
					clearActualClusterData();								//  clear the last cluster data
					_actualRelativeClusterBCID = iBCID;						//  set the minimum relative BCID [0:15] for the new cluster
					searchNextHits(iCol, iRow, iBCID);						//  find hits next to the actual one and update the actual cluster values, here the clustering takes place
					if (_actualClusterSize >= (int) _minClusterHits) {		//  only add cluster if it has at least _minClusterHits hits
						addCluster();										//  add cluster to output cluster array
						addClusterToResults();								//  add the actual cluster values to the histograms
						_actualClusterID++;									//  increase the cluster id for this event
					}
					else
						warning("clusterize: cluster size too small");
				}
				if (_nHits == 0)											//saves a lot of average run time, the loop is aborted if every hit is in a cluster (_nHits == 0)
					return true;
			}
		}
	}
	if (_nHits == 0)
		return true;

	error("clusterize: event " + LongIntToStr(_actualEventNumber) + ", only " + IntToStr(_actualClusterSize) + " of " + IntToStr(_nHits) + " hit clustered");
	clearHitMap();
	return false;
}

void Clusterizer::test()
{
	for (unsigned int i = 0; i < _clusterHitInfoSize; ++i) {
		std::cout << "_clusterHitInfo[" << i << "].eventNumber " << _clusterHitInfo[i].eventNumber << "\n";
		std::cout << "_clusterHitInfo[" << i << "].triggerNumber " << _clusterHitInfo[i].triggerNumber << "\n";
		std::cout << "_clusterHitInfo[" << i << "].relativeBCID " << (unsigned int) _clusterHitInfo[i].relativeBCID << "\n";
		std::cout << "_clusterHitInfo[" << i << "].LVLID " << (unsigned int) _clusterHitInfo[i].LVLID << "\n";
		std::cout << "_clusterHitInfo[" << i << "].column " << (unsigned int) _clusterHitInfo[i].column << "\n";
		std::cout << "_clusterHitInfo[" << i << "].row " << (unsigned int) _clusterHitInfo[i].row << "\n";
		std::cout << "_clusterHitInfo[" << i << "].tot " << (unsigned int) _clusterHitInfo[i].tot << "\n";
		std::cout << "_clusterHitInfo[" << i << "].BCID " << (unsigned int) _clusterHitInfo[i].BCID << "\n";
		std::cout << "_clusterHitInfo[" << i << "].triggerStatus " << (unsigned int) _clusterHitInfo[i].triggerStatus << "\n";
		std::cout << "_clusterHitInfo[" << i << "].serviceRecord " << (unsigned int) _clusterHitInfo[i].serviceRecord << "\n";
		std::cout << "_clusterHitInfo[" << i << "].eventStatus " << (unsigned int) _clusterHitInfo[i].eventStatus << "\n";
		std::cout << "_clusterHitInfo[" << i << "].clusterID " << (unsigned int) _clusterHitInfo[i].clusterID << "\n";
		std::cout << "_clusterHitInfo[" << i << "].isSeed " << (unsigned int) _clusterHitInfo[i].isSeed << "\n";
		std::cout << "_clusterHitInfo[" << i << "].clusterSize " << (unsigned int) _clusterHitInfo[i].clusterSize << "\n";
		std::cout << "_clusterHitInfo[" << i << "].nCluster " << (unsigned int) _clusterHitInfo[i].nCluster << "\n";
	}
	for (unsigned int i = 0; i < _clusterInfoSize; ++i) {
		std::cout << "_clusterInfo[" << i << "].eventNumber " << _clusterInfo[i].eventNumber << "\n";
		std::cout << "_clusterInfo[" << i << "].ID " << (unsigned int) _clusterInfo[i].ID << "\n";
		std::cout << "_clusterInfo[" << i << "].size " << (unsigned int) _clusterInfo[i].size << "\n";
		std::cout << "_clusterInfo[" << i << "].Tot " << (unsigned int) _clusterInfo[i].Tot << "\n";
		std::cout << "_clusterInfo[" << i << "].seed_column " << (unsigned int) _clusterInfo[i].seed_column << "\n";
		std::cout << "_clusterInfo[" << i << "].seed_row " << (unsigned int) _clusterInfo[i].seed_row << "\n";
		std::cout << "_clusterInfo[" << i << "].eventStatus " << (unsigned int) _clusterInfo[i].eventStatus << "\n";
	}
}

//private
void Clusterizer::addHit(const unsigned int& pHitIndex)
{
	debug("addHit");
	uint64_t tEvent = _hitInfo[pHitIndex].eventNumber;
	unsigned short tCol = _hitInfo[pHitIndex].column - 1;
	unsigned short tRow = _hitInfo[pHitIndex].row - 1;
	unsigned short tRelBcid = _hitInfo[pHitIndex].relativeBCID;
	unsigned short tTot = _hitInfo[pHitIndex].tot;
	float tCharge = -1;

	_actualEventStatus = _hitInfo[pHitIndex].eventStatus | _actualEventStatus;

	_nEventHits++;

	if (tTot > _maxHitTot)	// ommit hits with a tot that is too high
		return;

	if (_nHits == 0)
		_bCIDfirstHit = tRelBcid;

	if (tRelBcid > _bCIDlastHit)
		_bCIDlastHit = tRelBcid;

	if (tCol > _maxColHitPos)
		_maxColHitPos = tCol;
	if (tCol < _minColHitPos)
		_minColHitPos = tCol;
	if (tRow < _minRowHitPos)
		_minRowHitPos = tRow;
	if (tRow > _maxRowHitPos)
		_maxRowHitPos = tRow;

	if ((tCol > RAW_DATA_MAX_COLUMN) || (tRow > RAW_DATA_MAX_ROW))
		throw std::out_of_range("The column/row value is out of range. They have to start at 1!");

	if (_hitMap[(size_t) tCol + (size_t) tRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] == -1) {
		_hitMap[(size_t) tCol + (size_t) tRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] = tTot;
		_hitIndexMap[(size_t) tCol + (size_t) tRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] = pHitIndex;
		_nHits++;
	}
	else
		warning("addHit: event " + LongIntToStr(tEvent) + ", attempt to add the same hit col/row/rel.bcid=" + IntToStr(tCol) + "/" + IntToStr(tRow) + "/" + IntToStr(tRelBcid) + " again, ignored!");

	if (tCharge >= 0)
		_chargeMap[(size_t) tCol + (size_t) tRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tTot * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] = tCharge;

	if (_createClusterHitInfoArray) {
		if (_clusterHitInfo == 0)
			throw std::runtime_error("Cluster hit array is not defined and cannot be filled");
		_NclustersHits++;
		_clusterHitInfo[pHitIndex].eventNumber = _hitInfo[pHitIndex].eventNumber;
		_clusterHitInfo[pHitIndex].triggerNumber = _hitInfo[pHitIndex].triggerNumber;
		_clusterHitInfo[pHitIndex].relativeBCID = _hitInfo[pHitIndex].relativeBCID;
		_clusterHitInfo[pHitIndex].LVLID = _hitInfo[pHitIndex].LVLID;
		_clusterHitInfo[pHitIndex].column = _hitInfo[pHitIndex].column;
		_clusterHitInfo[pHitIndex].row = _hitInfo[pHitIndex].row;
		_clusterHitInfo[pHitIndex].tot = _hitInfo[pHitIndex].tot;
		_clusterHitInfo[pHitIndex].TDC = _hitInfo[pHitIndex].TDC;
		_clusterHitInfo[pHitIndex].TDCtimeStamp = _hitInfo[pHitIndex].TDCtimeStamp;
		_clusterHitInfo[pHitIndex].BCID = _hitInfo[pHitIndex].BCID;
		_clusterHitInfo[pHitIndex].triggerStatus = _hitInfo[pHitIndex].triggerStatus;
		_clusterHitInfo[pHitIndex].serviceRecord = _hitInfo[pHitIndex].serviceRecord;
		_clusterHitInfo[pHitIndex].eventStatus = _hitInfo[pHitIndex].eventStatus;
		_clusterHitInfo[pHitIndex].isSeed = 0;
		_clusterHitInfo[pHitIndex].clusterSize = 666;
		_clusterHitInfo[pHitIndex].nCluster = 666;
	}
}

void Clusterizer::searchNextHits(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid)
{
	if (Basis::debugSet()) {
		std::cout << "Clusterizer::searchNextHits(...): status: " << std::endl;
		std::cout << "  _nHits " << _nHits << std::endl;
		std::cout << "  _actualRelativeClusterBCID " << _actualRelativeClusterBCID << std::endl;
		std::cout << "  pRelBcid " << pRelBcid << std::endl;
		std::cout << "  _DbCID " << _DbCID << std::endl;
		std::cout << "  pCol " << pCol << std::endl;
		std::cout << "  pRow " << pRow << std::endl;
		showHits();
	}

	_actualClusterSize++;	//increase the total hits for this cluster value

	short unsigned int tTot = _hitMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) pRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW];

	if (tTot >= _actualClusterMaxTot && tTot <= _maxHitTot) {	//seed finding
		_actualClusterSeed_column = pCol;
		_actualClusterSeed_row = pRow;
		_actualClusterSeed_relbcid = pRelBcid;
		_actualClusterMaxTot = tTot;
	}

	if (_createClusterHitInfoArray) {
		if (_clusterHitInfo == 0)
			throw std::runtime_error("Cluster hit array is not defined and cannot be filled");
		if (_hitIndexMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) pRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] < _clusterHitInfoSize)
			_clusterHitInfo[_hitIndexMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) pRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW]].clusterID = _actualClusterID;
		else {
			std::stringstream tInfo;
			tInfo << "Clusterizer: searchNextHits(...): hit index " << _hitIndexMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) pRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] << " is out of range (0.." << _clusterHitInfoSize << ")";
			throw std::out_of_range(tInfo.str());
		}
	}

	if (tTot > (short int) _maxClusterHitTot || _actualClusterSize > (int) _maxClusterHits){	//omit cluster with a hit tot higher than _maxClusterHitTot, clustering is not aborted to delete all hits from this cluster from the hit array
		_abortCluster = true;
	}

	_actualClusterTot += tTot;		//add tot of the hit to the cluster tot
	_actualClusterCharge += _chargeMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tTot * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW];	//add charge of the hit to the cluster tot
	_actualClusterX += (float) ((float) pCol + 0.5) * (_chargeMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tTot * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] + 1);	//add x position of actual cluster weigthed by the charge
	_actualClusterY += (float) ((float) pRow + 0.5) * (_chargeMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) tTot * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] + 1);	//add y position of actual cluster weigthed by the charge

	if (Basis::debugSet()) {
//		std::cout<<"Clusterizer::searchNextHits"<<std::endl;
//		std::cout<<"  _chargeMap[pCol][pRow][tTot] "<<_chargeMap[pCol][pRow][tTot]<<std::endl;
//		std::cout<<"  ((double) pCol+0.5) * __PIXELSIZEX "<<((double) pCol+0.5) * __PIXELSIZEX<<std::endl;
//		std::cout<<"  ((double) pRow+0.5) * __PIXELSIZEY "<<((double) pRow+0.5) * __PIXELSIZEY<<std::endl;
//		std::cout<<"  _actualClusterX "<<_actualClusterX<<std::endl;
//		std::cout<<"  _actualClusterY "<<_actualClusterY<<std::endl;
	}

	if (deleteHit(pCol, pRow, pRelBcid))	//delete hit and return if no hit is in the array anymore
		return;

	//values set to true to avoid double searches in one direction with different step sizes
	bool tHitUp = false;
	bool tHitUpRight = false;
	bool tHitRight = false;
	bool tHitDownRight = false;
	bool tHitDown = false;
	bool tHitDownLeft = false;
	bool tHitLeft = false;
	bool tHitUpLeft = false;

	//search around the pixel in time and space
	for (unsigned int iDbCID = _actualRelativeClusterBCID; iDbCID <= _actualRelativeClusterBCID + _DbCID && iDbCID <= (unsigned int) _bCIDlastHit; ++iDbCID) {	//loop over the BCID window width starting from the actual cluster BCID
		for (int iDx = 1; iDx <= (int) _dx; ++iDx) {									//loop over the the x range
			for (int iDy = 1; iDy <= (int) _dy; ++iDy) {								//loop over the the y range
				_runTime++;
				if (hitExists(pCol, pRow + iDy, iDbCID) && !tHitUp) {					//search up
					tHitUp = true;
					searchNextHits(pCol, pRow + iDy, iDbCID);
				}
				if (hitExists(pCol + iDx, pRow + iDy, iDbCID) && !tHitUpRight) {		//search up, right
					tHitUpRight = true;
					searchNextHits(pCol + iDx, pRow + iDy, iDbCID);
				}
				if (hitExists(pCol + iDx, pRow, iDbCID) && !tHitRight) {				//search right
					tHitRight = true;
					searchNextHits(pCol + iDx, pRow, iDbCID);
				}
				if (hitExists(pCol + iDx, pRow - iDy, iDbCID) && !tHitDownRight) {		//search down, right
					tHitDownRight = true;
					searchNextHits(pCol + iDx, pRow - iDy, iDbCID);
				}
				if (hitExists(pCol, pRow - iDy, iDbCID) && !tHitDown) {				//search down
					tHitDown = true;
					searchNextHits(pCol, pRow - iDy, iDbCID);
				}
				if (hitExists(pCol - iDx, pRow - iDy, iDbCID) && !tHitDownLeft) {		//search down, left
					tHitDownLeft = true;
					searchNextHits(pCol - iDx, pRow - iDy, iDbCID);
				}
				if (hitExists(pCol - iDx, pRow, iDbCID) && !tHitLeft) {				//search left
					tHitLeft = true;
					searchNextHits(pCol - iDx, pRow, iDbCID);
				}
				if (hitExists(pCol - iDx, pRow + iDy, iDbCID) && !tHitUpLeft) {		//search up, left
					tHitUpLeft = true;
					searchNextHits(pCol - iDx, pRow + iDy, iDbCID);
				}
			}
		}
	}
}

bool Clusterizer::deleteHit(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid)
{
	_hitMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) pRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] = -1;
	_nHits--;
	if (_nHits == 0) {
		_minColHitPos = RAW_DATA_MAX_COLUMN - 1;
		_maxColHitPos = 0;
		_minRowHitPos = RAW_DATA_MAX_ROW - 1;
		_maxRowHitPos = 0;
		_bCIDfirstHit = -1;
		_bCIDlastHit = -1;
		return true;
	}
	return false;
}

bool Clusterizer::hitExists(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid)
{
	if (pCol >= 0 && pCol < RAW_DATA_MAX_COLUMN && pRow >= 0 && pRow < RAW_DATA_MAX_ROW && pRelBcid >= 0 && pRelBcid < __MAXBCID)
		if (_hitMap[(size_t) pCol + (size_t) pRow * (size_t) RAW_DATA_MAX_COLUMN + (size_t) pRelBcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] != -1)
			return true;
	return false;
}

void Clusterizer::initChargeCalibMap()
{
	info("initChargeCalibMap");

	for (size_t iCol = 0; iCol < (size_t) RAW_DATA_MAX_COLUMN; ++iCol) {
		for (size_t iRow = 0; iRow < (size_t) RAW_DATA_MAX_ROW; ++iRow) {
			for (size_t iTot = 0; iTot < (size_t) __MAXTOTLOOKUP; ++iTot)
				_chargeMap[iCol + iRow * RAW_DATA_MAX_COLUMN + iTot * RAW_DATA_MAX_COLUMN * RAW_DATA_MAX_ROW] = (float) (iTot + 1);
		}
	}
}

void Clusterizer::initHitMap()
{
	info("initHitMap");

	for (size_t iCol = 0; iCol < (size_t) RAW_DATA_MAX_COLUMN; ++iCol) {
		for (size_t iRow = 0; iRow < (size_t) RAW_DATA_MAX_ROW; ++iRow) {
			for (size_t iRbCID = 0; iRbCID < (size_t) __MAXBCID; ++iRbCID)
				_hitMap[iCol + iRow * RAW_DATA_MAX_COLUMN + iRbCID * RAW_DATA_MAX_COLUMN * RAW_DATA_MAX_ROW] = -1;
		}
	}

	_minColHitPos = RAW_DATA_MAX_COLUMN - 1;
	_maxColHitPos = 0;
	_minRowHitPos = RAW_DATA_MAX_ROW - 1;
	_maxRowHitPos = 0;
	_bCIDfirstHit = -1;
	_bCIDlastHit = -1;
	_nHits = 0;
}

void Clusterizer::addClusterToResults()
{
	if (!_abortCluster) {
		//histogramming of the results
		if (_actualClusterSize < __MAXCLUSTERHITSBINS)
			_clusterHits[_actualClusterSize]++;
		else
			throw std::out_of_range("Clusterizer::addClusterToResults: cluster size does not fit into cluster size histogram");
		if (_actualClusterTot < __MAXTOTBINS && _actualClusterSize < __MAXCLUSTERHITSBINS) {
			_clusterTots[(size_t)(_actualClusterTot) + (size_t) _actualClusterSize * (size_t) __MAXTOTBINS]++;
			_clusterTots[(size_t) _actualClusterTot]++;	//cluster size = 0 contains all cluster sizes
		}
		else {
			std::stringstream tInfo;
			tInfo << "Clusterizer::addClusterToResults: cluster tot " << _actualClusterTot << " with cluster size " << _actualClusterSize << " does not fit into cluster tot histogram.";
			info(tInfo.str());
		}

//		if((int) _actualClusterCharge<__MAXCHARGEBINS && _actualClusterSize<__MAXCLUSTERHITSBINS){
//			_clusterCharges[(int) _actualClusterCharge][0]++;
//			_clusterCharges[(int) _actualClusterCharge][_actualClusterSize]++;	//cluster size = 0 contains all cluster sizes
//		}
//		if(_actualClusterCharge > 0){	//avoid division by zero
//			int tActualClusterXbin = (int) (_actualClusterX/(__PIXELSIZEX*RAW_DATA_MAX_COLUMN) * __MAXPOSXBINS);
//			int tActualClusterYbin = (int) (_actualClusterY/(__PIXELSIZEY*RAW_DATA_MAX_ROW) * __MAXPOSYBINS);
//			if(tActualClusterXbin < __MAXPOSXBINS && tActualClusterYbin < __MAXPOSYBINS)
//				_clusterPosition[tActualClusterXbin][tActualClusterYbin]++;
//		}
	}
}

void Clusterizer::allocateClusterHitArray()
{
	debug(std::string("allocateClusterHitArray()"));
	try {
		_clusterHitInfo = new ClusterHitInfo[_clusterHitInfoSize];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateClusterHitArray(): ") + std::string(exception.what()));
		throw;
	}
}

void Clusterizer::deleteClusterHitArray()
{
	debug(std::string("deleteClusterHitArray()"));
	if (_clusterHitInfo == 0)
		return;
	delete[] _clusterHitInfo;
	_clusterHitInfo = 0;
}

void Clusterizer::allocateClusterInfoArray()
{
	debug(std::string("allocateClusterInfoArray()"));
	try {
		_clusterInfo = new ClusterInfo[_clusterInfoSize];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateClusterInfoArray(): ") + std::string(exception.what()));
		throw;
	}
}

void Clusterizer::deleteClusterInfoArray()
{
	debug(std::string("deleteClusterInfoArray()"));
	if (_clusterInfo == 0)
		return;
	delete[] _clusterInfo;
	_clusterInfo = 0;
}

void Clusterizer::allocateHitMap()
{
	info("allocateHitMap()");
	deleteHitMap();
	try {
		_hitMap = new short[(size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW * (size_t) __MAXBCID];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateHitMap: ") + std::string(exception.what()));
	}
}

void Clusterizer::clearHitMap()
{
	debug("Clusterizer::clearHitMap\n");

	if (_nHits != 0) {
		for (size_t iCol = 0; iCol < (size_t) RAW_DATA_MAX_COLUMN; ++iCol) {
			for (size_t iRow = 0; iRow < (size_t) RAW_DATA_MAX_ROW; ++iRow) {
				for (size_t iRbCID = 0; iRbCID < (size_t) __MAXBCID; ++iRbCID) {
					if (_hitMap[iCol + iRow * RAW_DATA_MAX_COLUMN + iRbCID * RAW_DATA_MAX_COLUMN * RAW_DATA_MAX_ROW] != -1) {
						_hitMap[iCol + iRow * RAW_DATA_MAX_COLUMN + iRbCID * RAW_DATA_MAX_COLUMN * RAW_DATA_MAX_ROW] = -1;
						_nHits--;
						if (_nHits == 0)
							goto exitLoop;
						//the fastest way to exit a nested loop
					}
				}
			}
		}
	}

	exitLoop: _minColHitPos = RAW_DATA_MAX_COLUMN - 1;
	_maxColHitPos = 0;
	_minRowHitPos = RAW_DATA_MAX_ROW - 1;
	_maxRowHitPos = 0;
	_bCIDfirstHit = -1;
	_bCIDlastHit = -1;
	_nHits = 0;
}

void Clusterizer::deleteHitMap()
{
	info("deleteHitMap()");
	if (_hitMap != 0)
		delete[] _hitMap;
	_hitMap = 0;
}

void Clusterizer::allocateHitIndexMap()
{
	info("allocateHitIndexMap()");
	deleteHitIndexMap();
	try {
		_hitIndexMap = new unsigned int[(size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW * (size_t) __MAXBCID];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateHitIndexMap: ") + std::string(exception.what()));
	}
}

void Clusterizer::deleteHitIndexMap()
{
	info(std::string("deleteHitIndexMap()"));
	if (_hitIndexMap != 0)
		delete[] _hitIndexMap;
	_hitIndexMap = 0;
}

void Clusterizer::allocateChargeMap()
{
	info("allocateChargeMap()");
	deleteChargeMap();
	try {
		_chargeMap = new float[(size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW * (size_t) __MAXTOTLOOKUP];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateChargeMap: ") + std::string(exception.what()));
	}
}

void Clusterizer::allocateResultHistograms()
{
	info("allocateResultHistograms()");
	deleteResultHistograms();
	try {
		_clusterTots = new unsigned int[(size_t)__MAXCLUSTERHITSBINS * (size_t) __MAXTOTBINS];
		_clusterCharges = new unsigned int[(size_t)__MAXCLUSTERHITSBINS * (size_t) __MAXCHARGEBINS];
		_clusterHits = new unsigned int[(size_t) __MAXCLUSTERHITSBINS];
		_clusterPosition = new unsigned int[(size_t) __MAXPOSYBINS * (size_t) __MAXPOSXBINS];
	} catch (std::bad_alloc& exception) {
		error(std::string("allocateResultHistograms: ") + std::string(exception.what()));
	}
}

void Clusterizer::clearResultHistograms()  // this function takes a long time
{
	info("clearResultHistograms()");
	for (size_t iTot = 0; iTot < (size_t) __MAXTOTBINS; ++iTot) {
		for (size_t iClusterHit = 0; iClusterHit < (size_t) __MAXCLUSTERHITSBINS; ++iClusterHit)
			_clusterTots[iTot + iClusterHit * (size_t) __MAXTOTBINS] = 0;
	}
//	for(unsigned int iCharge = 0; iCharge<__MAXCHARGEBINS; ++iCharge)
//		for(unsigned int iClusterHit = 0; iClusterHit<__MAXCLUSTERHITSBINS; ++iClusterHit)
//			_clusterCharges[(size_t)iCharge + (size_t)iClusterHit*(size_t)__MAXCLUSTERHITSBINS] = 0;
//	for(unsigned int iX = 0; iX<__MAXPOSXBINS; ++iX)
//			for(unsigned int iY = 0; iY<__MAXPOSYBINS; ++iY)
//				_clusterPosition[(size_t)iX + (size_t)iY*(size_t)__MAXPOSXBINS] = 0;
	for (size_t iClusterHit = 0; iClusterHit < (size_t) __MAXCLUSTERHITSBINS; ++iClusterHit)
		_clusterHits[iClusterHit] = 0;
}

void Clusterizer::deleteResultHistograms()
{
	info(std::string("deleteResultHistograms()"));
	if (_clusterTots != 0)
		delete[] _clusterTots;
	if (_clusterCharges != 0)
		delete[] _clusterCharges;
	if (_clusterHits != 0)
		delete[] _clusterHits;
	if (_clusterPosition != 0)
		delete[] _clusterPosition;
	_clusterTots = 0;
	_clusterCharges = 0;
	_clusterHits = 0;
	_clusterPosition = 0;
}

void Clusterizer::deleteChargeMap()
{
	info(std::string("deleteChargeMap()"));
	if (_chargeMap != 0)
		delete[] _chargeMap;
	_chargeMap = 0;
}

void Clusterizer::clearActualClusterData()
{
	_actualClusterTot = 0;
	_actualClusterSize = 0;
	_actualClusterCharge = 0;
	_actualRelativeClusterBCID = 0;
	_actualClusterX = 0;
	_actualClusterY = 0;
	_actualClusterMaxTot = 0;
	_actualClusterSeed_column = 0;
	_actualClusterSeed_row = 0;
	_actualClusterSeed_relbcid = 0;
	_abortCluster = false;					//reset abort flag for the new cluster
}

void Clusterizer::clearActualEventVariables()
{
	_actualEventNumber = 0;
	_actualEventStatus = 0;
	_actualClusterID = 0;
	_nEventHits = 0;
}

void Clusterizer::showHits()
{
	info("ShowHits");
	if (_nHits < 100) {
		for (size_t iCol = 0; iCol < (size_t) RAW_DATA_MAX_COLUMN; ++iCol) {
			for (size_t iRow = 0; iRow < (size_t) RAW_DATA_MAX_ROW; ++iRow) {
				for (size_t iRbCID = 0; iRbCID < (size_t) __MAXBCID; ++iRbCID) {
					if (_hitMap[ iCol + iRow * RAW_DATA_MAX_COLUMN + iRbCID * RAW_DATA_MAX_COLUMN * RAW_DATA_MAX_ROW] != -1)
						std::cout << "x/y/BCID/Tot = " << iCol << "/" << iRow << "/" << iRbCID << "/" << _hitMap[iCol + iRow * RAW_DATA_MAX_COLUMN + iRbCID * RAW_DATA_MAX_COLUMN * RAW_DATA_MAX_ROW] << std::endl;
				}
			}
		}
	}
	else
		std::cout << "TOO MANY HITS =  " << _nHits << " TO SHOW!" << std::endl;
}

void Clusterizer::addCluster()
{
	_actualClusterX /= (_actualClusterCharge + _actualClusterSize);  // normalize cluster x position
	_actualClusterY /= (_actualClusterCharge + _actualClusterSize);  // normalize cluster y position
	if (_createClusterInfoArray) {
		if (_clusterInfo == 0)
			throw std::runtime_error("Cluster info array is not defined and cannot be filled");
		if (_Nclusters < _clusterInfoSize) {
			_clusterInfo[_Nclusters].eventNumber = _actualEventNumber;
			_clusterInfo[_Nclusters].ID = _actualClusterID;
			_clusterInfo[_Nclusters].size = _actualClusterSize;
			_clusterInfo[_Nclusters].Tot = _actualClusterTot;
			_clusterInfo[_Nclusters].charge = _actualClusterCharge;
			_clusterInfo[_Nclusters].seed_column = _actualClusterSeed_column + 1;
			_clusterInfo[_Nclusters].seed_row = _actualClusterSeed_row + 1;
			_clusterInfo[_Nclusters].mean_column = (float) (_actualClusterX + 1.);
			_clusterInfo[_Nclusters].mean_row = (float) (_actualClusterY + 1.);
			_clusterInfo[_Nclusters].eventStatus = _actualEventStatus;
		}
		else
			throw std::out_of_range("Too many clusters attempt to be stored in cluster array");
	}

	_Nclusters++;

	//set cluster seed infos
	if (_createClusterHitInfoArray) {
		if (_hitIndexMap[(size_t) _actualClusterSeed_column + (size_t) _actualClusterSeed_row * (size_t) RAW_DATA_MAX_COLUMN + (size_t) _actualClusterSeed_relbcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW] < _clusterHitInfoSize)
			_clusterHitInfo[_hitIndexMap[(size_t) _actualClusterSeed_column + (size_t) _actualClusterSeed_row * (size_t) RAW_DATA_MAX_COLUMN + (size_t) _actualClusterSeed_relbcid * (size_t) RAW_DATA_MAX_COLUMN * (size_t) RAW_DATA_MAX_ROW]].isSeed = 1;
		else
			throw std::out_of_range("Clusterizer: addCluster(): hit index is out of range");
	}
}

void Clusterizer::addHitClusterInfo(const unsigned int& pHitIndex)
{
	if (_createClusterHitInfoArray) {
		if (_clusterInfo == 0)
			throw std::runtime_error("Cluster info array is not defined but needed");
		if (_clusterHitInfo == 0)
			throw std::runtime_error("Cluster hit array is not defined and cannot be filled");
		for (unsigned int iHitIndex = pHitIndex - _nEventHits; iHitIndex < pHitIndex; ++iHitIndex) {   // loop over cluster hits of actual event
			unsigned int clusterIndex = _Nclusters - _actualClusterID + _clusterHitInfo[iHitIndex].clusterID;
			_clusterHitInfo[iHitIndex].clusterSize = _clusterInfo[clusterIndex].size;
			_clusterHitInfo[iHitIndex].nCluster = _actualClusterID;
		}
	}
}

