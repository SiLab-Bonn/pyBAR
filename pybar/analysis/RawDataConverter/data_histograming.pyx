# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
import numpy as np
cimport numpy as cnp
from libcpp cimport bool as cpp_bool  # to be able to use bool variables, as cpp_bool according to http://code.google.com/p/cefpython/source/browse/cefpython/cefpython.pyx?spec=svne037c69837fa39ae220806c2faa1bbb6ae4500b9&r=e037c69837fa39ae220806c2faa1bbb6ae4500b9
from data_struct cimport numpy_hit_info, numpy_meta_data, numpy_meta_data_v2, numpy_par_info, numpy_cluster_info
from libc.stdint cimport uint64_t

cnp.import_array()  # if array is used it has to be imported, otherwise possible runtime error

cdef extern from "Basis.h":
    cdef cppclass Basis:
        Basis()

cdef extern from "Histogram.h":
    cdef cppclass HitInfo:
        HitInfo()
    cdef cppclass ParInfo:
        ParInfo()
    cdef cppclass ClusterInfo:
        ClusterInfo()
    cdef cppclass Histogram(Basis):
        Histogram() except +
        void setErrorOutput(cpp_bool pToggle)
        void setWarningOutput(cpp_bool pToggle)
        void setInfoOutput(cpp_bool pToggle)
        void setDebugOutput(cpp_bool pToggle)

        void createOccupancyHist(cpp_bool CreateOccHist)
        void createRelBCIDHist(cpp_bool CreateRelBCIDHist)
        void createTotHist(cpp_bool CreateTotHist)
        void createTdcHist(cpp_bool CreateTdcPixelHist)
        void createTdcPixelHist(cpp_bool CreateTdcPixelHist)
        void createTotPixelHist(cpp_bool CreateTotPixelHist)
        void setMaxTot(const unsigned int& rMaxTot)

        void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy, cpp_bool copy)  # returns the occupancy histogram for all hits
        void getTotHist(unsigned int*& rTotHist, cpp_bool copy)  # returns the tot histogram for all hits
        void getTdcHist(unsigned int*& rTdcHist, cpp_bool copy)
        void getRelBcidHist(unsigned int*& rRelBcidHist, cpp_bool copy)  # returns the relative BCID histogram for all hits
        void getTdcPixelHist(unsigned short*& rTdcPixelHist, cpp_bool copy)  # returns the tdc pixel histogram for all hits
        void getTotPixelHist(unsigned short*& rTotPixelHist, cpp_bool copy)  # returns the tot pixel histogram for all hits

        void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits) except +
        void addClusterSeedHits(ClusterInfo*& rClusterInfo, const unsigned int& rNcluster) except +
        void addScanParameter(int*& rParInfo, const unsigned int& rNparInfoLength) except +
        void setNoScanParameter()
        void addMetaEventIndex(uint64_t*& rMetaEventIndex, const unsigned int& rNmetaEventIndexLength) except +

        unsigned int getMinParameter()  # returns the minimum parameter from _parInfo
        unsigned int getMaxParameter()  # returns the maximum parameter from _parInfo
        unsigned int getNparameters()  # returns the parameter range from _parInfo

        void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[], const unsigned int& rMaxInjections, const unsigned int& min_parameter, const unsigned int& max_parameter)  # takes the occupancy histograms for different parameters for the threshold arrays

        void reset() except +
        void test()

cdef data_to_numpy_array_uint16(cnp.uint16_t* ptr, cnp.npy_intp N):
    cdef cnp.ndarray[cnp.uint16_t, ndim=1] arr = cnp.PyArray_SimpleNewFromData(1, <cnp.npy_intp*> &N, cnp.NPY_UINT16, <cnp.uint16_t*> ptr)
    #PyArray_ENABLEFLAGS(arr, np.NPY_OWNDATA)
    return arr

cdef data_to_numpy_array_uint32(cnp.uint32_t* ptr, cnp.npy_intp N):
    cdef cnp.ndarray[cnp.uint32_t, ndim=1] arr = cnp.PyArray_SimpleNewFromData(1, <cnp.npy_intp*> &N, cnp.NPY_UINT32, <cnp.uint32_t*> ptr)
    #PyArray_ENABLEFLAGS(arr, np.NPY_OWNDATA)
    return arr

cdef cnp.uint16_t* data_16
cdef cnp.uint32_t* data_32
cdef unsigned int Nparameter = 0

cdef class PyDataHistograming:
    cdef Histogram* thisptr  # hold a C++ instance which we're wrapping
    def __cinit__(self):
        self.thisptr = new Histogram()
    def __dealloc__(self):
        del self.thisptr
    def set_debug_output(self, toggle):
        self.thisptr.setDebugOutput(<cpp_bool> toggle)
    def set_info_output(self,toggle):
        self.thisptr.setInfoOutput(<cpp_bool> toggle)
    def set_warning_output(self,toggle):
        self.thisptr.setWarningOutput(<cpp_bool> toggle)
    def set_error_output(self,toggle):
        self.thisptr.setErrorOutput(<cpp_bool> toggle)
    def create_occupancy_hist(self,toggle):
        self.thisptr.createOccupancyHist(<cpp_bool> toggle)
    def create_rel_bcid_hist(self,toggle):
        self.thisptr.createRelBCIDHist(<cpp_bool> toggle)
    def create_tot_hist(self,toggle):
        self.thisptr.createTotHist(<cpp_bool> toggle)
    def create_tdc_hist(self,toggle):
        self.thisptr.createTdcHist(<cpp_bool> toggle)
    def create_tdc_pixel_hist(self,toggle):
        self.thisptr.createTdcPixelHist(<cpp_bool> toggle)
    def create_tot_pixel_hist(self,toggle):
        self.thisptr.createTotPixelHist(<cpp_bool> toggle)
    def set_max_tot(self, max_tot):
        self.thisptr.setMaxTot(<const unsigned int&> max_tot)
    def get_occupancy(self):
        self.thisptr.getOccupancy(Nparameter, <unsigned int*&> data_32, <cpp_bool> False)
        if data_32 != NULL:
            array = data_to_numpy_array_uint32(data_32, 80 * 336 * Nparameter)
            return array.reshape((80, 336, Nparameter), order='F')  # make linear array to 3d array (col,row,parameter)
    def get_tot_hist(self):
        self.thisptr.getTotHist(<unsigned int*&> data_32, <cpp_bool> False)
        if data_32 != NULL:
            return data_to_numpy_array_uint32(data_32, 16)
    def get_tdc_hist(self):
        self.thisptr.getTdcHist(<unsigned int*&> data_32, <cpp_bool> False)
        if data_32 != NULL:
            return data_to_numpy_array_uint32(data_32, 4096)
    def get_rel_bcid_hist(self):
        self.thisptr.getRelBcidHist(<unsigned int*&> data_32, <cpp_bool> False)
        if data_32 != NULL:
            return data_to_numpy_array_uint32(data_32, 256)
    def get_tot_pixel_hist(self):
        self.thisptr.getTotPixelHist(<cnp.uint16_t*&> data_16, <cpp_bool> False)
        if data_16 != NULL:
            array = data_to_numpy_array_uint16(data_16, 80 * 336 * 16)
            return array.reshape((80, 336, 16), order='F')  # make linear array to 3d array (col,row,parameter)
    def get_tdc_pixel_hist(self):
        self.thisptr.getTdcPixelHist(<cnp.uint16_t*&> data_16, <cpp_bool> False)
        if data_16 != NULL:
            array = data_to_numpy_array_uint16(data_16, 80 * 336 * 4096)
            return array.reshape((80, 336, 4096), order='F')
    def add_hits(self, cnp.ndarray[numpy_hit_info, ndim=1] hit_info):
        self.thisptr.addHits(<HitInfo*&> hit_info.data, <const unsigned int&> hit_info.shape[0])
    def add_cluster_seed_hits(self, cnp.ndarray[numpy_cluster_info, ndim=1] cluster_info, Ncluster):
        self.thisptr.addClusterSeedHits(<ClusterInfo*&> cluster_info.data, <const unsigned int&> Ncluster)
    def add_scan_parameter(self, cnp.ndarray[cnp.int32_t, ndim=1] parameter_info):
        self.thisptr.addScanParameter(<int*&> parameter_info.data, <const unsigned int&> parameter_info.shape[0])
    def set_no_scan_parameter(self):
        self.thisptr.setNoScanParameter()
    def add_meta_event_index(self, cnp.ndarray[cnp.uint64_t, ndim=1] event_index, array_length):
        self.thisptr.addMetaEventIndex(<uint64_t*&> event_index.data, <unsigned int&> array_length)
    def get_n_parameters(self):
        return <unsigned int> self.thisptr.getNparameters()
    def calculate_threshold_scan_arrays(self, cnp.ndarray[cnp.float64_t, ndim=1] threshold, cnp.ndarray[cnp.float64_t, ndim=1] noise, n_injections, min_parameter, max_parameter):
        self.thisptr.calculateThresholdScanArrays(<double*> threshold.data, <double*> noise.data, <const unsigned int&> n_injections, <const unsigned int&> min_parameter, <const unsigned int&> max_parameter)
    def reset(self):
        self.thisptr.reset()
    def test(self):
        self.thisptr.test()
