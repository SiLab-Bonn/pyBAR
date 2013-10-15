#include "Converter.h"

Converter::Converter(void):
  _interpret(), 
  _histogram()
{
  setSourceFileName("Converter");
  _inFile = 0;
  _outFile = 0;
  _parameterInfoBuffer = 0;
  _metaInfoBuffer = 0;
  _hitInfoBuffer = 0;
  setStandardSettings();
}

Converter::~Converter(void)
{
  closeInFile();
  closeOutFile();
  delete _hitInfoBuffer;
  delete _metaInfoBuffer;
  delete _parameterInfoBuffer;
}

bool Converter::convertTable(const std::string& FileName)
{
    clock_t tBeginTime = clock();

    if(!loadHDF5file(FileName))
      return false; 

    char* version = 0;
    char* date = 0;
    register_blosc(&version, &date); //Register the filter with the library
    info("Filter available: BLOSC in version "+std::string(version));

    unsigned int* dataChunks = 0; //array data pointer for one chunk

    H5::Group group = _inFile->openGroup(_groupName);
    H5::DataSet dataSetRaw = group.openDataSet(_rawDataSetName);
    H5::DataSet dataSetMeta = group.openDataSet(_metaDataSetName);

    hsize_t tNfieldsPar = 0;
    extractParameterData(group, tNfieldsPar, _NparInfoBuffer);

    hsize_t tNfields = 0;
    hsize_t tNrecordsMeta = 0;

    if(Basis::infoSet())
      printTableInfo(group.getId(), _metaDataSetName.c_str());
    info("Datatype for "+_metaDataSetName+": ");
    if(Basis::infoSet())
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
      return true;

    if(!_interpret.setMetaWordIndex((unsigned int&) tNrecordsMeta, _metaInfoBuffer))  //set the meta data array (word index, time stamp,... per readout)
      return false;
    
    unsigned int rEventNumberIndex = 0;
    unsigned long* rEventNumber = 0;

    if(dataSetRaw.getTypeClass() != H5T_INTEGER)  //error check if raw data type is correct
        throw 1;

    if(Basis::infoSet())
      printIntDataTypeInfo(dataSetRaw.getIntType());

    //check the data space of the data set and print infos
    H5::DataSpace dataSpace = dataSetRaw.getSpace();

    if(dataSpace.getSimpleExtentNdims() > 1) //check number of dimensions
      throw 3;
    int tNdims = 1;
    hsize_t tDimsLength;

    getDataSpaceDimensions(dataSpace, tNdims, tDimsLength);
    info(std::string("Data space dimension: 1"));
    info(std::string("Data space 1. dim length: ")+IntToStr((int) tDimsLength));

    //get the data set property list and print infos
    H5::DSetCreatPropList propertyList = dataSetRaw.getCreatePlist();
    info(std::string("Data set layout: "));
    if(Basis::infoSet()){
      printDataLayout(propertyList.getLayout());
      printFilters(propertyList);
    }

    hsize_t chunkLength = 0;  //length of the chunks in each dimensions
    int NdimChunk = propertyList.getChunk(1, &chunkLength); //length of the chunk, only one dimension
    info(std::string("Data set chunk dimension: ")+IntToStr((unsigned int) NdimChunk));
    info(std::string("Data set chunk 1. dim. length: ")+IntToStr((unsigned int) chunkLength));

    if(tDimsLength < chunkLength){
      chunkLength = tDimsLength;
      info(std::string("Data space length < chunk length, setting chunk length to space length"));
    }

    //create memory space with the chunk dimesions
    H5::DataSpace memorySpace(NdimChunk, &chunkLength, NULL); //define new memory space
    dataChunks = new unsigned int[(unsigned int) chunkLength];
    info("dimsLength/chunkLength "+IntToStr((unsigned int) (tDimsLength/chunkLength)));

    //reset the interpreter values
    _interpret.resetEventVariables();
    _interpret.resetCounters();

    //create output file
    if(_createOutFile){
      info("##### Out file "+_outputFileName);
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
                                        HOFFSET( HitInfo, triggerStatus ),
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
                                        sizeof( _hitInfoBuffer[0].triggerStatus),
                                        sizeof( _hitInfoBuffer[0].serviceRecord),
                                        sizeof( _hitInfoBuffer[0].eventStatus)};

    //read 1. chunk of the raw data table (offset = 0)
    hsize_t tOffset = 0;
    dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &tOffset);
    dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);

    //interpret the first chunk
    unsigned int tNhits = 0;                                    //numbers of hits
    HitInfo* tHitInfo = 0;                                      //interpreted hit data array pointer
    if(!_interpret.interpretRawData(dataChunks, (int) chunkLength)) //interpret the raw data
      return false;
    _interpret.getHits(tNhits, tHitInfo); //get the result array
    _interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber); //get the event number per read out

    //histogram data
    if(_createOccHist){
      _histogram.addMetaEventIndex(rEventNumberIndex, rEventNumber); //set the event number per read out for parameter data correlation
      _histogram.addHits(tNhits, tHitInfo);                          //histogram hits of the actual chunck
    }

    //create the output table with the first chunk data
    const char* tField_names[NFIELDS]  = {"Event","Trigger","Relative_BCID", "LVL1ID", "Column", "Row", "TOT", "BCID", "Trigger_Status", "Service_Record", "Event_status"};
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
    field_type[8] = H5T_NATIVE_UCHAR;
    field_type[9] = H5T_NATIVE_UINT;
    field_type[10] = H5T_NATIVE_UCHAR;

    if(_createHitsTable)
      status = H5TBmake_table("Hit Data", _outFile->getId(), _tableNameHits.c_str(), NFIELDS, tNhits, Hit_size, tField_names, Hit_offset, field_type, chunk_size, fill_data, compress, tHitInfo);

    if(status<0)
      throw 5;

    unsigned int tLastProgress = 0;

    if(Basis::infoSet())
      std::cout<<"Converting... ";

    //read remaining chunks of the raw data table and store to file
    for(hsize_t i = 1; i<tDimsLength/chunkLength;++i){
      if(Basis::infoSet() && (int)(i*100/(tDimsLength/chunkLength)) > tLastProgress && (int)(i*100/(tDimsLength/chunkLength))%5 == 0){
        std::cout<<i*100/(tDimsLength/chunkLength)<<" ";
        tLastProgress = (int)(i*100/(tDimsLength/chunkLength));
      }
      hsize_t tOffset = chunkLength*i;
      dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &tOffset);
      dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);
      if (!_interpret.interpretRawData(dataChunks,  (int) chunkLength))
        return false;
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
    if(tRemainingWords > 0){ //only read additional chunk if data words are not read so far
      H5::DataSpace memorySpaceLastChunk(NdimChunk, &tRemainingWords, NULL); //define new memory space
      unsigned int* dataLastChunk = new unsigned int[(unsigned int) tRemainingWords];
      tOffset = chunkLength*(tDimsLength/chunkLength);
      dataSpace.selectHyperslab(H5S_SELECT_SET, &tRemainingWords, &tOffset);
      dataSetRaw.read(dataLastChunk, H5::PredType::NATIVE_UINT, memorySpaceLastChunk, dataSpace);
      if (!_interpret.interpretRawData(dataLastChunk,  (int) tRemainingWords))
        return false;
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

    if(Basis::infoSet())
      std::cout<<"100\n";

    _runTime = clock() - tBeginTime;

    //printSummary();
    //exportSummary();

    //clean up
    if(dataChunks != 0)
      delete dataChunks;
    closeInFile();
    closeOutFile();
    return true;
}

void Converter::setStandardSettings()
{
  _groupName = "/";
  _outputFileName = "out.h5";
  _inFileName = "not set";
  _tableNameHits = "Hits";
  _tableNameMeta = "MetaData";
  _occHistName = "HistOcc";
  _parHistName = "Parameter";
  _threshHistName = "HistThreshold";
  _noiseHistName = "HistNoise";
  _errorHistName = "HistErrors";
  _triggerErrorHistName = "HistTrgError";
  _sRhistName = "HistServiceRecords";
  _rawDataSetName = "raw_data";
  _metaDataSetName = "meta_data";
  _parDataSetName = "scan_parameters";
  _relBcidHistName = "HistRelBCID";
  _totHistName = "HistTot";
  _metaMemberNames.resize(NFIELDSMETA);
  _metaMemberNames[0] = "start_index";
  _metaMemberNames[1] = "stop_index";
  _metaMemberNames[2] = "length";
  _metaMemberNames[3] = "timestamp";
  _metaMemberNames[4] = "error";
  _createOutFile = false;
  _createHitsTable = false;
  _createMetaData = false;
  _createParData = false;
  _createOccHist = false;
  _createTriggerErrorHist = false;
  _createErrorHist = false;
  _createSRhist = false;
  _createRelBcidHist = false;
  _createTotHist = false;
  setHDF5ExeptionOutput(false);
  _NparInfoBuffer = 0;
}

bool Converter::loadHDF5file(const std::string& FileName)
{
  if(!fileExists(FileName)){
    warning("loadHDF5file: Cannot find "+FileName);
    return false;
  }
  debug("loadHDF5file: "+FileName);
  closeInFile();
  try{
    _inFile = new H5::H5File(FileName, H5F_ACC_RDONLY); //open the file H5FILE_NAME with read only atribute
  }
  catch(...){
    error(std::string("loadHDF5file: ")+FileName);
  }
  _inFileName = FileName;
  return true;
}

void Converter::setGroupName(const std::string& GroupName)
{
  _groupName = GroupName;
}

void Converter::setRawDataSetName(const std::string& RawDataSetName)
{
  _rawDataSetName = RawDataSetName;
}

void Converter::setMetaDataSetName(const std::string& MetaDataSetName)
{
  _metaDataSetName = MetaDataSetName;
}

void Converter::setParDataSetName(const std::string& ParDataSetName)
{
  _parDataSetName = ParDataSetName;
}

void Converter::setOutFileName(const std::string& OutputFileName)
{
  _outputFileName = OutputFileName;
}

void Converter::setHitTableName(const std::string& TableName)
{
  _tableNameHits = TableName;
}

void Converter::setMetaTableName(const std::string& MetaTableName)
{
  _tableNameMeta = MetaTableName;
}

void Converter::setOccHistName(const std::string& OccHistName)
{
  _occHistName = OccHistName;
}

void Converter::setRelBcidHistName(const std::string& RelBcidHistName)
{
  _relBcidHistName = RelBcidHistName;
}

void Converter::setTotHistName(const std::string& TotHistName)
{
  _totHistName = TotHistName;
}

void Converter::setTriggerErrorHistName(const std::string& TriggerErrorHistName)
{
  _triggerErrorHistName = TriggerErrorHistName;
}

void Converter::setErrorHistName(const std::string& ErrorHistName)
{
  _errorHistName = ErrorHistName;
}

void Converter::setServiceRecordHistName(const std::string& ServiceRecordHistName)
{
  _sRhistName = ServiceRecordHistName;
}

void Converter::createTotHist(bool CreateTotHist)
{
  _createTotHist = CreateTotHist;
  _createOutFile = _createOutFile || _createTotHist;
  _histogram.createTotHist();
}

void Converter::createRelBcidHist(bool CreateRelBcidHist)
{
  _createRelBcidHist = CreateRelBcidHist;
  _createOutFile = _createOutFile || _createRelBcidHist;
  _histogram.createRelBCIDHist();
}

void Converter::createOccupancyHist(bool CreateOccHist)
{
  _createOccHist = CreateOccHist;
  _createOutFile = _createOutFile || _createOccHist;
  _histogram.createOccupancyHist();
}

void Converter::createThresholdHists(bool CreateThresholdHists)
{
  _createThresholdHists = CreateThresholdHists;
  _createOutFile = _createOutFile || _createThresholdHists;
}

void Converter::createHitsTable(bool CreateHitsTable)
{
  _createHitsTable = CreateHitsTable;
  _createOutFile = _createOutFile || _createHitsTable;
}

void Converter::createParameterData(bool CreateParameterData)
{
  _createParData = CreateParameterData;
  _createOutFile = _createOutFile || _createParData;
}

void Converter::createMetaData(bool CreateMetaData)
{
  _createMetaData = CreateMetaData;
  _createOutFile = _createOutFile || _createMetaData;
}

void Converter::createTriggerErrorHist(bool CreateTriggerErrorHist)
{
  _createTriggerErrorHist = CreateTriggerErrorHist;
  _createOutFile = _createOutFile || _createTriggerErrorHist;
}

void Converter::createErrorHist(bool CreateErrorHist)
{
  _createErrorHist = CreateErrorHist;
  _createOutFile = _createOutFile || _createErrorHist;
}

void Converter::createServiceRecordHist(bool CreateServiceRecordHist)
{
  _createSRhist = CreateServiceRecordHist;
  _createOutFile = _createOutFile || _createSRhist;
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

void Converter::exportSummary()
{
  std::cout<<"\n\n##### Export Summary ";
  std::ofstream tOutfile;
  tOutfile.open("Summary.txt", std::ios_base::app);
  std::stringstream tBuffer;

  std::string tFileName = _inFileName;

  tFileName = tFileName.substr(tFileName.find_last_of("\\")+1, tFileName.size()-tFileName.find_last_of("\\"));

  tBuffer<<"\n"<<tFileName<<"\t"<<_interpret.getNevents()<<"\t"<<_interpret.getNemptyEvents()<<"\t"<<_interpret.getNunknownWords()<<"\t"<<_interpret.getNtriggers()<<"\t"<<_interpret.getNhits()<<"\t"<<_interpret.getNtriggerNotInc()<<"\t"<<_interpret.getNtriggerNotOne()<<"\n";

  tOutfile<<tBuffer.str();
  tOutfile.close();
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
    
  double elapsed_secs = double(_runTime) / CLOCKS_PER_SEC;
  std::cout<<"\nRuntime "<<elapsed_secs<<" seconds\n";
}

void Converter::printOptions()
{
  std::cout<<"\n\n##### Converter options\n";
  std::cout<<"_groupName "<<_groupName<<"\n";
  std::cout<<"_outputFileName "<<_outputFileName<<"\n";
  std::cout<<"_inFileName "<<_inFileName<<"\n";
  std::cout<<"_tableNameHits "<<_tableNameHits<<"\n";
  std::cout<<"_tableNameMeta "<<_tableNameMeta<<"\n";
  std::cout<<"_occHistName "<<_occHistName<<"\n";
  std::cout<<"_parHistName "<<_parHistName<<"\n";

  std::cout<<"_threshHistName "<<_threshHistName<<"\n";
  std::cout<<"_noiseHistName "<<_noiseHistName<<"\n";
  std::cout<<"_errorHistName "<<_errorHistName<<"\n";
  std::cout<<"_sRhistName "<<_sRhistName<<"\n";
  std::cout<<"_rawDataSetName "<<_rawDataSetName<<"\n";
  std::cout<<"_metaDataSetName "<<_metaDataSetName<<"\n";
  std::cout<<"_parDataSetName "<<_parDataSetName<<"\n";

  std::cout<<"_metaMemberNames[0] "<<_metaMemberNames[0]<<"\n";
  std::cout<<"_metaMemberNames[1] "<<_metaMemberNames[1]<<"\n";
  std::cout<<"_metaMemberNames[2] "<<_metaMemberNames[2]<<"\n";
  std::cout<<"_metaMemberNames[3] "<<_metaMemberNames[3]<<"\n";
  std::cout<<"_metaMemberNames[4] "<<_metaMemberNames[4]<<"\n";

  std::cout<<"_createOutFile "<<_createOutFile<<"\n";
  std::cout<<"_createHitsTable "<<_createHitsTable<<"\n";
  std::cout<<"_createMetaData "<<_createMetaData<<"\n";
  std::cout<<"_createParData "<<_createParData<<"\n";
  std::cout<<"_createOccHist "<<_createOccHist<<"\n";
  std::cout<<"_createTriggerErrorHist "<<_createTriggerErrorHist<<"\n";
  std::cout<<"_createErrorHist "<<_createErrorHist<<"\n";
  std::cout<<"_createSRhist "<<_createSRhist<<"\n";
  std::cout<<"_NparInfoBuffer "<<_NparInfoBuffer<<"\n";
  
  ///_interpret.printOptions();
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
//  rOffset = HOFFSET(ParInfo, scanParameter);
//  rSizes = sizeof(_parameterInfoBuffer[0].scanParameter);
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
  if(_createTotHist)
    writeTotHist();
  if(_createRelBcidHist)
    writeRelBcidHist();
  if(_createTriggerErrorHist)
    writeTriggerErrorHist();
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

void Converter::writeTotHist()
{
  if (!_createOutFile)
    return;
  unsigned long* tTotHist = 0;
  _histogram.getTotHist(tTotHist);
  const unsigned int tNdim = 1;       //dimensions of output array
  hsize_t dims[tNdim] = {16};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim]={16};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_ULONG, &i);
  //propertyListOut.setFilter(FILTER_BLOSC);
  H5::DataSet tDataset = _outFile->createDataSet(_totHistName.c_str(), H5::PredType::NATIVE_ULONG, tMemorySpaceDataSet, propertyListOut);
  H5::DataSpace fspace1 = tDataset.getSpace();
  H5::DataSpace mspace2(tNdim, chunk_dims);
  hsize_t offset[tNdim];
  offset[0] = 0;
  fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
  tDataset.write(tTotHist, H5::PredType::NATIVE_ULONG, mspace2, fspace1);
}

void Converter::writeRelBcidHist()
{
  if (!_createOutFile)
    return;
  unsigned long* tRelBcidHist = 0;
  _histogram.getRelBcidHist(tRelBcidHist);
  const unsigned int tNdim = 1;       //dimensions of output array
  hsize_t dims[tNdim] = {16};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim] = {16};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_ULONG, &i);
  //propertyListOut.setFilter(FILTER_BLOSC);
  H5::DataSet tDataset = _outFile->createDataSet(_relBcidHistName.c_str(), H5::PredType::NATIVE_ULONG, tMemorySpaceDataSet, propertyListOut);
  H5::DataSpace fspace1 = tDataset.getSpace();
  H5::DataSpace mspace2(tNdim, chunk_dims);
  hsize_t offset[tNdim];
  offset[0] = 0;
  fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
  tDataset.write(tRelBcidHist, H5::PredType::NATIVE_ULONG, mspace2, fspace1);
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

void Converter::writeTriggerErrorHist()
{
  if (!_createOutFile)
    return;

  unsigned int tNtriggerErrorHist = 0;
  unsigned long* tTriggerErrorHist = 0;

  _interpret.getTriggerErrorCounters(tNtriggerErrorHist, tTriggerErrorHist);

  const unsigned int tNdim = 1;               //dimensions of output array

  hsize_t dims[tNdim] = {tNtriggerErrorHist};  // dataset dimensions at creation
  H5::DataSpace tMemorySpaceDataSet(tNdim, dims);
  H5::DSetCreatPropList propertyListOut;
  hsize_t chunk_dims[tNdim]={tNtriggerErrorHist};
  propertyListOut.setChunk(tNdim, chunk_dims);
  unsigned int i = 0;
  propertyListOut.setFillValue(H5::PredType::NATIVE_ULONG, &i);
  //propertyListOut.setFilter(FILTER_BLOSC);
  H5::DataSet tDataset = _outFile->createDataSet(_triggerErrorHistName.c_str(), H5::PredType::NATIVE_ULONG, tMemorySpaceDataSet, propertyListOut);
  H5::DataSpace fspace1 = tDataset.getSpace();
  H5::DataSpace mspace2(tNdim, chunk_dims);
  hsize_t offset[tNdim];
  offset[0] = 0;
  fspace1.selectHyperslab(H5S_SELECT_SET, chunk_dims, offset);
  tDataset.write(tTriggerErrorHist, H5::PredType::NATIVE_ULONG, mspace2, fspace1);
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
      size_t Par_offset[NFIELDSPAR] = {HOFFSET(ParInfo, scanParameter)};
      size_t Par_sizes[NFIELDSPAR] = {sizeof(_parameterInfoBuffer[0].scanParameter)};
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

void Converter::setNbCIDs(unsigned int NbCIDs)
{
  _interpret.setNbCIDs(NbCIDs);
}

void Converter::setMaxTot(unsigned int rMaxTot)
{
  _interpret.setMaxTot(rMaxTot);
}

void Converter::setErrorOutput(bool Toggle)
{
	Basis::setErrorOutput(Toggle);
	_interpret.setErrorOutput(Toggle);
	_histogram.setErrorOutput(Toggle);
}
void Converter::setWarningOutput(bool Toggle)
{
	Basis::setWarningOutput(Toggle);
	_interpret.setWarningOutput(Toggle);
	_histogram.setWarningOutput(Toggle);
}
void Converter::setInfoOutput(bool Toggle)
{
	Basis::setInfoOutput(Toggle);
	_interpret.setInfoOutput(Toggle);
	_histogram.setInfoOutput(Toggle);
}
void Converter::setDebugOutput(bool Toggle)
{
	Basis::setDebugOutput(Toggle);
	_interpret.setDebugOutput(Toggle);
	_histogram.setDebugOutput(Toggle);
}

void Converter::setBugReport(bool Toggle)
{
	Basis::setBugReport(Toggle);
	_interpret.setBugReport(Toggle);
	_histogram.setBugReport(Toggle);
}

void Converter::setHDF5ExeptionOutput(bool pToggle)
{
  if(pToggle)
    ;//H5::Exception::Print();//FIXME
  else
    H5::Exception::dontPrint();
}

void Converter::setDebugEvents(const unsigned long& rStartEvent, const unsigned long& rStopEvent, const bool& debugEvents)
{
  _interpret.debugEvents(rStartEvent, rStopEvent, debugEvents);
}

void Converter::closeInFile()
{
  if(_inFile != 0){
    _inFile->close();
    delete _inFile;
  }
  _inFile = 0;
}

void Converter::closeOutFile()
{
  if(_outFile != 0){
    _outFile->close();
    delete _outFile;
  }
  _outFile = 0;
}


