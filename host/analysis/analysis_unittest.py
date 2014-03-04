''' Script to check the correctness of the analysis. The analysis is done on raw data and all results are compared to a recorded analysis.'''
import unittest

import tables as tb
import numpy as np
from analyze_raw_data import AnalyzeRawData


class TestAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from RawDataConverter.data_interpreter import PyDataInterpreter
        from RawDataConverter.data_histograming import PyDataHistograming
        from RawDataConverter.data_clusterizer import PyDataClusterizer
        cls.interpreter = PyDataInterpreter()
        cls.histogram = PyDataHistograming()
        cls.clusterizer = PyDataClusterizer()
        # interpret the test data, do not show any feedback (no prints to console, no plots)
        with AnalyzeRawData(raw_data_file='unit_test_data_1.h5', analyzed_data_file='unit_test_data_1_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
            analyze_raw_data.create_cluster_hit_table = True  # adds the cluster id and seed info to each hit, std. setting is false
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_source_scan_hist = True  # create source scan hists
            analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.create_meta_word_index = True  # stores the start and stop raw data word index for every event, std. setting is false
            analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False
            analyze_raw_data.n_injections = 100  # set the numbers of injections, needed for fast threshold/noise determination
            analyze_raw_data.n_bcid = 16  # set the number of BCIDs per event, needed to judge the event structure
            analyze_raw_data.max_tot_value = 13  # set the maximum ToT value considered to be a hit, 14 is a late hit
            analyze_raw_data.use_trigger_number = False
            analyze_raw_data.interpreter.use_tdc_word(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.interpreter.set_debug_output(False)
            analyze_raw_data.histograming.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=False)  # the actual start conversion command

        with AnalyzeRawData(raw_data_file=None, analyzed_data_file='unit_test_data_1_interpreted.h5') as analyze_raw_data:
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.create_cluster_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file='unit_test_data_1_analyzed.h5')

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
        with tb.open_file('unit_test_data_1_result.h5', 'r') as h5_file_stored_results:
            with tb.open_file('unit_test_data_1_interpreted.h5', 'r') as h5_file_actual_results:
                expected_nodes = sum(1 for _ in enumerate(h5_file_stored_results.root))  # calculated the number of nodes
                nodes = sum(1 for _ in enumerate(h5_file_actual_results.root))  # calculated the number of nodes
                self.assertEqual(expected_nodes, nodes, msg='The number of nodes in the file is wrong.')  # compare the number of nodes
                data_equal = True
                error_msg = ''
                for node in h5_file_stored_results.root:  # loop over all nodes and compare each node, do not abort if one node is wrong
                    node_name = node.name
                    expected_data = h5_file_stored_results.get_node(h5_file_stored_results.root, node_name)[:]
                    data = h5_file_actual_results.get_node(h5_file_actual_results.root, node_name)[:]
                    try:
                        if not (expected_data == data).all():  # compare the arrays for each element
                            data_equal = False
                            error_msg += node_name + ' '
                    except AttributeError:  # .all() only works on non scalars
                        if not (expected_data == data):
                            data_equal = False
                            error_msg += node_name + ' '
                error_msg += 'are wrong.'
                self.assertTrue(data_equal, msg=error_msg)

    def test_hit_data_analysis(self):  # test the hit histograming/clustering starting from the interpreted data
        with tb.open_file('unit_test_data_1_result.h5', 'r') as h5_file_stored_results:
            with tb.open_file('unit_test_data_1_analyzed.h5', 'r') as h5_file_actual_results:
                expected_nodes = 7
                nodes = sum(1 for _ in enumerate(h5_file_actual_results.root))  # calculated the number of nodes
                self.assertEqual(expected_nodes, nodes, msg='The number of nodes in the file is wrong.')  # compare the number of nodes
                data_equal = True
                error_msg = ''
                for node in h5_file_actual_results.root:  # loop over all nodes and compare each node, do not abort if one node is wrong
                    node_name = node.name
                    expected_data = h5_file_stored_results.get_node(h5_file_stored_results.root, node_name)[:]
                    data = h5_file_actual_results.get_node(h5_file_actual_results.root, node_name)[:]
                    try:
                        if not (expected_data == data).all():  # compare the arrays for each element
                            data_equal = False
                            error_msg += node_name + ' '
                    except AttributeError:  # .all() only works on non scalars
                        if not (expected_data == data):
                            data_equal = False
                            error_msg += node_name + ' '
                error_msg += 'are wrong.'
                self.assertTrue(data_equal, msg=error_msg)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAnalysis)
    unittest.TextTestRunner(verbosity=2).run(suite)
