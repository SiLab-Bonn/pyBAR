''' A simple script that copies raw data from one file to another with similar timing as if the data comes from a FE. 
The new is a copy of the input file can be used to test a online monitor.
'''
import tables as tb
import numpy as np
import time

input_file = 'data//scan_threshold_fast_1.h5'
output_file = 'data//scan_threshold_fast_1_copy.h5'

from analysis.RawDataConverter.data_struct import MetaTableV2 as MetaTable

with tb.openFile(input_file, mode="r") as in_file_h5:
    meta_data = in_file_h5.root.meta_data[:]
    index_start = meta_data['index_start']
    index_stop = meta_data['index_stop']
    timestamp_start = meta_data['timestamp_start']
    timestamp_stop = meta_data['timestamp_stop']
    readout_frequency = np.divide(index_stop - index_start, timestamp_stop - timestamp_start)  # words read per second
    max_readout_frequency = int(np.amax(readout_frequency))
    average_readout_frequency = int(np.mean(readout_frequency))  # average readout speed in words per second
    scan_time = (timestamp_start * 5 - timestamp_start[0]).astype('uint')

    read_indices = np.array((0))
    read_indices = np.append(read_indices, np.where(np.diff(scan_time) != 0))
    stop_read_indices = read_indices[:-1] + np.diff(read_indices)

    with tb.openFile(output_file, mode="w") as out_file_h5:
        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        raw_data_earray = out_file_h5.createEArray(out_file_h5.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=filter_raw_data)
        meta_data_table = out_file_h5.createTable(out_file_h5.root, name='meta_data', description=MetaTable, title='meta_data', filters=filter_tables)
        for index in range(0, len(read_indices) - 1):
            print 'time', meta_data['timestamp_start'][0] - timestamp_start[0]
            meta_data = in_file_h5.root.meta_data.read(read_indices[index], stop_read_indices[index])
            raw_data = in_file_h5.root.raw_data.read(meta_data['index_start'][0], meta_data['index_stop'][-1])
            meta_data_table.append(meta_data[:])
            raw_data_earray.append(raw_data[:])
            meta_data_table.flush()
            raw_data_earray.flush()
            time.sleep(0.18)