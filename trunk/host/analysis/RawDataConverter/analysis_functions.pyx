# distutils: language = c++

import numpy as np
cimport numpy as cnp
cnp.import_array()  # if array is used it has to be imported, otherwise possible runtime error
from numpy cimport ndarray
from libcpp cimport bool  # to be able to use bool variables
from data_struct cimport numpy_hit_info, numpy_meta_data, numpy_meta_data_v2, numpy_meta_word_data
from data_struct import MetaTable, MetaTableV2
from tables import dtype_from_descr
from libc.stdint cimport int64_t

cdef extern from "AnalysisFunctions.h":
    unsigned int getNclusterInEvents(int64_t*& rEventNumber, const unsigned int& rSize, int64_t*& rResultEventNumber, unsigned int*& rResultCount)

def get_n_cluster_in_events(cnp.ndarray[cnp.int64_t, ndim=1] event_numbers, cnp.ndarray[cnp.int64_t, ndim=1] result_event_numbers, cnp.ndarray[cnp.uint32_t, ndim=1] result_cluster_count):
    return getNclusterInEvents(<int64_t*&> event_numbers.data, <const unsigned int&> event_numbers.shape[0], <int64_t*&> result_event_numbers.data, <unsigned int*&> result_cluster_count.data)
    
