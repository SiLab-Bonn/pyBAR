"""This is a script that analyzes the data taken with the scan_fei4_trigger scan. It uses the hit maps ad cluster maps for the analysis and can search for correlations etc.
"""

import logging
import itertools
import pandas as pd
import numpy as np
import tables as tb
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib import colors, cm
from datetime import datetime

from analysis.plotting.plotting import plot_correlation, plot_n_cluster
from analysis.analyze_raw_data import AnalyzeRawData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

#TODO trigger number...
#TODO omit TOT 14 before


def analyze(raw_data_file_triggered_fe=None, hit_file_triggered_fe=None, raw_data_file_trigger_fe=None, hit_file_trigger_fe=None, trigger_count=16, is_fei4b=False, print_warnings=True):
    if raw_data_file_triggered_fe != None:
        logging.info("Analyze triggered Fe data")
        with AnalyzeRawData(raw_data_file=raw_data_file_triggered_fe, analyzed_data_file=hit_file_triggered_fe) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(trigger_count)
            analyze_raw_data.max_tot_value = 13  # omit TOT = 14
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(print_warnings)
            analyze_raw_data.clusterizer.set_warning_output(print_warnings)
            analyze_raw_data.interpret_word_table(FEI4B=is_fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=hit_file_triggered_fe[:-3] + '.pdf')

    if raw_data_file_trigger_fe != None:
        logging.info("Analyze trigger Fe data")
        with AnalyzeRawData(raw_data_file=raw_data_file_trigger_fe, analyzed_data_file=hit_file_trigger_fe) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(trigger_count)
            analyze_raw_data.max_tot_value = 13  # omit TOT = 14
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(print_warnings)
            analyze_raw_data.clusterizer.set_warning_output(print_warnings)
            analyze_raw_data.interpret_word_table(FEI4B=is_fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=hit_file_trigger_fe[:-3] + '.pdf')


# @profile
def correlate_hits(hit_table_triggered_fe, hit_table_trigger_fe):
    logging.info("Correlating events")
    data_frame_triggered_fe = pd.DataFrame({'event_number': hit_table_triggered_fe[:]['event_number'], 'LVL1ID': hit_table_triggered_fe[:]['LVL1ID'], 'column': hit_table_triggered_fe[:]['column'], 'row': hit_table_triggered_fe[:]['row']})
    data_frame_trigger_fe = pd.DataFrame({'event_number': hit_table_trigger_fe[:]['event_number'], 'LVL1ID_trigger': hit_table_trigger_fe[:]['LVL1ID'], 'column_trigger': hit_table_trigger_fe[:]['column'], 'row_trigger': hit_table_trigger_fe[:]['row']})

    # remove duplicate hits from TOT = 14 hits or FE data error and count how many have been removed
    df_length_triggered_fe = len(data_frame_triggered_fe.index)
    df_length_trigger_fe = len(data_frame_trigger_fe.index)
    data_frame_triggered_fe = data_frame_triggered_fe.drop_duplicates()
    data_frame_trigger_fe = data_frame_trigger_fe.drop_duplicates()
    logging.info("Removed %d duplicates in triggered FE data" % (df_length_triggered_fe - len(data_frame_triggered_fe.index)))
    logging.info("Removed %d duplicates in trigger FE data" % (df_length_trigger_fe - len(data_frame_trigger_fe.index)))

    return data_frame_triggered_fe.merge(data_frame_trigger_fe, how='left', on='event_number')    # join in the events that the triggered fe sees, only these are interessting


def get_n_cluster_per_event_hist(cluster_table):
    logging.info("Calculate number of cluster per event")
    array = in_file_h5_triggered_fe.root.Cluster[:]['event_number']
    cluster_in_event = np.bincount(array)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
    print cluster_in_event[np.nonzero(cluster_in_event)][:20]
    return np.histogram(cluster_in_event, bins=range(0, np.max(cluster_in_event) + 2))  # histogram the occurrence of n cluster per event


def histogram_correlation(data_frame_combined):
    logging.info("Histograming correlations")
    corr_row = np.histogram2d(data_frame_combined['row'], data_frame_combined['row_trigger'], bins=(336, 336), range=[[1, 336], [1, 336]])
    corr_col = np.histogram2d(data_frame_combined['column'], data_frame_combined['column_trigger'], bins=(80, 80), range=[[1, 80], [1, 80]])
    return corr_col, corr_row


if __name__ == "__main__":
    start_time = datetime.now()
    chip_flavor = 'fei4a'
    scan_name = 'scan_fei4_trigger_51'

    raw_data_file_triggered_fe = 'data/' + scan_name + ".h5"
    raw_data_file_trigger_fe = 'data/' + scan_name + "_trigger_fe.h5"
    hit_file_triggered_fe = 'data/' + scan_name + "_interpreted.h5"
    hit_file_trigger_fe = 'data/' + scan_name + "_trigger_fe_interpreted.h5"

    analyze(raw_data_file_triggered_fe=raw_data_file_triggered_fe, hit_file_triggered_fe=hit_file_triggered_fe, raw_data_file_trigger_fe=raw_data_file_trigger_fe, hit_file_trigger_fe=hit_file_trigger_fe, print_warnings=False)
    with tb.openFile(hit_file_triggered_fe, mode="r") as in_file_h5_triggered_fe:
        with tb.openFile(hit_file_trigger_fe, mode="r") as in_file_h5_trigger_fe:
            hit_table_triggered_fe=in_file_h5_triggered_fe.root.Hits
            hit_table_trigger_fe=in_file_h5_trigger_fe.root.Hits
            cluster_table_triggered_fe=in_file_h5_triggered_fe.root.Cluster
            cluster_table_trigger_fe=in_file_h5_trigger_fe.root.Cluster

            hits_correlated = correlate_hits(hit_table_triggered_fe=hit_table_triggered_fe, hit_table_trigger_fe=hit_table_trigger_fe)
            hist_col, hist_row = histogram_correlation(data_frame_combined=hits_correlated)
            plot_correlation(hist=hist_col, title='Hit correlation plot on columns', xlabel="Column triggered FE", ylabel="Column trigger FE")
            plot_correlation(hist=hist_row, title='Hit correlation plot on rows', xlabel="Row triggered FE", ylabel="Row trigger FE")

            hist_n_cluster_triggered_fe = get_n_cluster_per_event_hist(cluster_table=cluster_table_triggered_fe)
            hist_n_cluster_trigger_fe = get_n_cluster_per_event_hist(cluster_table=cluster_table_trigger_fe)
            plot_n_cluster(hist=cluster_table_triggered_fe[0], title='Cluster per event for the triggered Front-End')
            plot_n_cluster(hist=cluster_table_trigger_fe[0], title='Cluster per event for the trigger Front-End')
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
