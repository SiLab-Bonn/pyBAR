"""This script takes the raw data file and can analyze it while it is still being filled. Thus this script can serve as an 'online monitor'
"""
import tables as tb
import numpy as np
import logging
import time
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib import colors, cm
from mpl_toolkits.axes_grid1 import make_axes_locatable

from analysis.analyze_raw_data import AnalyzeRawData
from analysis.RawDataConverter.data_interpreter import PyDataInterpreter
from analysis.RawDataConverter import data_struct
from analysis.RawDataConverter.data_histograming import PyDataHistograming
from analysis.plotting import plotting
# from analysis.RawDataConverter.data_clusterizer import PyDataClusterizer

analysis_configuration = {
    "scan_name": 'SCC_99_fei4_self_trigger_scan_259',
    "folder": 'data//SCC_99//',
    "chip_flavor": 'fei4a',
    "trig_count": 4,
    "integrate" : True,
    "chunk_size": 2000000,
    "no_data_wait_time": 1,
    "warnings": False,
    "infos": False
}


def analyze_raw_data(in_file_h5, start, stop):
    logging.info('Analyze raw data from word index ' + str(start) + ' to ' + str(stop))
    n_hits = 0
    if not analysis_configuration['integrate']:
        histograming.reset()
    for iWord in range(start, stop, analysis_configuration['chunk_size']):
        if stop - start <= analysis_configuration['chunk_size']:
            stop_index = stop
        else:
            stop_index = iWord + analysis_configuration['chunk_size']
        try:
            logging.info('Take chunk from ' + str(iWord) + ' to ' + str(stop_index))
            raw_data = in_file_h5.root.raw_data.read(iWord, stop_index)
            interpreter.interpret_raw_data(raw_data)  # interpret the raw data
            Nhits = interpreter.get_n_array_hits()
            histograming.add_hits(hits[0:Nhits], Nhits)
            n_hits += Nhits
        except tb.exceptions.NoSuchNodeError:
            logging.info('File in inconsistent state, omit hits')
        except tb.exceptions.HDF5ExtError:
            logging.info('File in inconsistent state, omit hits')

    occupancy = np.zeros(80 * 336 * histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
    histograming.get_occupancy(occupancy)
    occupancy_array = np.reshape(a=occupancy.view(), newshape=(80, 336, histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
    occupancy_array = np.swapaxes(occupancy_array, 0, 1)
    occupancy_array_ma = np.ma.array(occupancy_array)[:, :, 0]
    plotting.plot_fancy_occupancy(occupancy_array_ma, z_max='median')
#     plotting.plot_occupancy(occupancy_array_ma)
    error_counter_hist = np.zeros(16, dtype=np.uint32)
    interpreter.get_error_counters(error_counter_hist)
    plotting.plot_event_errors(error_counter_hist)

    rel_bcid_hist = np.empty(16, dtype=np.uint32)
    histograming.get_rel_bcid_hist(rel_bcid_hist)
    plotting.plot_relative_bcid(rel_bcid_hist)
    plt.pause(0.0001)
    return n_hits


def analyze_raw_data_file(input_file):
    last_index_read = 0
    old_last_index_read = 0
    total_hits = 0
    interpreter.set_hits_array(hits)  # set the temporary hit data to be filled by the interpreter
    start_time_scan = 0
    start_time_scan_set = False
    wait_for_data = False
    start_time_analysis = datetime.now()
    while True:# (datetime.now() - start_time).total_seconds() < 50:
        try:
            with tb.openFile(input_file, mode="r") as in_file_h5:
                meta_data = in_file_h5.root.meta_data[:]
                interpreter.set_meta_data(meta_data)  # set the recoreded meta data
                meta_event_index = np.zeros((meta_data.shape[0],), dtype=[('metaEventIndex', np.uint32)])  # this array is filled by the interpreter and holds the event number per read out
                interpreter.set_meta_event_data(meta_event_index)
                last_index_read = len(in_file_h5.root.meta_data) - 1
                if not start_time_scan_set:
                    start_time_scan = meta_data[old_last_index_read]['timestamp_start']
                    start_time_scan_set = True
                if (last_index_read != old_last_index_read):
#                     print 'new meta data from',old_last_index_read,'to',last_index_read
#                     print 'scan time', meta_data[old_last_index_read]['timestamp_start'] - start_time_scan
#                     print 'analysis time', (datetime.now() - start_time_analysis).total_seconds()
#                     print meta_data[old_last_index_read]['timestamp_start'] - start_time_scan - (datetime.now() - start_time_analysis).total_seconds()
                    start_index = meta_data[old_last_index_read]['index_start']
                    stop_index = meta_data[last_index_read]['index_start']
                    total_hits += analyze_raw_data(in_file_h5, start=start_index, stop=stop_index)
                    old_last_index_read = last_index_read
                else:
                    if not wait_for_data:
                        logging.info('No new data, wait %d seconds for new data' % analysis_configuration['no_data_wait_time'])
                        wait_for_data = True
                        time.sleep(analysis_configuration['no_data_wait_time'])
                    else:
                        break
        except tb.exceptions.HDF5ExtError:
            logging.info('File in inconsistent state, read again')

if __name__ == "__main__":
    interpreter = PyDataInterpreter()
    histograming = PyDataHistograming()

    interpreter.set_info_output(analysis_configuration['infos'])
    interpreter.set_warning_output(analysis_configuration['warnings'])
    interpreter.set_FEI4B(False if analysis_configuration['chip_flavor'] == 'fei4a' else True)
    interpreter.set_trig_count(analysis_configuration['trig_count'])
    histograming.set_no_scan_parameter()
    histograming.create_occupancy_hist(True)
    histograming.create_rel_bcid_hist(True)
    plt.ion()

    hits = np.empty((analysis_configuration['chunk_size'],), dtype=tb.dtype_from_descr(data_struct.HitInfoTable))  # hold the hits per analyze_raw_data call

    start_time = datetime.now()
    analyze_raw_data_file(input_file=analysis_configuration['folder'] + analysis_configuration['scan_name'] + '.h5')
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())

    plt.ioff()
    plt.show()
