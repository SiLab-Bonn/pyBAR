''' Script to check the correctness of the analysis. The analysis is done on raw data and all results are compared to a recorded analysis.
'''

import unittest
import os
import tables as tb
import numpy as np
import progressbar

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.RawDataConverter.data_interpreter import PyDataInterpreter
from pybar.analysis.RawDataConverter.data_histograming import PyDataHistograming
from pybar.analysis.RawDataConverter.data_clusterizer import PyDataClusterizer
from pybar.analysis import analysis_utils
from pybar.analysis.RawDataConverter import data_struct

tests_data_folder = 'tests//test_analysis//'


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
        for column_name in second_array.dtype.names:
            try:
                first_array[column_name]
            except ValueError:
                return_str += 'Additional column ' + column_name + ' found. '
                continue
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
                try:
                    expected_data = first_h5_file.get_node(first_h5_file.root, node_name)[:]
                    data = second_h5_file.get_node(second_h5_file.root, node_name)[:]
                    try:
                        if not (expected_data == data).all():  # compare the arrays for each element
                            checks_passed = False
                            error_msg += node_name
                            if detailed_comparison:
                                error_msg += get_array_differences(expected_data, data)
                            error_msg += '\n'
                    except AttributeError:  # .all() only works on non scalars, recarray is somewhat a scalar
                        if not (expected_data == data):
                            checks_passed = False
                            error_msg += node_name
                            if detailed_comparison:
                                error_msg += get_array_differences(expected_data, data)
                            error_msg += '\n'
                except tb.NoSuchNodeError:
                    checks_passed = False
                    error_msg += 'Unknown node ' + node_name + '\n'
    return checks_passed, error_msg


class TestAnalysis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.interpreter = PyDataInterpreter()
        cls.histogram = PyDataHistograming()
        cls.clusterizer = PyDataClusterizer()
        with AnalyzeRawData(raw_data_file=tests_data_folder + 'unit_test_data_1.h5', analyzed_data_file=tests_data_folder + 'unit_test_data_1_interpreted.h5') as analyze_raw_data:  # analyze the digital scan raw data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 3000017
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
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=tests_data_folder + 'unit_test_data_2.h5', analyzed_data_file=tests_data_folder + 'unit_test_data_2_interpreted.h5') as analyze_raw_data:  # analyze the fast threshold scan raw data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 3000017
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.create_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file=tests_data_folder + 'unit_test_data_1_interpreted.h5') as analyze_raw_data:   # analyze the digital scan hit data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 3000017
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.create_cluster_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file=tests_data_folder + 'unit_test_data_1_analyzed.h5')
        with AnalyzeRawData(raw_data_file=tests_data_folder + 'unit_test_data_3.h5', analyzed_data_file=tests_data_folder + 'unit_test_data_3_interpreted.h5') as analyze_raw_data:  # analyze the digital scan raw data per scan parameter, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 3000017
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
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=tests_data_folder + 'unit_test_data_2.h5', analyzed_data_file=tests_data_folder + 'unit_test_data_2_hits.h5') as analyze_raw_data:  # analyze the fast threshold scan raw data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 3000017
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.create_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file=tests_data_folder + 'unit_test_data_2_hits.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000017
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file=tests_data_folder + 'unit_test_data_2_analyzed.h5')
        with AnalyzeRawData(raw_data_file=tests_data_folder + 'unit_test_data_4.h5', analyzed_data_file=tests_data_folder + 'unit_test_data_4_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000017
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=[tests_data_folder + 'unit_test_data_4_parameter_128.h5', tests_data_folder + 'unit_test_data_4_parameter_256.h5'], analyzed_data_file=tests_data_folder + 'unit_test_data_4_interpreted_2.h5', scan_parameter_name='parameter') as analyze_raw_data:
            analyze_raw_data.chunk_size = 3000017
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command

    @classmethod
    def tearDownClass(cls):  # remove created files
        # explicit del call to check c++ library destructors
        del cls.interpreter
        del cls.histogram
        del cls.clusterizer
        os.remove(tests_data_folder + 'unit_test_data_1_interpreted.h5')
        os.remove(tests_data_folder + 'unit_test_data_1_analyzed.h5')
        os.remove(tests_data_folder + 'unit_test_data_2_interpreted.h5')
        os.remove(tests_data_folder + 'unit_test_data_2_analyzed.h5')
        os.remove(tests_data_folder + 'unit_test_data_2_hits.h5')
        os.remove(tests_data_folder + 'unit_test_data_3_interpreted.h5')
        os.remove(tests_data_folder + 'unit_test_data_4_interpreted.h5')
        os.remove(tests_data_folder + 'unit_test_data_4_interpreted_2.h5')

    def test_libraries_stability(self):  # calls 50 times the constructor and destructor to check the libraries
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.ETA()], maxval=50, term_width=80)
        progress_bar.start()
        for i in range(50):
            interpreter = PyDataInterpreter()
            histogram = PyDataHistograming()
            clusterizer = PyDataClusterizer()
            del interpreter
            del histogram
            del clusterizer
            progress_bar.update(i)
        progress_bar.finish()

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
                                     ('TDCtimeStamp', np.uint8),
                                     ('triggerStatus', np.uint8),
                                     ('serviceRecord', np.uint32),
                                     ('eventStatus', np.uint16)
                                     ])
        self.assertTrue(self.interpreter.get_hit_size() == hits.itemsize)

    def test_raw_data_analysis(self):  # test the created interpretation file against the stored one
        data_equal, error_msg = compare_h5_files(tests_data_folder + 'unit_test_data_1_result.h5', tests_data_folder + 'unit_test_data_1_interpreted.h5')
        self.assertTrue(data_equal, msg=error_msg)

    def test_threshold_analysis(self):  # test the created interpretation file of the threshold data against the stored one
        data_equal, error_msg = compare_h5_files(tests_data_folder + 'unit_test_data_2_result.h5', tests_data_folder + 'unit_test_data_2_interpreted.h5')
        self.assertTrue(data_equal, msg=error_msg)

    def test_hit_data_analysis(self):  # test the hit histograming/clustering starting from the predefined interpreted data
        data_equal, error_msg = compare_h5_files(tests_data_folder + 'unit_test_data_1_result.h5', tests_data_folder + 'unit_test_data_1_analyzed.h5', expected_nodes=8)
        self.assertTrue(data_equal, msg=error_msg)

    def test_analysis_per_scan_parameter(self):  # check if the data per scan parameter is correctly analyzed
        # check if the data with more than one scan parameter is correctly analyzed
        data_equal, error_msg = compare_h5_files(tests_data_folder + 'unit_test_data_3_result.h5', tests_data_folder + 'unit_test_data_3_interpreted.h5')
        self.assertTrue(data_equal, msg=error_msg)
        # check the data from two files with one scan parameter each with the previous file containing two scan parameters
        data_equal, error_msg = compare_h5_files(tests_data_folder + 'unit_test_data_4_interpreted.h5', tests_data_folder + 'unit_test_data_4_interpreted_2.h5')
        self.assertTrue(data_equal, msg=error_msg)
        # check if the occupancy hist from the threshold scan hit data is correctly created
        with tb.open_file(tests_data_folder + 'unit_test_data_2_interpreted.h5', 'r') as first_h5_file:
            with tb.open_file(tests_data_folder + 'unit_test_data_2_analyzed.h5', 'r') as second_h5_file:
                occupancy_expected = first_h5_file.root.HistOcc[:]
                occupancy = second_h5_file.root.HistOcc[:]
                self.assertTrue(np.all(occupancy_expected == occupancy), msg=error_msg)

    def test_analysis_utils_get_n_cluster_in_events(self):  # check compiled get_n_cluster_in_events function
        event_numbers = np.array([[0, 0, 1, 2, 2, 2, 4, 4000000000, 4000000000, 40000000000, 40000000000], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=np.int64)  # use data format with non linear memory alignment
        result = analysis_utils.get_n_cluster_in_events(event_numbers[0])
        self.assertListEqual([0, 1, 2, 4, 4000000000, 40000000000], result[:, 0].tolist())
        self.assertListEqual([2, 1, 3, 1, 2, 2], result[:, 1].tolist())

    def test_analysis_utils_get_events_in_both_arrays(self):  # check compiled get_events_in_both_arrays function
        event_numbers = np.array([[0, 0, 2, 2, 2, 4, 5, 5, 6, 7, 7, 7, 8], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=np.int64)
        event_numbers_2 = np.array([1, 1, 1, 2, 2, 2, 4, 4, 4, 7], dtype=np.int64)
        result = analysis_utils.get_events_in_both_arrays(event_numbers[0], event_numbers_2)
        self.assertListEqual([2, 4, 7], result.tolist())

    def test_analysis_utils_get_max_events_in_both_arrays(self):  # check compiled get_max_events_in_both_arrays function
        event_numbers = np.array([[0, 0, 1, 1, 2], [0, 0, 0, 0, 0]], dtype=np.int64)
        event_numbers_2 = np.array([0, 3, 3, 4], dtype=np.int64)
        result = analysis_utils.get_max_events_in_both_arrays(event_numbers[0], event_numbers_2)
        self.assertListEqual([0, 0, 1, 1, 2, 3, 3, 4], result.tolist())

    def test_map_cluster(self):  # check the compiled function against result
        cluster = np.zeros((20, ), dtype=tb.dtype_from_descr(data_struct.ClusterInfoTable))
        result = np.zeros((20, ), dtype=tb.dtype_from_descr(data_struct.ClusterInfoTable))
        result[1]["event_number"], result[3]["event_number"], result[4]["event_number"], result[7]["event_number"] = 1, 2, 3, 4

        for index in range(cluster.shape[0]):
            cluster[index]["event_number"] = index

        common_event_number = np.array([0, 1, 1, 2, 3, 3, 3, 4, 4], dtype=np.int64)
        self.assertTrue(np.all(analysis_utils.map_cluster(common_event_number, cluster) == result[:common_event_number.shape[0]]))

    def test_analysis_utils_in1d_events(self):  # check compiled get_in1d_sorted function
        event_numbers = np.array([[0, 0, 2, 2, 2, 4, 5, 5, 6, 7, 7, 7, 8], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=np.int64)
        event_numbers_2 = np.array([1, 1, 1, 2, 2, 2, 4, 4, 4, 7], dtype=np.int64)
        result = event_numbers[0][analysis_utils.in1d_events(event_numbers[0], event_numbers_2)]
        self.assertListEqual([2, 2, 2, 4, 7, 7, 7], result.tolist())

    def test_1d_index_histograming(self):  # check compiled hist_2D_index function
        x = np.random.randint(0, 100, 100)
        shape = (100, )
        array_fast = analysis_utils.hist_1d_index(x, shape=shape)
        array = np.histogram(x, bins=shape[0], range=(0, shape[0]))[0]
        shape = (5, )  # shape that is too small for the indices to trigger exception
        exception_ok = False
        try:
            array_fast = analysis_utils.hist_1d_index(x, shape=shape)
        except IndexError:
            exception_ok = True
        except:  # other exception that should not occur
            pass
        self.assertTrue(exception_ok & np.all(array == array_fast))

    def test_2d_index_histograming(self):  # check compiled hist_2D_index function
        x, y = np.random.randint(0, 100, 100), np.random.randint(0, 100, 100)
        shape = (100, 100)
        array_fast = analysis_utils.hist_2d_index(x, y, shape=shape)
        array = np.histogram2d(x, y, bins=shape, range=[[0, shape[0]], [0, shape[1]]])[0]
        shape = (5, 200)  # shape that is too small for the indices to trigger exception
        exception_ok = False
        try:
            array_fast = analysis_utils.hist_2d_index(x, y, shape=shape)
        except IndexError:
            exception_ok = True
        except:  # other exception that should not occur
            pass
        self.assertTrue(exception_ok & np.all(array == array_fast))

    def test_3d_index_histograming(self):  # check compiled hist_3D_index function
        with tb.open_file(tests_data_folder + 'hist_data.h5', mode="r") as in_file_h5:
            xyz = in_file_h5.root.HistDataXYZ[:]
            x, y, z = xyz[0], xyz[1], xyz[2]
            shape = (100, 100, 100)
            array_fast = analysis_utils.hist_3d_index(x, y, z, shape=shape)
            array = np.histogramdd(np.column_stack((x, y, z)), bins=shape, range=[[0, shape[0] - 1], [0, shape[1] - 1], [0, shape[2] - 1]])[0]
            shape = (50, 200, 200)  # shape that is too small for the indices to trigger exception
            exception_ok = False
            try:
                array_fast = analysis_utils.hist_3d_index(x, y, z, shape=shape)
            except IndexError:
                exception_ok = True
            except:  # other exception that should not occur
                pass
            self.assertTrue(exception_ok & np.all(array == array_fast))

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAnalysis)
    unittest.TextTestRunner(verbosity=2).run(suite)
