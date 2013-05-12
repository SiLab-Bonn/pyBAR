// RawDataConverter.cpp : Defines the entry point for the console application.
//

#include "stdafx.h" //precompiled header

#include <iostream>
#include <string>
#include <stdexcept>
#include <new>

#include "H5Cpp.h"  //hdf5 cpp header
#include "hdf5_hl.h"//table packet
#include "Converter.h"

int main(int argc, char* argv[])
{

  //unsigned int IN[32] = {1,0,1,1,1,0,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
  //unsigned int OUT[32];// = {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
  //for(unsigned int i = 0; i<32; ++i){
  //  std::cout<<IN[i]<<" ";
  //}
  ////std::cout<<convert_to_binary_string(test)<<"\n";
  //int index = 0;
  //for (int i =31; i>=0; i--){
  //   OUT[31-i] = 0;
	 // if (IN[i] == 1)
	 //   OUT[index++] = IN[i];
  //  else if (index !=0)
  //    OUT[index++] = 0;
  //}

  //std::cout<<"\n";
  // for(unsigned int i = 0; i<32; ++i){
  //  std::cout<<OUT[i]<<" ";
  //}

  //return 0;

   Converter converter;

   std::string tInputFileName = "ext_trigger_scan_4.h5";
   std::string tOutputFileName = "out.h5";
   std::string tGroupName = "/";
   std::string tRawDataSetName = "raw_data";
   std::string tMetaDataSetName = "meta_data";
   std::string tParameterDataSetName = "scan_parameters";

   //drag and drop on executable
   if(argc>1){
    tInputFileName = std::string(argv[1]);
    tOutputFileName = tInputFileName;
    tOutputFileName.insert(tInputFileName.size()-3,"_out");
   }

   converter.setNbCIDs(16);
   converter.setFEi4B(false);
   //return 0;
   converter.loadHDF5file(tInputFileName);
   converter.setOutFileName(tOutputFileName);
   converter.setGroupName(tGroupName);
   converter.setRawDataSetName(tRawDataSetName);
   converter.setMetaDataSetName(tMetaDataSetName);
   converter.setParDataSetName(tParameterDataSetName);

   converter.createHitsTable(true);
   converter.createMetaData(true);
   converter.createParameterData(true);
   converter.createErrorHist(true);
   converter.createServiceRecordHist(true);
   converter.createOccupancyHists(true);
   converter.createThresholdHists(true);
   
   try{
    converter.convertTable();
   }
   catch(H5::FileIException error) //catch failure caused by the H5File operations
   {
      std::cout<<"EXEPTION: File I/O error\n";
      error.printError();
      return -1;
   }
   catch(H5::DataSetIException error) //catch failure caused by the DataSet operations
   {
      std::cout<<"EXEPTION: Data set I/O error\n";
      error.printError();
      return -1;
   }
   catch(H5::DataSpaceIException error) //catch failure caused by the DataSpace operations
   {
      std::cout<<"EXEPTION: Data space I/O error\n";
      error.printError();
      return -1;
   }
   catch(H5::DataTypeIException error) //catch failure caused by the DataSpace operations
   {
      std::cout<<"EXEPTION: Data type I/O error\n";
      error.printError();
      return -1;
   }
   catch(H5::PropListIException error) //catch failure caused by the property list operations
   {
      std::cout<<"EXEPTION: Property list error\n";
      error.printError();
      return -1;
   }
   catch(std::bad_alloc& ba) //catch failure caused by the standard library
   {
      std::cout<<"EXEPTION: allocation error\n";
      std::cout<<ba.what()<<std::endl;
      return -1;
   }
   catch(std::exception& error) //catch failure caused by the standard library
   {
      std::cout<<"EXEPTION: Standart library exception\n";
      std::cout<<error.what()<<std::endl;
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
        case 11:
          std::cout<<"Hit array index out of bounds\n";
          break;
        case 12:
          std::cout<<"Hit buffer array index out of bounds\n";
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
      return -1;
   }
   catch (...){
      std::cout<<"EXEPTION unknown\n";
   }
   system("pause");
   return 0;

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

