import logging
from time import time
from threading import Timer
from contextlib import contextmanager

import progressbar
import numpy as np

from pybar.analysis.analyze_raw_data import AnalyzeRawData


raw_data_file = '/media/data/SHiP/charm_exp_2018/test_data_converter/elsa_testbeam_data/take_data/module_0/126_module_0_ext_trigger_scan_s_hi_p.h5'

with AnalyzeRawData(raw_data_file=raw_data_file, create_pdf=True) as analyze_raw_data:
    analyze_raw_data.trigger_data_format = 1
    analyze_raw_data.create_source_scan_hist = True
    analyze_raw_data.create_cluster_size_hist = True
    analyze_raw_data.create_cluster_tot_hist = True
    analyze_raw_data.align_at_trigger = True
    analyze_raw_data.create_hit_table = True
    analyze_raw_data.create_empty_event_hits = True
    analyze_raw_data.interpreter.set_warning_output(False)
    analyze_raw_data.interpret_word_table()
    analyze_raw_data.interpreter.print_summary()
    analyze_raw_data.plot_histograms()
#     hits = analyze_raw_data.interpreter.get_hits()
#     print hits[0]['trigger_time_stamp']
