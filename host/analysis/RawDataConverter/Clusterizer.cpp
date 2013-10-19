#include "Clusterizer.h"

Clusterizer::Clusterizer(void)
{
	setSourceFileName("Clusterizer");
	_dx = 1;
	_dy = 1;
	_DbCID = 0;
	_minClusterHits = 1;
	_maxClusterHits = 9;	//std. setting for maximum hits per cluster allowed
	_runTime = 0;
	_nHits = 0;
	_maxClusterHitTot = 13;
	_minColHitPos = RAW_DATA_MAX_COLUMN-1;
	_maxColHitPos = 0;
	_minRowHitPos = RAW_DATA_MAX_ROW-1;
	_maxRowHitPos = 0;
	initChargeCalibMap();
	initHitMap();
	clearClusterMaps();
	clearActualClusterData();
	clearActualEventVariables();
	_clusterHitInfo = 0;
	_clusterInfo = 0;
	_lateHitTot = 14;
}

Clusterizer::~Clusterizer(void)
{

}

void Clusterizer::setClusterHitInfoArray(ClusterHitInfo*& rClusterHitInfo, const unsigned int& rSize)
{
	_clusterHitInfo = rClusterHitInfo;
	_clusterHitInfoSize = rSize;
	_NclustersHits = 0;
}

void Clusterizer::setClusterInfoArray(ClusterInfo*& rClusterHitInfo, const unsigned int& rSize)
{
	_clusterInfo = rClusterHitInfo;
	_clusterInfoSize = rSize;
	_Nclusters = 0;
}

void Clusterizer::setXclusterDistance(const unsigned int& pDx)
{
	debug("setXclusterDistance: "+IntToStr(pDx));
	if (pDx > 1 && pDx < RAW_DATA_MAX_COLUMN-1)
		_dx = pDx;
}

void Clusterizer::setYclusterDistance(const unsigned int& pDy)
{
	debug("setYclusterDistance: "+IntToStr(pDy));
	if (pDy > 1 && pDy < RAW_DATA_MAX_ROW-1)
		_dy = pDy;
}

void Clusterizer::setBCIDclusterDistance(const unsigned int& pDbCID)
{
	debug("setBCIDclusterDistance: "+IntToStr(pDbCID));
	if (pDbCID < __MAXBCID-1)
		_DbCID = pDbCID;
}

void Clusterizer::setMinClusterHits(const unsigned int& pMinNclusterHits)
{
	debug("setMinClusterHits: "+IntToStr(pMinNclusterHits));
	_minClusterHits = pMinNclusterHits;
}

void Clusterizer::setMaxClusterHits(const unsigned int& pMaxNclusterHits)
{
	debug("setMaxClusterHits: "+IntToStr(pMaxNclusterHits));
	_maxClusterHits = pMaxNclusterHits;
}

void Clusterizer::setMaxClusterHitTot(const unsigned int& pMaxClusterHitTot)
{
	debug("setMaxClusterHitTot: "+IntToStr(pMaxClusterHitTot));
	_maxClusterHitTot = pMaxClusterHitTot;
}

void Clusterizer::setLateHitTot(const unsigned int&  pLateHitTot)
{
	_lateHitTot = pLateHitTot;
}

unsigned int Clusterizer::getNclusters()
{
	return _Nclusters;
}

void Clusterizer::addHits(HitInfo*& rHitInfo, const unsigned int& rNhits)
{
  if(Basis::debugSet())
	  debug("addHits(...,rNhits="+IntToStr(rNhits)+")");

  _hitInfo = rHitInfo;
  _Nclusters = 0;

  if(rNhits>0 && _actualEventNumber != 0 && rHitInfo[0].eventNumber == _actualEventNumber)
	  warning("addHits: hits not aligned at events, clusterizer will not work properly");

  for(unsigned int i = 0; i<rNhits; i++){
	  if(_actualEventNumber != rHitInfo[i].eventNumber){
		  clusterize();
		  clearActualEventVariables();
	  }
	  _actualEventNumber = rHitInfo[i].eventNumber;
	  addHit(i);
  }
  //manually add remaining hit data
  clusterize();
}

bool Clusterizer::clusterize()
{
	if(Basis::debugSet()){
		std::cout<<"Clusterizer::clusterize(): Status:\n";
		std::cout<<"  _nHits "<<_nHits<<std::endl;
		std::cout<<"  _bCIDfirstHit "<<_bCIDfirstHit<<"\n";
		std::cout<<"  _bCIDlastHit "<<_bCIDlastHit<<"\n";
		std::cout<<"  _minColHitPos "<<_minColHitPos<<"\n";
		std::cout<<"  _maxColHitPos "<<_maxColHitPos<<"\n";
		std::cout<<"  _minRowHitPos "<<_minRowHitPos<<"\n";
		std::cout<<"  _maxRowHitPos "<<_maxRowHitPos<<"\n";
	}

	_runTime = 0;

	for(int iBCID = _bCIDfirstHit; iBCID <= _bCIDlastHit; ++iBCID){			//loop over the hit array starting from the first hit BCID to the last hit BCID
		for(int iCol = _minColHitPos; iCol <= _maxColHitPos; ++iCol){		//loop over the hit array from the minimum to the maximum column with a hit
			for(int iRow = _minRowHitPos; iRow <= _maxRowHitPos; ++iRow){	//loop over the hit array from the minimum to the maximum row with a hit
				if(hitExists(iCol,iRow,iBCID)){								//if a hit in iCol,iRow,iBCID exists take this as a first hit of a cluster and do:
					clearActualClusterData();								//  clear the last cluster data
					_actualRelativeClusterBCID = iBCID;						//  set the minimum relative BCID [0:15] for the new cluster
					searchNextHits(iCol, iRow, iBCID);						//  find hits next to the actual one and update the actual cluster values, here the clustering takes place
					if (_actualClusterSize >= (int) _minClusterHits){		//  only add cluster if it has at least _minClusterHits hits
						addClusterToResults();								//  add the actual cluster values to the result histograms
						addCluster();
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

	warning("Clusterizer::clusterize: NOT ALL HITS CLUSTERED!");
	showHits();
	return false;
}

void Clusterizer::test()
{
	_clusterHitInfo[0].eventNumber = 666;
	for(unsigned int i=0; i<_clusterHitInfoSize; ++i){
		std::cout<<"_clusterHitInfo["<<i<<"].eventNumber "<<_clusterHitInfo[i].eventNumber<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].triggerNumber "<<_clusterHitInfo[i].triggerNumber<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].relativeBCID "<<(unsigned int)_clusterHitInfo[i].relativeBCID<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].LVLID "<<(unsigned int)_clusterHitInfo[i].LVLID<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].column "<<(unsigned int)_clusterHitInfo[i].column<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].row "<<(unsigned int)_clusterHitInfo[i].row<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].tot "<<(unsigned int)_clusterHitInfo[i].tot<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].BCID "<<(unsigned int)_clusterHitInfo[i].BCID<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].triggerStatus "<<(unsigned int)_clusterHitInfo[i].triggerStatus<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].serviceRecord "<<(unsigned int)_clusterHitInfo[i].serviceRecord<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].eventStatus "<<(unsigned int)_clusterHitInfo[i].eventStatus<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].clusterID "<<(unsigned int)_clusterHitInfo[i].clusterID<<"\n";
		std::cout<<"_clusterHitInfo["<<i<<"].isSeed "<<(unsigned int)_clusterHitInfo[i].isSeed<<"\n";
	}
	for(unsigned int i=0; i<_clusterInfoSize; ++i){
		std::cout<<"_clusterInfo["<<i<<"].eventNumber "<<_clusterInfo[i].eventNumber<<"\n";
		std::cout<<"_clusterInfo["<<i<<"].ID "<<(unsigned int)_clusterInfo[i].ID<<"\n";
		std::cout<<"_clusterInfo["<<i<<"].size "<<(unsigned int)_clusterInfo[i].size<<"\n";
		std::cout<<"_clusterInfo["<<i<<"].Tot "<<(unsigned int)_clusterInfo[i].Tot<<"\n";
		std::cout<<"_clusterInfo["<<i<<"].seed_column "<<(unsigned int)_clusterInfo[i].seed_column<<"\n";
		std::cout<<"_clusterInfo["<<i<<"].seed_row "<<(unsigned int)_clusterInfo[i].seed_row<<"\n";
		std::cout<<"_clusterInfo["<<i<<"].eventStatus "<<(unsigned int)_clusterInfo[i].eventStatus<<"\n";
	}
}

//private
void Clusterizer::addHit(const unsigned int& pHitIndex)
{
	debug("addHit");
	unsigned long tEvent = _hitInfo[pHitIndex].eventNumber;
	unsigned short tCol = _hitInfo[pHitIndex].column-1;
	unsigned short tRow = _hitInfo[pHitIndex].row-1;
	unsigned short tRelBcid = _hitInfo[pHitIndex].relativeBCID;
	unsigned short tTot = _hitInfo[pHitIndex].tot;
	float tCharge = -1;

	if(_nHits == 0)
		_bCIDfirstHit = tRelBcid;

	if(tRelBcid > _bCIDlastHit)
		_bCIDlastHit = tRelBcid;

	if(tCol > _maxColHitPos)
		_maxColHitPos = tCol;
	if(tCol < _minColHitPos)
		_minColHitPos = tCol;
	if(tRow < _minRowHitPos)
		_minRowHitPos = tRow;
	if(tRow > _maxRowHitPos)
		_maxRowHitPos = tRow;

	if(_hitMap[tCol][tRow][tRelBcid] == -1){
		_hitMap[tCol][tRow][tRelBcid] = tTot;
		_hitIndexMap[tCol][tRow][tRelBcid] = pHitIndex;
		_nHits++;
	}
	else
		warning("addHit: event "+IntToStr(tEvent)+", attempt to add the same hit col/row/rel.bcid="+IntToStr(tCol)+"/"+IntToStr(tRow)+"/"+IntToStr(tRelBcid)+" again, ignored!");

	if (tCharge >= 0)
		_chargeMap[tCol][tRow][tTot] = tCharge;

	_clusterHitInfo[pHitIndex].eventNumber = _hitInfo[pHitIndex].eventNumber;
	_clusterHitInfo[pHitIndex].triggerNumber = _hitInfo[pHitIndex].triggerNumber;
	_clusterHitInfo[pHitIndex].relativeBCID = _hitInfo[pHitIndex].relativeBCID;
	_clusterHitInfo[pHitIndex].LVLID = _hitInfo[pHitIndex].LVLID;
	_clusterHitInfo[pHitIndex].column = _hitInfo[pHitIndex].column;
	_clusterHitInfo[pHitIndex].row = _hitInfo[pHitIndex].row;
	_clusterHitInfo[pHitIndex].tot = _hitInfo[pHitIndex].tot;
	_clusterHitInfo[pHitIndex].BCID = _hitInfo[pHitIndex].BCID;
	_clusterHitInfo[pHitIndex].triggerStatus = _hitInfo[pHitIndex].triggerStatus;
	_clusterHitInfo[pHitIndex].serviceRecord = _hitInfo[pHitIndex].serviceRecord;
	_clusterHitInfo[pHitIndex].eventStatus = _hitInfo[pHitIndex].eventStatus;
	_clusterHitInfo[pHitIndex].isSeed = 0;
}

void Clusterizer::searchNextHits(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid)
{
	if(Basis::debugSet()){
		std::cout<<"Clusterizer::searchNextHits(...): status: "<<std::endl;
		std::cout<<"  _nHits "<<_nHits<<std::endl;
		std::cout<<"  _actualRelativeClusterBCID "<<_actualRelativeClusterBCID<<std::endl;
		std::cout<<"  pRelBcid "<<pRelBcid<<std::endl;
		std::cout<<"  _DbCID "<<_DbCID<<std::endl;
		std::cout<<"  pCol "<<pCol<<std::endl;
		std::cout<<"  pRow "<<pRow<<std::endl;
		showHits();
	}

	_actualClusterSize++;	//increase the total hits for this cluster value

	short unsigned int tTot = _hitMap[pCol][pRow][pRelBcid];

	if (tTot >= _actualClusterMaxTot && tTot < _lateHitTot){
		_actualClusterSeed_column = pCol;
		_actualClusterSeed_row = pRow;
		_actualClusterSeed_relbcid = pRelBcid;
		_actualClusterMaxTot = tTot;
	}

	if(_hitIndexMap[pCol][pRow][pRelBcid] < _clusterHitInfoSize)
		_clusterHitInfo[_hitIndexMap[pCol][pRow][pRelBcid]].clusterID = _actualClusterID;
	else
		throw std::out_of_range("hit index is out of range");

	if(tTot > (short int) _maxClusterHitTot)	//omit cluster with a hit tot higher than _maxClusterHitTot, clustering is not aborted to delete all hits from this cluster from the hit array
		_abortCluster = true;

	if(_actualClusterSize > (int) _maxClusterHits)		//omit cluster if it has more hits than _maxClusterHits, clustering is not aborted to delete all hits from this cluster from the hit array
		_abortCluster = true;

	_actualClusterTot+=tTot;		//add tot of the hit to the cluster tot
	_actualClusterCharge+=_chargeMap[pCol][pRow][tTot];	//add charge of the hit to the cluster tot
	_actualClusterX+=((double) pCol+0.5) * __PIXELSIZEX * _chargeMap[pCol][pRow][tTot];	//add x position of actual cluster weigthed by the charge
	_actualClusterY+=((double) pRow+0.5) * __PIXELSIZEY * _chargeMap[pCol][pRow][tTot];	//add y position of actual cluster weigthed by the charge

	if(Basis::debugSet()){
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
	for(unsigned int iDbCID = _actualRelativeClusterBCID; iDbCID <= _actualRelativeClusterBCID +_DbCID && iDbCID <= (unsigned int) _bCIDlastHit; ++iDbCID){	//loop over the BCID window width starting from the actual cluster BCID
		for(int iDx = 1; iDx <= (int) _dx; ++iDx){									//loop over the the x range
			for(int iDy = 1; iDy <= (int) _dy; ++iDy){								//loop over the the y range
				_runTime++;
				if(hitExists(pCol,pRow+iDy,iDbCID) && !tHitUp){					//search up
					tHitUp = true;
					searchNextHits(pCol, pRow+iDy, iDbCID);
				}
				if(hitExists(pCol+iDx,pRow+iDy,iDbCID) && !tHitUpRight){		//search up, right
					tHitUpRight = true;
					searchNextHits(pCol+iDx, pRow+iDy, iDbCID);
				}
				if(hitExists(pCol+iDx, pRow,iDbCID) && !tHitRight){				//search right
					tHitRight = true;
					searchNextHits(pCol+iDx, pRow, iDbCID);
				}
				if(hitExists(pCol+iDx, pRow-iDy,iDbCID) && !tHitDownRight){		//search down, right
					tHitDownRight = true;
					searchNextHits(pCol+iDx, pRow-iDy, iDbCID);
				}
				if(hitExists(pCol, pRow-iDy,iDbCID) && !tHitDown){				//search down
					tHitDown = true;
					searchNextHits(pCol, pRow-iDy, iDbCID);
				}
				if(hitExists(pCol-iDx, pRow-iDy,iDbCID) && !tHitDownLeft){		//search down, left
					tHitDownLeft = true;
					searchNextHits(pCol-iDx, pRow-iDy, iDbCID);
				}
				if(hitExists(pCol-iDx, pRow,iDbCID) && !tHitLeft){				//search left
					tHitLeft = true;
					searchNextHits(pCol-iDx, pRow, iDbCID);
				}
				if(hitExists(pCol-iDx, pRow+iDy,iDbCID) && !tHitUpLeft){		//search up, left
					tHitUpLeft = true;
					searchNextHits(pCol-iDx, pRow+iDy, iDbCID);
				}
			}
		}
	}
}

bool Clusterizer::deleteHit(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid)
{
	_hitMap[pCol][pRow][pRelBcid] = -1;
	_nHits--;
	if(_nHits == 0){
		_minColHitPos = RAW_DATA_MAX_COLUMN-1;
		_maxColHitPos = 0;
		_minRowHitPos = RAW_DATA_MAX_ROW-1;
		_maxRowHitPos = 0;
		_bCIDfirstHit = -1;
		_bCIDlastHit = -1;
		return true;
	}
	return false;
}

bool Clusterizer::hitExists(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid)
{
	if(pCol>= 0 && pCol < RAW_DATA_MAX_COLUMN && pRow >= 0 && pRow < RAW_DATA_MAX_ROW && pRelBcid >= 0 && pRelBcid < __MAXBCID)
		if(_hitMap[pCol][pRow][pRelBcid] != -1)
			return true;
	return false;
}

void Clusterizer::initChargeCalibMap()
{
	if(Basis::debugSet()) std::cout<<"Clusterizer::initChargeCalibMap\n";

	for(int i = 0; i < RAW_DATA_MAX_COLUMN; ++i){
		for(int j = 0; j < RAW_DATA_MAX_ROW; ++j){
			for(int k = 0; k < 14; ++k)
				_chargeMap[i][j][k] = 0;
		}
	}
}

void Clusterizer::initHitMap()
{
	if(Basis::debugSet()) std::cout<<"Clusterizer::initHitMap\n";

	for(int iCol = 0; iCol < RAW_DATA_MAX_COLUMN; ++iCol){
		for(int iRow = 0; iRow < RAW_DATA_MAX_ROW; ++iRow){
			for(int iRbCID = 0; iRbCID < __MAXBCID; ++iRbCID)
				_hitMap[iCol][iRow][iRbCID] = -1;
		}
	}

	_minColHitPos = RAW_DATA_MAX_COLUMN-1;
	_maxColHitPos = 0;
	_minRowHitPos = RAW_DATA_MAX_ROW-1;
	_maxRowHitPos = 0;
	_bCIDfirstHit = -1;
	_bCIDlastHit = -1;
	_nHits = 0;
}

void Clusterizer::addClusterToResults()
{
//	if(!_abortCluster){
//		//histogramming of the results
//		if(_actualClusterSize<__MAXCLUSTERHITSBINS)
//			_clusterHits[_actualClusterSize]++;
//		if(_actualClusterTot<__MAXTOTBINS && _actualClusterSize<__MAXCLUSTERHITSBINS){
//			_clusterTots[_actualClusterTot][0]++;	//cluster size = 0 contains all cluster sizes
//			_clusterTots[_actualClusterTot][_actualClusterSize]++;
//		}
//		if((int) _actualClusterCharge<__MAXCHARGEBINS && _actualClusterSize<__MAXCLUSTERHITSBINS){
//			_clusterCharges[(int) _actualClusterCharge][0]++;
//			_clusterCharges[(int) _actualClusterCharge][_actualClusterSize]++;
//		}
//		if(_actualClusterCharge > 0){	//avoid division by zero
//			_actualClusterX/=_actualClusterCharge;
//			_actualClusterY/=_actualClusterCharge;
//			int tActualClusterXbin = (int) (_actualClusterX/(__PIXELSIZEX*RAW_DATA_MAX_COLUMN) * __MAXPOSXBINS);
//			int tActualClusterYbin = (int) (_actualClusterY/(__PIXELSIZEY*RAW_DATA_MAX_ROW) * __MAXPOSYBINS);
//			if(tActualClusterXbin < __MAXPOSXBINS && tActualClusterYbin < __MAXPOSYBINS)
//				_clusterPosition[tActualClusterXbin][tActualClusterYbin]++;
//		}
//	}
}

void Clusterizer::clearHitMap()
{
	if(Basis::debugSet()) std::cout<<"Clusterizer::clearHitMap\n";

	if(_nHits != 0){
		for(int iCol = 0; iCol < RAW_DATA_MAX_COLUMN; ++iCol){
			for(int iRow = 0; iRow < RAW_DATA_MAX_ROW; ++iRow){
				for(int iRbCID = 0; iRbCID < __MAXBCID; ++iRbCID){
					if(_hitMap[iCol][iRow][iRbCID] != -1){
						_hitMap[iCol][iRow][iRbCID] = -1;
						_nHits--;
					if(_nHits == 0)
						goto exitLoop;	//the fastest way to exit a nested loop
					}
				}
			}
		}
	}

	exitLoop:
	_minColHitPos = RAW_DATA_MAX_COLUMN-1;
	_maxColHitPos = 0;
	_minRowHitPos = RAW_DATA_MAX_ROW-1;
	_maxRowHitPos = 0;
	_bCIDfirstHit = -1;
	_bCIDlastHit = -1;
	_nHits = 0;
}

void Clusterizer::clearClusterMaps()
{
	debug("clearClusterMaps");
	for (unsigned int i = 0; i < __MAXCLUSTERHITSBINS; ++i)
		_clusterHits[i] = 0;
	for (unsigned int i = 0; i < __MAXTOTBINS; ++i){
		for (unsigned int j = 0; j < __MAXCLUSTERHITSBINS; ++j)
			_clusterTots[i][j] = 0;
	}
	for (unsigned int i = 0; i < __MAXCHARGEBINS; ++i)
		for (unsigned int j = 0; j < __MAXCLUSTERHITSBINS; ++j)
			_clusterCharges[i][j] = 0;
	for (unsigned int i = 0; i < __MAXPOSXBINS; ++i){
		for (unsigned int j = 0; j < __MAXPOSYBINS; ++j)
			_clusterPosition[i][j] = 0;
	}
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
}

void Clusterizer::showHits()
{
	debug("ShowHits");
	if(_nHits < 100){
		for(int i = 0; i < RAW_DATA_MAX_COLUMN; ++i){
			for(int j = 0; j < RAW_DATA_MAX_ROW; ++j){
				for(int k = 0; k < __MAXBCID; ++k){
					if (_hitMap[i][j][k] != -1)
						std::cout<<"x/y/BCID/Tot = "<<i<<"/"<<j<<"/"<<k<<"/"<<_hitMap[i][j][k]<<std::endl;
				}
			}
		}
	}
	else
		std::cout<<"TOO MANY HITS =  "<<_nHits<<" TO SHOW!"<<std::endl;
}

void Clusterizer::addCluster()
{
	if(_Nclusters < _clusterInfoSize){
		_clusterInfo[_Nclusters].eventNumber = _actualEventNumber;
		_clusterInfo[_Nclusters].ID = _actualClusterID;
		_clusterInfo[_Nclusters].size = _actualClusterSize;
		_clusterInfo[_Nclusters].Tot = _actualClusterTot;
		_clusterInfo[_Nclusters].charge = _actualClusterCharge;
		_clusterInfo[_Nclusters].seed_column = _actualClusterSeed_column+1;
		_clusterInfo[_Nclusters].seed_row = _actualClusterSeed_row+1;
		_clusterInfo[_Nclusters].eventStatus = _actualEventStatus;
		_Nclusters++;
	}
	else
		throw std::out_of_range("too many clusters attempt to be stored in cluster array");

	//set seed
	if(_hitIndexMap[_actualClusterSeed_column][_actualClusterSeed_row][_actualClusterSeed_relbcid] < _clusterHitInfoSize)
		_clusterHitInfo[_hitIndexMap[_actualClusterSeed_column][_actualClusterSeed_row][_actualClusterSeed_relbcid]].isSeed = 1;
	else
		throw std::out_of_range("hit index is out of range");
}

