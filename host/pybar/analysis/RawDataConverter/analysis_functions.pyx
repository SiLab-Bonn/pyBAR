# distutils: language = c++

import numpy as np
cimport numpy as cnp
cnp.import_array()  # if array is used it has to be imported, otherwise possible runtime error
from numpy cimport ndarray
from libcpp cimport bool  # to be able to use bool variables
from tables import dtype_from_descr
from libc.stdint cimport uint8_t, int64_t

from pybar.analysis.RawDataConverter.data_struct cimport numpy_hit_info, numpy_meta_data, numpy_meta_data_v2, numpy_meta_word_data
from pybar.analysis.RawDataConverter.data_struct import MetaTable, MetaTableV2

cdef extern from "AnalysisFunctions.h":
    unsigned int getNclusterInEvents(int64_t*& rEventNumber, const unsigned int& rSize, int64_t*& rResultEventNumber, unsigned int*& rResultCount)
    unsigned int getEventsInBothArrays(int64_t*& rEventArrayOne, const unsigned int& rSizeArrayOne, int64_t*& rEventArrayTwo, const unsigned int& rSizeArrayTwo, int64_t*& rEventArrayIntersection)
    void in1d_sorted(int64_t*& rEventArrayOne, const unsigned int& rSizeArrayOne, int64_t*& rEventArrayTwo, const unsigned int& rSizeArrayTwo, uint8_t*& rSelection)
    void histogram_3d(int*& x, int*& y, int*& z, const unsigned int& rSize, const unsigned int& rNbinsX, const unsigned int& rNbinsY, const unsigned int& rNbinsZ, uint8_t*& rResult) except +

def get_n_cluster_in_events(cnp.ndarray[cnp.int64_t, ndim=1] event_numbers, cnp.ndarray[cnp.int64_t, ndim=1] result_event_numbers, cnp.ndarray[cnp.uint32_t, ndim=1] result_cluster_count):
    return getNclusterInEvents(<int64_t*&> event_numbers.data, <const unsigned int&> event_numbers.shape[0], <int64_t*&> result_event_numbers.data, <unsigned int*&> result_cluster_count.data)


def get_events_in_both_arrays(cnp.ndarray[cnp.int64_t, ndim=1] array_one, cnp.ndarray[cnp.int64_t, ndim=1] array_two, cnp.ndarray[cnp.int64_t, ndim=1] array_result):
    return getEventsInBothArrays(<int64_t*&> array_one.data, <const unsigned int&> array_one.shape[0], <int64_t*&> array_two.data, <const unsigned int&> array_two.shape[0], <int64_t*&> array_result.data)


def get_in1d_sorted(cnp.ndarray[cnp.int64_t, ndim=1] array_one, cnp.ndarray[cnp.int64_t, ndim=1] array_two, cnp.ndarray[cnp.uint8_t, ndim=1] array_result):
    in1d_sorted(<int64_t*&> array_one.data, <const unsigned int&> array_one.shape[0], <int64_t*&> array_two.data, <const unsigned int&> array_two.shape[0], <uint8_t*&> array_result.data)
    return (array_result == 1)


def hist_3d(cnp.ndarray[cnp.int32_t, ndim=1] x, cnp.ndarray[cnp.int32_t, ndim=1] y, cnp.ndarray[cnp.int32_t, ndim=1] z, const unsigned int& n_x, const unsigned int& n_y, const unsigned int& n_z, cnp.ndarray[cnp.uint8_t, ndim=1] array_result):
    histogram_3d(<int*&> x.data, <int*&> y.data, <int*&> z.data, <const unsigned int&> x.shape[0], <const unsigned int&> n_x, <const unsigned int&> n_y, <const unsigned int&> n_z, <uint8_t*&> array_result.data)
  