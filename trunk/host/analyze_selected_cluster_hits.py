"""This module takes hits from clusters that fulfill a certain criterion and histograms these.
"""
import tables as tb
from datetime import datetime
import logging
from analysis.RawDataConverter import data_struct
from analysis.analyze_raw_data import AnalyzeRawData
from analysis.analysis_utils import get_events_with_cluster_size, get_events_with_n_cluster, write_hits_in_events, data_aligned_at_events, in1d_sorted


def select_hits(input_file_hits, output_file_hits, cluster_size_condition='cluster_size==1', n_cluster_condition='n_cluster==1'):
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        with tb.openFile(output_file_hits, mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.createTable(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            last_word_number = 0
            for data, _ in data_aligned_at_events(cluster_table):
                selected_events_1 = get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition=cluster_size_condition)  # select the events with clusters of a certain size
                selected_events_2 = get_events_with_n_cluster(event_number=data['event_number'], condition=n_cluster_condition)  # select the events with a certain cluster number
                selected_events = selected_events_1[in1d_sorted(selected_events_1, selected_events_2)]  # select events with both conditions above
                logging.info('Selected ' + str(len(selected_events)) + ' events with ' + n_cluster_condition + ' and ' + cluster_size_condition)
                last_word_number = write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number)  # write the hits of the selected events into a new table
            in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file


def analyze_selected_hits(output_file_hits, output_file_hits_analyzed, scan_data_filename):
    with AnalyzeRawData(raw_data_file=None, analyzed_data_file=output_file_hits) as analyze_raw_data:
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
            analyze_raw_data.plot_histograms(scan_data_filename=output_file_hits_analyzed, analyzed_data_file=output_file_hits_analyzed)


if __name__ == "__main__":
    scan_name = 'scan_fei4_trigger_gdac_0'
    folder = 'K:\\data\\FE-I4\\ChargeRecoMethod\\bias_20\\'

    input_file_hits = folder + scan_name + "_interpreted.h5"
    output_file_hits = folder + scan_name + "_cut_1.h5"
    output_file_hits_analyzed = folder + scan_name + "_cut_0_analyzed.h5"
    scan_data_filename = folder + scan_name + "_cut_0_analyzed"

    start_time = datetime.now()
#     select_hits(input_file_hits, output_file_hits, cluster_size_condition='cluster_size==1', n_cluster_condition='n_cluster==1')
    analyze_selected_hits(output_file_hits, output_file_hits_analyzed, scan_data_filename)
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
