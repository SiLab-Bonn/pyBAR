/*
 * 4 July 2012, Bonn, pohl@physik.uni-bonn.de
 * 17.10.2013 changes done to use the clusterizer into phython usable c++ code via cython
 *
 * This is a simple and fast clusterizer. With a run time that is linearily dependend of:
 * _dx*_dy*_DbCID*number of hits
 *   _dx,_dy are the x,y-step sizes in pixel to search around a hit for additional hits
 *   _DbCID is the BCID window hits are clustered together
 *   number of hits per trigger/event is usually <10
 *
 * The basic idea is:
 * - use an array that is looped over only if hits are inside. Per trigger you have usually < 10 hits.
 *   Methods: Clusterize() for looping over the array
 * - start at one hit position and search around it with a distance of _dx,_dy (8 directions: up, up right, right ...) and _DbCID
 * 	Methods: Clusterize() for looping over the hit array and calling SearchNextHits() for finding next hits belonging to the clusters
 * - only increase the search distance in a certain direction (until _dx, _dy, _DbCID) if no hit was found in this direction already
 *   Method: SearchNextHits() does this
 * - do this iteratively and delete hits from the map if they are added to a cluster
 *   Method: SearchNextHits() deletes hits from the hit map if they are assigned to a cluster
 * - if the hit map is empty all hits are assigned to cluster, abort then
 * 	Method: Clusterize() does this
 *
 * 	The clusterizer can be filled externally with hits (addHit method)
 */

#pragma once

#include <vector>
#include <cmath>
#include <algorithm>
#include <iterator>
#include <set>

#include <stddef.h>

#include "Basis.h"
#include "defines.h"

class Clusterizer: public Basis
{
public:
	Clusterizer(void);
	~Clusterizer(void);
	//main functions
	void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits);		//add hits to cluster, starts clustering, warning hits have to be aligned at events
	void getHitCluster(ClusterHitInfo*& rClusterHitInfo, unsigned int& rSize, bool copy=false);
	void getCluster(ClusterInfo*& rClusterHitInfo, unsigned int& rSize, bool copy=false);
	void reset();														//resets all data but keeps the settings and the charge calibration
	// get result histograms
	void getClusterSizeHist(unsigned int& rNparameterValues, unsigned int*& rClusterSize, bool copy = false);
	void getClusterTotHist(unsigned int& rNparameterValues, unsigned int*& rClusterTot, bool copy = false);
	void getClusterChargeHist(unsigned int& rNparameterValues, unsigned int*& rClusterCharge, bool copy = false);  // no rested in reset function, deactivated at the moment since not used
	void getClusterPositionHist(unsigned int& rNparameterValues, unsigned int*& rClusterPosition, bool copy = false);  // no rested in reset function, deactivated at the moment since not used

	//options
	void createClusterHitInfoArray(bool toggle = true){_createClusterHitInfoArray = toggle;};
	void createClusterInfoArray(bool toggle = true){_createClusterInfoArray = toggle;};
	void setClusterHitInfoArraySize(const unsigned int& rSize);	//set the cluster hit array size
	void setClusterInfoArraySize(const unsigned int& rSize);	//set the cluster array size
	void setXclusterDistance(const unsigned int& pDx);					//sets the x distance between two hits that they belong to one cluster
	void setYclusterDistance(const unsigned int& pDy);					//sets the x distance between two hits that they belong to one cluster
	void setBCIDclusterDistance(const unsigned int& pDbCID);			//sets the BCID depth between two hits that they belong to one cluster
	void setMinClusterHits(const unsigned int&  pMinNclusterHits);		//minimum hits per cluster allowed, otherwise cluster omitted
	void setMaxClusterHits(const unsigned int&  pMaxNclusterHits);		//maximal hits per cluster allowed, otherwise cluster omitted
	void setMaxClusterHitTot(const unsigned int&  pMaxClusterHitTot);	//maximal tot for a cluster hit, otherwise cluster omitted
	void setMaxHitTot(const unsigned int&  pMaxHitTot);					//minimum tot a hit is considered to be a hit

	unsigned int getNclusters();										//returns the number of clusters//main function to start the clustering of the hit array
	void test();

private:
	void addHit(const unsigned int& pHitIndex);	//add hit with index pHitIndex of the input hit array
	inline void searchNextHits(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid);			//search for a hit next to the actual one in time (BCIDs) and space (col, row)
	inline bool deleteHit(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid);				//delete hit at position pCol,pRow from hit map, returns true if hit array is empty
	inline bool hitExists(const unsigned short& pCol, const unsigned short& pRow, const unsigned short& pRelBcid);				//check if the hit exists
	void initChargeCalibMap();											//sets the calibration map to all entries = 0
	void addClusterToResults();											//adds the actual cluster data to the result arrays
	bool clusterize();

	void setStandardSettings();

	void allocateClusterHitArray();
	void allocateClusterInfoArray();
	void deleteClusterHitArray();
	void deleteClusterInfoArray();

	void clearActualClusterData();
	void clearActualEventVariables();
	void showHits();													//shows the hit in the hit map for debugging

	void allocateHitMap();
	void initHitMap();													//sets the hit map to no hit = all entries = -1
	void clearHitMap();
	void deleteHitMap();

	void allocateHitIndexMap();
	void deleteHitIndexMap();

	void allocateChargeMap();
	void deleteChargeMap();

	void allocateResultHistograms();
	void clearResultHistograms();
	void deleteResultHistograms();

	void addCluster();													//adds the actual cluster to the _clusterInfo array
	void addHitClusterInfo(const unsigned int& pHitIndex);				//adds the cluster info to the actual cluster hits in the cluster hit table

	//input data structure
	HitInfo* _hitInfo;

	//output data structures
	ClusterHitInfo* _clusterHitInfo;
	size_t _clusterHitInfoSize;
	unsigned int _NclustersHits;
	ClusterInfo* _clusterInfo;
	size_t _clusterInfoSize;
	unsigned int _Nclusters;

	//cluster results
	unsigned int* _clusterTots;		//array [__MAXTOTBINS][__MAXCLUSTERHITSBINS] containing the cluster tots/cluster size for histogramming
	unsigned int* _clusterCharges;	//array [__MAXCHARGEBINS][__MAXCLUSTERHITSBINS] containing the cluster charge/cluster size for histogramming
	unsigned int* _clusterHits;		//array [__MAXCLUSTERHITSBINS] containing the cluster number of hits for histogramming
	unsigned int* _clusterPosition;	//array [__MAXPOSXBINS][__MAXPOSYBINS] containing the cluster positions for histogramming

	//data arrays for one event
	short int* _hitMap;       											//2d hit histogram for each relative BCID (in total 3d, linearly sorted via col, row, rel. BCID)
	unsigned int* _hitIndexMap;
	float* _chargeMap;													//array containing the lookup charge values for each pixel and TOT

	//cluster settings
	unsigned short _dx;													//max distance in x between two hits that they belong to a cluster
	unsigned short _dy;													//max distance in y between two hits that they belong to a cluster
	unsigned short _DbCID; 												//time window in BCIDs the clustering is done
	unsigned short _maxClusterHitTot; 									//the maximum number of cluster hit tot allowed, if exeeded cluster is omitted
	unsigned short _minClusterHits; 									//the minimum number of cluster hits allowed, if exeeded clustering aborted
	unsigned short _maxClusterHits; 									//the maximum number of cluster hits allowed, if exeeded clustering aborted
	unsigned int _runTime; 												//artificial value to represent the run time needed for clustering
	unsigned int _maxHitTot;											//the tot value a hit is considered to a hit (usually 13)
	bool _createClusterHitInfoArray;									//true if ClusterHitInfoArray has to be filled
	bool _createClusterInfoArray;										//true if ClusterHitInfoArray has to be filled

	//actual clustering variables
	unsigned int _nHits;												//number of hits for the actual event data to cluster
	unsigned short _minColHitPos;										//minimum column with a hit for the actual event data
	unsigned short _maxColHitPos;										//maximum column with a hit for the actual event data
	unsigned short _minRowHitPos;										//minimum row with a hit for the actual event data
	unsigned short _maxRowHitPos;										//maximum row with a hit for the actual event data
	short _bCIDfirstHit;										        //relative start BCID value of the first hit [0:15]
	short _bCIDlastHit;										            //relative stop BCID value of the last hit [0:15]
	unsigned int _actualClusterTot;										//temporary value holding the total tot value of the actual cluster
	unsigned int _actualClusterMaxTot;									//temporary value holding the maximum tot value of the actual cluster
	unsigned int _actualRelativeClusterBCID; 							//temporary value holding the relative BCID start value of the actual cluster [0:15]
	unsigned short _actualClusterID;									//temporary value holding the cluster ID of the actual cluster
	unsigned short _actualClusterSize;									//temporary value holding the total hit number of the actual cluster
	unsigned short _actualClusterSeed_column;							//temporary value holding the column number of the seed pixel of the actual cluster
	unsigned short _actualClusterSeed_row;								//temporary value holding the row number of the seed pixel of the actual cluster
	unsigned short _actualClusterSeed_relbcid;							//temporary value holding the relative BCID number of the seed pixel of the actual cluster
	float _actualClusterX;												//temporary value holding the x position of the actual cluster
	float _actualClusterY;												//temporary value holding the y position of the actual cluster
	float _actualClusterCharge;											//temporary value holding the total charge value of the actual cluster

	//actual event variables
	uint64_t _actualEventNumber;  										//event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
	unsigned int _actualEventStatus;
	unsigned int _nEventHits;											//number of hits of actual event

	bool _abortCluster;													//set to true if one cluster TOT hit exeeds _maxClusterHitTot, cluster is not added to the result array
};

