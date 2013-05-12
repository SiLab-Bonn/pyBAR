#pragma once

#include <iostream>
#include <string>
#include <stdexcept>
#include <ctime>
#include <new>

#include <vector>

#include "H5Cpp.h"        //hdf5 cpp header
#include "hdf5_hl.h"      //table packet
#include "blosc_filter.h" //external blosc filter
#include "Interpret.h"    //interpreter class
#include "Histogram.h"    //histogram class

const H5std_string META_MEMBER_NAME1("start_index");
const H5std_string META_MEMBER_NAME2("stop_index");
const H5std_string META_MEMBER_NAME3("length");
const H5std_string META_MEMBER_NAME4("timestamp");
const H5std_string META_MEMBER_NAME5("error");

const H5std_string PAR_MEMBER_NAME1("PlsrDAC");

#define NFIELDS  (hsize_t)  10  //field of the result table
#define NRECORDSRAW (hsize_t)  __MAXARRAYSIZE //write buffer size for the raw data table
//#define TABLE_NAME "HitData"

#define NFIELDSPAR  (hsize_t)  1     //fields for one parameter table record
#define NFIELDSMETA  (hsize_t)  5    //fields for one meta data table record
#define NRECORDSPMETA (hsize_t)  100  //read buffer size for the meta/parameter data table

#define OUTTABLECHUNKSIZE 1000    //determined by optimising time/file size

#define appendData false

class Converter
{
public:
  Converter(void);
  ~Converter(void);

  //main functions
  void loadHDF5file(std::string& pFileName);            //path+file name of the HDF5 file
  void convertTable();                                  //starts the converting: reads the file in chunks and stores the converted data for each read chunk into a new file

  //input data structure names
  void setGroupName(std::string pGroupName);                    //group name for all sub nodes (raw data, meta data,...)
  void setRawDataSetName(std::string pRawDataSetName);          //data set name with the FE raw data
  void setMetaDataSetName(std::string pMetaDataSetName);        //data set name with the FE meta data
  void setParDataSetName(std::string pParDataSetName);          //data set name with the FE parameter data
  void setErrorDataSetName(std::string pParDataSetName);        //data set name with the error histogram
  void setServiceRecordDataSetName(std::string pParDataSetName);//data set name with the service record histogram

  //output data structure names
  void setOutFileName(std::string pOutputFileName);     //path+file name of output HDF5 file
  void setHitTableName(std::string pTableName);         //name of the hit table node
  void setMetaTableName(std::string pMetaTableName);    //name of the meta table node
  void setOccHistName(std::string pOccHistName);        //name of the occupancy histogram node
  void setParHistName(std::string pParHistName);        //name of the parameter histogram node
  
  //options
  void createHitsTable(bool pCreateHitsTable = true);
  void createMetaData(bool pCreateMetaData = true);
  void createParameterData(bool pCreateParameterData = true);
  void createOccupancyHists(bool pCreateOccHist = true);
  void createThresholdHists(bool pCreateThresholdHists = true);
  void createErrorHist(bool pCreateErrorHist = true);
  void createServiceRecordHist(bool pCreateServiceRecordHist = true);
  void setFEi4B(bool pFEi4B = true);
  void setNbCIDs(int NbCIDs);

  // info prints
  void printSummary();
  void printDataType(H5T_class_t rTypeClass);
  void printIntDataTypeInfo(H5::IntType& rIntTypeClass);
  void printDataLayout(H5D_layout_t rLayoutClass);
  void printFilters(H5::DSetCreatPropList rPropertyList);
  void printTableInfo(hid_t pfileID, const char* pTableName);

private:
  bool getTableInfo(hid_t pfileID, const char* pTableName, hsize_t& tNfields_out, hsize_t& tNrecords_out);
  void extractParameterData(H5::Group& rGroup, hsize_t& rNfields, hsize_t& rNrecordsPar); //opens parameter data at group and if available gives parameter data access to other classes
  void getDataSpaceDimensions(H5::DataSpace& rDataSpace, int& rNdimensions, hsize_t& tDimsLength);
  void saveAdditionalData();

  void writeMetaData();             //writes the meta data table into the output file
  void writeParData();              //writes the parameter data histogram into the output file
  void writeOccupancyHist();        //writes the occupancy array into the output file
  void writeThresholdHists();       //writes the threshold/noise hists into the output file
  void writeErrorHist();            //writes the error hist into the output file
  void writeServiceRecordHists();   //writes the service record hist into the output file

  //void createParInfoBuffer(hsize_t& pNparRecords, size_t& rSize, size_t& rOffset, size_t& rSizes); //creates the memory space and determines the memory alignement for the parameter data with pNparRecords records (size, offset)
  //void createMetaInfoBuffer(unsigned int& pNmetaRecords, size_t& rSize, size_t& rOffset, size_t& rSizes); //creates the memory space and determines the memory alignement for the meta data with pNmetaRecords records (size, offset)
  //void createHitInfoBuffer(size_t& rSize, size_t& rOffset, size_t& rSizes); //creates the memory space and determines the memory alignement for the output hit info data
  //void createOutTable(unsigned int& rNhits, const size_t& rHitSize, const size_t& rHitOffset, HitInfo*& pHitInfo);  //settings for the output table (field names /type, compression, ...) are given and the output table is created
  
  Interpret _interpret; //interpreter class
  Histogram _histogram; //histogram class
  
  H5::H5File* _inFile;  //pointer to the input file
  H5::H5File* _outFile; //pointer to the ouput file

  std::string _outputFileName; //file name for the output
  std::string _groupName;      //group name of the stored data (root node is set per default)
  std::string _rawDataSetName, _metaDataSetName, _parDataSetName; //raw/meta/parameter data set names

  std::string _tableNameHits, _tableNameMeta, _occHistName, _parHistName, _threshHistName, _noiseHistName, _errorHistName, _sRhistName;

  bool _createOutFile, _createHitsTable, _createMetaData, _createParData, _createOccHist, _createThresholdHists, _createErrorHist, _createSRhist;

  ParInfo* _parameterInfoBuffer;  //pointer to the parameter buffer
  MetaInfo* _metaInfoBuffer;      //pointer to the meta buffer
  HitInfo* _hitInfoBuffer;        //pointer to the ouput hit info buffer

  hsize_t _NparInfoBuffer;        //entries in the parameter info buffer

  clock_t _runTime;               //timer for the total convertion run time
};

