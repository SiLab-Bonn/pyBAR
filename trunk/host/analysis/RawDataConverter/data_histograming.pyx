# distutils: language = c++
# distutils: sources = Basis.cpp Histogram.cpp

import numpy as np
cimport numpy as cnp
cnp.import_array()  # if array is used it has to be imported, otherwise possible runtime error

from libcpp cimport bool  # to be able to use bool variables

from data_struct cimport numpy_hit_info, numpy_meta_data, numpy_meta_data_v2, numpy_par_info, numpy_cluster_info

#from libc.stdint cimport uint64_t
cdef extern from "defines.h":
    ctypedef unsigned long long uint64_t  # http://stackoverflow.com/questions/3544240/conditional-ctypedef-with-cython

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
        void setErrorOutput(bool pToggle)
        void setWarningOutput(bool pToggle)
        void setInfoOutput(bool pToggle)
        void setDebugOutput(bool pToggle)

        void createOccupancyHist(bool CreateOccHist)
        void createRelBCIDHist(bool CreateRelBCIDHist)
        void createTotHist(bool CreateTotHist)
        void createTdcHist(bool CreateTdcPixelHist)
        void createTdcPixelHist(bool CreateTdcPixelHist)
        void setMaxTot(const unsigned int& rMaxTot)

        void getOccupancy(unsigned int& rNparameterValues, unsigned int*& rOccupancy, bool copy)  # returns the occupancy histogram for all hits
        void getTotHist(unsigned int*& rTotHist, bool copy)  # returns the tot histogram for all hits
        void getTdcHist(unsigned int*& rTdcHist, bool copy)
        void getRelBcidHist(unsigned int*& rRelBcidHist, bool copy)  # returns the relative BCID histogram for all hits
        void setTdcPixelHist(unsigned short*& rTdcPixelHist)  # sets the tdc pixel histogram for all hits

        void addHits(HitInfo*& rHitInfo, const unsigned int& rNhits) except +
        void addClusterSeedHits(ClusterInfo*& rClusterInfo, const unsigned int& rNcluster) except +
        void addScanParameter(unsigned int*& rParInfo, const unsigned int& rNparInfoLength) except +
        void setNoScanParameter()
        void addMetaEventIndex(uint64_t*& rMetaEventIndex, const unsigned int& rNmetaEventIndexLength) except +

        unsigned int getMinParameter()  # returns the minimum parameter from _parInfo
        unsigned int getMaxParameter()  # returns the maximum parameter from _parInfo
        unsigned int getNparameters()  # returns the parameter range from _parInfo

        void calculateThresholdScanArrays(double rMuArray[], double rSigmaArray[], const unsigned int& rMaxInjections, const unsigned int& min_parameter, const unsigned int& max_parameter)  # takes the occupancy histograms for different parameters for the threshold arrays

        void reset()
        void test()

cdef class PyDataHistograming:
    cdef Histogram* thisptr  # hold a C++ instance which we're wrapping
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

    def create_occupancy_hist(self,toggle):
        self.thisptr.createOccupancyHist(<bool> toggle)
    def create_rel_bcid_hist(self,toggle):
        self.thisptr.createRelBCIDHist(<bool> toggle)
    def create_tot_hist(self,toggle):
        self.thisptr.createTotHist(<bool> toggle)
    def create_tdc_hist(self,toggle):
        self.thisptr.createTdcHist(<bool> toggle)
    def create_tdc_pixel_hist(self,toggle):
        self.thisptr.createTdcPixelHist(<bool> toggle)
    def set_max_tot(self, max_tot):
        self.thisptr.setMaxTot(<const unsigned int&> max_tot)

    def get_occupancy(self, cnp.ndarray[cnp.uint32_t, ndim=1] occupancy, copy = True):
        cdef unsigned int NparameterValues = 0
        self.thisptr.getOccupancy(NparameterValues, <unsigned int*&> occupancy.data, <bool> copy)
        return NparameterValues
    def get_tot_hist(self, cnp.ndarray[cnp.uint32_t, ndim=1] tot_hist, copy = True):
        self.thisptr.getTotHist(<unsigned int*&> tot_hist.data, <bool> copy)
    def get_tdc_hist(self, cnp.ndarray[cnp.uint32_t, ndim=1] tdc_hist, copy = True):
        self.thisptr.getTdcHist(<unsigned int*&> tdc_hist.data, <bool> copy)
    def set_tdc_pixel_hist(self, cnp.ndarray[cnp.uint16_t, ndim=1] tdc_pixel_hist):
        self.thisptr.setTdcPixelHist(<unsigned short*&> tdc_pixel_hist.data)
    def get_rel_bcid_hist(self, cnp.ndarray[cnp.uint32_t, ndim=1] rel_bcid_hist, copy = True):
        self.thisptr.getRelBcidHist(<unsigned int*&> rel_bcid_hist.data, <bool> copy)

    def add_hits(self, cnp.ndarray[numpy_hit_info, ndim=1] hit_info, Nhits):
        self.thisptr.addHits(<HitInfo*&> hit_info.data, <const unsigned int&> Nhits)
    def add_cluster_seed_hits(self, cnp.ndarray[numpy_cluster_info, ndim=1] cluster_info, Ncluster):
        self.thisptr.addClusterSeedHits(<ClusterInfo*&> cluster_info.data, <const unsigned int&> Ncluster)
    def add_scan_parameter(self, cnp.ndarray[cnp.uint32_t, ndim=1] parameter_info):
        self.thisptr.addScanParameter(<unsigned int*&> parameter_info.data, <const unsigned int&> parameter_info.shape[0])
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
