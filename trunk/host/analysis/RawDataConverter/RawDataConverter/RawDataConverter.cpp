// RawDataConverter.cpp : Defines the entry point for the console application.
//

#include "stdafx.h" //precompiled header

#include <iostream>
#include <string>
#include <exception>

#include "H5Cpp.h"  //hdf5 cpp header
#include "hdf5_hl.h"//table packet
#include "blosc_filter.h"//external blosc filter
#include "Interpret.h"  //interpreter class
#include "Occupancy.h"  //occupancy class

#include <ctime>

//const H5std_string H5FILE_NAME("test_table.h5");
//const H5std_string GROUP_NAME("RawData");
//const H5std_string DATASET_RAW_NAME("FEI4data");

const H5std_string H5FILE_NAME("threshold_scan.h5");
const H5std_string GROUP_NAME("/");

const H5std_string DATASET_RAW_NAME("raw_data");
const H5std_string DATASET_META_NAME("meta_data");
const H5std_string DATASET_PAR_NAME("scan_parameters");

const H5std_string META_MEMBER_NAME1("start_index");
const H5std_string META_MEMBER_NAME2("stop_index");
const H5std_string META_MEMBER_NAME3("length");
const H5std_string META_MEMBER_NAME4("timestamp");
const H5std_string META_MEMBER_NAME5("error");

const H5std_string PAR_MEMBER_NAME1("PlsrDAC");

#define NFIELDS  (hsize_t)  8
#define NRECORDSRAW (hsize_t)  __MAXARRAYSIZE //write buffer size for the raw data table
#define TABLE_NAME "HitData"

#define NFIELDSPAR  (hsize_t)  1     //fields for one parameter table record
#define NFIELDSMETA  (hsize_t)  5    //fields for one meta data table record
#define NRECORDSPMETA (hsize_t)  100  //read buffer size for the meta/parameter data table

#define appendData false


void printDataType(H5T_class_t rTypeClass)
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

void printDataLayout(H5D_layout_t rLayoutClass)
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

void printFilters(H5::DSetCreatPropList rPropertyList)
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

void printTableInfo(hid_t pfileID, const char* pTableName){
  hsize_t tNfields_out;
  hsize_t tNrecords_out;
  H5TBget_table_info (pfileID, pTableName, &tNfields_out, &tNrecords_out);
  std::cout<<"Table "<<std::string(pTableName)<<" has "<<(int)tNfields_out<<" fields and "<<(int)tNrecords_out<<" records\n";
}

void getTableInfo(hid_t pfileID, const char* pTableName, hsize_t& tNfields_out, hsize_t& tNrecords_out){
  H5TBget_table_info (pfileID, pTableName, &tNfields_out, &tNrecords_out);
}

int main(void)
{
   clock_t begin = clock();

   char *version = 0;
   char *date = 0;
   register_blosc(&version, &date); //Register the filter with the library
   std::cout<<"Filter available: BLOSC in version "<<std::string(version)<<"\n";

   unsigned int *dataChunks = 0; //array data pointer for one chunk
   ParInfo* tPar_buf = 0; //array pointer for the parameter infos
   MetaInfo* tMeta_buf = 0; //array pointer for the meta infos

   Interpret interpret; //interpreter class
   interpret.setFEI4B(false);
   interpret.setNbCIDs(16);

   Occupancy occupancy; //occupancy class

   //H5::Exception::dontPrint();  //do not automatically print exeption description

   try{

      std::cout<<"\n##### In file "<<std::string(H5FILE_NAME)<<" #####\n";
      H5::H5File inFile(H5FILE_NAME, H5F_ACC_RDONLY); //open the file H5FILE_NAME with read only atribute
      H5::Group group = inFile.openGroup(GROUP_NAME); //open the group GROUP_NAME at the root node /
      H5::DataSet dataSetRaw = group.openDataSet(DATASET_RAW_NAME); //open the data set with the raw data in the group GROUP_NAME
      H5::DataSet dataSetMeta = group.openDataSet(DATASET_META_NAME); //open the data set with the meta data in the group GROUP_NAME
      H5::DataSet dataSetPar = group.openDataSet(DATASET_PAR_NAME); //open the data set with the parameter data in the group GROUP_NAME

      printTableInfo(group.getId(), DATASET_META_NAME.c_str());
      std::cout<<"Datatype for "<<DATASET_META_NAME<<" ";
      printDataType(dataSetMeta.getTypeClass());
      
      printTableInfo(group.getId(), DATASET_PAR_NAME.c_str());
      std::cout<<"Datatype for "<<DATASET_PAR_NAME<<" ";
      printDataType(dataSetPar.getTypeClass());
      
      hsize_t tNfields = 0;
      hsize_t tNrecordsMeta = 0;
      hsize_t tNrecordsPar = 0;
      getTableInfo(group.getId(), DATASET_META_NAME.c_str(), tNfields, tNrecordsMeta);
      getTableInfo(group.getId(), DATASET_PAR_NAME.c_str(), tNfields, tNrecordsPar);
      if(tNrecordsMeta != tNrecordsPar)
        throw 4;

      // Calculate the type_size and the offsets of the struct members
      tPar_buf = new ParInfo[tNrecordsPar];
      //ParInfo tPar_buf[NRECORDSPMETA];
      size_t Par_size = sizeof(ParInfo);
      size_t Par_offset[NFIELDSPAR] = {HOFFSET(ParInfo, pulserDAC)};
      size_t Par_sizes[NFIELDSPAR] = {sizeof(tPar_buf[0].pulserDAC)};

      tMeta_buf = new MetaInfo[tNrecordsMeta];
      //MetaInfo tMeta_buf[NRECORDSPMETA];
      size_t Meta_size = sizeof(MetaInfo);
      size_t Meta_offset[NFIELDSMETA] = {HOFFSET(MetaInfo, startIndex),
                                        HOFFSET(MetaInfo, stopIndex),
                                        HOFFSET(MetaInfo, length),
                                        HOFFSET(MetaInfo, timeStamp),
                                        HOFFSET(MetaInfo, errorCode)};
      size_t Meta_sizes[NFIELDSMETA] = {sizeof(tMeta_buf[0].startIndex),
                                        sizeof(tMeta_buf[0].stopIndex),
                                        sizeof(tMeta_buf[0].length),
                                        sizeof(tMeta_buf[0].timeStamp),
                                        sizeof(tMeta_buf[0].errorCode)};

      // read the whole tables into the buffers and give access to them to the interpreter class
      H5TBread_records(inFile.getId(), DATASET_PAR_NAME.c_str(), 0, tNrecordsPar, Par_size, Par_offset, Par_sizes, tPar_buf);
      H5TBread_records(inFile.getId(), DATASET_META_NAME.c_str(), 0, tNrecordsMeta, Meta_size, Meta_offset, Meta_sizes, tMeta_buf);
      interpret.setMetaWordIndex((unsigned int&) tNrecordsMeta, tMeta_buf);  //set the meta data array (word index, time stamp,... per readout)
      ////%FIXME fake data
      //tPar_buf[0].pulserDAC = 123;
      //tPar_buf[1].pulserDAC = 44;
      //tPar_buf[2].pulserDAC = 1;
      //tPar_buf[3].pulserDAC = 2;
      //tPar_buf[4].pulserDAC = 3;
      //tPar_buf[5].pulserDAC = 3;
      //tPar_buf[6].pulserDAC = 3;
      //tPar_buf[7].pulserDAC = 4;
      //tPar_buf[8].pulserDAC = 4;
      //tPar_buf[9].pulserDAC = 5;
      //tPar_buf[10].pulserDAC = 8;

      occupancy.addScanParameter((unsigned int&) tNrecordsPar, tPar_buf); //set the parameter array (plsr DAC value per readout)
      unsigned int rEventNumberIndex = 0;
      unsigned long* rEventNumber = 0;

      /*char* tFieldNames[100];
      size_t tField_sizes[5] = {666, 666, 666, 666, 666};
      size_t tField_offsets[5] = {666, 666, 666, 666, 666};
      size_t tType_size[5] = {666, 666, 666, 666, 666};

      std::cout<<"ERROR "<<H5TBget_field_info(inFile.getId(), DATASET_META_NAME.c_str(), tFieldNames, tField_sizes, tField_offsets, tType_size);

      std::cout<<"tFieldNames "<<tFieldNames[0]<<" tField_sizes[0] "<<tField_sizes[0]<<"\ttField_offsets[0] "<<tField_offsets[0]<<"\ttType_size[0] "<<tType_size[0]<<"\n";
      std::cout<<"tFieldNames "<<tFieldNames[0]<<"tField_sizes[1] "<<tField_sizes[1]<<"\ttField_offsets[1] "<<tField_offsets[1]<<"\ttType_size[1] "<<tType_size[1]<<"\n";
      std::cout<<"tFieldNames "<<tFieldNames[0]<<"tField_sizes[2] "<<tField_sizes[2]<<"\ttField_offsets[2] "<<tField_offsets[2]<<"\ttType_size[2] "<<tType_size[2]<<"\n";
      std::cout<<"tFieldNames "<<tFieldNames[0]<<"tField_sizes[3] "<<tField_sizes[3]<<"\ttField_offsets[3] "<<tField_offsets[3]<<"\ttType_size[3] "<<tType_size[3]<<"\n";
      std::cout<<"tFieldNames "<<tFieldNames[0]<<"tField_sizes[4] "<<tField_sizes[4]<<"\ttField_offsets[4] "<<tField_offsets[4]<<"\ttType_size[4] "<<tType_size[4]<<"\n";*/

      /*for(int i = 0; i < tNrecordsMeta; ++i){
        std::cout<<i<<" PlsrDAC \t"<<(unsigned int) tPar_buf[i].pulserDAC<<"\n";
        std::cout<<i<<" startIndex \t"<<(unsigned int) tMeta_buf[i].startIndex<<"\n";
        std::cout<<i<<" stopIndex \t"<<(unsigned int) tMeta_buf[i].stopIndex<<"\n";
        std::cout<<i<<" length \t"<<(unsigned int) tMeta_buf[i].length<<"\n";
        std::cout<<i<<" timeStamp \t"<<tMeta_buf[i].timeStamp<<"\n";
        std::cout<<i<<" errorCode \t"<<(unsigned int) tMeta_buf[i].errorCode<<"\n";
      }*/

      //return 0;

      //check the raw data type for int and print infos
      if(dataSetRaw.getTypeClass() != H5T_INTEGER)
        throw 1;

      std::cout<<"Data type: integer\n";
      H5::IntType intype = dataSetRaw.getIntType();
      H5std_string orderString;
      H5T_order_t order = intype.getOrder(orderString);
      std::cout<<"Data order: "<<orderString <<"\n";
      size_t size = intype.getSize();
      std::cout<<"Data size: "<<size<<" byte\n";

      //check the data space of the data set and print infos
      H5::DataSpace dataSpace = dataSetRaw.getSpace(); 
      if(dataSpace.getSimpleExtentNdims() > 1) //check number of dimensions
        throw 3;
      hsize_t dimsLength;
      int Ndims = dataSpace.getSimpleExtentDims(&dimsLength, NULL);  //get the length of all dimensions
      std::cout<<"Data space dimension: 1\n";
      std::cout<<"Data space 1. dim length: "<<dimsLength<<"\n";

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
      dataChunks = new unsigned int[chunkLength];
      hsize_t chunkOffset = 0;
      dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &chunkOffset);
      dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);
      std::cout<<"dimsLength/chunkLength "<<dimsLength/chunkLength<<"\n";

      //reset the interpreter values
      interpret.resetEventVariables();
      interpret.resetCounters();

      //create output file
      H5std_string tOutFileName = H5FILE_NAME;
      tOutFileName.replace(tOutFileName.find(".h5"),3,"_interpreted.h5");
      H5::H5File outFile(tOutFileName, H5F_ACC_TRUNC);
      std::cout<<"\n##### Out file "<<tOutFileName<<" #####\n";

      // Calculate the size and the offsets of the hit struct members in memory
      HitInfo dst_buf[NRECORDSRAW];
      size_t dst_size = sizeof( HitInfo );
      size_t dst_offset[NFIELDS] = {HOFFSET( HitInfo, eventNumber ),
                                    HOFFSET( HitInfo, relativeBCID ),
                                    HOFFSET( HitInfo, LVLID ),
                                    HOFFSET( HitInfo, column ),
                                    HOFFSET( HitInfo, row ),
                                    HOFFSET( HitInfo, tot ),
                                    HOFFSET( HitInfo, BCID ),
                                    HOFFSET( HitInfo, eventStatus )};

      size_t dst_sizes[NFIELDS] = { sizeof( dst_buf[0].eventNumber),
                                    sizeof( dst_buf[0].relativeBCID),
                                    sizeof( dst_buf[0].LVLID),
                                    sizeof( dst_buf[0].column),
                                    sizeof( dst_buf[0].row),
                                    sizeof( dst_buf[0].tot),
                                    sizeof( dst_buf[0].BCID),
                                    sizeof( dst_buf[0].eventStatus)};

      // Define field information and type
      const char *field_names[NFIELDS]  = {"Event","BCID relative", "LVL1ID", "Column", "Row", "TOT", "BCID", "Event status"};
      hid_t      field_type[NFIELDS];
      hsize_t    chunk_size = 2000;
      int        *fill_data = NULL;
      int        compress  = 1;
      herr_t     status;
      field_type[0] = H5T_NATIVE_ULONG;
      field_type[1] = H5T_NATIVE_UCHAR;
      field_type[2] = H5T_NATIVE_USHORT;
      field_type[3] = H5T_NATIVE_UCHAR;
      field_type[4] = H5T_NATIVE_USHORT;
      field_type[5] = H5T_NATIVE_UCHAR;
      field_type[6] = H5T_NATIVE_USHORT;
      field_type[7] = H5T_NATIVE_UCHAR;
      field_type[7] = H5T_NATIVE_UCHAR;

      //read 1. chunk of the raw data table
      hsize_t tOffset = 0;
      dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &tOffset);
      dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);

      //interpret the first chunk
      unsigned int tNhits = 0;
      HitInfo* tHitInfo = 0;  //interpreted hit data pointer
      interpret.interpretRawData(dataChunks, chunkLength);
      interpret.getHits(tNhits, tHitInfo);
      interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber); //get the event number per read out

      ////%FIXME fake data
      //rEventNumber[0] = 0;
      //rEventNumber[1] = 20;
      //rEventNumber[2] = 300;
      //rEventNumber[3] = 400;
      //rEventNumber[4] = 600;
      //rEventNumber[5] = 650;
      //rEventNumber[6] = 700;
      //rEventNumber[7] = 710;
      //rEventNumber[8] = 720;
      //rEventNumber[9] = 900;
      //rEventNumber[10] = 1100;

      occupancy.addMetaEventIndex(rEventNumberIndex, rEventNumber); //set the event number per read out for parameter array correlation
      /*occupancy.test();
      return 0;*/
      occupancy.addHits(tNhits, tHitInfo);  //occupancy histogramming

      status = H5TBmake_table("Hit Data", outFile.getId(), TABLE_NAME, NFIELDS, tNhits,
                              dst_size,field_names, dst_offset, field_type,
                              chunk_size, fill_data, compress, tHitInfo);

      if(status<0)
        throw 5;

      std::cout<<"Progress ";
      bool progressSet = false;

      //read remaining chunks of the raw data table and store to file
      for(hsize_t i = 1; i<dimsLength/chunkLength;++i){
     // for(hsize_t i = 1; i<100;++i){
        if((int)((double) i*100/(double)(dimsLength/chunkLength))%10 == 0)
          std::cout<<i*100/(dimsLength/chunkLength)<<" ";
        hsize_t tOffset = chunkLength*i;
        dataSpace.selectHyperslab(H5S_SELECT_SET, &chunkLength, &tOffset);
        dataSetRaw.read(dataChunks, H5::PredType::NATIVE_UINT, memorySpace, dataSpace);
        if (!interpret.interpretRawData(dataChunks, chunkLength))
          return -1;
        interpret.getHits(tNhits, tHitInfo);
        interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber);
        occupancy.addMetaEventIndex(rEventNumberIndex, rEventNumber);
        occupancy.addHits(tNhits, tHitInfo);  //occupancy histogramming
        if (appendData){
          status = H5TBappend_records(outFile.getId(), TABLE_NAME, tNhits, dst_size, dst_offset, dst_sizes, tHitInfo);
          if(status<0)
            throw 5;
        }
      }

      std::cout<<"\n\n##### Interpreter summary ";
      if(interpret.getFEI4B())
        std::cout<<"FE-I4B #####\n";
      else
        std::cout<<"FE-I4A #####\n";

      interpret.printSummary();
      std::cout<<"\nFirst 10 hits of the last chunk\n";
      interpret.printHits(10);

      std::cout<<"\nEvent numbers at first 10 read outs\n";

      interpret.getMetaEventIndex(rEventNumberIndex, rEventNumber);

      for(unsigned int i=0; i<10; ++i)
        std::cout<<"read out "<<i<<"\t"<<rEventNumber[i]<<"\n";

      //clean up
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;

      clock_t end = clock();
      double elapsed_secs = double(end - begin) / CLOCKS_PER_SEC;
      std::cout<<"Runtime "<<elapsed_secs<<" seconds\n";

// backup stuff

      //using namespace H5;
      //using namespace std;

      //const H5std_string FILE_NAME( "SDSextendible.h5" );
      //const H5std_string DATASET_RAW_NAME( "ExtendibleArray" );
      //const int NX = 10;
      //const int NY = 5;
      //const int RANK = 2;

      /*for(unsigned int i = 0; i < 10; ++i)
        std::cout<<tHitInfo[i].eventNumber<<"\t"<<(unsigned int) tHitInfo[i].relativeBCID<<"\t"<<tHitInfo[i].LVLID<<"\t"<<(unsigned int) tHitInfo[i].column<<"\t"<<tHitInfo[i].row<<"\t"<<(unsigned int) tHitInfo[i].tot<<"\t"<<tHitInfo[i].BCID<<"\t"<<(unsigned int) tHitInfo[i].eventStatus<<"\n";*/
  
      /* close the file */
     // H5Fclose( file_id );

     // //HDF5 Table (H5TB) code

     // //Calculate the size and the offsets of the hit struct members in memory
     // HitInfo dst_buf[NRECORDSRAW];
     // size_t dst_size =  sizeof( dst_buf );

     // size_t dst_offset[NFIELDS] = {HOFFSET(HitInfo, eventNumber),
     //                               HOFFSET(HitInfo, relativeBCID),
     //                               HOFFSET(HitInfo, LVLID),
     //                               HOFFSET(HitInfo, column),
     //                               HOFFSET(HitInfo, row),
     //                               HOFFSET(HitInfo, tot),
     //                               HOFFSET(HitInfo, BCID),
     //                               HOFFSET(HitInfo, eventStatus)};

     // size_t dst_sizes[NFIELDS] = { sizeof( dst_buf[0].eventNumber),
     //                               sizeof( dst_buf[0].relativeBCID),
     //                               sizeof( dst_buf[0].LVLID),
     //                               sizeof( dst_buf[0].column),
     //                               sizeof( dst_buf[0].row),
     //                               sizeof( dst_buf[0].tot),
     //                               sizeof( dst_buf[0].BCID),
     //                               sizeof( dst_buf[0].eventStatus)};

     // HitInfo  p_data[NRECORDSRAW];
     // for(int i = 0; i < NRECORDSRAW; ++i){
     //   p_data[i].eventNumber = 0;
     //   p_data[i].relativeBCID = 0;
     //   p_data[i].LVLID = 0;
     //   p_data[i].column = 0;
     //   p_data[i].row = 0;
     //   p_data[i].tot = 0;
     //   p_data[i].BCID = 0;
     //   p_data[i].eventStatus = 0;
     // }

     // // Define field information
     // const char *field_names[NFIELDS] = {"Event","BCID relative", "LVL1ID", "Column", "Row", "TOT", "BCID", "Event status"};
     // hid_t      field_type[NFIELDS];
     // hid_t      string_type;
     // hid_t      file_id;
     // hsize_t    chunk_size = 10;
     // int        *fill_data = NULL;
     // int        compress  = 0;
     // herr_t     status;
     // //int        i;

     // // Initialize field_type
     // //string_type = H5Tcopy( H5T_C_S1 );
     // //H5Tset_size( string_type, 16 );
     // //field_type[0] = string_type;
     // field_type[0] = H5T_NATIVE_ULLONG;
     // field_type[1] = H5T_NATIVE_UCHAR;
     // field_type[2] = H5T_NATIVE_USHORT;
     // field_type[3] = H5T_NATIVE_UCHAR;
     // field_type[4] = H5T_NATIVE_USHORT;
     // field_type[5] = H5T_NATIVE_UCHAR;
     // field_type[6] = H5T_NATIVE_USHORT;
     // field_type[7] = H5T_NATIVE_UCHAR;
     // //char c;

     // file_id = H5Fcreate( "ex_table.h5", H5F_ACC_TRUNC, H5P_DEFAULT, H5P_DEFAULT );

     // status=H5TBmake_table( "Table Title", file_id, TABLE_NAME,NFIELDS,NRECORDSRAW,
     //                    dst_size,field_names, dst_offset, field_type,
     //                    chunk_size, fill_data, compress, p_data  );

     ////status=H5TBread_table( file_id, TABLE_NAME, dst_size, dst_offset, dst_sizes, dst_buf);

     /////* print it by rows */
     ///*for (int i=0; i<NRECORDSRAW; ++i) {
     // std::cout<<p_data[i].eventNumber<<"\t"<<(unsigned int) p_data[i].relativeBCID<<"\t"<<p_data[i].LVLID<<"\t"<<(unsigned int) p_data[i].column<<"\t"<<p_data[i].row<<"\t"<<(unsigned int) p_data[i].tot<<"\t"<<p_data[i].BCID<<"\t"<<p_data[i].eventStatus<<"\n";
     //}*/

     // //close type
     // //H5Tclose( string_type );
 
     // //close the file
     // H5Fclose( file_id );

      //std::cin>>c;

     // unsigned int tHitIndex = 0;
     // unsigned long* tEventNumber = 0;
     // unsigned char* tRelBCID = 0;
     // unsigned short int* tLVLID = 0;
     // unsigned char* tColumn = 0;
     // unsigned short int* tRow = 0;
     // unsigned char* tTot = 0;
     // unsigned short int* tBCID = 0;
     // unsigned char* tEventStatus = 0;
     // interpret.getHits(tHitIndex, tEventNumber, tRelBCID, tLVLID, tColumn, tRow, tTot, tBCID, tEventStatus);

     // //create output file
     // H5std_string tOutFileName = H5FILE_NAME;
     // tOutFileName.replace(tOutFileName.find(".h5"),3,"_interpreted.h5");
     // H5::H5File outFile(tOutFileName, H5F_ACC_TRUNC);

     // //create property list and add chunking, compression, fill value options
     // H5::DSetCreatPropList propertyListOut;
     // hsize_t chunkLengthOut = chunkLength;
     // //propertyListOut.setFilter(FILTER_BLOSC);
     // propertyListOut.setChunk(1, &chunkLengthOut);
	    ////int tFillValue = 0;
     // //propertyListOut.setFillValue(H5::PredType::NATIVE_USHORT, &tFillValue);

     // //create memory space for the output data
     // const int tDimensionsOut  = 1;  // dataSetRaw dimensions at creation
     // hsize_t tMaxDim[1] = {H5S_UNLIMITED};
     // H5::DataSpace memorySpaceOut(tDimensionsOut, &chunkLength, tMaxDim);

     // //create file data set, get the space space for the output data and write to it
     // H5::DataSet dataSetOut = outFile.createDataSet("HitData", H5::PredType::NATIVE_INT, memorySpaceOut, propertyListOut);
     // H5::DataSpace dataSpaceOut = dataSetOut.getSpace();
     // dataSetOut.write(tLVLID, H5::PredType::NATIVE_USHORT, memorySpaceOut, dataSpaceOut);

      /*H5TBmake_table( "Table Title", file_id, TABLE_NAME,NFIELDS,NRECORDSRAW,
                         dst_size,field_names, dst_offset, field_type,
                         chunk_size, fill_data, compress, p_data  );*/

   }
   catch(H5::FileIException error) //catch failure caused by the H5File operations
   {
      std::cout<<"EXEPTION: File I/O error\n";
      error.printError();
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   catch(H5::DataSetIException error) //catch failure caused by the DataSet operations
   {
      std::cout<<"EXEPTION: Data set I/O error\n";
      error.printError();
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   catch(H5::DataSpaceIException error) //catch failure caused by the DataSpace operations
   {
      std::cout<<"EXEPTION: Data space I/O error\n";
      error.printError();
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   catch(H5::DataTypeIException error) //catch failure caused by the DataSpace operations
   {
      std::cout<<"EXEPTION: Data type I/O error\n";
      error.printError();
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   catch(H5::PropListIException error) //catch failure caused by the property list operations
   {
      std::cout<<"EXEPTION: Property list error\n";
      error.printError();
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   catch(std::exception& error) //catch failure caused by the standard library
   {
      std::cout<<"EXEPTION: Standart library exception\n";
      std::cout<<error.what()<<std::endl;
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   catch(int e) //catch failure caused by the DataSpace operations
   {
      std::cout<<"\nEXEPTION: Wrong data structure: ";
      switch(e){
        case 1:
          std::cout<<"Data type is not an integer type\n";
          break;
        case 2:
          std::cout<<"Data set has unknown layout\n";
          break;
        case 3:
          std::cout<<"Data space has more than one dimension\n";
          break;
        case 4:
          std::cout<<"Parameter and Metadata table have different length\n";
          break;
        case 5:
          std::cout<<"Error writing table table\n";
          break;
        case 10:
          std::cout<<"The meta data does not make sense\n";
          break;
        case 20:
          std::cout<<"Col index out of bounds\n";
          break;
        case 21:
          std::cout<<"Row index out of bounds\n";
          break;
        case 22:
          std::cout<<"Event index out of bounds\n";
          break;
        case 23:
          std::cout<<"Parameter<->Event correlation failed\n";
          break;
        default:
          std::cout<<"unknown exception\n";
      }
      delete dataChunks;
      delete tPar_buf;
      delete tMeta_buf;
      return -1;
   }
   return 0;
}

