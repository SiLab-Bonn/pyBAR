"""This scan takes the interpreted meta data and plots the events per time.
"""
import tables as tb
import numpy as np
from datetime import datetime
import logging
from analysis import analysis_utils
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import time


analysis_configuration = {
    'data_files': ['data//SCC_99//SCC_99_fei4_self_trigger_gdac_scan_280', 'data//MDBM30//MDBM30_fei4_self_trigger_gdac_scan_373'],
    'combine_n_readouts': 1000,
    'time_line_absolute': True
}


def analyze_event_rate():
    for data_file in analysis_configuration['data_files']:
        with tb.openFile(data_file + '_interpreted.h5', mode="r") as in_file_h5:
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_ranges = np.column_stack((meta_data_array['timestamp_start'][::analysis_configuration['combine_n_readouts']], meta_data_array['timestamp_stop'][::analysis_configuration['combine_n_readouts']], analysis_utils.get_event_range(meta_data_array['event_number'][::analysis_configuration['combine_n_readouts']])))
            if analysis_configuration['time_line_absolute']:
                test = parameter_ranges[:-1, 0] + (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]) / 2.
                print test
                result = []
                for time in test:
                    result.append(datetime.fromtimestamp(time))
                ax = plt.gca()
                ax.format_xdata = mdates.DateFormatter('%Y-%m-%d')
                plt.plot(result, parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2])
            else:
                plt.plot((parameter_ranges[:-1, 0] + (parameter_ranges[:-1, 1] - parameter_ranges[:-1, 0]) / 2. - parameter_ranges[0, 0]) / 60., parameter_ranges[:-1, 3] - parameter_ranges[:-1, 2])
    plt.title('Events per time')
    if analysis_configuration['time_line_absolute']:
        pass
    else:
        plt.xlabel('Progressed time [min.]')
        plt.ylabel('Events per time [a.u.]')
    plt.show()

if __name__ == "__main__":
    start_time = datetime.now()
    analyze_event_rate()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
