# distutils: language = c++
# distutils: sources = Basis.cpp Histogram.cpp

import numpy as np
cimport numpy as np
from libcpp cimport bool    #to be able to use bool variables

np.import_array()   #if array is used it has to be imported, otherwise possible runtime error
  
cdef extern from "Basis.h":
    cdef cppclass Basis:
        Basis()
    
cdef packed struct numpy_meta_data:
    np.uint32_t start_index
    np.uint32_t stop_index
    np.uint32_t length
    np.float64_t timestamp
    np.uint32_t error
    
cdef packed struct numpy_hit_info:
    np.uint32_t eventNumber  #event number value (unsigned long long: 0 to 18,446,744,073,709,551,615)
    np.uint32_t triggerNumber #external trigger number for read out system
    np.uint8_t relativeBCID #relative BCID value (unsigned char: 0 to 255)
    np.uint16_t LVLID   #LVL1ID (unsigned short int: 0 to 65.535)
    np.uint8_t column       #column value (unsigned char: 0 to 255)
    np.uint16_t row     #row value (unsigned short int: 0 to 65.535)
    np.uint8_t tot          #tot value (unsigned char: 0 to 255)
    np.uint16_t BCID    #absolute BCID value (unsigned short int: 0 to 65.535)
    np.uint8_t triggerStatus#event trigger status
    np.uint32_t serviceRecord #event service records
    np.uint8_t eventStatus #event status value (unsigned char: 0 to 255)
          
cdef extern from "Histogram.h":
    cdef cppclass MetaInfo:
        MetaInfo()
    cdef cppclass HitInfo:
        HitInfo()    
    cdef cppclass Histogram(Basis):
        Histogram()
        void setErrorOutput(bool pToggle)
        void setWarningOutput(bool pToggle)
        void setInfoOutput(bool pToggle)
        void setDebugOutput(bool pToggle)
        
        void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy);  #returns the occupancy histogram for all hits
        void getTotHist(unsigned long*& rTotHist);           #returns the tot histogram for all hits
        void getRelBcidHist(unsigned long*& rRelBcidHist);   #returns the relative BCID histogram for all hits
        
        void createOccupancyHist(bool CreateOccHist = true);
        void createRelBCIDHist(bool CreateRelBCIDHist = true);
        void createTotHist(bool CreateTotHist = true);
        
        void addHits(const unsigned int& rNhits, HitInfo*& rHitInfo);
        void addScanParameter(const unsigned int& rNparInfoLength, ParInfo*& rParInfo);
        void setNoScanParameter();
        void addMetaEventIndex(const unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex);
        
        void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[]); #takes the occupancy histograms for different parameters for the threshold arrays

cdef class PyDataHistograming:
    cdef Histogram* thisptr      # hold a C++ instance which we're wrapping
    def __cinit__(self):
        self.thisptr = new Histogram()
    def __dealloc__(self):
        del self.thisptr
    def set_debug_output(self,toggle):
        self.thisptr.setDebugOutput(<bool> toggle)
    def set_info_output(self,toggle):
        self.thisptr.setInfoOutput(<bool> toggle)
    def set_warning_output(self,toggle):
        self.thisptr.setWarningOutput(<bool> toggle)
    def set_error_output(self,toggle):
        self.thisptr.setErrorOutput(<bool> toggle)
        
    def add_hits(self, Nhits, np.ndarray[numpy_hit_info, ndim=1] hit_info):
        self.thisptr.addHits(<unsigned int> Nhits, <HitInfo*&> hit_info.data)
    def set_no_scan_parameter(self):
        self.thisptr.setNoScanParameter()
    def addMetaEventIndex(self, const unsigned int& rNmetaEventIndexLength, unsigned long*& rMetaEventIndex):
        
                     