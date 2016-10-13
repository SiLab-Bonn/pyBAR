''' Script to convert the raw data and to plot all histograms'''
from __future__ import division

import logging
import warnings
import os
import multiprocessing as mp
from functools import partial

import tables as tb
from tables import dtype_from_descr, Col
import numpy as np
from scipy.optimize import curve_fit, OptimizeWarning
from scipy.special import erf
from matplotlib.backends.backend_pdf import PdfPages

import progressbar

from pixel_clusterizer.clusterizer import HitClusterizer

from pybar_fei4_interpreter.data_interpreter import PyDataInterpreter
from pybar_fei4_interpreter.data_histograming import PyDataHistograming
from pybar_fei4_interpreter import data_struct
from pybar_fei4_interpreter import analysis_utils as fast_analysis_utils

from pybar.analysis import analysis_utils
from pybar.analysis.plotting import plotting
from pybar.analysis.analysis_utils import check_bad_data, fix_raw_data, consecutive
from pybar.daq.readout_utils import is_fe_word, is_data_header, is_trigger_word, logical_and


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def scurve(x, A, mu, sigma):
    return 0.5 * A * erf((x - mu) / (np.sqrt(2) * sigma)) + 0.5 * A


def fit_scurve(scurve_data, PlsrDAC):  # data of some pixels to fit, has to be global for the multiprocessing module
    index = np.argmax(np.diff(scurve_data))
    max_occ = np.median(scurve_data[index:])
    threshold = PlsrDAC[index]
    if abs(max_occ) <= 1e-08:  # or index == 0: occupancy is zero or close to zero
        popt = [0, 0, 0]
    else:
        try:
            popt, _ = curve_fit(scurve, PlsrDAC, scurve_data, p0=[max_occ, threshold, 2.5], check_finite=False)
        except RuntimeError:  # fit failed
            popt = [0, 0, 0]
    if popt[1] < 0:  # threshold < 0 rarely happens if fit does not work
        popt = [0, 0, 0]
    return popt[1:3]


class AnalyzeRawData(object):

    """A class to analyze FE-I4 raw data"""

    def __init__(self, raw_data_file=None, analyzed_data_file=None, create_pdf=True, scan_parameter_name=None):
        '''Initialize the AnalyzeRawData object:
            - The c++ objects (Interpreter, Histogrammer, Clusterizer) are constructed
            - Create one scan parameter table from all provided raw data files
            - Create PdfPages object if needed

        Parameters
        ----------
        raw_data_file : string or tuple, list
            A string or a list of strings with the raw data file name(s). File ending (.h5)
            does not not have to be set.
        analyzed_data_file : string
            The file name of the output analyzed data file. File ending (.h5)
            Does not have to be set.
        create_pdf : boolean
            Creates interpretation plots into one PDF file. Only active if raw_data_file is given.
        scan_parameter_name : string or iterable
            The name/names of scan parameter(s) to be used during analysis. If not set the scan parameter
            table is used to extract the scan parameters. Otherwise no scan parameter is set.
        '''
        self.interpreter = PyDataInterpreter()
        self.histograming = PyDataHistograming()

        raw_data_files = []

        if isinstance(raw_data_file, (list, set, tuple)):
            for one_raw_data_file in raw_data_file:
                if one_raw_data_file is not None and os.path.splitext(one_raw_data_file)[1].strip().lower() != ".h5":
                    raw_data_files.append(os.path.splitext(one_raw_data_file)[0] + ".h5")
                else:
                    raw_data_files.append(one_raw_data_file)
        else:
            f_list = analysis_utils.get_data_file_names_from_scan_base(raw_data_file, sort_by_time=True, meta_data_v2=self.interpreter.meta_table_v2)
            if f_list:
                raw_data_files = f_list
            elif raw_data_file is not None and os.path.splitext(raw_data_file)[1].strip().lower() != ".h5":
                raw_data_files.append(os.path.splitext(raw_data_file)[0] + ".h5")
            elif raw_data_file is not None:
                raw_data_files.append(raw_data_file)
            else:
                raw_data_files = None

        if analyzed_data_file:
            if os.path.splitext(analyzed_data_file)[1].strip().lower() != ".h5":
                self._analyzed_data_file = os.path.splitext(analyzed_data_file)[0] + ".h5"
            else:
                self._analyzed_data_file = analyzed_data_file
        else:
            if isinstance(raw_data_file, basestring):
                self._analyzed_data_file = os.path.splitext(raw_data_file)[0] + '_interpreted.h5'
            else:
                self._analyzed_data_file = None
#                 raise analysis_utils.IncompleteInputError('Output file name is not given.')

        # create a scan parameter table from all raw data files
        if raw_data_files is not None:
            self.files_dict = analysis_utils.get_parameter_from_files(raw_data_files, parameters=scan_parameter_name)
            if not analysis_utils.check_parameter_similarity(self.files_dict):
                raise analysis_utils.NotSupportedError('Different scan parameters in multiple files are not supported.')
            self.scan_parameters = analysis_utils.create_parameter_table(self.files_dict)
            scan_parameter_names = analysis_utils.get_scan_parameter_names(self.scan_parameters)
            logging.info('Scan parameter(s) from raw data file(s): %s', (', ').join(scan_parameter_names) if scan_parameter_names else 'None',)
        else:
            self.files_dict = None
            self.scan_parameters = None

        self.out_file_h5 = None
        self.set_standard_settings()
        if raw_data_file is not None and create_pdf:
            if isinstance(raw_data_file, list):  # for multiple raw data files name pdf accorfing to the first file
                output_pdf_filename = os.path.splitext(raw_data_file[0])[0] + ".pdf"
            else:
                output_pdf_filename = os.path.splitext(raw_data_file)[0] + ".pdf"
            logging.info('Opening output PDF file: %s', output_pdf_filename)
            self.output_pdf = PdfPages(output_pdf_filename)
        else:
            self.output_pdf = None
        self._scan_parameter_name = scan_parameter_name
        self._settings_from_file_set = False  # the scan settings are in a list of files only in the first one, thus set this flag to suppress warning for other files

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        del self.interpreter
        del self.histograming
        del self.clusterizer
        if self.output_pdf is not None and isinstance(self.output_pdf, PdfPages):
            logging.info('Closing output PDF file: %s', str(self.output_pdf._file.fh.name))
            self.output_pdf.close()
        if self.is_open(self.out_file_h5):
            self.out_file_h5.close()

    def _setup_clusterizer(self):
        # Define all field names and data types
        hit_fields = {'event_number': 'event_number',
                      'column': 'column',
                      'row': 'row',
                      'relative_BCID': 'frame',
                      'tot': 'charge',
                      'LVL1ID': 'LVL1ID',
                      'trigger_number': 'trigger_number',
                      'BCID': 'BCID',
                      'TDC': 'TDC',
                      'TDC_time_stamp': 'TDC_time_stamp',
                      'trigger_status': 'trigger_status',
                      'service_record': 'service_record',
                      'event_status': 'event_status'
                      }

        hit_dtype = np.dtype([('event_number', '<i8'),
                              ('trigger_number', '<u4'),
                              ('relative_BCID', '<u1'),
                              ('LVL1ID', '<u2'),
                              ('column', '<u1'),
                              ('row', '<u2'),
                              ('tot', '<u1'),
                              ('BCID', '<u2'),
                              ('TDC', '<u2'),
                              ('TDC_time_stamp', '<u1'),
                              ('trigger_status', '<u1'),
                              ('service_record', '<u4'),
                              ('event_status', '<u2')])

        cluster_fields = {'event_number': 'event_number',
                          'column': 'column',
                          'row': 'row',
                          'size': 'n_hits',
                          'ID': 'ID',
                          'tot': 'charge',
                          'seed_column': 'seed_column',
                          'seed_row': 'seed_row',
                          'mean_column': 'mean_column',
                          'mean_row': 'mean_row'}

        cluster_dtype = np.dtype([('event_number', '<i8'),
                                  ('ID', '<u2'),
                                  ('size', '<u2'),
                                  ('tot', '<u2'),
                                  ('seed_column', '<u1'),
                                  ('seed_row', '<u2'),
                                  ('mean_column', '<f4'),
                                  ('mean_row', '<f4'),
                                  ('event_status', '<u2')])

        self.clusterizer = HitClusterizer(hit_fields, hit_dtype, cluster_fields, cluster_dtype)  # Initialize clusterizer with custom hit/cluster fields

        # Set the cluster event status from the hit event status
        def end_of_cluster_function(hits, cluster, is_seed, n_cluster, cluster_size, cluster_id, actual_cluster_index, actual_event_hit_index, actual_cluster_hit_indices, seed_index):
            cluster[actual_cluster_index].event_status = hits[seed_index].event_status
        self.clusterizer.set_end_of_cluster_function(end_of_cluster_function)  # Set the new function to the clusterizer

        self.clusterizer.set_frame_cluster_distance(2)
        self.clusterizer.set_max_cluster_hits(1000)  # Make sure clusterizer can handle 1000 hits per cluster

    def set_standard_settings(self):
        '''Set all settings to their standard values.
        '''
        if self.is_open(self.out_file_h5):
            self.out_file_h5.close()
        self.out_file_h5 = None
        self._setup_clusterizer()
        self.chunk_size = 3000000
        self.n_injections = None
        self.trig_count = 0  # 0 trig_count = 16 BCID per trigger
        self.max_tot_value = 13
        self.vcal_c0, self.vcal_c1 = None, None
        self.c_low, self.c_mid, self.c_high = None, None, None
        self.c_low_mask, self.c_high_mask = None, None
        self._filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        warnings.simplefilter("ignore", OptimizeWarning)
        self.meta_event_index = None
        self.fei4b = False
        self.create_hit_table = False
        self.create_empty_event_hits = False
        self.create_meta_event_index = True
        self.create_tot_hist = True
        self.create_mean_tot_hist = False
        self.create_tot_pixel_hist = True
        self.create_rel_bcid_hist = True
        self.correct_corrupted_data = False
        self.create_error_hist = True
        self.create_service_record_hist = True
        self.create_occupancy_hist = True
        self.create_meta_word_index = False
        self.create_source_scan_hist = False
        self.max_cluster_size = 1024  # Maximum clustersize to histogram the cluster
        self.create_tdc_hist = False
        self.create_tdc_counter_hist = False
        self.create_tdc_pixel_hist = False
        self.create_trigger_error_hist = False
        self.create_threshold_hists = False
        self.create_threshold_mask = True  # Threshold/noise histogram mask: masking all pixels out of bounds
        self.create_fitted_threshold_mask = True  # Fitted threshold/noise histogram mask: masking all pixels out of bounds
        self.create_fitted_threshold_hists = False
        self.create_cluster_hit_table = False
        self.create_cluster_table = False
        self.create_cluster_size_hist = False
        self.create_cluster_tot_hist = False
        self.align_at_trigger = False  # use the trigger word to align the events
        self.align_at_tdc = False  # use the trigger word to align the events
        self.use_trigger_time_stamp = False  # the trigger number is a time stamp
        self.use_tdc_trigger_time_stamp = False  # the tdc time stamp is the difference between trigger and tdc rising edge
        self.max_tdc_delay = 255
        self.max_trigger_number = 2 ** 16 - 1
        self.set_stop_mode = False  # The FE is read out with stop mode, therefore the BCID plot is different

    def reset(self):
        '''Reset the c++ libraries for new analysis.
        '''
        self.interpreter.reset()
        self.histograming.reset()

    @property
    def chunk_size(self):
        return self._chunk_size

    @chunk_size.setter
    def chunk_size(self, value):
        self.interpreter.set_hit_array_size(2 * value)
        self.clusterizer.set_max_hits(value)
        self._chunk_size = value

    @property
    def create_hit_table(self):
        return self._create_hit_table

    @create_hit_table.setter
    def create_hit_table(self, value):
        self._create_hit_table = value

    @property
    def create_empty_event_hits(self):
        return self._create_empty_event_hits

    @create_empty_event_hits.setter
    def create_empty_event_hits(self, value):
        self._create_empty_event_hits = value
        self.interpreter.create_empty_event_hits(value)

    @property
    def create_occupancy_hist(self):
        return self._create_occupancy_hist

    @create_occupancy_hist.setter
    def create_occupancy_hist(self, value):
        self._create_occupancy_hist = value
        self.histograming.create_occupancy_hist(value)

    @property
    def create_mean_tot_hist(self):
        return self._create_mean_tot_hist

    @create_mean_tot_hist.setter
    def create_mean_tot_hist(self, value):
        self._create_mean_tot_hist = value
        self.histograming.create_mean_tot_hist(value)

    @property
    def create_source_scan_hist(self):
        return self._create_source_scan_hist

    @create_source_scan_hist.setter
    def create_source_scan_hist(self, value):
        self._create_source_scan_hist = value

    @property
    def create_tot_hist(self):
        return self.create_tot_hist

    @create_tot_hist.setter
    def create_tot_hist(self, value):
        self._create_tot_hist = value
        self.histograming.create_tot_hist(value)

    @property
    def create_tdc_hist(self):
        return self._create_tdc_hist

    @create_tdc_hist.setter
    def create_tdc_hist(self, value):
        self._create_tdc_hist = value
        self.histograming.create_tdc_hist(value)

    @property
    def create_tdc_pixel_hist(self):
        return self._create_tdc_pixel_hist

    @create_tdc_pixel_hist.setter
    def create_tdc_pixel_hist(self, value):
        self._create_tdc_pixel_hist = value
        self.histograming.create_tdc_pixel_hist(value)

    @property
    def create_tot_pixel_hist(self):
        return self._create_tot_pixel_hist

    @create_tot_pixel_hist.setter
    def create_tot_pixel_hist(self, value):
        self._create_tot_pixel_hist = value
        self.histograming.create_tot_pixel_hist(value)

    @property
    def create_rel_bcid_hist(self):
        return self._create_rel_bcid_hist

    @create_rel_bcid_hist.setter
    def create_rel_bcid_hist(self, value):
        self._create_rel_bcid_hist = value
        self.histograming.create_rel_bcid_hist(value)

    @property
    def create_threshold_hists(self):
        return self._create_threshold_hists

    @create_threshold_hists.setter
    def create_threshold_hists(self, value):
        self._create_threshold_hists = value

    @property
    def create_threshold_mask(self):
        return self._create_threshold_mask

    @create_threshold_mask.setter
    def create_threshold_mask(self, value):
        self._create_threshold_mask = value

    @property
    def create_fitted_threshold_mask(self):
        return self._create_fitted_threshold_mask

    @create_fitted_threshold_mask.setter
    def create_fitted_threshold_mask(self, value):
        self._create_fitted_threshold_mask = value

    @property
    def create_fitted_threshold_hists(self):
        return self._create_fitted_threshold_hists

    @create_fitted_threshold_hists.setter
    def create_fitted_threshold_hists(self, value):
        self._create_fitted_threshold_hists = value

    @property
    def correct_corrupted_data(self):
        return self._correct_corrupted_data

    @correct_corrupted_data.setter
    def correct_corrupted_data(self, value):
        self._correct_corrupted_data = value

    @property
    def create_error_hist(self):
        return self._create_error_hist

    @create_error_hist.setter
    def create_error_hist(self, value):
        self._create_error_hist = value

    @property
    def create_trigger_error_hist(self):
        return self._create_trigger_error_hist

    @create_trigger_error_hist.setter
    def create_trigger_error_hist(self, value):
        self._create_trigger_error_hist = value

    @property
    def create_service_record_hist(self):
        return self._create_service_record_hist

    @create_service_record_hist.setter
    def create_service_record_hist(self, value):
        self._create_service_record_hist = value

    @property
    def create_tdc_counter_hist(self):
        return self._create_tdc_counter_hist

    @create_tdc_counter_hist.setter
    def create_tdc_counter_hist(self, value):
        self._create_tdc_counter_hist = value

    @property
    def create_meta_event_index(self):
        return self._create_meta_event_index

    @create_meta_event_index.setter
    def create_meta_event_index(self, value):
        self._create_meta_event_index = value

    @property
    def create_meta_word_index(self):
        return self._create_meta_word_index

    @create_meta_word_index.setter
    def create_meta_word_index(self, value):
        self._create_meta_word_index = value
        self.interpreter.create_meta_data_word_index(value)

    @property
    def fei4b(self):
        return self._fei4b

    @fei4b.setter
    def fei4b(self, value):
        self._fei4b = value
        self.interpreter.set_FEI4B(value)

    @property
    def n_injections(self):
        """Get the numbers of injections per pixel."""
        return self._n_injection

    @n_injections.setter
    def n_injections(self, value):
        """Set the numbers of injections per pixel."""
        self._n_injection = value

    @property
    def trig_count(self):
        """Get the numbers of BCIDs (usually 16) of one event."""
        return self._trig_count

    @trig_count.setter
    def trig_count(self, value):
        """Set the numbers of BCIDs (usually 16) of one event."""
        self._trig_count = 16 if value == 0 else value
        self.interpreter.set_trig_count(self._trig_count)

    @property
    def max_tot_value(self):
        """Get maximum ToT value that is considered to be a hit"""
        return self._max_tot_value

    @max_tot_value.setter
    def max_tot_value(self, value):
        """Set maximum ToT value that is considered to be a hit"""
        self._max_tot_value = value
        self.interpreter.set_max_tot(self._max_tot_value)
        self.histograming.set_max_tot(self._max_tot_value)
        self.clusterizer.set_max_hit_charge(self._max_tot_value)

    @property
    def max_cluster_size(self):
        """Get maximum cluster size value that defines if a hit is used for histograming"""
        return self._max_cluster_size

    @max_cluster_size.setter
    def max_cluster_size(self, value):
        """Set maximum cluster size value that defines if a hit is used for histograming"""
        self._max_cluster_size = value
        self.clusterizer.set_max_cluster_hits(self._max_cluster_size)

    @property
    def create_cluster_hit_table(self):
        return self._create_cluster_hit_table

    @create_cluster_hit_table.setter
    def create_cluster_hit_table(self, value):
        self._create_cluster_hit_table = value

    @property
    def create_cluster_table(self):
        return self._create_cluster_table

    @create_cluster_table.setter
    def create_cluster_table(self, value):
        self._create_cluster_table = value

    @property
    def create_cluster_size_hist(self):
        return self._create_cluster_size_hist

    @create_cluster_size_hist.setter
    def create_cluster_size_hist(self, value):
        self._create_cluster_size_hist = value

    @property
    def create_cluster_tot_hist(self):
        return self._create_cluster_tot_hist

    @create_cluster_tot_hist.setter
    def create_cluster_tot_hist(self, value):
        self._create_cluster_tot_hist = value

    @property
    def align_at_trigger(self):
        return self._align_at_trigger

    @align_at_trigger.setter
    def align_at_trigger(self, value):
        self._align_at_trigger = value
        self.interpreter.align_at_trigger(value)

    @property
    def align_at_tdc(self):
        return self._align_at_tdc

    @align_at_tdc.setter
    def align_at_tdc(self, value):
        self._align_at_tdc = value
        self.interpreter.align_at_tdc(value)

    @property
    def use_trigger_time_stamp(self):
        return self._use_trigger_time_stamp

    @use_trigger_time_stamp.setter
    def use_trigger_time_stamp(self, value):
        self._use_trigger_time_stamp = value
        self.interpreter.use_trigger_time_stamp(value)

    @property
    def use_tdc_trigger_time_stamp(self):
        return self._use_tdc_trigger_time_stamp

    @use_tdc_trigger_time_stamp.setter
    def use_tdc_trigger_time_stamp(self, value):
        self._use_tdc_trigger_time_stamp = value
        self.interpreter.use_tdc_trigger_time_stamp(value)

    @property
    def max_tdc_delay(self):
        return self._max_tdc_delay

    @max_tdc_delay.setter
    def max_tdc_delay(self, value):
        self._max_tdc_delay = value
        self.interpreter.set_max_tdc_delay(value)

    @property
    def max_trigger_number(self):
        return self._max_trigger_number

    @max_trigger_number.setter
    def max_trigger_number(self, value):
        self._max_trigger_number = value
        self.interpreter.set_max_trigger_number(value)

    @property
    def set_stop_mode(self):
        return self._set_stop_mode

    @set_stop_mode.setter
    def set_stop_mode(self, value):
        self._set_stop_mode = value

    def interpret_word_table(self, analyzed_data_file=None, use_settings_from_file=True, fei4b=None):
        '''Interprets the raw data word table of all given raw data files with the c++ library.
        Creates the h5 output file and PDF plots.

        Parameters
        ----------
        analyzed_data_file : string
            The file name of the output analyzed data file. If not set the output analyzed data file
            specified during initialization is taken.
        fei4b : boolean
            True if the raw data is from FE-I4B.
        use_settings_from_file : boolean
            True if the needed parameters should be extracted from the raw data file
        '''

        logging.info('Interpreting raw data file(s): ' + (', ').join(self.files_dict.keys()))

        if self._create_meta_word_index:
            meta_word = np.empty((self._chunk_size,), dtype=dtype_from_descr(data_struct.MetaInfoWordTable))
            self.interpreter.set_meta_data_word_index(meta_word)
        self.interpreter.reset_event_variables()
        self.interpreter.reset_counters()

        self.meta_data = analysis_utils.combine_meta_data(self.files_dict, meta_data_v2=self.interpreter.meta_table_v2)

        if self.meta_data is None or self.meta_data.shape[0] == 0:
            raise analysis_utils.IncompleteInputError('Meta data is empty. Stopping interpretation.')

        self.interpreter.set_meta_data(self.meta_data)  # tell interpreter the word index per readout to be able to calculate the event number per read out
        meta_data_size = self.meta_data.shape[0]
        self.meta_event_index = np.zeros((meta_data_size,), dtype=[('metaEventIndex', np.uint64)])  # this array is filled by the interpreter and holds the event number per read out
        self.interpreter.set_meta_event_data(self.meta_event_index)  # tell the interpreter the data container to write the meta event index to

        if self.scan_parameters is None:
            self.histograming.set_no_scan_parameter()
        else:
            self.scan_parameter_index = analysis_utils.get_scan_parameters_index(self.scan_parameters)  # a array that labels unique scan parameter combinations
            self.histograming.add_scan_parameter(self.scan_parameter_index)  # just add an index for the different scan parameter combinations

        if self._create_cluster_size_hist:  # Cluster size result histogram
            self._cluster_size_hist = np.zeros(shape=(self.max_cluster_size, ), dtype=np.uint32)

        if self._create_cluster_tot_hist:  # Cluster tot/size result histogram
            self._cluster_tot_hist = np.zeros(shape=(128, self.max_cluster_size), dtype=np.uint32)

        # create output file
        if analyzed_data_file:
            self._analyzed_data_file = analyzed_data_file

        if self._analyzed_data_file is not None:
            self.out_file_h5 = tb.openFile(self._analyzed_data_file, mode="w", title="Interpreted FE-I4 raw data")
            if self._create_hit_table is True:
                description = data_struct.HitInfoTable().columns.copy()
                if self.use_trigger_time_stamp:  # replace the column name if trigger gives you a time stamp
                    description['trigger_time_stamp'] = description.pop('trigger_number')
                hit_table = self.out_file_h5.create_table(self.out_file_h5.root, name='Hits', description=description, title='hit_data', filters=self._filter_table, chunkshape=(self._chunk_size / 100,))
            if self._create_meta_word_index is True:
                meta_word_index_table = self.out_file_h5.create_table(self.out_file_h5.root, name='EventMetaData', description=data_struct.MetaInfoWordTable, title='event_meta_data', filters=self._filter_table, chunkshape=(self._chunk_size / 10,))
            if self._create_cluster_table:
                cluster_table = self.out_file_h5.create_table(self.out_file_h5.root, name='Cluster', description=data_struct.ClusterInfoTable, title='Cluster data', filters=self._filter_table, expectedrows=self._chunk_size)
            if self._create_cluster_hit_table:
                description = data_struct.ClusterHitInfoTable().columns.copy()
                if self.use_trigger_time_stamp:  # replace the column name if trigger gives you a time stamp
                    description['trigger_time_stamp'] = description.pop('trigger_number')
                cluster_hit_table = self.out_file_h5.create_table(self.out_file_h5.root, name='ClusterHits', description=description, title='cluster_hit_data', filters=self._filter_table, expectedrows=self._chunk_size)

        logging.info("Interpreting...")
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=analysis_utils.get_total_n_data_words(self.files_dict), term_width=80)
        progress_bar.start()
        total_words = 0

        for file_index, raw_data_file in enumerate(self.files_dict.keys()):  # loop over all raw data files
            self.interpreter.reset_meta_data_counter()
            with tb.open_file(raw_data_file, mode="r") as in_file_h5:
                if use_settings_from_file:
                    self._deduce_settings_from_file(in_file_h5)
                else:
                    self.fei4b = fei4b
                if self.interpreter.meta_table_v2:
                    index_start = in_file_h5.root.meta_data.read(field='index_start')
                    index_stop = in_file_h5.root.meta_data.read(field='index_stop')
                else:
                    index_start = in_file_h5.root.meta_data.read(field='start_index')
                    index_stop = in_file_h5.root.meta_data.read(field='stop_index')
                bad_word_index = set()

                # Check for bad data
                if self._correct_corrupted_data:
                    tw = 2147483648  # trigger word
                    dh = 15269888  # data header
                    is_fe_data_header = logical_and(is_fe_word, is_data_header)
                    found_first_trigger = False
                    readout_slices = np.column_stack((index_start, index_stop))
                    previous_prepend_data_headers = None
                    prepend_data_headers = None
                    last_good_readout_index = None
                    last_index_with_event_data = None
                    for read_out_index, (index_start, index_stop) in enumerate(readout_slices):
                        try:
                            raw_data = in_file_h5.root.raw_data.read(index_start, index_stop)
                        except OverflowError, e:
                            pass
                        except tb.exceptions.HDF5ExtError:
                            break
                        # previous data chunk had bad data, check for good data
                        if (index_start - 1) in bad_word_index:
                            bad_data, current_prepend_data_headers, _ , _ = check_bad_data(raw_data, prepend_data_headers=1, trig_count=None)
                            if bad_data:
                                bad_word_index = bad_word_index.union(range(index_start, index_stop))
                            else:
#                                 logging.info("found good data in %s from index %d to %d (chunk %d, length %d)" % (in_file_h5.filename, index_start, index_stop, read_out_index, (index_stop - index_start)))
                                if last_good_readout_index + 1 == read_out_index - 1:
                                    logging.warning("found bad data in %s from index %d to %d (chunk %d, length %d)" % (in_file_h5.filename, readout_slices[last_good_readout_index][1], readout_slices[read_out_index - 1][1], last_good_readout_index + 1, (readout_slices[read_out_index - 1][1] - readout_slices[last_good_readout_index][1])))
                                else:
                                    logging.warning("found bad data in %s from index %d to %d (chunk %d to %d, length %d)" % (in_file_h5.filename, readout_slices[last_good_readout_index][1], readout_slices[read_out_index - 1][1], last_good_readout_index + 1, read_out_index - 1, (readout_slices[read_out_index - 1][1] - readout_slices[last_good_readout_index][1])))
                                previous_good_raw_data = in_file_h5.root.raw_data.read(readout_slices[last_good_readout_index][0], readout_slices[last_good_readout_index][1] - 1)
                                previous_bad_raw_data = in_file_h5.root.raw_data.read(readout_slices[last_good_readout_index][1] - 1, readout_slices[read_out_index - 1][1])
                                fixed_raw_data, _ = fix_raw_data(previous_bad_raw_data, lsb_byte=None)
                                fixed_raw_data = np.r_[previous_good_raw_data, fixed_raw_data, raw_data]
                                _, prepend_data_headers, n_triggers, n_dh = check_bad_data(fixed_raw_data, prepend_data_headers=previous_prepend_data_headers, trig_count=self.trig_count)
                                last_good_readout_index = read_out_index
                                if n_triggers != 0 or n_dh != 0:
                                    last_index_with_event_data = read_out_index
                                    last_event_data_prepend_data_headers = prepend_data_headers
                                fixed_previous_raw_data = np.r_[previous_good_raw_data, fixed_raw_data]
                                _, previous_prepend_data_headers, _ , _ = check_bad_data(fixed_previous_raw_data, prepend_data_headers=previous_prepend_data_headers, trig_count=self.trig_count)
                        # check for bad data
                        else:
                            # workaround for first data chunk, might have missing trigger in some rare cases (already fixed in firmware)
                            if read_out_index == 0 and (np.any(is_trigger_word(raw_data) >= 1) or np.any(is_fe_data_header(raw_data) >= 1)):
                                bad_data, current_prepend_data_headers, n_triggers , n_dh = check_bad_data(raw_data, prepend_data_headers=1, trig_count=None)
                                # check for full last event in data
                                if current_prepend_data_headers == self.trig_count:
                                    current_prepend_data_headers = None
                            # usually check for bad data happens here
                            else:
                                bad_data, current_prepend_data_headers, n_triggers , n_dh = check_bad_data(raw_data, prepend_data_headers=prepend_data_headers, trig_count=self.trig_count)

                            # do additional check with follow up data chunk and decide whether current chunk is defect or not
                            if bad_data:
                                if read_out_index == 0:
                                    fixed_raw_data_chunk, _ = fix_raw_data(raw_data, lsb_byte=None)
                                    fixed_raw_data_list = [fixed_raw_data_chunk]
                                else:
                                    previous_raw_data = in_file_h5.root.raw_data.read(*readout_slices[read_out_index - 1])
                                    raw_data_with_previous_data_word = np.r_[previous_raw_data[-1], raw_data]
                                    fixed_raw_data_chunk, _ = fix_raw_data(raw_data_with_previous_data_word, lsb_byte=None)
                                    fixed_raw_data = np.r_[previous_raw_data[:-1], fixed_raw_data_chunk]
                                    # last data word of chunk before broken chunk migh be a trigger word or data header which cannot be recovered
                                    fixed_raw_data_with_tw = np.r_[previous_raw_data[:-1], tw, fixed_raw_data_chunk]
                                    fixed_raw_data_with_dh = np.r_[previous_raw_data[:-1], dh, fixed_raw_data_chunk]
                                    fixed_raw_data_list = [fixed_raw_data, fixed_raw_data_with_tw, fixed_raw_data_with_dh]
                                bad_fixed_data, _, _ , _ = check_bad_data(fixed_raw_data_with_dh, prepend_data_headers=previous_prepend_data_headers, trig_count=self.trig_count)
                                bad_fixed_data = map(lambda data: check_bad_data(data, prepend_data_headers=previous_prepend_data_headers, trig_count=self.trig_count)[0], fixed_raw_data_list)
                                if not all(bad_fixed_data): # good fixed data
                                    # last word in chunk before currrent chunk is also bad
                                    if index_start != 0:
                                        bad_word_index.add(index_start - 1)
                                    # adding all word from current chunk
                                    bad_word_index = bad_word_index.union(range(index_start, index_stop))
                                    last_good_readout_index = read_out_index - 1
                                else:
                                    # a previous chunk might be broken and the last data word becomes a trigger word, so do additional checks
                                    if last_index_with_event_data and last_event_data_prepend_data_headers != read_out_index:
                                        before_bad_raw_data = in_file_h5.root.raw_data.read(readout_slices[last_index_with_event_data - 1][0], readout_slices[last_index_with_event_data - 1][1] - 1)
                                        previous_bad_raw_data = in_file_h5.root.raw_data.read(readout_slices[last_index_with_event_data][0] - 1, readout_slices[last_index_with_event_data][1])
                                        fixed_raw_data, _ = fix_raw_data(previous_bad_raw_data, lsb_byte=None)
                                        previous_good_raw_data = in_file_h5.root.raw_data.read(readout_slices[last_index_with_event_data][1], readout_slices[read_out_index - 1][1])
                                        fixed_raw_data = np.r_[before_bad_raw_data, fixed_raw_data, previous_good_raw_data, raw_data]
                                        bad_fixed_previous_data, current_prepend_data_headers, _ , _ = check_bad_data(fixed_raw_data, prepend_data_headers=last_event_data_prepend_data_headers, trig_count=self.trig_count)
                                        if not bad_fixed_previous_data:
                                            logging.warning("found bad data in %s from index %d to %d (chunk %d, length %d)" % (in_file_h5.filename, readout_slices[last_index_with_event_data][0], readout_slices[last_index_with_event_data][1], last_index_with_event_data, (readout_slices[last_index_with_event_data][1] - readout_slices[last_index_with_event_data][0])))
                                            bad_word_index = bad_word_index.union(range(readout_slices[last_index_with_event_data][0] - 1, readout_slices[last_index_with_event_data][1]))
                                        else:
                                            logging.warning("found bad data which cannot be corrected in %s from index %d to %d (chunk %d, length %d)" % (in_file_h5.filename, index_start, index_stop, read_out_index, (index_stop - index_start)))
                                    else:
                                        logging.warning("found bad data which cannot be corrected in %s from index %d to %d (chunk %d, length %d)" % (in_file_h5.filename, index_start, index_stop, read_out_index, (index_stop - index_start)))
                            if n_triggers != 0 or n_dh != 0:
                                last_index_with_event_data = read_out_index
                                last_event_data_prepend_data_headers = prepend_data_headers
                            if not bad_data or (bad_data and bad_fixed_data):
                                previous_prepend_data_headers = prepend_data_headers
                                prepend_data_headers = current_prepend_data_headers

                    consecutive_bad_words_list = consecutive(sorted(bad_word_index))

                lsb_byte = None
                # Loop over raw data in chunks
                for word_index in range(0, in_file_h5.root.raw_data.shape[0], self._chunk_size):  # loop over all words in the actual raw data file
                    try:
                        raw_data = in_file_h5.root.raw_data.read(word_index, word_index + self._chunk_size)
                    except OverflowError, e:
                        logging.error('%s: 2^31 xrange() limitation in 32-bit Python', e)
                    except tb.exceptions.HDF5ExtError:
                        logging.warning('Raw data file %s has missing raw data. Continue raw data analysis.', in_file_h5.filename)
                        break
                    total_words += raw_data.shape[0]
                    # fix bad data
                    if self._correct_corrupted_data:
                        # increase word shift for every bad data chunk in raw data chunk
                        word_shift = 0
                        chunk_indices = np.arange(word_index, word_index + self._chunk_size)
                        for consecutive_bad_word_indices in consecutive_bad_words_list:
                            selected_words = np.intersect1d(consecutive_bad_word_indices, chunk_indices, assume_unique=True)
                            if selected_words.shape[0]:
                                fixed_raw_data, lsb_byte = fix_raw_data(raw_data[selected_words - word_index - word_shift], lsb_byte=lsb_byte)
                                raw_data = np.r_[raw_data[:selected_words[0] - word_index - word_shift], fixed_raw_data, raw_data[selected_words[-1] - word_index + 1 - word_shift:]]
                                # check if last word of bad data chunk in current raw data chunk
                                if consecutive_bad_word_indices[-1] in selected_words:
                                    lsb_byte = None
                                    # word shift by removing data word at the beginning of each defect chunk
                                    word_shift += 1
                                # bad data chunk is at the end of current raw data chunk
                                else:
                                    break

                    self.interpreter.interpret_raw_data(raw_data)  # interpret the raw data
                    # store remaining buffered event in the interpreter at the end of the last file
                    if file_index == len(self.files_dict.keys()) - 1 and word_index == range(0, in_file_h5.root.raw_data.shape[0], self._chunk_size)[-1]:  # store hits of the latest event of the last file
                        self.interpreter.store_event()
                    hits = self.interpreter.get_hits()
                    if self.scan_parameters is not None:
                        nEventIndex = self.interpreter.get_n_meta_data_event()
                        self.histograming.add_meta_event_index(self.meta_event_index, nEventIndex)
                    if self.is_histogram_hits():
                        self.histogram_hits(hits)
                    if self.is_cluster_hits():
                        clustered_hits, cluster = self.cluster_hits(hits)
                        if self._create_cluster_hit_table:
                            cluster_hit_table.append(clustered_hits)
                        if self._create_cluster_table:
                            cluster_table.append(cluster)
                        if self._create_cluster_size_hist:
                            self._cluster_size_hist += fast_analysis_utils.hist_1d_index(cluster['size'], shape=self._cluster_size_hist.shape)
                        if self._create_cluster_tot_hist:
                            self._cluster_tot_hist += fast_analysis_utils.hist_2d_index(cluster['tot'][cluster['tot'] < 128], cluster['size'][cluster['tot'] < 128], shape=self._cluster_tot_hist.shape)
                    if self._analyzed_data_file is not None and self._create_hit_table:
                        hit_table.append(hits)
                    if self._analyzed_data_file is not None and self._create_meta_word_index:
                        size = self.interpreter.get_n_meta_data_word()
                        meta_word_index_table.append(meta_word[:size])

                    if total_words <= progress_bar.maxval:  # Otherwise exception is thrown
                        progress_bar.update(total_words)
                if self._analyzed_data_file is not None and self._create_hit_table:
                    hit_table.flush()
        progress_bar.finish()
        self._create_additional_data()
        if self._analyzed_data_file is not None:
            self.out_file_h5.close()

    def _create_additional_data(self):
        logging.info('Create selected event histograms')
        if self._analyzed_data_file is not None and self._create_meta_event_index:
            meta_data_size = self.meta_data.shape[0]
            n_event_index = self.interpreter.get_n_meta_data_event()
            if meta_data_size == n_event_index:
                if self.interpreter.meta_table_v2:
                    description = data_struct.MetaInfoEventTableV2().columns.copy()
                else:
                    description = data_struct.MetaInfoEventTable().columns.copy()
                last_pos = len(description)
                if self.scan_parameters is not None:  # add additional column with the scan parameter
                    for index, scan_par_name in enumerate(self.scan_parameters.dtype.names):
                        dtype, _ = self.scan_parameters.dtype.fields[scan_par_name][:2]
                        description[scan_par_name] = Col.from_dtype(dtype, dflt=0, pos=last_pos + index)
                meta_data_out_table = self.out_file_h5.create_table(self.out_file_h5.root, name='meta_data', description=description, title='MetaData', filters=self._filter_table)
                entry = meta_data_out_table.row
                for i in range(0, n_event_index):
                    if self.interpreter.meta_table_v2:
                        entry['event_number'] = self.meta_event_index[i][0]  # event index
                        entry['timestamp_start'] = self.meta_data[i][3]  # timestamp
                        entry['timestamp_stop'] = self.meta_data[i][4]  # timestamp
                        entry['error_code'] = self.meta_data[i][5]  # error code
                    else:
                        entry['event_number'] = self.meta_event_index[i][0]  # event index
                        entry['time_stamp'] = self.meta_data[i][3]  # time stamp
                        entry['error_code'] = self.meta_data[i][4]  # error code
                    if self.scan_parameters is not None:  # scan parameter if available
                        for scan_par_name in self.scan_parameters.dtype.names:
                            entry[scan_par_name] = self.scan_parameters[scan_par_name][i]
                    entry.append()
                meta_data_out_table.flush()
                if self.scan_parameters is not None:
                    logging.info("Save meta data with scan parameter " + scan_par_name)
            else:
                logging.error('Meta data analysis failed')
        if self._create_service_record_hist:
            self.service_record_hist = self.interpreter.get_service_records_counters()
            if self._analyzed_data_file is not None:
                service_record_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistServiceRecord', title='Service Record Histogram', atom=tb.Atom.from_dtype(self.service_record_hist.dtype), shape=self.service_record_hist.shape, filters=self._filter_table)
                service_record_hist_table[:] = self.service_record_hist
        if self._create_tdc_counter_hist:
            self.tdc_counter_hist = self.interpreter.get_tdc_counters()
            if self._analyzed_data_file is not None:
                tdc_counter_hist = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistTdcCounter', title='All Tdc word counter values', atom=tb.Atom.from_dtype(self.tdc_counter_hist.dtype), shape=self.tdc_counter_hist.shape, filters=self._filter_table)
                tdc_counter_hist[:] = self.tdc_counter_hist
        if self._create_error_hist:
            self.error_counter_hist = self.interpreter.get_error_counters()
            if self._analyzed_data_file is not None:
                error_counter_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistErrorCounter', title='Error Counter Histogram', atom=tb.Atom.from_dtype(self.error_counter_hist.dtype), shape=self.error_counter_hist.shape, filters=self._filter_table)
                error_counter_hist_table[:] = self.error_counter_hist
        if self._create_trigger_error_hist:
            self.trigger_error_counter_hist = self.interpreter.get_trigger_error_counters()
            if self._analyzed_data_file is not None:
                trigger_error_counter_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistTriggerErrorCounter', title='Trigger Error Counter Histogram', atom=tb.Atom.from_dtype(self.trigger_error_counter_hist.dtype), shape=self.trigger_error_counter_hist.shape, filters=self._filter_table)
                trigger_error_counter_hist_table[:] = self.trigger_error_counter_hist

        self._create_additional_hit_data()
        self._create_additional_cluster_data()

    def _create_additional_hit_data(self, safe_to_file=True):
        logging.info('Create selected hit histograms')
        if self._create_tot_hist:
            self.tot_hist = self.histograming.get_tot_hist()
            if self._analyzed_data_file is not None and safe_to_file:
                tot_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistTot', title='ToT Histogram', atom=tb.Atom.from_dtype(self.tot_hist.dtype), shape=self.tot_hist.shape, filters=self._filter_table)
                tot_hist_table[:] = self.tot_hist
        if self._create_tot_pixel_hist:
            if self._analyzed_data_file is not None and safe_to_file:
                self.tot_pixel_hist_array = np.swapaxes(self.histograming.get_tot_pixel_hist(), 0, 1)  # swap axis col,row, parameter --> row, col, parameter
                tot_pixel_hist_out = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistTotPixel', title='Tot Pixel Histogram', atom=tb.Atom.from_dtype(self.tot_pixel_hist_array.dtype), shape=self.tot_pixel_hist_array.shape, filters=self._filter_table)
                tot_pixel_hist_out[:] = self.tot_pixel_hist_array
        if self._create_tdc_hist:
            self.tdc_hist = self.histograming.get_tdc_hist()
            if self._analyzed_data_file is not None and safe_to_file:
                tdc_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistTdc', title='Tdc Histogram', atom=tb.Atom.from_dtype(self.tdc_hist.dtype), shape=self.tdc_hist.shape, filters=self._filter_table)
                tdc_hist_table[:] = self.tdc_hist
        if self._create_tdc_pixel_hist:
            if self._analyzed_data_file is not None and safe_to_file:
                self.tdc_pixel_hist_array = np.swapaxes(self.histograming.get_tdc_pixel_hist(), 0, 1)  # swap axis col,row, parameter --> row, col, parameter
                tdc_pixel_hist_out = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistTdcPixel', title='Tdc Pixel Histogram', atom=tb.Atom.from_dtype(self.tdc_pixel_hist_array.dtype), shape=self.tdc_pixel_hist_array.shape, filters=self._filter_table)
                tdc_pixel_hist_out[:] = self.tdc_pixel_hist_array
        if self._create_rel_bcid_hist:
            self.rel_bcid_hist = self.histograming.get_rel_bcid_hist()
            if self._analyzed_data_file is not None and safe_to_file:
                if not self.set_stop_mode:
                    rel_bcid_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistRelBcid', title='relative BCID Histogram', atom=tb.Atom.from_dtype(self.rel_bcid_hist.dtype), shape=(16, ), filters=self._filter_table)
                    rel_bcid_hist_table[:] = self.rel_bcid_hist[0:16]
                else:
                    rel_bcid_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistRelBcid', title='relative BCID Histogram in stop mode read out', atom=tb.Atom.from_dtype(self.rel_bcid_hist.dtype), shape=self.rel_bcid_hist.shape, filters=self._filter_table)
                    rel_bcid_hist_table[:] = self.rel_bcid_hist
        if self._create_occupancy_hist:
            self.occupancy_array = np.swapaxes(self.histograming.get_occupancy(), 0, 1)  # swap axis col,row, parameter --> row, col, parameter
            if self._analyzed_data_file is not None and safe_to_file:
                occupancy_array_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistOcc', title='Occupancy Histogram', atom=tb.Atom.from_dtype(self.occupancy_array.dtype), shape=self.occupancy_array.shape, filters=self._filter_table)
                occupancy_array_table[0:336, 0:80, 0:self.histograming.get_n_parameters()] = self.occupancy_array
        if self._create_mean_tot_hist:
            self.mean_tot_array = np.swapaxes(self.histograming.get_mean_tot(), 0, 1)  # swap axis col,row, parameter --> row, col, parameter
            if self._analyzed_data_file is not None and safe_to_file:
                mean_tot_array_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistMeanTot', title='Mean ToT Histogram', atom=tb.Atom.from_dtype(self.mean_tot_array.dtype), shape=self.mean_tot_array.shape, filters=self._filter_table)
                mean_tot_array_table[0:336, 0:80, 0:self.histograming.get_n_parameters()] = self.mean_tot_array
        if self._create_threshold_hists:
            threshold, noise = np.zeros(80 * 336, dtype=np.float64), np.zeros(80 * 336, dtype=np.float64)
            self.histograming.calculate_threshold_scan_arrays(threshold, noise, self._n_injection, np.min(self.scan_parameters['PlsrDAC']), np.max(self.scan_parameters['PlsrDAC']))  # calling fast algorithm function: M. Mertens, PhD thesis, Juelich 2010, note: noise zero if occupancy was zero
            threshold_hist, noise_hist = np.reshape(a=threshold.view(), newshape=(80, 336), order='F'), np.reshape(a=noise.view(), newshape=(80, 336), order='F')
            self.threshold_hist, self.noise_hist = np.swapaxes(threshold_hist, 0, 1), np.swapaxes(noise_hist, 0, 1)
            if self._analyzed_data_file is not None and safe_to_file:
                threshold_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistThreshold', title='Threshold Histogram', atom=tb.Atom.from_dtype(self.threshold_hist.dtype), shape=(336, 80), filters=self._filter_table)
                threshold_hist_table[:] = self.threshold_hist
                noise_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistNoise', title='Noise Histogram', atom=tb.Atom.from_dtype(self.noise_hist.dtype), shape=(336, 80), filters=self._filter_table)
                noise_hist_table[:] = self.noise_hist
        if self._create_fitted_threshold_hists:
            scan_parameters = np.linspace(np.amin(self.scan_parameters['PlsrDAC']), np.amax(self.scan_parameters['PlsrDAC']), num=self.histograming.get_n_parameters(), endpoint=True)
            self.scurve_fit_results = self.fit_scurves_multithread(self.out_file_h5, PlsrDAC=scan_parameters)
            if self._analyzed_data_file is not None and safe_to_file:
                fitted_threshold_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistThresholdFitted', title='Threshold Fitted Histogram', atom=tb.Atom.from_dtype(self.scurve_fit_results.dtype), shape=(336, 80), filters=self._filter_table)
                fitted_noise_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistNoiseFitted', title='Noise Fitted Histogram', atom=tb.Atom.from_dtype(self.scurve_fit_results.dtype), shape=(336, 80), filters=self._filter_table)
                fitted_threshold_hist_table.attrs.dimensions, fitted_noise_hist_table.attrs.dimensions = 'column, row, PlsrDAC', 'column, row, PlsrDAC'
                fitted_threshold_hist_table[:], fitted_noise_hist_table[:] = self.scurve_fit_results[:, :, 0], self.scurve_fit_results[:, :, 1]

                fitted_threshold_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistThresholdFittedCalib', title='Threshold Fitted Histogram with PlsrDAC clalibration', atom=tb.Atom.from_dtype(self.scurve_fit_results.dtype), shape=(336, 80), filters=self._filter_table)
                fitted_noise_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistNoiseFittedCalib', title='Noise Fitted Histogram with PlsrDAC clalibration', atom=tb.Atom.from_dtype(self.scurve_fit_results.dtype), shape=(336, 80), filters=self._filter_table)
                fitted_threshold_hist_table.attrs.dimensions, fitted_noise_hist_table.attrs.dimensions = 'column, row, electrons', 'column, row, electrons'
                self.threshold_hist_calib, self.noise_hist_calib = self._get_plsr_dac_charge(self.scurve_fit_results[:, :, 0]), self._get_plsr_dac_charge(self.scurve_fit_results[:, :, 1], no_offset=True)
                fitted_threshold_hist_table[:], fitted_noise_hist_table[:] = self.threshold_hist_calib, self.noise_hist_calib

    def _create_additional_cluster_data(self, safe_to_file=True):
        logging.info('Create selected cluster histograms')
        if self._create_cluster_size_hist:
            if self._analyzed_data_file is not None and safe_to_file:
                cluster_size_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistClusterSize', title='Cluster Size Histogram', atom=tb.Atom.from_dtype(self._cluster_size_hist.dtype), shape=self._cluster_size_hist.shape, filters=self._filter_table)
                cluster_size_hist_table[:] = self._cluster_size_hist
        if self._create_cluster_tot_hist:
            self._cluster_tot_hist[:, 0] = self._cluster_tot_hist.sum(axis=1)  # First bin is the projection of the others
            if self._analyzed_data_file is not None and safe_to_file:
                cluster_tot_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name='HistClusterTot', title='Cluster Tot Histogram', atom=tb.Atom.from_dtype(self._cluster_tot_hist.dtype), shape=self._cluster_tot_hist.shape, filters=self._filter_table)
                cluster_tot_hist_table[:] = self._cluster_tot_hist

    def analyze_hit_table(self, analyzed_data_file=None, analyzed_data_out_file=None):
        '''Analyzes a hit table with the c++ histogramer/clusterizer.

        Parameters
        ----------
        analyzed_data_file : string
            The file name of the already analyzed data file. If not set the analyzed data file
            specified during initialization is taken.
        analyzed_data_out_file : string
            The file name of the new analyzed data file. If not set the analyzed data file
            specified during initialization is taken.
        '''
        in_file_h5 = None

        # set output file if an output file name is given, otherwise check if an output file is already opened
        if analyzed_data_out_file is not None:  # if an output file name is specified create new file for analyzed data
            if self.is_open(self.out_file_h5):
                self.out_file_h5.close()
            self.out_file_h5 = tb.openFile(analyzed_data_out_file, mode="w", title="Analyzed FE-I4 hits")
        elif self._analyzed_data_file is not None:  # if no output file is specified check if an output file is already open and write new data into the opened one
            if not self.is_open(self.out_file_h5):
                self.out_file_h5 = tb.openFile(self._analyzed_data_file, mode="r+")
                in_file_h5 = self.out_file_h5  # input file is output file
        else:
            pass

        if analyzed_data_file is not None:
            self._analyzed_data_file = analyzed_data_file
        elif self._analyzed_data_file is None:
            logging.warning("No data file with analyzed data given, abort!")
            return

        if in_file_h5 is None:
            in_file_h5 = tb.openFile(self._analyzed_data_file, mode="r")

        if self._create_cluster_table:
            cluster_table = self.out_file_h5.create_table(self.out_file_h5.root, name='Cluster', description=data_struct.ClusterInfoTable, title='cluster_hit_data', filters=self._filter_table, expectedrows=self._chunk_size)
        if self._create_cluster_hit_table:
            cluster_hit_table = self.out_file_h5.create_table(self.out_file_h5.root, name='ClusterHits', description=data_struct.ClusterHitInfoTable, title='cluster_hit_data', filters=self._filter_table, expectedrows=self._chunk_size)

        if self._create_cluster_size_hist:  # Cluster size result histogram
            self._cluster_size_hist = np.zeros(shape=(self.max_cluster_size, ), dtype=np.uint32)

        if self._create_cluster_tot_hist:  # Cluster tot/size result histogram
            self._cluster_tot_hist = np.zeros(shape=(128, self.max_cluster_size), dtype=np.uint32)

        try:
            meta_data_table = in_file_h5.root.meta_data
            meta_data = meta_data_table[:]
            self.scan_parameters = analysis_utils.get_unique_scan_parameter_combinations(meta_data, scan_parameter_columns_only=True)
            if self.scan_parameters is not None:  # check if there is an additional column after the error code column, if yes this column has scan parameter infos
                meta_event_index = np.ascontiguousarray(analysis_utils.get_unique_scan_parameter_combinations(meta_data)['event_number'].astype(np.uint64))
                self.histograming.add_meta_event_index(meta_event_index, array_length=len(meta_event_index))
                self.scan_parameter_index = analysis_utils.get_scan_parameters_index(self.scan_parameters)  # a array that labels unique scan parameter combinations
                self.histograming.add_scan_parameter(self.scan_parameter_index)  # just add an index for the different scan parameter combinations
                scan_parameter_names = analysis_utils.get_scan_parameter_names(self.scan_parameters)
                logging.info('Adding scan parameter(s) for analysis: %s', (', ').join(scan_parameter_names) if scan_parameter_names else 'None',)
            else:
                logging.info("No scan parameter data provided")
                self.histograming.set_no_scan_parameter()
        except tb.exceptions.NoSuchNodeError:
            logging.info("No meta data provided")
            self.histograming.set_no_scan_parameter()

        table_size = in_file_h5.root.Hits.shape[0]
        n_hits = 0  # number of hits in actual chunk

        if table_size == 0:
            logging.warning('Hit table is empty.')
            self._create_additional_hit_data()
            self.out_file_h5.close()
            in_file_h5.close()
            return

        logging.info('Analyze hits...')
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.ETA()], maxval=table_size, term_width=80)
        progress_bar.start()

        for hits, index in analysis_utils.data_aligned_at_events(in_file_h5.root.Hits, chunk_size=self._chunk_size):
            n_hits += hits.shape[0]

            if self.is_cluster_hits():
                self.cluster_hits(hits)

            if self.is_histogram_hits():
                self.histogram_hits(hits)

            if self._analyzed_data_file is not None and self._create_cluster_hit_table:
                cluster_hits = self.clusterizer.get_hit_cluster()
                cluster_hit_table.append(cluster_hits)
            if self._analyzed_data_file is not None and self._create_cluster_table:
                cluster = self.clusterizer.get_cluster()
                cluster_table.append(cluster)
                if self._create_cluster_size_hist:
                    self._cluster_size_hist += fast_analysis_utils.hist_1d_index(cluster['size'], shape=self._cluster_size_hist.shape)
                if self._create_cluster_tot_hist:
                    self._cluster_tot_hist += fast_analysis_utils.hist_2d_index(cluster['tot'][cluster['tot'] < 128], cluster['size'][cluster['tot'] < 128], shape=self._cluster_tot_hist.shape)

            progress_bar.update(index)

        if n_hits != table_size:
            logging.warning('Not all hits analyzed, check analysis!')

        progress_bar.finish()
        self._create_additional_hit_data()
        self._create_additional_cluster_data()

        self.out_file_h5.close()
        in_file_h5.close()

    def analyze_hits(self, hits, scan_parameter=None):
        n_hits = hits.shape[0]
        logging.debug('Analyze %d hits' % n_hits)

        if self._create_cluster_table:
            cluster = np.zeros((n_hits,), dtype=dtype_from_descr(data_struct.ClusterInfoTable))
            self.clusterizer.set_cluster_info_array(cluster)
        else:
            cluster = None

        if self._create_cluster_hit_table:
            cluster_hits = np.zeros((n_hits,), dtype=dtype_from_descr(data_struct.ClusterHitInfoTable))
            self.clusterizer.set_cluster_hit_info_array(cluster_hits)
        else:
            cluster_hits = None

        if scan_parameter is None:  # if nothing specified keep actual setting
            logging.debug('Keep scan parameter settings ')
        elif not scan_parameter:    # set no scan parameter
            logging.debug('No scan parameter used')
            self.histograming.set_no_scan_parameter()
        else:
            logging.info('Setting a scan parameter')
            self.histograming.add_scan_parameter(scan_parameter)

        if self.is_cluster_hits():
            logging.debug('Cluster hits')
            self.cluster_hits(hits)

        if self.is_histogram_hits():
            logging.debug('Histogram hits')
            self.histogram_hits(hits)

        return cluster, cluster_hits

    def cluster_hits(self, hits, start_index=0, stop_index=None):
        if stop_index is not None:
            return self.clusterizer.cluster_hits(hits[start_index:stop_index])
        else:
            return self.clusterizer.cluster_hits(hits[start_index:])

    def histogram_hits(self, hits, start_index=0, stop_index=None):
        if stop_index is not None:
            self.histograming.add_hits(hits[start_index:stop_index])
        else:
            self.histograming.add_hits(hits[start_index:])

    def histogram_cluster_seed_hits(self, cluster, start_index=0, stop_index=None):
        if stop_index is not None:
            self.histograming.add_hits(cluster[start_index:stop_index])
        else:
            self.histograming.add_hits(cluster[start_index:])

    def plot_histograms(self, pdf_filename=None, analyzed_data_file=None, maximum=None, create_hit_hists_only=False):  # plots the histogram from output file if available otherwise from ram
        logging.info('Creating histograms%s', (' (source: %s)' % analyzed_data_file) if analyzed_data_file is not None else (' (source: %s)' % self._analyzed_data_file) if self._analyzed_data_file is not None else '')
        if analyzed_data_file is not None:
            out_file_h5 = tb.openFile(analyzed_data_file, mode="r")
        elif self._analyzed_data_file is not None:
            try:
                out_file_h5 = tb.openFile(self._analyzed_data_file, mode="r")
            except ValueError:
                logging.info('Output file handle in use, will histogram from RAM')
                out_file_h5 = None
        else:
            out_file_h5 = None
        if pdf_filename is not None:
            if os.path.splitext(pdf_filename)[1].strip().lower() != ".pdf":  # check for correct filename extension
                output_pdf_filename = os.path.splitext(pdf_filename)[0] + ".pdf"
            else:
                output_pdf_filename = pdf_filename
            logging.info('Opening output PDF file: %s', output_pdf_filename)
            output_pdf = PdfPages(output_pdf_filename)
        else:
            output_pdf = self.output_pdf
        if not output_pdf:
            raise analysis_utils.IncompleteInputError('Output PDF file descriptor not given.')
        logging.info('Saving histograms to PDF file: %s', str(output_pdf._file.fh.name))

        if self._create_threshold_hists:
            if self._create_threshold_mask:  # mask pixel with bad data for plotting
                if out_file_h5 is not None:
                    self.threshold_mask = analysis_utils.generate_threshold_mask(out_file_h5.root.HistNoise[:])
                else:
                    self.threshold_mask = analysis_utils.generate_threshold_mask(self.noise_hist)
            else:
                self.threshold_mask = np.zeros_like(out_file_h5.root.HistThreshold[:] if out_file_h5 is not None else self.threshold_hist, dtype=np.bool)
            threshold_hist = np.ma.array(out_file_h5.root.HistThreshold[:] if out_file_h5 is not None else self.threshold_hist, mask=self.threshold_mask)
            noise_hist = np.ma.array(out_file_h5.root.HistNoise[:] if out_file_h5 is not None else self.noise_hist, mask=self.threshold_mask)
            mask_cnt = np.ma.count_masked(noise_hist)
            logging.info('Fast algorithm: masking %d pixel(s)', mask_cnt)
            plotting.plot_three_way(hist=threshold_hist, title='Threshold%s' % ((' (masked %i pixel(s))' % mask_cnt) if self._create_threshold_mask else ''), x_axis_title="threshold [PlsrDAC]", filename=output_pdf, bins=100, minimum=0, maximum=maximum)
            plotting.plot_three_way(hist=noise_hist, title='Noise%s' % ((' (masked %i pixel(s))' % mask_cnt) if self._create_threshold_mask else ''), x_axis_title="noise [PlsrDAC]", filename=output_pdf, bins=100, minimum=0, maximum=maximum)
        if self._create_fitted_threshold_hists:
            if self._create_fitted_threshold_mask:
                if out_file_h5 is not None:
                    self.fitted_threshold_mask = analysis_utils.generate_threshold_mask(out_file_h5.root.HistNoiseFitted[:])
                else:
                    self.fitted_threshold_mask = analysis_utils.generate_threshold_mask(self.scurve_fit_results[:, :, 1])
            else:
                self.threshold_mask = np.zeros_like(out_file_h5.root.HistThresholdFitted[:] if out_file_h5 is not None else self.scurve_fit_results, dtype=np.bool8)
            threshold_hist = np.ma.array(out_file_h5.root.HistThresholdFitted[:] if out_file_h5 is not None else self.scurve_fit_results[:, :, 0], mask=self.fitted_threshold_mask)
            noise_hist = np.ma.array(out_file_h5.root.HistNoiseFitted[:] if out_file_h5 is not None else self.scurve_fit_results[:, :, 1], mask=self.fitted_threshold_mask)
            threshold_hist_calib = np.ma.array(out_file_h5.root.HistThresholdFittedCalib[:] if out_file_h5 is not None else self.threshold_hist_calib[:], mask=self.fitted_threshold_mask)
            noise_hist_calib = np.ma.array(out_file_h5.root.HistNoiseFittedCalib[:] if out_file_h5 is not None else self.noise_hist_calib[:], mask=self.fitted_threshold_mask)
            mask_cnt = np.ma.count_masked(noise_hist)
            logging.info('S-curve fit: masking %d pixel(s)', mask_cnt)
            plotting.plot_three_way(hist=threshold_hist, title='Threshold (S-curve fit, masked %i pixel(s))' % mask_cnt, x_axis_title="Threshold [PlsrDAC]", filename=output_pdf, bins=100, minimum=0, maximum=maximum)
            plotting.plot_three_way(hist=noise_hist, title='Noise (S-curve fit, masked %i pixel(s))' % mask_cnt, x_axis_title="Noise [PlsrDAC]", filename=output_pdf, bins=100, minimum=0, maximum=maximum)
            plotting.plot_three_way(hist=threshold_hist_calib, title='Threshold (S-curve fit, masked %i pixel(s))' % mask_cnt, x_axis_title="Threshold [e]", filename=output_pdf, bins=100, minimum=0)
            plotting.plot_three_way(hist=noise_hist_calib, title='Noise (S-curve fit, masked %i pixel(s))' % mask_cnt, x_axis_title="Noise [e]", filename=output_pdf, bins=100, minimum=0)
        if self._create_occupancy_hist:
            if self._create_fitted_threshold_hists:
                plotting.plot_scurves(occupancy_hist=out_file_h5.root.HistOcc[:] if out_file_h5 is not None else self.occupancy_array[:], filename=output_pdf, scan_parameters=np.linspace(np.amin(self.scan_parameters['PlsrDAC']), np.amax(self.scan_parameters['PlsrDAC']), num=self.histograming.get_n_parameters(), endpoint=True), scan_parameter_name="PlsrDAC")
            else:
                hist = np.sum(out_file_h5.root.HistOcc[:], axis=2) if out_file_h5 is not None else np.sum(self.occupancy_array[:], axis=2)
                occupancy_array_masked = np.ma.masked_equal(hist, 0)
                if self._create_source_scan_hist:
                    plotting.plot_fancy_occupancy(hist=occupancy_array_masked, filename=output_pdf, z_max='median')
                    plotting.plot_occupancy(hist=occupancy_array_masked, filename=output_pdf, z_max='maximum')
                else:
                    plotting.plot_three_way(hist=occupancy_array_masked, title="Occupancy", x_axis_title="occupancy", filename=output_pdf, maximum=maximum)
                    plotting.plot_occupancy(hist=occupancy_array_masked, filename=output_pdf, z_max='median')
        if self._create_tot_hist:
            plotting.plot_tot(hist=out_file_h5.root.HistTot if out_file_h5 is not None else self.tot_hist, filename=output_pdf)
        if self._create_tot_pixel_hist:
            tot_pixel_hist = out_file_h5.root.HistTotPixel[:] if out_file_h5 is not None else self.tot_pixel_hist_array
            mean_pixel_tot = np.average(tot_pixel_hist, axis=2, weights=range(16)) * sum(range(0, 16)) / np.sum(tot_pixel_hist, axis=2)
            plotting.plot_three_way(mean_pixel_tot, title='Mean ToT', x_axis_title='mean ToT', filename=output_pdf, minimum=0, maximum=15)
        if self._create_tdc_counter_hist:
            plotting.plot_tdc_counter(hist=out_file_h5.root.HistTdcCounter if out_file_h5 is not None else self.tdc_hist_counter, filename=output_pdf)
        if self._create_tdc_hist:
            plotting.plot_tdc(hist=out_file_h5.root.HistTdc if out_file_h5 is not None else self.tdc_hist, filename=output_pdf)
        if self._create_cluster_size_hist:
            plotting.plot_cluster_size(hist=out_file_h5.root.HistClusterSize if out_file_h5 is not None else self.cluster_size_hist, filename=output_pdf)
        if self._create_cluster_tot_hist:
            plotting.plot_cluster_tot(hist=out_file_h5.root.HistClusterTot if out_file_h5 is not None else self.cluster_tot_hist, filename=output_pdf)
        if self._create_cluster_tot_hist and self._create_cluster_size_hist:
            plotting.plot_cluster_tot_size(hist=out_file_h5.root.HistClusterTot if out_file_h5 is not None else self.cluster_tot_hist, filename=output_pdf)
        if self._create_rel_bcid_hist:
            if self.set_stop_mode:
                plotting.plot_relative_bcid_stop_mode(hist=out_file_h5.root.HistRelBcid if out_file_h5 is not None else self.rel_bcid_hist, filename=output_pdf)
            else:
                plotting.plot_relative_bcid(hist=out_file_h5.root.HistRelBcid[0:16] if out_file_h5 is not None else self.rel_bcid_hist[0:16], filename=output_pdf)
        if self._create_tdc_pixel_hist:
            tdc_pixel_hist = out_file_h5.root.HistTdcPixel[:, :, :1024] if out_file_h5 is not None else self.tdc_pixel_hist_array[:, :, :1024]  # only take first 1024 values, otherwise memory error likely
            mean_pixel_tdc = np.average(tdc_pixel_hist, axis=2, weights=range(1024)) * sum(range(0, 1024)) / np.sum(tdc_pixel_hist, axis=2)
            plotting.plot_three_way(mean_pixel_tdc, title='Mean TDC', x_axis_title='mean TDC', maximum=2 * np.ma.median(np.ma.masked_invalid(mean_pixel_tdc)), filename=output_pdf)
        if not create_hit_hists_only:
            if analyzed_data_file is None and self._create_error_hist:
                plotting.plot_event_errors(hist=out_file_h5.root.HistErrorCounter if out_file_h5 is not None else self.error_counter_hist, filename=output_pdf)
            if analyzed_data_file is None and self._create_service_record_hist:
                plotting.plot_service_records(hist=out_file_h5.root.HistServiceRecord if out_file_h5 is not None else self.service_record_hist, filename=output_pdf)
            if analyzed_data_file is None and self._create_trigger_error_hist:
                plotting.plot_trigger_errors(hist=out_file_h5.root.HistTriggerErrorCounter if out_file_h5 is not None else self.trigger_error_counter_hist, filename=output_pdf)

        if out_file_h5 is not None:
            out_file_h5.close()
        if pdf_filename is not None:
            logging.info('Closing output PDF file: %s', str(output_pdf._file.fh.name))
            output_pdf.close()

    def fit_scurves_multithread(self, hit_table_file=None, PlsrDAC=None):
        logging.info("Start S-curve fit on %d CPU core(s)", mp.cpu_count())
        occupancy_hist = hit_table_file.root.HistOcc[:] if hit_table_file is not None else self.occupancy_array[:]  # take data from RAM if no file is opened
        occupancy_hist_shaped = occupancy_hist.reshape(occupancy_hist.shape[0] * occupancy_hist.shape[1], occupancy_hist.shape[2])
        partialfit_scurve = partial(fit_scurve, PlsrDAC=PlsrDAC)  # trick to give a function more than one parameter, needed for pool.map
        pool = mp.Pool()  # create as many workers as physical cores are available
        try:
            result_list = pool.map(partialfit_scurve, occupancy_hist_shaped.tolist())
        except TypeError:
            raise analysis_utils.NotSupportedError('Less than 3 points found for S-curve fit.')
        finally:
            pool.close()
            pool.join()
        result_array = np.array(result_list)
        logging.info("S-curve fit finished")
        return result_array.reshape(occupancy_hist.shape[0], occupancy_hist.shape[1], 2)

    def is_open(self, h5_file):
        try:  # check if output h5 file is already opened
            h5_file.root
        except AttributeError:
            return False
        return True

    def is_histogram_hits(self):  # returns true if a setting needs to have the hit histogramming active
        if self._create_occupancy_hist or self._create_tot_hist or self._create_rel_bcid_hist or self._create_hit_table or self._create_threshold_hists or self._create_fitted_threshold_hists:
            return True
        return False

    def is_cluster_hits(self):  # returns true if a setting needs to have the clusterizer active
        if self.create_cluster_hit_table or self.create_cluster_table or self.create_cluster_size_hist or self.create_cluster_tot_hist:
            return True
        return False

    def _deduce_settings_from_file(self, opened_raw_data_file):  # TODO: parse better
        '''Tries to get the scan parameters needed for analysis from the raw data file
        '''
        try:  # take infos raw data files (not avalable in old files)
            flavor = opened_raw_data_file.root.configuration.miscellaneous[:][np.where(opened_raw_data_file.root.configuration.miscellaneous[:]['name'] == 'Flavor')]['value'][0]
            self._settings_from_file_set = True
            trig_count = opened_raw_data_file.root.configuration.global_register[:][np.where(opened_raw_data_file.root.configuration.global_register[:]['name'] == 'Trig_Count')]['value'][0]
            vcal_c0 = opened_raw_data_file.root.configuration.calibration_parameters[:][np.where(opened_raw_data_file.root.configuration.calibration_parameters[:]['name'] == 'Vcal_Coeff_0')]['value'][0]
            vcal_c1 = opened_raw_data_file.root.configuration.calibration_parameters[:][np.where(opened_raw_data_file.root.configuration.calibration_parameters[:]['name'] == 'Vcal_Coeff_1')]['value'][0]
            c_low = opened_raw_data_file.root.configuration.calibration_parameters[:][np.where(opened_raw_data_file.root.configuration.calibration_parameters[:]['name'] == 'C_Inj_Low')]['value'][0]
            c_mid = opened_raw_data_file.root.configuration.calibration_parameters[:][np.where(opened_raw_data_file.root.configuration.calibration_parameters[:]['name'] == 'C_Inj_Med')]['value'][0]
            c_high = opened_raw_data_file.root.configuration.calibration_parameters[:][np.where(opened_raw_data_file.root.configuration.calibration_parameters[:]['name'] == 'C_Inj_High')]['value'][0]
            self.c_low_mask = opened_raw_data_file.root.configuration.C_Low[:]
            self.c_high_mask = opened_raw_data_file.root.configuration.C_High[:]
            self.fei4b = False if str(flavor) == 'fei4a' else True
            self.trig_count = int(trig_count)
            self.vcal_c0 = float(vcal_c0)
            self.vcal_c1 = float(vcal_c1)
            self.c_low = float(c_low)
            self.c_mid = float(c_mid)
            self.c_high = float(c_high)
            self.n_injections = int(opened_raw_data_file.root.configuration.run_conf[:][np.where(opened_raw_data_file.root.configuration.run_conf[:]['name'] == 'n_injections')]['value'][0])
        except tb.exceptions.NoSuchNodeError:
            if not self._settings_from_file_set:
                logging.warning('No settings stored in raw data file %s, use standard settings', opened_raw_data_file.filename)
            else:
                logging.info('No settings provided in raw data file %s, use already set settings', opened_raw_data_file.filename)
        except IndexError:  # happens if setting is not available (e.g. repeat_command)
            pass

    def _get_plsr_dac_charge(self, plsr_dac_array, no_offset=False):
        '''Takes the PlsrDAC calibration and the stored C-high/C-low mask to calculate the charge from the PlsrDAC array on a pixel basis
        '''
        charge = np.zeros_like(self.c_low_mask, dtype=np.float16)  # charge in electrons
        voltage = self.vcal_c1 * plsr_dac_array if no_offset else self.vcal_c0 + self.vcal_c1 * plsr_dac_array
        charge[np.logical_and(self.c_low_mask, ~self.c_high_mask)] = voltage[np.logical_and(self.c_low_mask, ~self.c_high_mask)] * self.c_low / 0.16022
        charge[np.logical_and(~self.c_low_mask, self.c_high_mask)] = voltage[np.logical_and(self.c_low_mask, ~self.c_high_mask)] * self.c_mid / 0.16022
        charge[np.logical_and(self.c_low_mask, self.c_high_mask)] = voltage[np.logical_and(self.c_low_mask, ~self.c_high_mask)] * self.c_high / 0.16022
        return charge

if __name__ == "__main__":
    pass
