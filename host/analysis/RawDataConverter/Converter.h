#pragma once

#include <iostream>
#include <fstream>
#include <string>
#include <stdexcept>
#include <ctime>
#include <new>
#include <sstream>
#include <vector>

#include "H5Cpp.h"        //hdf5 cpp header
#include "hdf5_hl.h"      //table packet
#include "blosc_filter.h" //external blosc filter

#include "Basis.h"        //basis class for often needed c++ functions
#include "Interpret.h"    //interpreter class
#include "Histogram.h"    //histogram class

#define NFIELDS  (hsize_t)  11  //field of the result table
#define NRECORDSRAW (hsize_t)  __MAXARRAYSIZE //write buffer size for the raw data table

#define NFIELDSPAR  (hsize_t)  1      //fields for one parameter table record
#define NFIELDSMETA  (hsize_t)  5     //fields for one meta data table record
#define NRECORDSPMETA (hsize_t)  100  //read buffer size for the meta/parameter data table

#define OUTTABLECHUNKSIZE 1000    //determined by optimising time/file size

#define appendData false

class Converter: public Basis
{
public:
  Converter(void);
  ~Converter(void);

  //main functions
  void loadHDF5file(const std::string& FileName);            //path+file name of the HDF5 file
  void convertTable();                                        //starts the converting: reads the file in chunks and stores the converted data for each read chunk into a new file

  //input data structure names
  void setGroupName(const std::string& GroupName);                      //group name for all sub nodes (raw data, meta data,...)
  void setRawDataSetName(const std::string& RawDataSetName);            //data set name with the FE raw data
  void setMetaDataSetName(const std::string& MetaDataSetName);          //data set name with the FE meta data
  void setParDataSetName(const std::string& ParDataSetName);            //data set name with the FE parameter data

  //output data structure names
  void setOutFileName(const std::string& OutputFileName);                  //path+file name of output HDF5 file
  void setHitTableName(const std::string& TableName);                      //name of the hit table node
  void setMetaTableName(const std::string& MetaTableName);                 //name of the meta table node
  void setOccHistName(const std::string& OccHistName);                     //name of the occupancy histogram node
  void setTriggerErrorHistName(const std::string& TriggerErrorHistName);   //data set name with the trigger error histogram
  void setErrorHistName(const std::string& ErrorHistName);                 //data set name with the error histogram
  void setServiceRecordHistName(const std::string& ServiceRecordHistName); //data set name with the service record histogram
  
  //options
  void createHitsTable(bool CreateHitsTable = true);
  void createMetaData(bool CreateMetaData = true);
  void createParameterData(bool CreateParameterData = true);
  void createOccupancyHists(bool CreateOccHist = true);
  void createThresholdHists(bool CreateThresholdHists = true);
  void createTriggerErrorHist(bool CreateTriggerErrorHist = true);
  void createErrorHist(bool CreateErrorHist = true);
  void createServiceRecordHist(bool CreateServiceRecordHist = true);
  void setFEi4B(bool FEi4B = true);
  void setNbCIDs(unsigned int NbCIDs);
  void setMaxTot(unsigned int MaxTot);

  //info options
  void setErrorOutput(bool pToggle = true);								//set to see errors output, standard setting: on
	void setWarningOutput(bool pToggle = true);							//set to see warnings output, standard setting: on
	void setInfoOutput(bool pToggle = true);								//set to see infos output, standard setting: off
	void setDebugOutput(bool pToggle = true);								//set to see debug output, standard setting: off
	void setBugReport(bool pToggle = true);									//set to create Bug report, standard setting: off
  void setHDF5ExeptionOutput(bool pToggle = true);        //set to see HDF5 errors

  // info outputs
  void exportSummary();
  void printSummary();
  void printOptions();

private:
  void setStandardSettings(); //sets standard settings for the data names and analysis options
  bool getTableInfo(hid_t pfileID, const char* pTableName, hsize_t& tNfields_out, hsize_t& tNrecords_out);
  void extractParameterData(H5::Group& rGroup, hsize_t& rNfields, hsize_t& rNrecordsPar); //opens parameter data at group and if available gives parameter data access to other classes
  void getDataSpaceDimensions(H5::DataSpace& rDataSpace, int& rNdimensions, hsize_t& tDimsLength);
  void saveAdditionalData();

  void printDataType(H5T_class_t rTypeClass);
  void printIntDataTypeInfo(H5::IntType& rIntTypeClass);
  void printDataLayout(H5D_layout_t rLayoutClass);
  void printFilters(H5::DSetCreatPropList rPropertyList);
  void printTableInfo(hid_t pfileID, const char* pTableName);

  void writeMetaData();             //writes the meta data table into the output file
  void writeParData();              //writes the parameter data histogram into the output file
  void writeOccupancyHist();        //writes the occupancy array into the output file
  void writeThresholdHists();       //writes the threshold/noise hists into the output file
  void writeErrorHist();            //writes the error hist into the output file
  void writeTriggerErrorHist();          //writes the trigger error hist into the output file
  void writeServiceRecordHists();   //writes the service record hist into the output file

  //void createParInfoBuffer(hsize_t& pNparRecords, size_t& rSize, size_t& rOffset, size_t& rSizes); //creates the memory space and determines the memory alignement for the parameter data with pNparRecords records (size, offset)
  //void createMetaInfoBuffer(unsigned int& pNmetaRecords, size_t& rSize, size_t& rOffset, size_t& rSizes); //creates the memory space and determines the memory alignement for the meta data with pNmetaRecords records (size, offset)
  //void createHitInfoBuffer(size_t& rSize, size_t& rOffset, size_t& rSizes); //creates the memory space and determines the memory alignement for the output hit info data
  //void createOutTable(unsigned int& rNhits, const size_t& rHitSize, const size_t& rHitOffset, HitInfo*& pHitInfo);  //settings for the output table (field names /type, compression, ...) are given and the output table is created
  
  Interpret _interpret; //interpreter class
  Histogram _histogram; //histogram class
  
  H5::H5File* _inFile;  //pointer to the input file
  H5::H5File* _outFile; //pointer to the ouput file

  std::string _inFileName, _outputFileName; //file name for the input/output
  std::string _groupName;                   //group name of the stored data (root node is set per default)
  std::string _rawDataSetName, _metaDataSetName, _parDataSetName; //raw/meta/parameter data set names

  std::vector<std::string> _metaMemberNames;

  std::string _tableNameHits, _tableNameMeta, _occHistName, _parHistName, _threshHistName, _noiseHistName, _triggerErrorHistName, _errorHistName, _sRhistName; //node names for different output data

  bool _createOutFile, _createHitsTable, _createMetaData, _createParData, _createOccHist, _createThresholdHists, _createTriggerErrorHist, _createErrorHist, _createSRhist; //flags for different analysis options

  std::map<std::string, std::string> _optionNames; //TODO: use this container for the string names

  ParInfo* _parameterInfoBuffer;  //pointer to the parameter buffer
  MetaInfo* _metaInfoBuffer;      //pointer to the meta buffer
  HitInfo* _hitInfoBuffer;        //pointer to the ouput hit info buffer

  hsize_t _NparInfoBuffer;        //entries in the parameter info buffer

  clock_t _runTime;               //timer for the total convertion run time
};

