"""This script takes the interpreted hit table, selects events with only one hit with one hit cluster and histograms the TDC info for these hits.
"""

import numpy as np
import tables as tb
from datetime import datetime
import logging
from analysis.RawDataConverter import data_struct
from analysis.analyze_raw_data import AnalyzeRawData
from analysis import analysis_utils

analysis_configuration = {
    "scan_name": 'SCC_50_fei4_self_trigger_scan_390',
    "folder": 'data//SCC_50//',
    'input_file_calibration': None,
    "chip_flavor": 'fei4a',
    "n_bcid": 4,
}


def analyze_raw_data():
    scan_base = analysis_configuration['folder'] + analysis_configuration['scan_name']
    with AnalyzeRawData(raw_data_file=scan_base + '.h5', analyzed_data_file=scan_base + '_interpreted.h5') as analyze_raw_data:
        analyze_raw_data.create_hit_table = True  # can be set to false to omit hit table creation, std. setting is false
        analyze_raw_data.create_cluster_table = True
        analyze_raw_data.create_cluster_size_hist = True  # enables cluster size histogramming, can save some time, std. setting is false
        analyze_raw_data.create_cluster_tot_hist = True  # enables cluster ToT histogramming per cluster size, std. setting is false
        analyze_raw_data.n_bcid = analysis_configuration['n_bcid']  # set the number of BCIDs per event, needed to judge the event structure
        analyze_raw_data.max_tot_value = 13  # set the maximum ToT value considered to be a hit, 14 is a late hit
        analyze_raw_data.interpreter.set_warning_output(True)  # std. setting is True
        analyze_raw_data.interpret_word_table(fei4b=True if(analysis_configuration['chip_flavor'] == 'fei4b') else False)  # the actual start conversion command
        analyze_raw_data.interpreter.print_summary()  # prints the interpreter summary
        analyze_raw_data.plot_histograms(scan_data_filename=scan_base)  # plots all activated histograms into one pdf


def histogram_tdc_hits():
    scan_base = analysis_configuration['folder'] + analysis_configuration['scan_name']
    with tb.openFile(scan_base + '_interpreted.h5', mode="r+") as in_hit_file_h5:  # select hits
        analysis_utils.index_event_number(in_hit_file_h5.root.Hits)
        with tb.openFile(scan_base + '_selected_hits.h5', mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.createTable(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            last_word_number = 0
            for data, _ in analysis_utils.data_aligned_at_events(cluster_table):
                selected_events_1 = analysis_utils.get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition='cluster_size==1')  # select the events with clusters of a certain size
                selected_events_2 = analysis_utils.get_events_with_n_cluster(event_number=data['event_number'], condition='n_cluster==1')  # select the events with a certain cluster number
                selected_events = selected_events_1[analysis_utils.in1d_sorted(selected_events_1, selected_events_2)]  # select events with both conditions above
                logging.info('Selected ' + str(len(selected_events)) + ' events with  n_cluster==1 and cluster_size==1')
                last_word_number = analysis_utils.write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number)  # write the hits of the selected events into a new table
            in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file
    # histogram selected hits
    with tb.openFile(scan_base + '_selected_hits.h5', mode="r") as in_hit_file_h5:
        hits = in_hit_file_h5.root.Hits[:]
        col_row_tdc_hist, _ = np.histogramdd((hits[:]['column'], hits[:]['row'], hits[:]['TDC']), bins=(80, 336, 1024), range=[[1, 80], [1, 336], [0, 1024]])
        print col_row_tdc_hist[3, 5, :]


if __name__ == "__main__":
    start_time = datetime.now()
    analyze_raw_data()
    histogram_tdc_hits()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
