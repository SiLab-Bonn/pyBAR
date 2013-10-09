# distutils: language = c++
# distutils: sources = Basis.cpp Interpret.cpp

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
          
cdef extern from "Interpret.h":
    cdef cppclass MetaInfo:
        MetaInfo()
    cdef cppclass HitInfo:
        HitInfo()    
    cdef cppclass Interpret(Basis):
        Interpret()
        void printStatus()
        void setErrorOutput(bool pToggle)
        void setWarningOutput(bool pToggle)
        void setInfoOutput(bool pToggle)
        void setDebugOutput(bool pToggle)
    
        void setFEI4B(bool setFEI4B)
        
        void setMetaWordIndex(const unsigned int& tLength, MetaInfo* &rMetaInfo)
        void interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords)
        void getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned long*& rEventNumber)
        void getHits(unsigned int &rNhits, HitInfo* &rHitInfo)
        
        void resetEventVariables()
        void resetCounters()
        
        void printSummary()
        #void getSimple(unsigned int* pDataWords, const unsigned int& pNdataWords, unsigned int* pHits, unsigned int& pNhits)
        #void getSimpleStruct(unsigned int &rNhits, HitInfo* &rHitInfo)
        #void interpretSimple(const unsigned int& tLength, MetaInfo * rMetaInfo)

cdef class PyDataInterpreter:
    cdef Interpret* thisptr      # hold a C++ instance which we're wrapping
    def __cinit__(self):
        self.thisptr = new Interpret()
    def __dealloc__(self):
        del self.thisptr
    def print_status(self):
        self.thisptr.printStatus()
    def set_debug_output(self,toggle):
        self.thisptr.setDebugOutput(<bool> toggle)
    def set_info_output(self,toggle):
        self.thisptr.setInfoOutput(<bool> toggle)
    def set_warning_output(self,toggle):
        self.thisptr.setWarningOutput(<bool> toggle)
    def set_error_output(self,toggle):
        self.thisptr.setErrorOutput(<bool> toggle)             
#     def get_simple(self, np.ndarray[np.uint32_t, ndim=1] dataIn):
#         cdef unsigned int sizeOut = 0
#         cdef np.ndarray[np.uint32_t, ndim=1, mode="c"] dataOut = np.empty_like(dataIn)        
#         self.thisptr.getSimple(<unsigned int*> dataIn.data, <unsigned int> dataIn.shape[0], <unsigned int*> dataOut.data, sizeOut)       
#         return dataOut, sizeOut
    def interpret_raw_data(self, np.ndarray[np.uint32_t, ndim=1] data):
        self.thisptr.interpretRawData(<unsigned int*> data.data, <unsigned int> data.shape[0])
        return data, data.shape[0]
    def get_hits(self, np.ndarray[numpy_hit_info, ndim=1] hit_info):
        cdef unsigned int Nhits = 0
        self.thisptr.getHits(Nhits, <HitInfo*&> hit_info.data)
        return Nhits
    def set_meta_word_index(self, np.ndarray[numpy_meta_data, ndim=1] meta_data):
        self.thisptr.setMetaWordIndex(<unsigned int> meta_data.shape[0], <MetaInfo*&> meta_data.data)
    def get_meta_event_index(self, np.ndarray[np.uint32_t, ndim=1] event_index):
        cdef unsigned int NreadOuts = 0
        self.thisptr.getMetaEventIndex(NreadOuts, <unsigned long*&> event_index.data)
        return NreadOuts
    def reset_event_variables(self):
        self.thisptr.resetEventVariables()       
    def reset_counters(self):
        self.thisptr.resetCounters()      
    def print_summary(self):
        self.thisptr.printSummary()
    def set_FEI4B(self, setFEI4B):
        self.thisptr.setFEI4B(<bool> setFEI4B)    