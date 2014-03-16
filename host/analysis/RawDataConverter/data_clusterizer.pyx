# distutils: language = c++
# distutils: sources = Basis.cpp Clusterizer.cpp
# cython: boundscheck=False
# cython: wraparound=False
import numpy as np
cimport numpy as cnp
cnp.import_array()  # if array is used it has to be imported, otherwise possible runtime error

from libcpp cimport bool  # to be able to use bool variables

from data_struct cimport numpy_hit_info, numpy_cluster_hit_info, numpy_cluster_info

cdef extern from "Basis.h":
    cdef cppclass Basis:
        Basis()

cdef extern from "Clusterizer.h":
    cdef cppclass HitInfo:
        HitInfo()
    cdef cppclass ClusterHitInfo:
        ClusterHitInfo()
    cdef cppclass ClusterInfo:
        ClusterInfo()
    cdef cppclass Clusterizer(Basis):
        Clusterizer() except +
        void setErrorOutput(bool pToggle)
        void setWarningOutput(bool pToggle)
        void setInfoOutput(bool pToggle)
        void setDebugOutput(bool pToggle)

        void addHits(HitInfo *& rHitInfo, const unsigned int & rNhits) except +

        void createClusterHitInfoArray(bool toggle)
        void createClusterInfoArray(bool toggle)

        void setClusterHitInfoArray(ClusterHitInfo *& rClusterHitInfo, const unsigned int & rSize)
        void setClusterInfoArray(ClusterInfo *& rClusterHitInfo, const unsigned int & rSize)
        void setXclusterDistance(const unsigned int & pDx)
        void setYclusterDistance(const unsigned int & pDy)
        void setBCIDclusterDistance(const unsigned int & pDbCID)
        void setMinClusterHits(const unsigned int & pMinNclusterHits)
        void setMaxClusterHits(const unsigned int & pMaxNclusterHits)
        void setMaxClusterHitTot(const unsigned int & pMaxClusterHitTot)

        void setMaxHitTot(const unsigned int & pMaxHitTot)

        void getClusterSizeHist(unsigned int & rNparameterValues, unsigned int *& rClusterSize, bool copy)
        void getClusterTotHist(unsigned int & rNparameterValues, unsigned int *& rClusterTot, bool copy)

        # void clusterize()

        unsigned int getNclusters()

        void reset()
        void test()

cdef class PyDataClusterizer:
    cdef Clusterizer * thisptr  # hold a C++ instance which we're wrapping
    def __cinit__(self):
        self.thisptr = new Clusterizer()
    def __dealloc__(self):
        del self.thisptr
    def set_debug_output(self, toggle):
        self.thisptr.setDebugOutput(< bool > toggle)
    def set_info_output(self, toggle):
        self.thisptr.setInfoOutput(< bool > toggle)
    def set_warning_output(self, toggle):
        self.thisptr.setWarningOutput(< bool > toggle)
    def set_error_output(self, toggle):
        self.thisptr.setErrorOutput(< bool > toggle)
    def add_hits(self, cnp.ndarray[numpy_hit_info, ndim=1] hit_info):
        self.thisptr.addHits(< HitInfo *&> hit_info.data, < unsigned int > hit_info.shape[0])
    def create_cluster_hit_info_array(self, value=True):
        self.thisptr.createClusterHitInfoArray(< bool > value)
    def create_cluster_info_array(self, value=True):
        self.thisptr.createClusterInfoArray(< bool > value)
    def set_cluster_hit_info_array(self, cnp.ndarray[numpy_cluster_hit_info, ndim=1] cluster_hit_info):
        self.thisptr.setClusterHitInfoArray(< ClusterHitInfo *&> cluster_hit_info.data, < const unsigned int &> cluster_hit_info.shape[0])
    def set_cluster_info_array(self, cnp.ndarray[numpy_cluster_info, ndim=1] cluster_info):
        self.thisptr.setClusterInfoArray(< ClusterInfo *&> cluster_info.data, < const unsigned int &> cluster_info.shape[0])
    def set_x_cluster_distance(self, value):
        self.thisptr.setXclusterDistance(< const unsigned int &> value)
    def set_y_cluster_distance(self, value):
        self.thisptr.setYclusterDistance(< const unsigned int &> value)
    def set_bcid_cluster_distance(self, value):
        self.thisptr.setBCIDclusterDistance(< const unsigned int &> value)
    def set_min_cluster_hits(self, value):
        self.thisptr.setMinClusterHits(< const unsigned int &> value)
    def set_max_cluster_hits(self, value):
        self.thisptr.setMaxClusterHits(< const unsigned int &> value)
    def set_max_cluster_hit_tot(self, value):
        self.thisptr.setMaxClusterHitTot(< const unsigned int &> value)
    def set_max_tot(self, value):
        self.thisptr.setMaxHitTot(<const unsigned int &> value)
    def get_cluster_size_hist(self, cnp.ndarray[cnp.uint32_t, ndim=1] cluster_size_hist, value=True):
        rNparameterValues = 0
        self.thisptr.getClusterSizeHist(< unsigned int &> rNparameterValues, < unsigned int *&> cluster_size_hist.data, < bool > value)
        return rNparameterValues
    def get_cluster_tot_hist(self, cnp.ndarray[cnp.uint32_t, ndim=1] cluster_tot_hist, value=True):
        rNparameterValues = 0
        self.thisptr.getClusterTotHist(< unsigned int &> rNparameterValues, < unsigned int *&> cluster_tot_hist.data, < bool > value)
        return rNparameterValues
    def get_n_clusters(self):
        return < unsigned int > self.thisptr.getNclusters()
    def reset(self):
        self.thisptr.reset()
    def test(self):
        self.thisptr.test()
