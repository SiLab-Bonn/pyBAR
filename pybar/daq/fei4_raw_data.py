import logging
import time
import glob
import zmq
from threading import RLock
import tables as tb
import os.path
from os import remove
from operator import itemgetter

from pybar.daq.readout_utils import save_configuration_dict
from pybar.analysis.RawDataConverter.data_struct import MetaTableV2 as MetaTable, generate_scan_parameter_description


def send_meta_data(socket, conf, name):
    '''Sends the config via ZeroMQ to a specified socket. Is called at the beginning of a run and when the config changes. Conf can be any config dictionary.
    '''
    meta_data = dict(
        name=name,
        conf=conf
    )
    try:
        socket.send_json(meta_data, flags=zmq.NOBLOCK)
    except zmq.Again:
        pass


def send_data(socket, data, scan_parameters={}, name='FEI4readoutData'):
    '''Sends the data of every read out (raw data and meta data) via ZeroMQ to a specified socket
    '''
    if not scan_parameters:
        scan_parameters = {}
    data_meta_data = dict(
        name=name,
        dtype=str(data[0].dtype),
        shape=data[0].shape,
        timestamp_start=data[1],  # float
        timestamp_stop=data[2],  # float
        readout_error=data[3],  # int
        scan_parameters=scan_parameters  # dict
    )
    try:
        socket.send_json(data_meta_data, flags=zmq.SNDMORE | zmq.NOBLOCK)
        socket.send(data[0], flags=zmq.NOBLOCK)  # PyZMQ supports sending numpy arrays without copying any data
    except zmq.Again:
        pass


def open_raw_data_file(filename, mode="w", title="", register=None, conf=None, run_conf=None, scan_parameters=None, socket_addr=None, zmq_context=None):
    '''Mimics pytables.open_file() and stores the configuration and run configuration

    Returns:
    RawDataFile Object

    Examples:
    with open_raw_data_file(filename = self.scan_data_filename, title=self.scan_id, scan_parameters=[scan_parameter]) as raw_data_file:
        # do something here
        raw_data_file.append(self.readout.data, scan_parameters={scan_parameter:scan_parameter_value})
    '''
    return RawDataFile(filename=filename, mode=mode, title=title, register=register, conf=conf, run_conf=run_conf, scan_parameters=scan_parameters, socket_addr=socket_addr, zmq_context=zmq_context)


class RawDataFile(object):

    max_table_size = 2**31 - 1000000  # pytables bug not allowing more than 2^31 entries in a table, since the read function uses xrange which behaves differently on 32/64bit platforms, fixed in pytables 3.2.0 release

    '''Raw data file object. Saving data queue to HDF5 file.
    '''

    def __init__(self, filename, mode="w", title='', register=None, conf=None, run_conf=None, scan_parameters=None, socket_addr=None, zmq_context=None):  # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created):
        self.lock = RLock()
        if os.path.splitext(filename)[1].strip().lower() != '.h5':
            self.base_filename = filename
        else:
            self.base_filename = os.path.splitext(filename)[0]
        if isinstance(scan_parameters, dict):
            self.scan_parameters = scan_parameters
        elif isinstance(scan_parameters, (list, tuple)):
            self.scan_parameters = dict.fromkeys(scan_parameters)
        else:
            self.scan_parameters = {}
        self.register = register  # reference to register object needed to store to fei4 raw data file
        self.raw_data_earray = None
        self.meta_data_table = None
        self.scan_param_table = None
        self.h5_file = None
        if mode and mode[0] == 'w':
            h5_files = glob.glob(os.path.splitext(filename)[0] + '*.h5')
            if h5_files:
                logging.info('Removing following file(s): %s', ', '.join(h5_files))
            for h5_file in h5_files:
                remove(h5_file)
        # list of filenames and index
        self.curr_filename = self.base_filename
        self.filenames = {self.curr_filename: 0}
        self.open(self.curr_filename, mode, title)
        if conf is not None:
            save_configuration_dict(self.h5_file, 'conf', conf)
        if run_conf is not None:
            save_configuration_dict(self.h5_file, 'run_conf', run_conf)
        if socket_addr is None:
            self.socket = None
        elif isinstance(socket_addr, basestring):
            if zmq_context is None:
                zmq_context = zmq.Context()  # create own context
            self.socket = zmq_context.socket(zmq.PUB)  # push data non blocking
            self.socket.bind(socket_addr)
            time.sleep(0.3)  # small sleep needed to be able to use ZMQ socket after creation
            send_meta_data(self.socket, run_conf, name='RunConf')  # send run info to indicate new scan
            logging.info('Sending data to %s' % socket_addr)
        else:
            raise ValueError('Expecting string for socket_addr.')

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False  # do not hide exceptions

    def open(self, filename, mode='w', title=''):
        if os.path.splitext(filename)[1].strip().lower() != '.h5':
            filename = os.path.splitext(filename)[0] + '.h5'
        if os.path.isfile(filename) and mode in ('r+', 'a'):
            logging.info('Opening existing raw data file: %s', filename)
        else:
            logging.info('Opening new raw data file: %s', filename)

        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        self.h5_file = tb.open_file(filename, mode=mode, title=title if title else filename)
        try:
            self.raw_data_earray = self.h5_file.createEArray(self.h5_file.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=filter_raw_data)  # expectedrows = ???
        except tb.exceptions.NodeError:
            self.raw_data_earray = self.h5_file.getNode(self.h5_file.root, name='raw_data')
        try:
            self.meta_data_table = self.h5_file.createTable(self.h5_file.root, name='meta_data', description=MetaTable, title='meta_data', filters=filter_tables)
        except tb.exceptions.NodeError:
            self.meta_data_table = self.h5_file.getNode(self.h5_file.root, name='meta_data')
        if self.scan_parameters:
            try:
                scan_param_descr = generate_scan_parameter_description(self.scan_parameters)
                self.scan_param_table = self.h5_file.createTable(self.h5_file.root, name='scan_parameters', description=scan_param_descr, title='scan_parameters', filters=filter_tables)
            except tb.exceptions.NodeError:
                self.scan_param_table = self.h5_file.getNode(self.h5_file.root, name='scan_parameters')

    def close(self):
        with self.lock:
            self.flush()
            logging.info('Closing raw data file: %s', self.h5_file.filename)
            self.h5_file.close()
            self.h5_file = None

    def append_item(self, data_tuple, scan_parameters=None, new_file=False, flush=True):
        with self.lock:
            if scan_parameters:
                # check for not existing keys
                diff = set(scan_parameters).difference(set(self.scan_parameters))
                if diff:
                    raise ValueError('Unknown scan parameter(s): %s' % ', '.join(diff))
                # parameters that have changed
                diff = [name for name in scan_parameters.keys() if scan_parameters[name] != self.scan_parameters[name]]
                self.scan_parameters.update(scan_parameters)
                if (new_file is True and diff) or (isinstance(new_file, (list, tuple)) and len([name for name in diff if name in new_file]) != 0):
                    self.curr_filename = os.path.splitext(self.base_filename)[0].strip() + '_' + '_'.join([str(item) for item in reduce(lambda x, y: x + y, [(key, value) for key, value in scan_parameters.items() if (new_file is True or (isinstance(new_file, (list, tuple)) and key in new_file))])])
                    index = self.filenames.get(self.curr_filename, 0)
                    if index == 0:
                        filename = self.curr_filename + '.h5'
                        self.filenames[self.curr_filename] = 0  # add to dict
                    else:
                        filename = self.curr_filename + '_' + str(index) + '.h5'
                    # copy nodes to new file
                    nodes = self.h5_file.list_nodes('/', classname='Group')
                    with tb.open_file(filename, mode='a', title=filename) as h5_file:  # append, since file can already exists when scan parameters are jumping back and forth
                        for node in nodes:
                            self.h5_file.copy_node(node, h5_file.root, overwrite=True, recursive=True)
                    self.close()
                    self.open(filename, 'a', filename)
            total_words = self.raw_data_earray.nrows
            raw_data = data_tuple[0]
            len_raw_data = raw_data.shape[0]
            if total_words + len_raw_data > self.max_table_size:
                index = self.filenames.get(self.curr_filename, 0) + 1  # reached file size limit, increase index by one
                self.filenames[self.curr_filename] = index  # update dict
                filename = self.curr_filename + '_' + str(index) + '.h5'
                # copy nodes to new file
                nodes = self.h5_file.list_nodes('/', classname='Group')
                with tb.open_file(filename, mode='a', title=filename) as h5_file:  # append, since file can already exists when scan parameters are jumping back and forth
                    for node in nodes:
                        self.h5_file.copy_node(node, h5_file.root, overwrite=True, recursive=True)
                self.close()
                self.open(filename, 'a', filename)
                total_words = self.raw_data_earray.nrows  # in case of re-opening existing file
            self.raw_data_earray.append(raw_data)
            self.meta_data_table.row['timestamp_start'] = data_tuple[1]
            self.meta_data_table.row['timestamp_stop'] = data_tuple[2]
            self.meta_data_table.row['error'] = data_tuple[3]
            self.meta_data_table.row['data_length'] = len_raw_data
            self.meta_data_table.row['index_start'] = total_words
            total_words += len_raw_data
            self.meta_data_table.row['index_stop'] = total_words
            self.meta_data_table.row.append()
            if self.scan_parameters:
                for key in self.scan_parameters:
                    self.scan_param_table.row[key] = self.scan_parameters[key]
                self.scan_param_table.row.append()
            if flush:
                self.flush()
            if self.socket:
                send_data(self.socket, data_tuple, self.scan_parameters)

    def append(self, data_iterable, scan_parameters=None, flush=True):
        with self.lock:
            for data_tuple in data_iterable:
                self.append_item(data_tuple, scan_parameters, flush=False)
            if flush:
                self.flush()

    def save_register_configuration(self):
        if self.register is None:
            raise RuntimeError('Register object not available for storing in FEi4 raw data file')
        self.register.save_configuration(self.h5_file)
        if self.socket:  # send global register config if socket is specified
            global_register_config = {}
            for global_reg in sorted(self.register.get_global_register_objects(readonly=False), key=itemgetter('name')):
                global_register_config[global_reg['name']] = global_reg['value']
            send_meta_data(self.socket, global_register_config, name='GlobalRegisterConf')  # send run info

    def flush(self):
        with self.lock:
            self.raw_data_earray.flush()
            self.meta_data_table.flush()
            if self.scan_parameters:
                self.scan_param_table.flush()


def save_raw_data_from_data_queue(data_queue, filename, mode='a', title='', scan_parameters=None):  # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created
    '''Writing raw data file from data queue

    If you need to write raw data once in a while this function may make it easy for you.
    '''
    if not scan_parameters:
        scan_parameters = {}
    with open_raw_data_file(filename, mode='a', title='', scan_parameters=list(dict.iterkeys(scan_parameters))) as raw_data_file:
        raw_data_file.append(data_queue, scan_parameters=scan_parameters)
