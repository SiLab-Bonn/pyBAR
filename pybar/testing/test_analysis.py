''' Script to check the correctness of the analysis. The analysis is done on raw data and all results are compared to a recorded analysis.
'''
import unittest
import os
import zlib

import tables as tb
import numpy as np
from numpy.testing import assert_array_equal

import progressbar

from pixel_clusterizer.clusterizer import HitClusterizer

from pybar_fei4_interpreter.data_interpreter import PyDataInterpreter
from pybar_fei4_interpreter.data_histograming import PyDataHistograming
from pybar_fei4_interpreter import analysis_utils as fast_analysis_utils
from pybar_fei4_interpreter import data_struct

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.testing.tools import test_tools
from pybar.scans.calibrate_hit_or import create_hitor_calibration
from pybar.daq.readout_utils import get_col_row_array_from_data_record_array, convert_data_array, is_data_record
from pybar.analysis.analysis_utils import data_aligned_at_events, InvalidInputError
import pybar.scans.analyze_source_scan_tdc_data as tdc_analysis


tests_data_folder = 'test_analysis_data/'


class TestAnalysis(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.interpreter = PyDataInterpreter()
        cls.histogram = PyDataHistograming()
        with AnalyzeRawData(raw_data_file=os.path.join(tests_data_folder, 'unit_test_data_1.h5'), analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_1_interpreted.h5'), create_pdf=False) as analyze_raw_data:  # analyze the digital scan raw data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 500009
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
            analyze_raw_data.create_cluster_hit_table = True  # adds the cluster id and seed info to each hit, std. setting is false
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.create_meta_word_index = True  # stores the start and stop raw data word index for every event, std. setting is false
            analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=os.path.join(tests_data_folder, 'unit_test_data_2.h5'), analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_2_interpreted.h5'), create_pdf=False) as analyze_raw_data:  # analyze the fast threshold scan raw data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 500009
            analyze_raw_data.n_injections = 100  # Not stored in file for unit test data, has to be set manually
            analyze_raw_data.create_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # The old unit test data does not hav the settings stored in file
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_1_interpreted.h5'), create_pdf=False) as analyze_raw_data:   # analyze the digital scan hit data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 500009
            analyze_raw_data.create_cluster_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file=os.path.join(tests_data_folder, 'unit_test_data_1_analyzed.h5'))
        with AnalyzeRawData(raw_data_file=os.path.join(tests_data_folder, 'unit_test_data_3.h5'), analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_3_interpreted.h5'), create_pdf=False) as analyze_raw_data:  # analyze the digital scan raw data per scan parameter, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 500009
            analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
            analyze_raw_data.create_cluster_hit_table = True  # adds the cluster id and seed info to each hit, std. setting is false
            analyze_raw_data.create_cluster_table = True  # enables the creation of a table with all clusters, std. setting is false
            analyze_raw_data.create_trigger_error_hist = True  # creates a histogram summing up the trigger errors
            analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
            analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
            analyze_raw_data.create_meta_word_index = True  # stores the start and stop raw data word index for every event, std. setting is false
            analyze_raw_data.create_meta_event_index = True  # stores the event number for each readout in an additional meta data array, default: False
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # The old unit test data does not hav the settings stored in file
        with AnalyzeRawData(raw_data_file=os.path.join(tests_data_folder, 'unit_test_data_2.h5'), analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_2_hits.h5'), create_pdf=False) as analyze_raw_data:  # analyze the fast threshold scan raw data, do not show any feedback (no prints to console, no plots)
            analyze_raw_data.chunk_size = 2999999
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_threshold_hists = True  # makes only sense if threshold scan data is analyzed, std. setting is false
            analyze_raw_data.n_injections = 100  # Not stored in file for unit test data, has to be set manually
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # The old unit test data does not hav the settings stored in file
        with AnalyzeRawData(raw_data_file=None, analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_2_hits.h5'), create_pdf=False) as analyze_raw_data:
            analyze_raw_data.chunk_size = 2999999
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.n_injections = 100  # Not stored in file for unit test data, has to be set manually
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file=os.path.join(tests_data_folder, 'unit_test_data_2_analyzed.h5'))
        with AnalyzeRawData(raw_data_file=os.path.join(tests_data_folder, 'unit_test_data_4.h5'), analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_4_interpreted.h5'), create_pdf=False) as analyze_raw_data:
            analyze_raw_data.chunk_size = 2999999
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=[os.path.join(tests_data_folder, 'unit_test_data_4_parameter_128.h5'), os.path.join(tests_data_folder, 'unit_test_data_4_parameter_256.h5')], analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_4_interpreted_2.h5'), scan_parameter_name='parameter', create_pdf=False) as analyze_raw_data:
            analyze_raw_data.chunk_size = 2999999
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpret_word_table(use_settings_from_file=False, fei4b=False)  # the actual start conversion command
        with AnalyzeRawData(raw_data_file=os.path.join(tests_data_folder, 'unit_test_data_5.h5'), analyzed_data_file=os.path.join(tests_data_folder, 'unit_test_data_5_interpreted.h5'), create_pdf=False) as analyze_raw_data:
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.trig_count = 255
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.set_stop_mode = True
            analyze_raw_data.trigger_data_format = 0  # time stamp only
            analyze_raw_data.align_at_trigger = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(use_settings_from_file=False)  # The old unit test data does not hav the settings stored in file

    @classmethod
    def tearDownClass(cls):  # remove created files
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_1_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_1_analyzed.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_2_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_2_analyzed.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_2_hits.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_3_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_4_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_4_interpreted_2.h5'))
        os.remove(os.path.join(tests_data_folder, 'unit_test_data_5_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'hit_or_calibration.pdf'))
        os.remove(os.path.join(tests_data_folder, 'hit_or_calibration_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'hit_or_calibration_calibration.h5'))
        os.remove(os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted.h5'))
        os.remove(os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted_calibrated_tdc_hists.pdf'))
        os.remove(os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted_tdc_hists.h5'))
        os.remove(os.path.join(tests_data_folder, 'ext_trigger_scan_tdc.pdf'))
        os.remove(os.path.join(tests_data_folder, 'ext_trigger_scan_tlu.pdf'))
        os.remove(os.path.join(tests_data_folder, 'ext_trigger_scan_tlu_interpreted.h5'))

    def test_libraries_stability(self):  # calls 50 times the constructor and destructor to check the libraries
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.ETA()], maxval=50, term_width=80)
        progress_bar.start()
        for i in range(50):
            interpreter = PyDataInterpreter()
            histogram = PyDataHistograming()
            clusterizer = HitClusterizer()
            del interpreter
            del histogram
            del clusterizer
            progress_bar.update(i)
        progress_bar.finish()

    def test_data_alignement(self):  # Test if the data alignment is correct (important to detect 32/64 bit related issues)
        hits = np.empty((1,), dtype=[('event_number', np.uint64),
                                     ('trigger_number', np.uint32),
                                     ('trigger_time_stamp', np.uint32),
                                     ('relative_BCID', np.uint8),
                                     ('LVL1ID', np.uint16),
                                     ('column', np.uint8),
                                     ('row', np.uint16),
                                     ('tot', np.uint8),
                                     ('BCID', np.uint16),
                                     ('TDC', np.uint16),
                                     ('TDC_time_stamp', np.uint8),
                                     ('trigger_status', np.uint8),
                                     ('service_record', np.uint32),
                                     ('event_status', np.uint16)
                                     ])
        self.assertTrue(self.interpreter.get_hit_size() == hits.itemsize)

    def test_raw_data_analysis(self):  # test the created interpretation file against the stored one
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_1_result.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_1_interpreted.h5'))
        self.assertTrue(data_equal, msg=error_msg)

    def test_threshold_analysis(self):  # test the created interpretation file of the threshold data against the stored one
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_2_interpreted.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_2_result.h5'),
                                                            exact=False)
        self.assertTrue(data_equal, msg=error_msg)

    def test_hit_data_analysis(self):  # test the hit histogramming/clustering starting from the predefined interpreted data
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_1_result.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_1_analyzed.h5'),
                                                            node_names=["HistClusterTot", "HistTotPixel", "HistOcc", "ClusterHits", "Cluster", "HistClusterSize", "HistRelBcid", "HistTot"])
        self.assertTrue(data_equal, msg=error_msg)

    def test_analysis_per_scan_parameter(self):  # check if the data per scan parameter is correctly analyzed
        # check if the data with more than one scan parameter is correctly analyzed
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_3_result.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_3_interpreted.h5'))
        self.assertTrue(data_equal, msg=error_msg)
        # check the data from two files with one scan parameter each with the previous file containing two scan parameters
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_4_interpreted.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_4_interpreted_2.h5'))
        self.assertTrue(data_equal, msg=error_msg)
        # check if the occupancy hist from the threshold scan hit data is correctly created
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_2_interpreted.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_2_analyzed.h5'),
                                                            node_names=["HistThreshold", "HistNoise", "HistTotPixel", "HistOcc", "HistRelBcid", "HistTot"])
        self.assertTrue(data_equal, msg=error_msg)


    def test_analysis_utils_get_n_cluster_in_events(self):  # check compiled get_n_cluster_in_events function
        event_numbers = np.array([[0, 0, 1, 2, 2, 2, 4, 4000000000, 4000000000, 40000000000, 40000000000], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=np.int64)  # use data format with non linear memory alignment
        result = fast_analysis_utils.get_n_cluster_in_events(event_numbers[0])
        self.assertListEqual([0, 1, 2, 4, 4000000000, 40000000000], result[:, 0].tolist())
        self.assertListEqual([2, 1, 3, 1, 2, 2], result[:, 1].tolist())

    def test_analysis_utils_get_events_in_both_arrays(self):  # check compiled get_events_in_both_arrays function
        event_numbers = np.array([[0, 0, 2, 2, 2, 4, 5, 5, 6, 7, 7, 7, 8], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=np.int64)
        event_numbers_2 = np.array([1, 1, 1, 2, 2, 2, 4, 4, 4, 7], dtype=np.int64)
        result = fast_analysis_utils.get_events_in_both_arrays(event_numbers[0], event_numbers_2)
        self.assertListEqual([2, 4, 7], result.tolist())

    def test_analysis_utils_get_max_events_in_both_arrays(self):  # check compiled get_max_events_in_both_arrays function
        event_numbers = np.array([[0, 0, 1, 1, 2], [0, 0, 0, 0, 0]], dtype=np.int64)
        event_numbers_2 = np.array([0, 3, 3, 4], dtype=np.int64)
        result = fast_analysis_utils.get_max_events_in_both_arrays(event_numbers[0], event_numbers_2)
        self.assertListEqual([0, 0, 1, 1, 2, 3, 3, 4], result.tolist())

    def test_map_cluster(self):  # Check the compiled function against result
        cluster = np.zeros((20, ), dtype=tb.dtype_from_descr(data_struct.ClusterInfoTable))
        result = np.zeros((20, ), dtype=tb.dtype_from_descr(data_struct.ClusterInfoTable))
        result[1]["event_number"], result[3]["event_number"], result[4]["event_number"], result[7]["event_number"] = 1, 2, 3, 4

        for index in range(cluster.shape[0]):
            cluster[index]["event_number"] = index

        common_event_number = np.array([0, 1, 1, 2, 3, 3, 3, 4, 4], dtype=np.int64)
        self.assertTrue(np.all(fast_analysis_utils.map_cluster(common_event_number, cluster) == result[:common_event_number.shape[0]]))

    def test_hit_histogram(self):
        raw_data = np.array([67307647, 67645759, 67660079, 67541711, 67718111, 67913663, 67914223, 67847647, 67978655, 68081199, 68219119, 68219487, 68425615, 68311343, 68490719, 68373295, 68553519, 68693039, 68573503, 68709951, 68717058, 68734735, 68604719, 68753999, 68761151, 68847327, 69014799, 69079791, 69211359, 69221055, 69279567, 69499247, 69773183, 69788527, 69998559, 69868559, 69872655, 70003599, 69902527, 70274575, 70321471, 70429983, 70563295, 70574959, 70447631, 70584591, 70783023, 71091999, 70972687, 70985087, 71214815, 71382623, 71609135, 71643519, 71720527, 71897695, 72167199, 72040047, 72264927, 72423983, 77471983, 77602863, 77604383, 77485295, 77616415, 77618927, 77619231, 77639983, 77655871, 77544159, 77548303, 77338399, 77345567, 77346287, 77360399, 77255407, 77386211, 77268287, 77279215, 77409599, 77075983, 76951903, 76980527, 77117023, 76991055, 77011007, 77148127, 77148815, 76827167, 76700031, 76868895, 76758575, 76889567, 76558303, 76429599, 76584783, 76468191, 76610943, 76613743, 76620879, 76629375, 76285999, 76321908, 76194319, 76205599, 76233759, 76065391, 76075839, 76093759, 75801311, 75826319, 75829215, 75699231, 75403887, 75565039, 75439135, 75111711, 75115151, 75251487, 75258399, 75138015, 75303471, 74974111, 74868559, 75030047, 75050079, 74714591, 74722847, 74595103, 74649935, 74656815, 74796511, 74455519, 74391519, 74402607, 74534383, 74189695, 74064911, 74246271, 74116063, 74248719, 74133119, 73935183, 73941087, 73811295, 73663583, 73743423, 73449647, 73453391, 73323743, 73343471, 73474159, 73345087, 73206751, 72899295, 72958559, 72828447, 72542623, 82383232, 67374687, 67503967, 67766575, 68179999, 68052847, 68198239, 68104495, 68235759, 68238223, 68472415, 68490463, 68501279, 68621071, 68623903, 68821791, 68988639, 68864047, 69003183, 68876015, 69007423, 68891407, 69267743, 69272367, 69159567, 69666911, 69684447, 70003247, 70018895, 69898927, 69938543, 69942031, 70198863, 70339919, 70587455, 70462783, 70597679, 70796399, 70800015, 70703887, 71121183, 71323151, 71243535, 71578703, 71467695, 71622879, 71629359, 71831264, 71836511, 71710319, 71992943, 72353855, 72355039, 77606628, 77608287, 77622047, 77510223, 77653263, 77664319, 77546223, 77677471, 77549375, 77213519, 77219551, 77232207, 77234991, 77366511, 77373791, 77389647, 77404383, 77070655, 77087199, 76956975, 76996431, 77009183, 77015327, 76683567, 76840351, 76862255, 76888804, 76548975, 76554767, 76427087, 76560159, 76451967, 76456847, 76468015, 76627295, 76352831, 76354863, 76365887, 75923999, 76074175, 75955439, 76086063, 75774239, 75781535, 75792671, 75662111, 75793647, 75797167, 75827023, 75696543, 75390527, 75522031, 75533663, 75541775, 75432255, 75571535, 75115535, 75247999, 75145197, 75151391, 75160799, 74974991, 74852831, 74871839, 74882783, 75023199, 74896943, 75028767, 75046431, 74922463, 74725711, 74621199, 74658623, 74663183, 74336383, 74484559, 74364526, 74370287, 74370639, 74517983, 74393615, 74205471, 74217359, 74227263, 74231727, 74102559, 74237999, 74248735, 73953599, 73868591, 74000703, 74002975, 73877295, 73664910, 73695967, 73704751, 73579583, 73582639, 73719055, 73405998, 73448207, 73481951, 73008831, 73175087, 73044495, 73058863, 73194895, 73197919, 73093151, 72895567, 72918543, 72947039, 72957919, 82383481, 67392015, 67303135, 67312799, 67318303, 67453727, 67454767, 67634719, 67645887, 67717391, 67914111, 67947919, 67818463, 68052959, 68097215, 68500543, 68711909, 68584735, 68726975, 68741679, 68615471, 68750559, 68755487, 68629311, 68764687, 68765648, 68990175, 69022959, 69023727, 69217327, 69547327, 69665839, 69809983, 69814815, 70006831, 70037807, 70055951, 70068511, 70184031, 70323999, 70334687, 70566095, 70588751, 70723935, 71049695, 70952031, 71084831, 71376863, 71256287, 71611039, 71487727, 71618591, 71623999, 71514239, 71891231, 71897327, 71897663, 72036783, 72391487, 77604975, 77608163, 77621327, 77501983, 77635039, 77646559, 77654671, 77655695, 77546543, 77678383, 77345471, 77224735, 77375519, 77385519, 77393967, 76944399, 76975663, 77114628, 77115231, 77127525, 77142959, 76677423, 76699967, 76722287, 76857647, 76739039, 76883567, 76891615, 76453343, 76584335, 76590623, 76594607, 76600031, 76611167, 76617743, 76622303, 76285999, 76329231, 76335839, 76348175, 76350351, 76356783, 75910383, 75639343, 75787615, 75660079, 75796895, 75797615, 75692559, 75827999, 75833487, 75836479, 75518943, 75568143, 75278943, 75290271, 75297903, 75309391, 75312479, 75315119, 74852223, 74987055, 74858047, 74992943, 74875439, 75008031, 74885407, 75027743, 75055583, 74927839, 74738719, 74629087, 74767391, 74779295, 74789343, 74791247, 74323183, 74454239, 74349455, 74364751, 74516047, 74528559, 74192207, 74201535, 74084367, 74220511, 74109039, 74263263, 74133215, 73807119, 73945313, 73868148, 74001631, 73536815, 73684815, 73711439, 73275407, 73408799, 73052767, 73190975, 73209823, 72788271, 72960607, 72487647, 82383730, 67407151, 67415583, 67322127, 67523871, 67700959, 67583039, 67905375, 67793199, 68159583, 68237791, 68306479, 68492399], np.uint32)
        interpreter = PyDataInterpreter()
        histogram = PyDataHistograming()
        interpreter.set_trig_count(1)
        interpreter.set_warning_output(False)
        histogram.set_no_scan_parameter()
        histogram.create_occupancy_hist(True)
        interpreter.interpret_raw_data(raw_data)
        interpreter.store_event()
        histogram.add_hits(interpreter.get_hits())
        occ_hist_cpp = histogram.get_occupancy()[:, :, 0]
        col_arr, row_arr = convert_data_array(raw_data, filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)
        occ_hist_python, _, _ = np.histogram2d(col_arr, row_arr, bins=(80, 336), range=[[1, 80], [1, 336]])
        self.assertTrue(np.all(occ_hist_cpp == occ_hist_python))

    def test_analysis_utils_in1d_events(self):  # check compiled get_in1d_sorted function
        event_numbers = np.array([[0, 0, 2, 2, 2, 4, 5, 5, 6, 7, 7, 7, 8], [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]], dtype=np.int64)
        event_numbers_2 = np.array([1, 1, 1, 2, 2, 2, 4, 4, 4, 7], dtype=np.int64)
        result = event_numbers[0][fast_analysis_utils.in1d_events(event_numbers[0], event_numbers_2)]
        self.assertListEqual([2, 2, 2, 4, 7, 7, 7], result.tolist())

    def test_1d_index_histogram(self):  # check compiled hist_2D_index function
        x = np.random.randint(0, 100, 100)
        shape = (100, )
        array_fast = fast_analysis_utils.hist_1d_index(x, shape=shape)
        array = np.histogram(x, bins=shape[0], range=(0, shape[0]))[0]
        shape = (5,)  # shape that is too small for the indices to trigger exception
        exception_ok = False
        try:
            array_fast = fast_analysis_utils.hist_1d_index(x, shape=shape)
        except IndexError:
            exception_ok = True
        except:  # other exception that should not occur
            pass
        self.assertTrue(exception_ok & np.all(array == array_fast))

    def test_2d_index_histogram(self):  # check compiled hist_2D_index function
        x, y = np.random.randint(0, 100, 100), np.random.randint(0, 100, 100)
        shape = (100, 100)
        array_fast = fast_analysis_utils.hist_2d_index(x, y, shape=shape)
        array = np.histogram2d(x, y, bins=shape, range=[[0, shape[0]], [0, shape[1]]])[0]
        shape = (5, 200)  # shape that is too small for the indices to trigger exception
        exception_ok = False
        try:
            array_fast = fast_analysis_utils.hist_2d_index(x, y, shape=shape)
        except IndexError:
            exception_ok = True
        except:  # other exception that should not occur
            pass
        self.assertTrue(exception_ok & np.all(array == array_fast))

    def test_3d_index_histogram(self):  # check compiled hist_3D_index function
        with tb.open_file(os.path.join(tests_data_folder, 'hist_data.h5'), mode="r") as in_file_h5:
            xyz = in_file_h5.root.HistDataXYZ[:]
            x, y, z = xyz[0], xyz[1], xyz[2]
            shape = (100, 100, 100)
            array_fast = fast_analysis_utils.hist_3d_index(x, y, z, shape=shape)
            array = np.histogramdd(np.column_stack((x, y, z)), bins=shape, range=[[0, shape[0] - 1], [0, shape[1] - 1], [0, shape[2] - 1]])[0]
            shape = (50, 200, 200)  # shape that is too small for the indices to trigger exception
            exception_ok = False
            try:
                array_fast = fast_analysis_utils.hist_3d_index(x, y, z, shape=shape)
            except IndexError:
                exception_ok = True
            except:  # other exception that should not occur
                pass
            self.assertTrue(exception_ok & np.all(array == array_fast))

    def test_hit_or_calibration(self):
        create_hitor_calibration(os.path.join(tests_data_folder, 'hit_or_calibration'), plot_pixel_calibrations=True)
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'hit_or_calibration_interpreted_result.h5'),
                                                            os.path.join(tests_data_folder, 'hit_or_calibration_interpreted.h5'))
        self.assertTrue(data_equal, msg=error_msg)
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'hit_or_calibration_result.h5'),
                                                            os.path.join(tests_data_folder, 'hit_or_calibration_calibration.h5'),
                                                            exact=False)
        self.assertTrue(data_equal, msg=error_msg)

    def test_stop_mode_analysis(self):
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'unit_test_data_5_interpreted.h5'),
                                                            os.path.join(tests_data_folder, 'unit_test_data_5_result.h5'))
        self.assertTrue(data_equal, msg=error_msg)

    def test_data_aligned_at_events(self):
        def test_gen(generator, table, start, stop=None, size=None, iterations=None):

            #for arr, stop_index in generator:
            while True:
                try:
                    arr, stop_index = generator.next()
                except StopIteration:
                    if stop is None:
                        self.assertEqual(table.nrows, start, "Generator did not return all data")
                    else:
                        self.assertEqual(stop, start, "Generator did not return all data until stop index")
                    break
                else:
                    pass
                arr_size = stop_index - start
                self.assertNotEqual(arr.shape[0], 0)
                self.assertEqual(arr_size, arr.shape[0])
                np.testing.assert_array_equal(arr, table[start:start + arr_size], "Generator returned wrong data")
                start += arr_size
                if size is not None:
                    self.assertGreaterEqual(size, arr_size, "Generator exceeded chunk size")

                if iterations is not None:
                    iterations -= 1
                    if iterations == 0:
                        break

            if stop is None:
                self.assertGreaterEqual(table.nrows, start, "Generator index exceeded table nrows")
            else:
                self.assertGreaterEqual(stop, start, "Generator index exceeded stop index")

        with tb.open_file(os.path.join(tests_data_folder, 'unit_test_data_2_hits.h5'), 'r+') as h5_file:
            # testing full table
            hist_table, _ = np.histogram(h5_file.root.Hits[:]["event_number"])
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=1000000)
            event_numbers = []
            for arr, _ in gen:
                event_numbers.extend(arr[:]["event_number"])
            hist, _ = np.histogram(event_numbers)
#             self.assertSequenceEqual(event_numbers, h5_file.root.Hits[:]["event_number"].tolist())
            self.assertSequenceEqual(hist_table.tolist(), hist.tolist())

            # test chunk size
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=224)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            test_gen(generator=gen, table=h5_file.root.Hits, start=0, iterations=3)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=223)
            self.assertRaises(InvalidInputError, gen.next)

            # test stop event number
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=0, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=3800, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(224, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=110200, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            arr, index = gen.next()
            self.assertEqual(4786, arr.shape[0])
            self.assertEqual(14784, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=3800, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(224, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=3800, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=224)
            self.assertRaises(InvalidInputError, gen.next)

            # test start event number
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(224, index)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(448, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=2, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(448, index)
            arr, index = gen.next()
            self.assertEqual(165, arr.shape[0])
            self.assertEqual(613, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=2, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=224, size=10000)

            # test start and stop event number
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=0, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=2, stop_event_number=2, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=3800, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=3800, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(224, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=2, stop_event_number=3801, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=2, stop_event_number=110200, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)

            # test stop index
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(499, arr.shape[0])
            self.assertEqual(499, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=14784, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            arr, index = gen.next()
            self.assertEqual(4784, arr.shape[0])
            self.assertEqual(14782, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=None, stop_index=14785, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            arr, index = gen.next()
            self.assertEqual(4786, arr.shape[0])
            self.assertEqual(14784, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=110199, start_index=None, stop_index=14785, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            arr, index = gen.next()
            self.assertEqual(4784, arr.shape[0])
            self.assertEqual(14782, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=110199, start_index=None, stop_index=14784, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            arr, index = gen.next()
            self.assertEqual(4784, arr.shape[0])
            self.assertEqual(14782, index)
            self.assertRaises(StopIteration, gen.next)

            # test start index
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=0, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=500, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9999, arr.shape[0])
            self.assertEqual(10499, index)
            arr, index = gen.next()
            self.assertEqual(9996, arr.shape[0])
            self.assertEqual(20495, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(10222, index)
            arr, index = gen.next()
            self.assertEqual(9995, arr.shape[0])
            self.assertEqual(20217, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(10222, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3801, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)

            # test start index, first event not aligned
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=0, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=0, size=10000)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=500, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=501, size=10000)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=448, size=10000)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3801, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)

            # test start index, start event number
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=None, start_index=0, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()  # assuming start index 0 is always aligned
            self.assertEqual(9998, arr.shape[0])
            self.assertEqual(9998, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=2, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(448, index)
            arr, index = gen.next()
            self.assertEqual(165, arr.shape[0])
            self.assertEqual(613, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=224, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=200, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=225)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(448, index)
            arr, index = gen.next()
            self.assertEqual(165, arr.shape[0])
            self.assertEqual(613, index)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=200, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=225)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(448, index)
            arr, index = gen.next()
            self.assertEqual(165, arr.shape[0])
            self.assertEqual(613, index)

            # test stop index, stop event number
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=0, start_index=None, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=0, start_index=None, stop_index=224, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=0, start_index=None, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=3800, start_index=None, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=3800, start_index=None, stop_index=224, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=None, stop_event_number=3800, start_index=None, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(224, index)
            self.assertRaises(StopIteration, gen.next)

            # test start/stop index, start/stop event number
            # bad input
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=0, start_index=0, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=0, start_index=100, stop_index=0, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            # others
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=0, start_index=0, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=0, start_index=0, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=3800, start_index=0, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=3800, start_index=0, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(224, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=3800, start_index=0, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=3800, start_index=0, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=3801, start_index=0, stop_index=100, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=3801, start_index=0, stop_index=500, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            arr, index = gen.next()
            self.assertEqual(224, arr.shape[0])
            self.assertEqual(448, index)
            self.assertRaises(StopIteration, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3801, stop_event_number=110200, start_index=100, stop_index=15000, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=110200, start_index=100, stop_index=15000, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=224, stop=14784, size=10000)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=110200, start_index=100, stop_index=15000, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=224, stop=14784, size=10000)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=110200, start_index=224, stop_index=15000, first_event_aligned=False, try_speedup=False, chunk_size=10000)
            self.assertRaises(InvalidInputError, gen.next)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=110200, start_index=100, stop_index=14784, first_event_aligned=True, try_speedup=False, chunk_size=10000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=224, stop=14782, size=10000)

            # chunk size
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=None, start_index=100, stop_index=None, first_event_aligned=False, try_speedup=False, chunk_size=224)
            self.assertRaises(InvalidInputError, gen.next)

            # read full table
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=0, stop_event_number=239500, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=100000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=0, stop=None, size=100000)
            gen = data_aligned_at_events(h5_file.root.Hits, start_event_number=3800, stop_event_number=239500, start_index=None, stop_index=None, first_event_aligned=True, try_speedup=False, chunk_size=100000)
            test_gen(generator=gen, table=h5_file.root.Hits, start=224, stop=None, size=100000)

    def test_tdc_analysis(self):
        def analyze_tdc(source_scan_filename, calibration_filename, col_span, row_span):
            # Data files
            calibation_file = calibration_filename
            raw_data_file = source_scan_filename
            hit_file = os.path.splitext(raw_data_file)[0] + r'_interpreted.h5'
            # Selection criterions
            # deselect edge pixels for better cluster size cut
            hit_selection = '(column > %d) & (column < %d) & (row > %d) & (row < %d)' % (col_span[0] + 1,
                                                                                         col_span[1] - 1,
                                                                                         row_span[0] + 5,
                                                                                         row_span[1] - 5)
            hit_selection_conditions = ['(n_cluster==1)',
                                        '(n_cluster==1) & (cluster_size == 1)',
                                        '(n_cluster==1) & (cluster_size == 1) & '
                                        '(relative_BCID > 1) & (relative_BCID < 4) & %s' % hit_selection,
                                        '(n_cluster==1) & (cluster_size == 1) & '
                                        '(relative_BCID > 1) & (relative_BCID < 4) & ((tot > 12) | '
                                        '((TDC * 1.5625 - tot * 25 < 100) & (tot * 25 - TDC * 1.5625 < 100))) & %s' % hit_selection]
            event_status_select_mask = 0b0000111111011111
            event_status_condition = 0b0000000100000000  # trigger, one in-time tdc word and perfect event structure required
            # Interpret and create hit table
            tdc_analysis.analyze_raw_data(input_files=raw_data_file,
                                          output_file_hits=hit_file,
                                          interpreter_plots=True,
                                          overwrite_output_files=True,
                                          align_at_trigger=True,
                                          use_tdc_trigger_time_stamp=True,
                                          max_tdc_delay=255)
            # Select TDC histograms for different cut criterions and with charge calibrations
            tdc_analysis.histogram_tdc_hits(hit_file,
                                            hit_selection_conditions,
                                            event_status_select_mask,
                                            event_status_condition,
                                            calibation_file,
                                            max_tdc=500,
                                            n_bins=1000)

        analyze_tdc(source_scan_filename=os.path.join(tests_data_folder, 'ext_trigger_scan_tdc.h5'),
                    calibration_filename=os.path.join(tests_data_folder, 'hit_or_calibration_tdc.h5'),
                    col_span=[55, 75], row_span=[75, 275])
        # Test raw data interpretation with TDC words
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted_result.h5'),
                                                            os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted.h5'),
                                                            chunk_size=100000)
        self.assertTrue(data_equal, msg=error_msg)
        # Test TDC histogram creation
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted_tdc_hists_result.h5'),
                                                            os.path.join(tests_data_folder, 'ext_trigger_scan_tdc_interpreted_tdc_hists.h5'))
        self.assertTrue(data_equal, msg=error_msg)

    def test_tlu_analysis(self):
        ' Use data with 4 TLU trigger errors (not increasing by one) and check analysis'
        def analyze_raw_data_tlu(input_file, align_at_trg=False):  # FE-I4 raw data analysis
            with AnalyzeRawData(raw_data_file=input_file, create_pdf=True) as analyze_raw_data:
                analyze_raw_data.align_at_trigger_number = align_at_trg  # if trigger number is at the beginning of each event activate this for event alignment
                analyze_raw_data.use_trigger_time_stamp = False  # the trigger number is a time stamp
                analyze_raw_data.use_tdc_word = False
                analyze_raw_data.create_hit_table = True
                analyze_raw_data.create_meta_event_index = True
                analyze_raw_data.create_trigger_error_hist = True
                analyze_raw_data.create_rel_bcid_hist = True
                analyze_raw_data.create_error_hist = True
                analyze_raw_data.create_service_record_hist = True
                analyze_raw_data.create_occupancy_hist = True
                analyze_raw_data.create_tot_hist = False
                analyze_raw_data.interpreter.create_empty_event_hits(False)
                analyze_raw_data.interpreter.set_warning_output(False)
                analyze_raw_data.interpret_word_table()
                analyze_raw_data.interpreter.print_summary()
                analyze_raw_data.plot_histograms()

        # Test raw data interpretation with event alignment on BCIDs
        analyze_raw_data_tlu(input_file=os.path.join(tests_data_folder, 'ext_trigger_scan_tlu.h5'),
                             align_at_trg=False)
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'ext_trigger_scan_tlu_interpreted_result.h5'),
                                                            os.path.join(tests_data_folder, 'ext_trigger_scan_tlu_interpreted.h5'))
        self.assertTrue(data_equal, msg=error_msg)

        # Test raw data interpretation with event alignment on trigger number
        analyze_raw_data_tlu(input_file=os.path.join(tests_data_folder, 'ext_trigger_scan_tlu.h5'),
                             align_at_trg=True)
        data_equal, error_msg = test_tools.compare_h5_files(os.path.join(tests_data_folder, 'ext_trigger_scan_tlu_interpreted_result.h5'),
                                                            os.path.join(tests_data_folder, 'ext_trigger_scan_tlu_interpreted.h5'))
        self.assertTrue(data_equal, msg=error_msg)

if __name__ == '__main__':
    tests_data_folder = 'test_analysis_data//'
    suite = unittest.TestLoader().loadTestsFromTestCase(TestAnalysis)
    unittest.TextTestRunner(verbosity=2).run(suite)
