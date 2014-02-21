# distutils: language = c++
# distutils: sources = Basis.cpp Interpret.cpp

import numpy as np
cimport numpy as cnp
cnp.import_array()  # if array is used it has to be imported, otherwise possible runtime error
from numpy cimport ndarray

from libcpp cimport bool  # to be able to use bool variables

from data_struct cimport numpy_hit_info, numpy_meta_data, numpy_meta_data_v2, numpy_meta_word_data

from data_struct import MetaTable, MetaTableV2

from tables import dtype_from_descr


cdef extern from "Basis.h":
    cdef cppclass Basis:
        Basis()


cdef extern from "Interpret.h":
    cdef cppclass MetaInfo:
        MetaInfo()
    cdef cppclass MetaInfoV2:
        MetaInfoV2()
    cdef cppclass MetaWordInfoOut:
        MetaWordInfoOut()
    cdef cppclass HitInfo:
        HitInfo()
    cdef cppclass Interpret(Basis):
        Interpret() except +
        void printStatus()
        void setErrorOutput(bool pToggle)
        void setWarningOutput(bool pToggle)
        void setInfoOutput(bool pToggle)
        void setDebugOutput(bool pToggle)

        void setNbCIDs(const unsigned int& NbCIDs)
        void setMaxTot(const unsigned int& rMaxTot)
        void setFEI4B(bool setFEI4B)
        bool getFEI4B()
        bool getMetaTableV2()

        void setHitsArray(HitInfo* &rHitInfo, const unsigned int &rSize)

        void setMetaData(MetaInfo*& rMetaInfo, const unsigned int& tLength) except +
        void setMetaDataV2(MetaInfoV2*& rMetaInfo, const unsigned int& tLength) except +
 
        void setMetaDataEventIndex(unsigned int*& rEventNumber, const unsigned int& rSize)
        void setMetaDataWordIndex(MetaWordInfoOut*& rWordNumber, const unsigned int& rSize)

        void interpretRawData(unsigned int* pDataWords, const unsigned int& pNdataWords) except +
#         void getMetaEventIndex(unsigned int& rEventNumberIndex, unsigned int*& rEventNumber)
        void getHits(unsigned int &rNhits, HitInfo* &rHitInfo)

        void getServiceRecordsCounters(unsigned int*& rServiceRecordsCounter, unsigned int& rNserviceRecords, bool copy)  # returns the total service record counter array
        void getErrorCounters(unsigned int*& rErrorCounter, unsigned int& rNerrorCounters, bool copy)  # returns the total errors counter array
        void getTriggerErrorCounters(unsigned int*& rTriggerErrorCounter, unsigned int& rNTriggerErrorCounters, bool copy)  # returns the total trigger errors counter array
        void getTdcCounters(unsigned int*& rTdcCounter, unsigned int& rNtdcCounters, bool copy)
        unsigned int getNarrayHits()  # returns the maximum index filled with hits in the hit array
        unsigned int getNmetaDataEvent()  # returns the maximum index filled with event data infos
        unsigned int getNmetaDataWord()
        void useTriggerNumber(bool useTriggerNumber)
        void useTdcWord(bool useTdcWord)

        void resetEventVariables()
        void resetCounters()
        void createMetaDataWordIndex(bool CreateMetaDataWordIndex)

        void printSummary()
        void debugEvents(const unsigned int& rStartEvent, const unsigned int& rStopEvent, const bool& debugEvents)

        void addEvent()

        unsigned int getHitSize()

        void reset()


cdef class PyDataInterpreter:
    cdef Interpret* thisptr  # hold a C++ instance which we're wrapping
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
    def set_hits_array(self, cnp.ndarray[numpy_hit_info, ndim=1] hit_info):
        self.thisptr.setHitsArray(<HitInfo*&> hit_info.data, <const unsigned int&> hit_info.shape[0])
    def interpret_raw_data(self, cnp.ndarray[cnp.uint32_t, ndim=1] data):
        self.thisptr.interpretRawData(<unsigned int*> data.data, <unsigned int> data.shape[0])
        return data, data.shape[0]
    def set_meta_data(self, ndarray meta_data):  # set_meta_data(self, cnp.ndarray[numpy_meta_data, ndim=1] meta_data)
        meta_data_dtype = meta_data.dtype
        if meta_data_dtype == dtype_from_descr(MetaTable):
            self.thisptr.setMetaData(<MetaInfo*&> meta_data.data, <const unsigned int&> meta_data.shape[0])
        elif meta_data_dtype == dtype_from_descr(MetaTableV2):
            self.thisptr.setMetaDataV2(<MetaInfoV2*&> meta_data.data, <const unsigned int&> meta_data.shape[0])
#         if meta_data_dtype == np.dtype([('start_index', '<u4'), ('stop_index', '<u4'), ('length', '<u4'), ('timestamp', '<f8'), ('error', '<u4')]):
#             self.thisptr.setMetaData(<MetaInfo*&> meta_data.data, <const unsigned int&> meta_data.shape[0])
#         elif meta_data_dtype == np.dtype([('index_start', '<u4'), ('index_stop', '<u4'), ('data_length', '<u4'), ('timestamp_start', '<f8'), ('timestamp_stop', '<f8'), ('error', '<u4')]):
#             self.thisptr.setMetaDataV2(<MetaInfoV2*&> meta_data.data, <const unsigned int&> meta_data.shape[0])
        else:
            raise NotImplementedError('Unknown meta data type %s' % meta_data_dtype)
    def set_meta_event_data(self, cnp.ndarray[cnp.uint32_t, ndim=1] meta_data_event_index):
        self.thisptr.setMetaDataEventIndex(<unsigned int*&> meta_data_event_index.data, <const unsigned int&> meta_data_event_index.shape[0])
    def set_meta_data_word_index(self, cnp.ndarray[numpy_meta_word_data, ndim=1] meta_word_data):
        self.thisptr.setMetaDataWordIndex(<MetaWordInfoOut*&> meta_word_data.data, <const unsigned int&>  meta_word_data.shape[0])
    def get_service_records_counters(self, cnp.ndarray[cnp.uint32_t, ndim=1] service_records_counters):
        cdef unsigned int Ncounters = 0
        self.thisptr.getServiceRecordsCounters(<unsigned int*&> service_records_counters.data, <unsigned int&> Ncounters, <bool> True)
        return Ncounters
    def get_error_counters(self, cnp.ndarray[cnp.uint32_t, ndim=1] error_counters):
        cdef unsigned int NerrorCodes = 0
        self.thisptr.getErrorCounters(<unsigned int*&> error_counters.data, <unsigned int&> NerrorCodes, <bool> True)
        return NerrorCodes
    def get_trigger_error_counters(self, cnp.ndarray[cnp.uint32_t, ndim=1] trigger_error_counters):
        cdef unsigned int NtriggerErrorCodes = 0
        self.thisptr.getTriggerErrorCounters(<unsigned int*&> trigger_error_counters.data, <unsigned int&> NtriggerErrorCodes, <bool> True)
        return NtriggerErrorCodes
    def get_tdc_counters(self, cnp.ndarray[cnp.uint32_t, ndim=1] tdc_counters):
        cdef unsigned int NtdcCounters = 0
        self.thisptr.getTdcCounters(<unsigned int*&> tdc_counters.data, <unsigned int&> NtdcCounters, <bool> True)
        return NtdcCounters
    def get_n_array_hits(self):
        return <unsigned int> self.thisptr.getNarrayHits()
    def get_n_meta_data_word(self):
        return <unsigned int> self.thisptr.getNmetaDataWord()
    def use_trigger_number(self, use_trigger_number):
        self.thisptr.useTriggerNumber(<bool> use_trigger_number)
    def use_tdc_word(self, use_tdc_word):
        self.thisptr.useTdcWord(<bool> use_tdc_word)
    def get_n_meta_data_event(self):
        return <unsigned int> self.thisptr.getNmetaDataEvent()
#     def get_meta_event_index(self, cnp.ndarray[cnp.uint32_t, ndim=1] event_index):
#         cdef unsigned int NreadOuts = 0
#         self.thisptr.getMetaEventIndex(NreadOuts, <unsigned int*&> event_index.data)
#         return NreadOuts
    def reset_event_variables(self):
        self.thisptr.resetEventVariables()
    def reset_counters(self):
        self.thisptr.resetCounters()
    def create_meta_data_word_index(self, value = True):
        self.thisptr.createMetaDataWordIndex(<bool> value)
    def print_summary(self):
        self.thisptr.printSummary()
    def set_trig_count(self, trig_count):
        trigger_count = trig_count if trig_count > 0 else 16
        self.thisptr.setNbCIDs(<const unsigned int&> trigger_count)
    def set_max_tot(self, max_tot):
        self.thisptr.setMaxTot(<const unsigned int&> max_tot)
    def set_FEI4B(self, setFEI4B):
        self.thisptr.setFEI4B(<bool> setFEI4B)
    def store_event(self):
        self.thisptr.addEvent()
    def debug_events(self,start_event,stop_event,toggle = True):
        self.thisptr.debugEvents(<const unsigned int&> start_event, <const unsigned int&> stop_event, <const bool&> toggle)
    def get_hit_size(self):
        return <unsigned int> self.thisptr.getHitSize()

    @property
    def fei4b(self):
        return <bool> self.thisptr.getFEI4B()

    @property
    def meta_table_v2(self):
        return <bool> self.thisptr.getMetaTableV2()

    def reset(self):
        self.thisptr.reset()
