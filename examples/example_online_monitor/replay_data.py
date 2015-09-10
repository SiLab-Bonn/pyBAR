'''This example shows the power of a fast raw data analysis and a data taking system where no data is discarded.
A raw data file is loaded and and data chunks are sent to the online monitor. These chunks are sent with the same speed
as it was done during data taking. This script can used to replay existing raw data files.

The online monitor will be automatically started when calling this script.
'''

import zmq
import time
import numpy as np
import tables as tb
import progressbar
import sys
from subprocess import Popen

from pybar.daq.fei4_raw_data import send_data


def transfer_file(file_name, socket):  # Function to open the raw data file and sending the readouts periodically
    with tb.openFile(file_name, mode="r") as in_file_h5:
        meta_data = in_file_h5.root.meta_data[:]
        raw_data = in_file_h5.root.raw_data[:]
        try:
            scan_parameter = in_file_h5.root.scan_parameters[:]
            scan_parameter_name = scan_parameter.dtype.names[0]
        except tb.NoSuchNodeError:
            scan_parameter = None
        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=meta_data.shape[0], term_width=80)
        progress_bar.start()
        for index, (index_start, index_stop) in enumerate(np.column_stack((meta_data['index_start'], meta_data['index_stop']))):
            time.sleep(delay)
            try:
                data = []
                data.append(raw_data[index_start:index_stop])
                data.extend((meta_data[index]['timestamp_start'], meta_data[index]['timestamp_stop'], meta_data[index]['error']))
                if scan_parameter is not None:
                    send_data(socket, data, scan_parameters={scan_parameter_name: float(scan_parameter[index][0])})
                else:
                    send_data(socket, data, scan_parameters='')
            except zmq.ZMQError:
                time.sleep(0.01)
            progress_bar.update(index)
        progress_bar.finish()


if __name__ == '__main__':
    # Open th online monitor
    Popen(["python", "../../pybar/online_monitor.py"] + sys.argv[1:])  # if this call fails, comment it out and start the script manually
    # Send delay in s; readout frequency is ~ 20Hz
    delay = 0.05
    # Prepare to send data
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.bind("tcp://127.0.0.1:5678")
    # Transfer file to socket
    transfer_file("../../tests/test_analysis/unit_test_data_2.h5", socket=socket)
    # Clean up
    socket.close()
    context.term()

