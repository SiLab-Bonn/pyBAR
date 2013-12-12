"""This is a script that analyzes the data taken with the scan_fei4_trigger scan. It uses the hit maps ad cluster maps for the analysis and can search for correlations etc.
"""

import numpy as np
import math
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pandas as pd
import itertools
import re
from matplotlib import colors, cm
from matplotlib.backends.backend_pdf import PdfPages


import logging

import tables as tb
from datetime import datetime
from analysis.analysis_utils import AnalysisUtils
from analysis.plotting.plotting import plot_correlation, plot_n_cluster, plot_pixel_matrix
from analysis.analyze_raw_data import AnalyzeRawData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def analyze(raw_data_file_triggered_fe=None, hit_file_triggered_fe=None, raw_data_file_trigger_fe=None, hit_file_trigger_fe=None, trigger_count=16, is_fei4b=False, print_warnings=True):
    if raw_data_file_triggered_fe != None:
        logging.info("Analyze triggered Fe data")
        with AnalyzeRawData(raw_data_file=raw_data_file_triggered_fe, analyzed_data_file=hit_file_triggered_fe) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(trigger_count)
            analyze_raw_data.max_tot_value = 13  # omit ToT = 14
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(print_warnings)
            analyze_raw_data.clusterizer.set_warning_output(print_warnings)
            analyze_raw_data.interpret_word_table(FEI4B=is_fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=hit_file_triggered_fe[:-3] + '.pdf', maximum='maximum')

    if raw_data_file_trigger_fe != None:
        logging.info("Analyze trigger Fe data")
        with AnalyzeRawData(raw_data_file=raw_data_file_trigger_fe, analyzed_data_file=hit_file_trigger_fe) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(trigger_count)
            analyze_raw_data.max_tot_value = 13  # omit ToT = 14
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(print_warnings)
            analyze_raw_data.clusterizer.set_warning_output(print_warnings)
            analyze_raw_data.interpret_word_table(FEI4B=is_fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=hit_file_trigger_fe[:-3] + '.pdf', maximum='maximum')


if __name__ == "__main__":
    start_time = datetime.now()
    chip_flavor = 'fei4a'
    scan_name = 'scan_fei4_trigger_107'

    raw_data_file_triggered_fe = 'data/' + scan_name + ".h5"
    raw_data_file_trigger_fe = 'data/' + scan_name + "_trigger_fe.h5"
    hit_file_triggered_fe = 'data/' + scan_name + "_interpreted.h5"
    hit_file_trigger_fe = 'data/' + scan_name + "_trigger_fe_interpreted.h5"

    analysis_utils = AnalysisUtils()

#     analyze(raw_data_file_triggered_fe=raw_data_file_triggered_fe, hit_file_triggered_fe=hit_file_triggered_fe, raw_data_file_trigger_fe=raw_data_file_trigger_fe, hit_file_trigger_fe=hit_file_trigger_fe, print_warnings=False)
    with tb.openFile(hit_file_triggered_fe, mode="r") as in_file_h5_triggered_fe:
        with tb.openFile(hit_file_trigger_fe, mode="r") as in_file_h5_trigger_fe:
            hit_table_triggered_fe = in_file_h5_triggered_fe.root.Hits
            hit_table_trigger_fe = in_file_h5_trigger_fe.root.Hits
            cluster_table_triggered_fe = in_file_h5_triggered_fe.root.Cluster
            cluster_table_trigger_fe = in_file_h5_trigger_fe.root.Cluster

#             print cluster_table_trigger_fe[]
#             tt = cluster_table_trigger_fe.read_where('size==1')
            print hit_table_triggered_fe[:3]['column']
            print hit_table_triggered_fe[:3]['row']

            occupancy = analysis_utils.histogram_occupancy_per_pixel(array=hit_table_triggered_fe[:])[0]
            print occupancy.shape
#             print np.where(occupancy[:]!=0)
#             print occupancy[occupancy[:]!=0].idx
# 
# 
            array = hit_table_triggered_fe[:]
            print array
# 
#             print analysis_utils.histogram_tot(array=array)
#             hist_tot = analysis_utils.histogram_tot_per_pixel(array=array)[0]
#             print hist_tot[42,156,5]

#             plot_pixel_matrix(analysis_utils.histogram_mean_tot_per_pixel(array=array), title='Mean ToT')
            plot_pixel_matrix(analysis_utils.histogram_occupancy_per_pixel(array=array, mask_no_hit=True)[0], title='Occupancy')

# #             extent = [hist_mean[2] - 0.5, hist_mean[2][-1] + 0.5, hist_mean[1][-1] + 0.5, hist_mean[1][0] - 0.5]
#             plt.imshow(hist.T, aspect='auto', cmap=cmap, interpolation='nearest')
# #             plt.gca().invert_yaxis()
#             divider = make_axes_locatable(plt.gca())
#             cax = divider.append_axes("right", size="5%", pad=0.05)
#             z_max = np.max(hist)
#             bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
#             norm = colors.BoundaryNorm(bounds, cmap.N)
#             plt.colorbar(boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True), cax=cax)
#             plt.show()

#             data_frame_triggered_fe_subset = analysis_utils.get_hits_with_n_cluster_per_event(hits_table=hit_table_triggered_fe, cluster_table=cluster_table_triggered_fe, n_cluster=1)
#             data_frame_trigger_fe_subset = analysis_utils.get_hits_with_n_cluster_per_event(hits_table=hit_table_trigger_fe, cluster_table=cluster_table_trigger_fe, n_cluster=1)
# #             print hit_table_triggered_fe_subset.head()
# #             print hit_table_trigger_fe_subset.head()
# 
#             # change column, row name to make them unique and usable for the correlation method 
#             data_frame_triggered_fe_subset = data_frame_triggered_fe_subset.rename(columns={'column': 'column_fe0', 'row': 'row_fe0'})
#             data_frame_trigger_fe_subset = data_frame_trigger_fe_subset.rename(columns={'column': 'column_fe1', 'row': 'row_fe1'})
# #             print hit_table_trigger_fe_subset.head()
# 
#             hist_n_cluster_triggered_fe = analysis_utils.get_n_cluster_per_event_hist(cluster_table=cluster_table_triggered_fe)
#             hist_n_cluster_trigger_fe = analysis_utils.get_n_cluster_per_event_hist(cluster_table=cluster_table_trigger_fe)
#             plot_n_cluster(hist=hist_n_cluster_triggered_fe, title='Cluster per event for the triggered Front-End')
#             plot_n_cluster(hist=hist_n_cluster_trigger_fe, title='Cluster per event for the trigger Front-End')
# #             analysis_utils.get_hits_with_n_cluster_per_event(hits_table=hit_table_triggered_fe, cluster_table=cluster_table_triggered_fe)
#  
#             hits_correlated = analysis_utils.correlate_events(data_frame_fe_1=data_frame_triggered_fe_subset, data_frame_fe_2=data_frame_trigger_fe_subset)
#             hist_col, hist_row = analysis_utils.histogram_correlation(data_frame_combined=hits_correlated)
#             plot_correlation(hist=hist_row, title='Hit correlation plot on rows', xlabel="Row triggered FE", ylabel="Row trigger FE")
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
