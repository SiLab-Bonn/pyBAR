#include "StdAfx.h"
#include "Converter.h"

Converter::Converter(void):
  _interpret(), 
  _histogram()
{
  _inFile = 0;
  _outFile = 0;
  _parameterInfoBuffer = 0;
  _metaInfoBuffer = 0;
  _hitInfoBuffer = 0;
  _NparInfoBuffer = 0;
  _groupName = "/";
  _outputFileName = "out.h5";
  _tableNameHits = "Hits";
  _tableNameMeta = "MetaData";
  _occHistName = "HistOcc";
  _parHistName = "Parameter";
  _threshHistName = "HistThreshold";
  _noiseHistName = "HistNoise";
  _errorHistName = "HistErrors";
  _sRhistName = "HistServiceRecords";
  _createOutFile = false;
  _createHitsTable = false;
  _createMetaData = false;
  _createParData = false;
  _createOccHist = false;
  _createErrorHist = false;
  _createSRhist = false;
}


Converter::~Converter(void)
{
  if(_inFile != 0){
    _inFile->close();
    delete _inFile;
  }
  if(_outFile != 0){
    _outFile->close();
    delete _outFile;
  }
  delete _hitInfoBuffer;
  delete _metaInfoBuffer;
  delete _parameterInfoBuffer;
}

void Converter::loadHDF5file(std::string& pFileName)
{
  _inFile = new H5::H5File(pFileName, H5F_ACC_RDONLY); //open the file H5FILE_NAME with read only atribute
}

void Converter::setGroupName(std::string pGroupName)
{
  _groupName = pGroupName;
}

void Converter::setRawDataSetName(std::string pRawDataSetName)
{
  _rawDataSetName = pRawDataSetName;
}

void Converter::setMetaDataSetName(std::string pMetaDataSetName)
{
  _metaDataSetName = pMetaDataSetName;
}

void Converter::setParDataSetName(std::string pParDataSetName)
{
  _parDataSetName = pParDataSetName;
}

void Converter::setOutFileName(std::string pOutputFileName)
{
  _outputFileName = pOutputFileName;
}

void Converter::setHitTableName(std::string pTableName)
{
  _tableNameHits = pTableName;
}

void Converter::setMetaTableName(std::string pMetaTableName)
{
  _tableNameMeta = pMetaTableName;
}

void Converter::setOccHistName(std::string pOccHistName)
{
  _occHistName = pOccHistName;
}

void Converter::createOccupancyHists(bool pCreateOccHist)
{
  _createOccHist = pCreateOccHist;
  _createOutFile = _createOutFile || _createOccHist;
}

void Converter::createThresholdHists(bool pCreateThresholdHists)
{
  _createThresholdHists = pCreateThresholdHists;
  _createOutFile = _createOutFile || _createThresholdHists;
}


void Converter::createHitsTable(bool pCreateHitsTable)
{
  _createHitsTable = pCreateHitsTable;
  _createOutFile = _createOutFile || _createHitsTable;
}

void Converter::createParameterData(bool pCreateParameterData)
{
  _createParData = pCreateParameterData;
  _createOutFile = _createOutFile || _createParData;
}

void Converter::createMetaData(bool pCreateMetaData)
{
  _createMetaData = pCreateMetaData;
  _createOutFile = _createOutFile || _createMetaData;
}

void Converter::createErrorHist(bool pCreateErrorHist)
{
  _createErrorHist = pCreateErrorHist;
  _createOutFile = _createOutFile || pCreateErrorHist;
}

void Converter::createServiceRecordHist(bool pCreateServiceRecordHist)
{
  _createSRhist = pCreateServiceRecordHist;
  _createOutFile = _createOutFile || _createSRhist;
}

void Converter::convertTable()
{
    clock_t tBeginTime = clock();

    char* version = 0;
    char* date = 0;
    register_blosc(&version, &date); //Register the filter with the library
    std::cout<<"Filter available: BLOSC in version "<<std::string(version)<<"\n";

    unsigned int* dataChunks = 0; //array data pointer for one chunk

    H5::Group group = _inFile->openGroup(_groupName);
    H5::DataSet dataSetRaw = group.openDataSet(_rawDataSetName);
    H5::DataSet dataSetMeta = group.openDataSet(_metaDataSetName);

    hsize_t tNfieldsPar = 0;
    extractParameterData(group, tNfieldsPar, _NparInfoBuffer);

    hsize_t tNfields = 0;
    hsize_t tNrecordsMeta = 0;

    printTableInfo(group.getId(), _metaDataSetName.c_str());
    std::cout<<"Datatype for "<<_metaDataSetName<<" ";
    printDataType(dataSetMeta.getTypeClass());

    getTableInfo(group.getId(), _metaDataSetName.c_str(), tNfields, tNrecordsMeta);

    //read meta array from table
    _metaInfoBuffer = new MetaInfo[(unsigned int) tNrecordsMeta];
    size_t Meta_size = sizeof(MetaInfo);
    size_t Meta_offset[NFIELDSMETA] = {HOFFSET(MetaInfo, startIndex),
                                      HOFFSET(MetaInfo, stopIndex),
                                      HOFFSET(MetaInfo, length),
                                      HOFFSET(MetaInfo, timeStamp),
                                      HOFFSET(MetaInfo, errorCode)};
    size_t Meta_sizes[NFIELDSMETA] = {sizeof(_metaInfoBuffer[0].startIndex),
                                      sizeof(_metaInfoBuffer[0].stopIndex),
                                      sizeof(_metaInfoBuffer[0].length),
                                      sizeof(_metaInfoBuffer[0].timeStamp),
                                      sizeof(_metaInfoBuffer[0].errorCode)};
    H5TBread_records(_inFile->getId(), _metaDataSetName.c_str(), 0, tNrecordsMeta, Meta_size, Meta_offset, Meta_sizes, _metaInfoBuffer);

    if(_NparInfoBuffer != 0 && tNrecordsMeta != _NparInfoBuffer) //if parameters are set the length (# read outs) has to be the same as the meta data array
      throw 4;

    if(!_createHitsTable && !_createMetaData && !_createOccHist && !_createThresholdHists) //only this data needs a raw data interpretation
      return;

    _interpret.setMetaWordIndex((unsigned int&) tNrecordsMeta, _metaInfoBuffer);  //set the meta data array (word index, time stamp,... per readout)
    
    unsigned int rEventNumberIndex = 0;
    unsigned long* rEventNumber = 0;

    if(dataSetRaw.getTypeClass() != H5T_INTEGER)  //error check if raw data type is correct
        throw 1;

    printIntDataTypeInfo(dataSetRaw.getIntType());

    //check the data space of the data set and print infos
    H5::DataSpace dataSpace = dataSetRaw.getSpace(); 
    if(dataSpace.getSimpleExtentNdims() > 1) //check number of dimensions
      throw 3;
    int tNdims = 1;
    hsize_t tDimsLength;
    getDataSpaceDimensions(dataSpace, tNdims, tDimsLength);
    std::cout<<"Data space dimension: 1\n";
    std::cout<<"Data space 1. dim length: "<<tDimsLength<<"\n";

    //get the data set property list and print infos
    H5::DSetCreatPropList propertyList = dataSetRaw.getCreatePlist();
    std::cout<<"Data set layout: ";
    printDataLayout(propertyList.getLayout());
    printFilters(propertyList);
    hsize_t chunkLength = 0;  //length of the chunks in each dimensions
    int NdimChunk = propertyList.getChunk(1, &chunkLength); //length of the chunk, only one dimension
    std::cout<<"Data set chunk dimension: "<<NdimChunk<<"\n";
    std::cout<<"Data set chunk 1. dim. length: "<<chunkLength<<"\n";

    //create memory space with the chunk dimesions
    H5::DataSpace memorySpace(NdimChunk, &chunkLength, NULL); //define new memory space
    dataChunks = new unsigned int[(unsigned int) chunkLength];
    std::cout<<"dimsLength/chunkLength "<<tDimsLength/chunkLength<<"\n";

    //reset the interpreter values
    _interpret.resetEventVariables();
    _interpret.resetCounters();

    //create output file
    if(_createOutFile){
      std::cout<<"\n##### Out file "<<_outputFileName<<" #####\n";
      _outFile = new H5::H5File(_outputFileName, H5F_ACC_TRUNC);
    }

    // Calculate the size and the offsets of the hit struct members in memory
    _hitInfoBuffer = new HitInfo[NRECORDSRAW];
    const size_t Hit_size = sizeof( HitInfo );
    const size_t Hit_offset[NFIELDS] = {HOFFSET( HitInfo, eventNumber ),
                                        HOFFSET( HitInfo, triggerNumber ),
                                        HOFFSET( HitInfo, relativeBCID ),
                                        HOFFSET( HitInfo, LVLID ),
                                        HOFFSET( HitInfo, column ),
                                        HOFFSET( HitInfo, row ),
                                        HOFFSET( HitInfo, tot ),
                                        HOFFSET( HitInfo, BCID ),
                                        HOFFSET( HitInfo, serviceRecord ),
                                        HOFFSET( HitInfo, eventStatus )};

    const size_t Hit_sizes[NFIELDS] = { sizeof( _hitInfoBuffer[0].eventNumber),
                                        sizeof( _hitInfoBuffer[0].triggerNumber),
                                        sizeof( _hitInfoBuffer[0].relativeBCID),
                                        sizeof( _hitInfoBuffer[0].LVLID),
                                        sizeof( _hitInfoBuffer[0].column),
                                        sizeof( _hitInfoBuffer[0].row),
                                        sizeof( _hitInfoBuffer[0].tot),
                                        sizeof( _hitInfoBuffer[0].BCID),
                                        sizeof( _hitInfoBuffer[0].serviceRecord),
                                        sizeof( _hitInfoBuffer[0].eventStatus)};

    //read 1. chunk of the raw data table (offset = 0)
    hsize_t tOffset = 0;
    dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &tOffset);
    dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);

    //interpret the first chunk
    unsigned int tNhits = 0;                                    //numbers of hits
    HitInfo* tHitInfo = 0;                                      //interpreted hit data array pointer
    if(!_interpret.interpretRawData(dataChunks, (int) chunkLength)) //interret the raw data
      return;
    _interpret.getHits(tNhits, tHitInfo);                       //get the result array
    _interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber); //get the event number per read out

    //histogram data
    if(_createOccHist){
      _histogram.addMetaEventIndex(rEventNumberIndex, rEventNumber); //set the event number per read out for parameter data correlation
      _histogram.addHits(tNhits, tHitInfo);                          //histogram hits of actual chunck
    }
    
    //create the output table with the first chunk data
    const char* tField_names[NFIELDS]  = {"Event","Trigger","Relative_BCID", "LVL1ID", "Column", "Row", "TOT", "BCID", "Service_Record", "Event_status"};
    hid_t field_type[NFIELDS];
    hsize_t chunk_size = OUTTABLECHUNKSIZE;
    int* fill_data = NULL;
    int compress  = 1;
    herr_t status = 0;
    field_type[0] = H5T_NATIVE_ULONG;
    field_type[1] = H5T_NATIVE_UINT;
    field_type[2] = H5T_NATIVE_UCHAR;
    field_type[3] = H5T_NATIVE_USHORT;
    field_type[4] = H5T_NATIVE_UCHAR;
    field_type[5] = H5T_NATIVE_USHORT;
    field_type[6] = H5T_NATIVE_UCHAR;
    field_type[7] = H5T_NATIVE_USHORT;
    field_type[8] = H5T_NATIVE_UINT;
    field_type[9] = H5T_NATIVE_UCHAR;

    if(_createHitsTable)
      status = H5TBmake_table("Hit Data", _outFile->getId(), _tableNameHits.c_str(), NFIELDS, tNhits, Hit_size, tField_names, Hit_offset, field_type, chunk_size, fill_data, compress, tHitInfo);

    if(status<0)
      throw 5;

    unsigned int tLastProgress = 0;
    std::cout<<"Converting... ";

    //read remaining chunks of the raw data table and store to file
    for(hsize_t i = 1; i<tDimsLength/chunkLength;++i){
      if((int)(i*100/(tDimsLength/chunkLength)) > tLastProgress && (int)(i*100/(tDimsLength/chunkLength))%5 == 0){
        std::cout<<i*100/(tDimsLength/chunkLength)<<" ";
        tLastProgress = (int)(i*100/(tDimsLength/chunkLength));
      }
      hsize_t tOffset = chunkLength*i;
      dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &tOffset);
      dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);
      if (!_interpret.interpretRawData(dataChunks,  (int) chunkLength))
        return;
      _interpret.getHits(tNhits, tHitInfo);
      _interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber);
      if(_createOccHist){
        _histogram.addMetaEventIndex(rEventNumberIndex, rEventNumber);
        _histogram.addHits(tNhits, tHitInfo);  //hit histogramming
      }
      if (_createHitsTable){
        status = H5TBappend_records(_outFile->getId(), _tableNameHits.c_str(), tNhits, Hit_size, Hit_offset, Hit_sizes, tHitInfo);
        if(status<0)
          throw 5;
      }
    }

    //create memory space with the chunk dimension of the last smaller chunk
    hsize_t tRemainingWords = tDimsLength-tDimsLength/chunkLength*chunkLength;  //because Nwords%chunksize != 0: the last chunk has to be treated differently
    if(tRemainingWords > 0){ //only read additional chuk if data words are not read so far
      H5::DataSpace memorySpaceLastChunk(NdimChunk, &tRemainingWords, NULL); //define new memory space
      unsigned int* dataLastChunk = new unsigned int[(unsigned int) tRemainingWords];
      tOffset = chunkLength*(tDimsLength/chunkLength);
      dataSpace.selectHyperslab(H5S_SELECT_SET, &tRemainingWords, &tOffset);
      dataSetRaw.read(dataLastChunk, H5::PredType::NATIVE_UINT, memorySpaceLastChunk, dataSpace);
      if (!_interpret.interpretRawData(dataLastChunk,  (int) tRemainingWords))
        return;
      _interpret.getHits(tNhits, tHitInfo);
      _interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber);
      if(_createOccHist){
        _histogram.addMetaEventIndex(rEventNumberIndex, rEventNumber);
        _histogram.addHits(tNhits, tHitInfo);  //hit histogramming
      }
      if (_createHitsTable){
        status = H5TBappend_records(_outFile->getId(), _tableNameHits.c_str(), tNhits, Hit_size, Hit_offset, Hit_sizes, tHitInfo);
        if(status<0)
          throw 5;
      }
      delete dataLastChunk;
    }
    
    saveAdditionalData();

    _runTime = clock() - tBeginTime;

    printSummary();

    //clean up
    delete dataChunks;
}

void Converter::printDataType(H5T_class_t rTypeClass)
{
  switch(rTypeClass){
    case H5T_NO_CLASS:
      std::cout<<"H5T_NO_CLASS\n";
      break;
    case H5T_INTEGER:
      std::cout<<"H5T_INTEGER\n";
      break;
    case H5T_FLOAT:
      std::cout<<"H5T_FLOAT\n";
      break;
    case H5T_TIME:
      std::cout<<"H5T_TIME\n";
      break;
    case H5T_STRING:
      std::cout<<"H5T_STRING\n";
      break;
    case H5T_BITFIELD:
      std::cout<<"H5T_BITFIELD\n";
      break;
    case H5T_OPAQUE:
      std::cout<<"H5T_OPAQUE\n";
      break;
    case H5T_COMPOUND:
      std::cout<<"H5T_COMPOUND\n";
      break;
    case H5T_REFERENCE:
      std::cout<<"H5T_REFERENCE\n";
      break;
    case H5T_ENUM:
      std::cout<<"H5T_ENUM\n";
      break;
    case H5T_VLEN:
      std::cout<<"H5T_VLEN\n";
      break;
    case H5T_ARRAY:
      std::cout<<"H5T_ARRAY\n";
      break;
    default:
      std::cout<<"UNKNOWN\n";
  }
}

void Converter::printDataLayout(H5D_layout_t rLayoutClass)
{
  switch(rLayoutClass){
    case H5D_COMPACT:
        std::cout<<"H5D_COMPACT\n";
        break;
    case H5D_CONTIGUOUS:
        std::cout<<"H5D_CONTIGUOUS\n";
        break;
    case H5D_CHUNKED:
        std::cout<<"H5D_CHUNKED\n";
        break;
    default:
        std::cout<<"UNKOWN LAYOUT\n";
        throw 2;
  };
}

void Converter::printFilters(H5::DSetCreatPropList rPropertyList)
{
  int Nfilters = rPropertyList.getNfilters();  //number of filters used for the data set
  std::cout<<"Filters: "<<Nfilters<<"\n";
  std::cout<<"Filter names: ";
  for(int i = 0; i<Nfilters; ++i){
    unsigned int tFilterConfig = 0;
    char *tFiltername = 0;
    size_t tCd_nelmts = 0;
    unsigned int tFilterflags = 0;
    switch (rPropertyList.getFilter(0, tFilterflags, tCd_nelmts, NULL, 0, tFiltername, tFilterConfig)){
    case H5Z_FILTER_DEFLATE:
        std::cout<<"H5Z_FILTER_DEFLATE\n";
        break;
    case H5Z_FILTER_SHUFFLE:
        std::cout<<"H5Z_FILTER_SHUFFLE\n";
        break;
    case H5Z_FILTER_FLETCHER32:
        std::cout<<"H5Z_FILTER_FLETCHER32\n";
        break;
    case H5Z_FILTER_SZIP:
        std::cout<<"H5Z_FILTER_SZIP\n";
        break;
    case H5Z_FILTER_NBIT:
        std::cout<<"H5Z_FILTER_NBIT\n";
        break;
    case H5Z_FILTER_SCALEOFFSET:
        std::cout<<"H5Z_FILTER_SCALEOFFSET\n";
        break;
    case FILTER_BLOSC:
        std::cout<<"FILTER_BLOSC\n";
        break;
    default:
        std::cout<<"UNKNOWN FILTER\n";
       }
    }
}

void Converter::printTableInfo(hid_t pfileID, const char* pTableName)
{
  hsize_t tNfields_out;
  hsize_t tNrecords_out;
  H5TBget_table_info (pfileID, pTableName, &tNfields_out, &tNrecords_out);
  std::cout<<"Table "<<std::string(pTableName)<<" has "<<(int)tNfields_out<<" fields and "<<(int)tNrecords_out<<" records\n";
}

bool Converter::getTableInfo(hid_t pfileID, const char* pTableName, hsize_t& tNfields_out, hsize_t& tNrecords_out)
{
  herr_t status = H5TBget_table_info(pfileID, pTableName, &tNfields_out, &tNrecords_out);
  if(status<0)
    return false;
  return true;
}

void Converter::printIntDataTypeInfo(H5::IntType& rIntTypeClass)
{
  H5std_string orderString;
  H5T_order_t order = rIntTypeClass.getOrder(orderString);
  std::cout<<"Data order: "<<orderString <<"\n";
  size_t size = rIntTypeClass.getSize();
  std::cout<<"Data size: "<<size<<" byte\n";
}

void Converter::getDataSpaceDimensions(H5::DataSpace& rDataSpace, int& rNdimensions, hsize_t& tDimsLength)
{
  rNdimensions = rDataSpace.getSimpleExtentNdims();
  rDataSpace.getSimpleExtentDims(&tDimsLength, NULL);  //get the length of all dimensions
}

void Converter::printSummary()
{
  std::cout<<"\n\n##### Interpreter summary ";
  if(_interpret.getFEI4B())
    std::cout<<"FE-I4B #####\n"<<_interpret.getFEI4B()<<"\n";
  else
    std::cout<<"FE-I4A #####\n";

  _interpret.printSummary();
  std::cout<<"\nFirst 10 hits of the last chunk\n";
  _interpret.printHits(10);

  std::cout<<"\nEvent numbers at first/last 5 read outs\n";
  std::cout<<"#read out\tEventNumber\n";

  unsigned int tEventNumberIndex = 0;
  unsigned long* tEventNumber = 0;

  _interpret.getMetaEventIndex(tEventNumberIndex, tEventNumber);
  for(unsigned int i = 0; i<5; ++i)
    if(i<tEventNumberIndex)
      std::cout<<i<<"\t"<<tEventNumber[i]<<"\n";
  for(unsigned int i = tEventNumberIndex-5; i<tEventNumberIndex; ++i)
    if(i<tEventNumberIndex)
      std::cout<<i<<"\t"<<tEventNumber[i]<<"\n";

  _histogram.test();
    
  double elapsed_secs = double(_runTime) / CLOCKS_PER_SEC;
  std::cout<<"\nRuntime "<<elapsed_secs<<" seconds\n";
}

//TODO: bring this helper functions to work

//void Converter::createOutTable(unsigned int& rNhits, const size_t& rHitSize, const size_t& rHitOffset, HitInfo*& pHitInfo)
//{
//  const char* tField_names[NFIELDS]  = {"Event","BCID relative", "LVL1ID", "Column", "Row", "TOT", "BCID", "Event status"};
//  hid_t field_type[NFIELDS];
//  hsize_t chunk_size = 2000;  //determined by optimising time/file size
//  int* fill_data = NULL;
//  int compress  = 1;
//  herr_t status = 0;
//  field_type[0] = H5T_NATIVE_ULONG;
//  field_type[1] = H5T_NATIVE_UCHAR;
//  field_type[2] = H5T_NATIVE_USHORT;
//  field_type[3] = H5T_NATIVE_UCHAR;
//  field_type[4] = H5T_NATIVE_USHORT;
//  field_type[5] = H5T_NATIVE_UCHAR;
//  field_type[6] = H5T_NATIVE_USHORT;
//  field_type[7] = H5T_NATIVE_UCHAR;
//  field_type[7] = H5T_NATIVE_UINT;
//
//  //status = H5TBmake_table("Hit Data", _outFile->getId(), TABLE_NAME, NFIELDS, rNhits, rHitSize, tField_names, rHitOffset, field_type, chunk_size, fill_data, compress, pHitInfo);
//}
//
//void Converter::createParInfoBuffer(hsize_t& pNparRecords, size_t& rSize, size_t& rOffset, size_t& rSizes)
//{
//  _parameterInfoBuffer = new ParInfo[(unsigned int) pNparRecords];
//  rSize = sizeof(ParInfo);
//  rOffset = HOFFSET(ParInfo, pulserDAC);
//  rSizes = sizeof(_parameterInfoBuffer[0].pulserDAC);
//}
//
//void Converter::createMetaInfoBuffer(unsigned int& pNmetaRecords, size_t& rSize, size_t& rOffset, size_t& rSizes)
//{
//  _metaInfoBuffer = new MetaInfo[pNmetaRecords];
//  rSize = sizeof(MetaInfo);
//  rOffset = HOFFSET(MetaInfo, startIndex),
//            HOFFSET(MetaInfo, stopIndex),
//            HOFFSET(MetaInfo, length),
//            HOFFSET(MetaInfo, timeStamp),
//            HOFFSET(MetaInfo, errorCode);
//  rSizes = sizeof(_metaInfoBuffer[0].startIndex),
//           sizeof(_metaInfoBuffer[0].stopIndex),
//           sizeof(_metaInfoBuffer[0].length),
//           sizeof(_metaInfoBuffer[0].timeStamp),
//           sizeof(_metaInfoBuffer[0].errorCode);
//}
//
//void Converter::createHitInfoBuffer(size_t& rSize, size_t& rOffset, size_t& rSizes)
//{
//  _hitInfoBuffer = new HitInfo[NRECORDSRAW];
//  rSize = sizeof(HitInfo);
//  rOffset = HOFFSET( HitInfo, eventNumber ),
//            HOFFSET( HitInfo, relativeBCID ),
//            HOFFSET( HitInfo, LVLID ),
//            HOFFSET( HitInfo, column ),
//            HOFFSET( HitInfo, row ),
//            HOFFSET( HitInfo, tot ),
//            HOFFSET( HitInfo, BCID ),
//            HOFFSET( HitInfo, eventStatus ),
//            HOFFSET( HitInfo, serviceRecord );
//
//  rSizes =  sizeof( _hitInfoBuffer[0].eventNumber),
//            sizeof( _hitInfoBuffer[0].relativeBCID),
//            sizeof( _hitInfoBuffer[0].LVLID),
//            sizeof( _hitInfoBuffer[0].column),
//            sizeof( _hitInfoBuffer[0].row),
//            sizeof( _hitInfoBuffer[0].tot),
//            sizeof( _hitInfoBuffer[0].BCID),
//            sizeof( _hitInfoBuffer[0].eventStatus),
//            sizeof( _hitInfoBuffer[0].serviceRecord);
//}

void Converter::saveAdditionalData()
{
  if(_createMetaData)
    writeMetaData();
  if(_createParData)
    writeParData();
  if(_createOccHist)
    writeOccupancyHist();
  if(_createThresholdHists)
    writeThresholdHists();
  if(_createErrorHist)
    writeErrorHist();
  if(_createSRhist)
    writeServiceRecordHists();
}

void Converter::writeOccupancyHist()
{
  if (!_createOutFile)
    return;

  const unsigned int tNdim = 3;       //dimensions of output array
  unsigned int tNparameterValues = 0; //number of different parameter values (e.g. PlsrDAC)
  unsigned int* tOccupancy;           //pointer to the occupancy array (linearized 3 dim)

  _histogram.getOccupancy(tNparameterValues, tOccupancy);

  hsize_t dims[tNdim] = {RAW_DATA_MAX_ROW, RAW_DATA_MAX_COLUMN, tNparameterValues};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim]={RAW_DATA_MAX_ROW, RAW_DATA_MAX_COLUMN, 1};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_UINT, &i);
  propertyListOut.setFilter(H5Z_FILTER_SHUFFLE); 
  propertyListOut.setFilter(FILTER_BLOSC);
  //propertyListOut.setFilter(H5Z_FILTER_ALL);
  //propertyListOut.setFilter(H5Z_FILTER_DEFLATE);
  //propertyListOut.setFletcher32();
  H5::DataSet dataset = _outFile->createDataSet(_occHistName.c_str(), H5::PredType::NATIVE_UINT, tMemorySpaceDataSet, propertyListOut);

  H5::DataSpace fspace1 = dataset.getSpace();

  //hsize_t dims1[3] = {2, 2, 2};
  H5::DataSpace mspace2(tNdim, chunk_dims);

  for (unsigned int k = 0; k < tNparameterValues; k++){
    hsize_t offset[tNdim];
    offset[0] = 0;
    offset[1] = 0;
    offset[2] = k;
    fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
    dataset.write(&tOccupancy[(long)k*(long)RAW_DATA_MAX_COLUMN*(long)RAW_DATA_MAX_ROW], H5::PredType::NATIVE_UINT, mspace2, fspace1 );
  }
}

void Converter::writeThresholdHists()
{
  if (!_createOutFile || _NparInfoBuffer < 2)
    return;

  double tMu[RAW_DATA_MAX_COLUMN*RAW_DATA_MAX_ROW];
  double tSigma[RAW_DATA_MAX_COLUMN*RAW_DATA_MAX_ROW];
  _histogram.calculateThresholdScanArrays(tMu, tSigma);

  unsigned int tNparameterValues = 0; //number of different parameter values (e.g. PlsrDAC)

  const unsigned int tNdim = 2;       //dimensions of output array

  hsize_t dims[tNdim] = {RAW_DATA_MAX_ROW, RAW_DATA_MAX_COLUMN};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim]={RAW_DATA_MAX_ROW, RAW_DATA_MAX_COLUMN};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_DOUBLE, &i);
  propertyListOut.setFilter(FILTER_BLOSC);
  H5::DataSet tDatasetMu = _outFile->createDataSet(_threshHistName.c_str(), H5::PredType::NATIVE_DOUBLE, tMemorySpaceDataSet, propertyListOut);
  H5::DataSet tDatasetSigma = _outFile->createDataSet(_noiseHistName.c_str(), H5::PredType::NATIVE_DOUBLE, tMemorySpaceDataSet, propertyListOut);

  H5::DataSpace fspace1 = tDatasetMu.getSpace();
  H5::DataSpace mspace2(tNdim, chunk_dims);

  hsize_t offset[tNdim];
  offset[0] = 0;
  offset[1] = 0;
  fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
  tDatasetMu.write(&tMu, H5::PredType::NATIVE_DOUBLE, mspace2, fspace1);
  tDatasetSigma.write(&tSigma, H5::PredType::NATIVE_DOUBLE, mspace2, fspace1);
}

void Converter::writeMetaData()
{
  if (!_createOutFile || !_createMetaData)
    return;
  unsigned int tNeventNumberIndizes = 0;
  unsigned long* tEventNumber = 0;
  _interpret.getMetaEventIndex(tNeventNumberIndizes, tEventNumber);
  MetaInfoOut* tMetaInfoInterpreted = new MetaInfoOut[tNeventNumberIndizes];

  for(unsigned int i = 0; i<tNeventNumberIndizes; ++i){ //fill out meta table from in meta table
    tMetaInfoInterpreted[i].eventIndex = tEventNumber[i]; 
    tMetaInfoInterpreted[i].timeStamp = _metaInfoBuffer[i].timeStamp;
    tMetaInfoInterpreted[i].errorCode = _metaInfoBuffer[i].errorCode;
  }

  //create the meta info output table
  const char* tField_names[3]  = {"Event","Timestamp", "ErrorCode"};
  hid_t field_type[3];
  hsize_t chunk_size = tNeventNumberIndizes;
  int* fill_data = NULL;
  int compress  = 1;
  herr_t status = 0;
  field_type[0] = H5T_NATIVE_ULONG;
  field_type[1] = H5T_NATIVE_DOUBLE;
  field_type[2] = H5T_NATIVE_UINT;

  const size_t Meta_size = sizeof(MetaInfoOut);
  const size_t Meta_offset[3] = {HOFFSET( MetaInfoOut, eventIndex),
                                HOFFSET( MetaInfoOut, timeStamp),
                                HOFFSET( MetaInfoOut, errorCode)};

  status = H5TBmake_table("MetaData", _outFile->getId(), _tableNameMeta.c_str(), 3, tNeventNumberIndizes, Meta_size, tField_names, Meta_offset, field_type, chunk_size, fill_data, compress, tMetaInfoInterpreted);
}

void Converter::writeParData()
{
  if (!_createOutFile || _parameterInfoBuffer == 0)
    return;

  hsize_t dims[1] = {_NparInfoBuffer};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(1, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[1]={_NparInfoBuffer};
  propertyListOut.setChunk(1, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_UINT, &i);
  //propertyListOut.setFilter(H5Z_FILTER_SHUFFLE);
  //propertyListOut.setFilter(FILTER_BLOSC);
  //propertyListOut.setFilter(H5Z_FILTER_SZIP);
  //propertyListOut.setFilter(H5Z_FILTER_DEFLATE);
  propertyListOut.setFletcher32();
  H5::DataSet dataset = _outFile->createDataSet(_parHistName.c_str(), H5::PredType::NATIVE_UINT, tMemorySpaceDataSet, propertyListOut);

  H5::DataSpace fspace1 = dataset.getSpace();
  dataset.write(_parameterInfoBuffer, H5::PredType::NATIVE_INT, tMemorySpaceDataSet, fspace1 );
}

void Converter::writeErrorHist()
{
  if (!_createOutFile)
    return;

  unsigned int tNerrorHist = 0;
  unsigned long* terrorHistCounter = 0;

  _interpret.getErrorCounters(tNerrorHist, terrorHistCounter);

  const unsigned int tNdim = 1;       //dimensions of output array

  hsize_t dims[tNdim] = {tNerrorHist};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim]={tNerrorHist};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_ULONG, &i);
  //propertyListOut.setFilter(FILTER_BLOSC);
  H5::DataSet tDataset = _outFile->createDataSet(_errorHistName.c_str(), H5::PredType::NATIVE_ULONG, tMemorySpaceDataSet, propertyListOut);
  H5::DataSpace fspace1 = tDataset.getSpace();
  H5::DataSpace mspace2(tNdim, chunk_dims);
  hsize_t offset[tNdim];
  offset[0] = 0;
  fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
  tDataset.write(terrorHistCounter, H5::PredType::NATIVE_ULONG, mspace2, fspace1);
}

void Converter::writeServiceRecordHists()
{
  if (!_createOutFile)
    return;

  unsigned int tNserviceRecords = 0;
  unsigned long* tSercieRecordCounter = 0;

  _interpret.getServiceRecordsCounters(tNserviceRecords, tSercieRecordCounter);

  const unsigned int tNdim = 1;       //dimensions of output array

  hsize_t dims[tNdim] = {tNserviceRecords};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim]={tNserviceRecords};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_ULONG, &i);
  propertyListOut.setFilter(FILTER_BLOSC);
  H5::DataSet tDataset = _outFile->createDataSet(_sRhistName.c_str(), H5::PredType::NATIVE_ULONG, tMemorySpaceDataSet, propertyListOut);
  H5::DataSpace fspace1 = tDataset.getSpace();
  H5::DataSpace mspace2(tNdim, chunk_dims);
  hsize_t offset[tNdim];
  offset[0] = 0;
  fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
  tDataset.write(tSercieRecordCounter, H5::PredType::NATIVE_ULONG, mspace2, fspace1);
}

void Converter::extractParameterData(H5::Group& rGroup, hsize_t& rNfields, hsize_t& rNrecordsPar)
{
  try{
    H5::DataSet dataSetPar = rGroup.openDataSet(_parDataSetName);
    if(getTableInfo(rGroup.getId(), _parDataSetName.c_str(), rNfields, rNrecordsPar)){  //a parameter table does not have to exist
      //read parameter array from table
      _parameterInfoBuffer = new ParInfo[(unsigned int) rNrecordsPar];
      size_t Par_size = sizeof(ParInfo);
      size_t Par_offset[NFIELDSPAR] = {HOFFSET(ParInfo, pulserDAC)};
      size_t Par_sizes[NFIELDSPAR] = {sizeof(_parameterInfoBuffer[0].pulserDAC)};
      H5TBread_records(_inFile->getId(), _parDataSetName.c_str(), 0, rNrecordsPar, Par_size, Par_offset, Par_sizes, _parameterInfoBuffer);
      _histogram.addScanParameter((unsigned int&) rNrecordsPar, _parameterInfoBuffer); //set the parameter array (plsr DAC value per readout)
      printTableInfo(rGroup.getId(), _parDataSetName.c_str());
      std::cout<<"Datatype for "<<_parDataSetName<<" ";
      printDataType(dataSetPar.getTypeClass());
    }
    else
      _histogram.setNoScanParameter();
  }
  catch(...){
    _histogram.setNoScanParameter();
  }
}

void Converter::setFEi4B(bool pFEi4B)
{
  _interpret.setFEI4B(pFEi4B);
}

void Converter::setNbCIDs(int NbCIDs)
{
  _interpret.setNbCIDs(NbCIDs);
}




