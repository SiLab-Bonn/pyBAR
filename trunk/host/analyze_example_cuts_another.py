"""This is an example module how to use the analysis_utils to apply cuts on interpreted hit and cluster data.
"""
scan_name = 'scan_fei4_trigger_141'

chip_flavor = 'fei4a'
input_file = 'data/' + scan_name + ".h5"
input_file_hits = 'data/' + scan_name + "_interpreted.h5"
output_file_hits = 'data/' + scan_name + "_cut.h5"
scan_data_filename = 'data/' + scan_name

import tables as tb
import numpy as np
from datetime import datetime
import logging
from analysis.RawDataConverter import data_struct
from analysis.analysis_utils import get_events_with_cluster_size, get_events_with_n_cluster, write_hits_in_events

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

nrows = 0
start_row = 0
chunk_size = 10000000


def select_hits():
    n_cluster_condition = 'n_cluster==1'
    cluster_size_condition = 'cluster_size==1'
    with tb.openFile(input_file_hits, mode="r") as in_hit_file_h5:
        with tb.openFile(output_file_hits, mode="w") as out_hit_file_h5:
            hit_table_out = out_hit_file_h5.createTable(out_hit_file_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            cluster_table = in_hit_file_h5.root.Cluster
            while(start_row < cluster_table.nrows):
                #print "start row", start_row
                src_array = cluster_table.read(start=start_row, stop=start_row + chunk_size)
                if start_row + src_array.shape[0] == cluster_table.nrows:
                    nrows = src_array.shape[0]
                else:
                    last_event = src_array["Event"][-1]
                    last_event_start_index = np.where(src_array["Event"] == last_event)[0][0]
                    #last_event_start_index = 0
                    if last_event_start_index == 0:
                        nrows = src_array.shape[0]
                        logging.info("Buffer too small to fit event. Possible loss of data")
                    else:
                        nrows = last_event_start_index
                #print "nrows", nrows
                start_row = start_row + nrows


            selected_events_1 = get_events_with_cluster_size(event_number=src_array['event_number'][0:nrows], cluster_size=src_array['size'][0:nrows], condition=cluster_size_condition)  # select the events with clusters of a certain size
#             selected_events_2 = get_events_with_n_cluster(event_number=src_array['event_number'][0:nrows], condition=n_cluster_condition)  # select the events with a certain cluster number
#             selected_events = selected_events_1[np.in1d(selected_events_1, selected_events_2, assume_unique=True)]  # select events with both conditions above
#             logging.info('Selected ' + str(len(selected_events)) + ' events with ' + n_cluster_condition + ' and ' + cluster_size_condition)
#             write_hits_in_events(hit_table_in=in_hit_file_h5.root.Hits, hit_table_out=hit_table_out, events=selected_events)  # write the hits of the selected events into a new table

if __name__ == "__main__":
    start_time = datetime.now()
    select_hits()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
