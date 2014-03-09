''' Script to check the correctness of the analysis. The analysis is done on raw data and all results are compared to a recorded analysis.'''
import unittest
import os
import tables as tb
import numpy as np
from analyze_raw_data import AnalyzeRawData
from RawDataConverter.data_interpreter import PyDataInterpreter
from RawDataConverter.data_histograming import PyDataHistograming
from RawDataConverter.data_clusterizer import PyDataClusterizer


def get_array_differences(first_array, second_array):
    '''Takes two numpy.ndarrays and compares them on a column basis.
    Different column data types, missing columns and columns with different values are returned in a string.

    Parameters
    ----------
    first_array : numpy.ndarray
    second_array : numpy.ndarray

    Returns
    -------
    string
    '''
    if first_array.dtype.names is None:  # normal nd.array
        return ': Sum first array: ' + str(np.sum(first_array)) + ', Sum second array: ' + str(np.sum(second_array))
    else:
        return_str = ''
        for column_name in first_array.dtype.names:
            first_column = first_array[column_name]
            try:
                second_column = second_array[column_name]
            except ValueError:
                return_str += 'No ' + column_name + ' column found. '
                continue
            if (first_column.dtype != second_column.dtype):
                return_str += 'Column ' + column_name + ' has different data type. '
            if not (first_column == second_column).all():  # check if the data of the column is equal
                return_str += 'Column ' + column_name + ' not equal. '
                print column_name, np.where(first_column != second_column)
                print first_array[np.where(first_column != second_column)]
                print second_array[np.where(first_column != second_column)]
        return ': ' + return_str


def compare_h5_files(first_file, second_file, expected_nodes=None, detailed_comparison=True):
    '''Takes two hdf5 files and check for equality of all nodes.
    Returns true if the node data is equal and the number of nodes is the number of expected nodes.
    It also returns a error string containing the names of the nodes that are not equal.

    Parameters
    ----------
    first_file : string
        Path to the first file.
    second_file : string
        Path to the first file.
    expected_nodes : Int
        The number of nodes expected in the second_file. If not specified the number of nodes expected in the second_file equals
        the number of nodes in the first file.

    Returns
    -------
    bool, string
    '''
    checks_passed = True
    error_msg = ""
    with tb.open_file(first_file, 'r') as first_h5_file:
        with tb.open_file(second_file, 'r') as second_h5_file:
            expected_nodes = sum(1 for _ in enumerate(first_h5_file.root)) if expected_nodes is None else expected_nodes  # set the number of expected nodes
            nodes = sum(1 for _ in enumerate(second_h5_file.root))  # calculated the number of nodes
            if nodes != expected_nodes:
                checks_passed = False
                error_msg += 'The number of nodes in the file is wrong.\n'
            for node in second_h5_file.root:  # loop over all nodes and compare each node, do not abort if one node is wrong
                node_name = node.name
                expected_data = first_h5_file.get_node(first_h5_file.root, node_name)[:]
                data = second_h5_file.get_node(second_h5_file.root, node_name)[:]
                try:
                    if not (expected_data == data).all():  # compare the arrays for each element
                        checks_passed = False
                        error_msg += node_name
                        if detailed_comparison:
                            error_msg += get_array_differences(data, expected_data)
                        error_msg += '\n'
                except AttributeError:  # .all() only works on non scalars, recarray is somewhat a scalar
                    if not (expected_data == data):
                        checks_passed = False
                        error_msg += node_name
                        if detailed_comparison:
                            error_msg += get_array_differences(data, expected_data)
                        error_msg += '\n'
    return checks_passed, error_msg


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.interpreter = PyDataInterpreter()
        cls.histogram = PyDataHistograming()
        cls.clusterizer = PyDataClusterizer()

#         # analyze the digital scan raw data, do not show any feedback (no prints to console, no plots)
        with AnalyzeRawData(raw_data_file='unittest_data//unit_test_data_1.h5', analyzed_data_file='unittest_data//unit_test_data_1_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000001
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
            analyze_raw_data.create_cluster_hit_table = True  # adds the cluster id and seed info to each hit, std. setting is false
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.create_meta_word_index = True  # stores the start and stop raw data word index for every event, std. setting is false
            analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False
            analyze_raw_data.use_trigger_number = False
            analyze_raw_data.interpreter.use_tdc_word(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=False)  # the actual start conversion command

        # analyze the fast threshold scan raw data, do not show any feedback (no prints to console, no plots)
        with AnalyzeRawData(raw_data_file='unittest_data//unit_test_data_2.h5', analyzed_data_file='unittest_data//unit_test_data_2_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000001
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.create_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
            analyze_raw_data.interpret_word_table(fei4b=False)  # the actual start conversion command

        # analyze the digital scan hit data, do not show any feedback (no prints to console, no plots)
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file='unittest_data//unit_test_data_1_result.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000001
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.create_cluster_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file='unittest_data//unit_test_data_1_analyzed.h5')

        # analyze the digital scan raw data per scan parameter, do not show any feedback (no prints to console, no plots)
        with AnalyzeRawData(raw_data_file='unittest_data//unit_test_data_3.h5', analyzed_data_file='unittest_data//unit_test_data_3_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000001
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
            analyze_raw_data.create_cluster_hit_table = True  # adds the cluster id and seed info to each hit, std. setting is false
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.create_meta_word_index = True  # stores the start and stop raw data word index for every event, std. setting is false
            analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False
            analyze_raw_data.use_trigger_number = False
            analyze_raw_data.interpreter.use_tdc_word(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file='unittest_data//unit_test_data_4.h5', analyzed_data_file='unittest_data//unit_test_data_4_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000001
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=['unittest_data//unit_test_data_4_parameter_128.h5', 'unittest_data//unit_test_data_4_parameter_256.h5'], analyzed_data_file='unittest_data//unit_test_data_4_interpreted_2.h5', scan_parameter_name='parameter') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000001
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=False)  # the actual start conversion command

    @classmethod
    def tearDownClass(cls):  # remove created files
        # explicit del call to check c++ library destructors
        del cls.interpreter
        del cls.histogram
        del cls.clusterizer
        os.remove('unittest_data//unit_test_data_1_interpreted.h5')
        os.remove('unittest_data//unit_test_data_1_analyzed.h5')
        os.remove('unittest_data//unit_test_data_2_interpreted.h5')
        os.remove('unittest_data//unit_test_data_3_interpreted.h5')
        os.remove('unittest_data//unit_test_data_4_interpreted.h5')
        os.remove('unittest_data//unit_test_data_4_interpreted_2.h5')

    def test_libraries_stability(self):  # calls 10000 times the constructor and destructor to check the libraries
        for _ in range(1000):
            interpreter = PyDataInterpreter()
            histogram = PyDataHistograming()
            clusterizer = PyDataClusterizer()
            del interpreter
            del histogram
            del clusterizer

    def test_data_alignement(self):  # test if the data alignment is correct (important to detect 32/64 bit related issues)
        hits = np.empty((1,), dtype=[('eventNumber', np.uint64),
             ('triggerNumber', np.uint32),
             ('relativeBCID', np.uint8),
             ('LVLID', np.uint16),
             ('column', np.uint8),
             ('row', np.uint16),
             ('tot', np.uint8),
             ('BCID', np.uint16),
             ('TDC', np.uint16),
             ('triggerStatus', np.uint8),
             ('serviceRecord', np.uint32),
             ('eventStatus', np.uint16)
             ])
        self.assertTrue(self.interpreter.get_hit_size() == hits.itemsize)

    def test_raw_data_analysis(self):  # test the created interpretation file against the stored one
        data_equal, error_msg = compare_h5_files('unittest_data//unit_test_data_1_result.h5', 'unittest_data//unit_test_data_1_interpreted.h5')
        self.assertTrue(data_equal, msg=error_msg)

    def test_threshold_analysis(self):  # test the created interpretation file of the threshold data against the stored one
        data_equal, error_msg = compare_h5_files('unittest_data//unit_test_data_2_result.h5', 'unittest_data//unit_test_data_2_interpreted.h5')
        self.assertTrue(data_equal, msg=error_msg)

    def test_hit_data_analysis(self):  # test the hit histograming/clustering starting from the predefined interpreted data
        data_equal, error_msg = compare_h5_files('unittest_data//unit_test_data_1_result.h5', 'unittest_data//unit_test_data_1_analyzed.h5', expected_nodes=7)
        self.assertTrue(data_equal, msg=error_msg)

    def test_analysis_per_scan_parameter(self):  # check if the data per scan parameter is correctly analyzed
        data_equal, error_msg = compare_h5_files('unittest_data//unit_test_data_3_result.h5', 'unittest_data//unit_test_data_3_interpreted.h5')
        self.assertTrue(data_equal, msg=error_msg)
        data_equal, error_msg = compare_h5_files('unittest_data//unit_test_data_4_interpreted.h5', 'unittest_data//unit_test_data_4_interpreted_2.h5')
        self.assertTrue(data_equal, msg=error_msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAnalysis)
    unittest.TextTestRunner(verbosity=2).run(suite)
