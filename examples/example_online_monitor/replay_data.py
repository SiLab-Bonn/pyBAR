'''This example shows the power of a fast raw data analysis and a data taking system where no data is discarded.
A raw data file is loaded and and data chunks are sent to the online monitor. These chunks are sent with the same speed
as it was done during data taking. This script can used to replay existing raw data files.

The online monitor will be automatically started when calling this script.
'''
import time
from subprocess import Popen

import numpy as np
import tables as tb

import zmq
from tqdm import tqdm

from pybar.daq.fei4_raw_data import send_data


def transfer_file(file_name, socket):  # Function to open the raw data file and sending the readouts periodically
    with tb.open_file(file_name, mode="r") as in_file_h5:
        meta_data = in_file_h5.root.meta_data[:]
        raw_data = in_file_h5.root.raw_data[:]
        try:
            scan_parameter_names = in_file_h5.root.scan_parameters.dtype.names
        except tb.NoSuchNodeError:
            scan_parameter_names = None
        pbar = tqdm(total=meta_data.shape[0], ncols=80)
        for index, (index_start, index_stop) in enumerate(np.column_stack((meta_data['index_start'], meta_data['index_stop']))):
            data = []
            data.append(raw_data[index_start:index_stop])
            data.extend((float(meta_data[index]['timestamp_start']), float(meta_data[index]['timestamp_stop']), int(meta_data[index]['error'])))
            if scan_parameter_names is not None:
                scan_parameter_value = [int(value) for value in in_file_h5.root.scan_parameters[index]]
                send_data(socket, data, scan_parameters=dict(zip(scan_parameter_names, scan_parameter_value)))
            else:
                send_data(socket, data)
            time.sleep(meta_data[index]['timestamp_stop'] - meta_data[index]['timestamp_start'])
            pbar.update(index - pbar.n)
        pbar.close()


if __name__ == '__main__':
    # Open th online monitor
    socket_addr = "tcp://127.0.0.1:5678"
    Popen(["python", "../../pybar/online_monitor.py", socket_addr])  # if this call fails, comment it out and start the script manually
    # Prepare socket
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(socket_addr)
    # Transfer file to socket
    transfer_file("../../tests/test_analysis/unit_test_data_2.h5", socket=socket)
    # Clean up
    socket.close()
    context.term()
