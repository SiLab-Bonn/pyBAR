"""This is an example module how to use the analysis_utils to apply cuts on interpreted hit and cluster data.
"""
scan_name = 'scan_fei4_trigger_141'

chip_flavor = 'fei4a'
input_file = 'data/' + scan_name + ".h5"
input_file_hits = 'data/' + scan_name + "_interpreted.h5"
output_file_hits = 'data/' + scan_name + "_cut_0.h5"
scan_data_filename = 'data/' + scan_name

import tables as tb
import numpy as np
from datetime import datetime
import logging
from analysis.RawDataConverter import data_struct
from analysis.analysis_utils import get_events_with_cluster_size, get_events_with_n_cluster, write_hits_in_events, data_aligned_at_events

chunk_size = 10000000


def select_hits():
    n_cluster_condition = 'n_cluster==1'
    cluster_size_condition = 'cluster_size==1'
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        with tb.openFile(output_file_hits, mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.createTable(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            last_word_number = 0
            for data in data_aligned_at_events(cluster_table):
                selected_events_1 = get_events_with_cluster_size(event_number=data['event_number'], cluster_size=data['size'], condition=cluster_size_condition)  # select the events with clusters of a certain size
                selected_events_2 = get_events_with_n_cluster(event_number=data['event_number'], condition=n_cluster_condition)  # select the events with a certain cluster number
                selected_events = selected_events_1[np.in1d(selected_events_1, selected_events_2, assume_unique=True)]  # select events with both conditions above
                logging.info('Selected ' + str(len(selected_events)) + ' events with ' + n_cluster_condition + ' and ' + cluster_size_condition)
                last_word_number = write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events, start_hit_word=last_word_number)  # write the hits of the selected events into a new table
            in_hit_file_h5.root.meta_data.copy(out_hit_file_h5.root)  # copy meta_data note to new file
if __name__ == "__main__":
    start_time = datetime.now()
    select_hits()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
