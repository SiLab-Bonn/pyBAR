import logging
import struct
import itertools
import time
import os.path
from threading import Thread, Event, Timer
from collections import deque
#from multiprocessing import Process as Thread
#from multiprocessing import Event
#from multiprocessing import Queue

import numpy as np
import numexpr as ne
import tables as tb

from utils.utils import get_float_time
from utils.utils import get_all_from_queue, split_seq
from analysis.data_struct import MetaTable

from SiLibUSB import SiUSBDevice

logging.basicConfig(level=logging.INFO, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

data_dict_names = ["data", "timestamp_start", "timestamp_stop", "error"]

class Readout(object):
    def __init__(self, device, data_filter = None):
        if isinstance(device, SiUSBDevice):
            self.device = device
        else:
            raise ValueError('Device object is not compatible')
        self.worker_thread = None
        self.data = deque()
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        self.readout_interval = 0.05
        self.rx_base_address = dict([(idx, addr) for idx, addr in enumerate(range(0x8600, 0x8200, -0x0100))])
        self.sram_base_address = dict([(idx, addr) for idx, addr in enumerate(range(0x8100, 0x8200, 0x0100))])
        self.timestamp_start = get_float_time()
        self.timestamp_stop = self.timestamp_start
    
    def start(self, reset_rx=False, empty_data_queue=True, reset_sram_fifo=True, filename=None):
        if self.worker_thread != None:
            raise RuntimeError('Thread is not None')
        if reset_rx:
            self.reset_rx()
        if empty_data_queue:
            #self.data.empty()
            self.data.clear()
        if reset_sram_fifo:
            self.reset_sram_fifo()
        self.stop_thread_event.clear()
        self.worker_thread = Thread(target=self.worker)
        logging.info('Starting readout')
        self.worker_thread.start()
    
    def stop(self, timeout=None):
        if self.worker_thread == None:
            raise RuntimeError('Thread is already None')
        if timeout:
            timeout_event = Event()
            timeout_event.clear()
            
            def set_timeout_event(timeout_event, timeout):
                timer = Timer(timeout, timeout_event.set)
                timer.start()
            
            timeout_thread = Thread(target=set_timeout_event, args=[timeout_event, timeout])
            timeout_thread.start()
            
            fifo_size = self.get_sram_fifo_size()
            old_fifo_size = -1
            while (old_fifo_size != fifo_size or fifo_size != 0) and not timeout_event.wait(1.5*self.readout_interval):
                old_fifo_size = fifo_size
                fifo_size = self.get_sram_fifo_size()
            if timeout_event.is_set():
                logging.warning('Waiting for empty SRAM FIFO: timeout after %.1f second(s)' % timeout)
            else:
                timeout_event.set()
            timeout_thread.join()
        self.stop_thread_event.set()
        self.worker_thread.join()
        self.worker_thread = None
        logging.info('Stopped readout')
    
    def print_readout_status(self):
        logging.info('Data queue size: %d' % len(self.data))#.qsize())
        logging.info('SRAM FIFO size: %d' % self.get_sram_fifo_size())
        logging.info('Channel:                     %s', " | ".join([('CH%d' % channel).rjust(3) for channel in range(1, 5, 1)]))
        logging.info('RX FIFO sync:                %s', " | ".join(["YES".rjust(3) if status == True else "NO".rjust(3) for status in self.get_rx_sync_status()]))
        logging.info('RX FIFO discard counter:     %s', " | ".join([repr(count).rjust(3) for count in self.get_rx_fifo_discard_count()]))
        logging.info('RX FIFO 8b10b error counter: %s', " | ".join([repr(count).rjust(3) for count in self.get_rx_8b10b_error_count()]))
    
    def worker(self):
        '''Reading thread to continuously reading SRAM
        
        Worker thread function that uses read_data_dict()
        ''' 
        while not self.stop_thread_event.wait(self.readout_interval): # TODO: this is probably what you need to reduce processor cycles
            self.device.lock.acquire() 
            try:
                data = self.read_data_dict()  
            except Exception as e:
                logging.error('Stopping readout: %s' % (e))
                self.stop_thread_event.set() # stop readout on any occurring exception
                continue
            finally:
                self.device.lock.release()
            if data[data_dict_names[0]].shape[0]>0: # TODO: make it optional
                self.data.append(data)#put({'timestamp':get_float_time(), 'raw_data':filtered_data_words, 'error':0})
                        
    def read_data_dict(self, append=True):
        '''Read single to read SRAM once
        
        can be used without threading
        '''
        # TODO: check FIFO status (overflow) and check rx status (sync) once in a while
        self.timestamp_stop = get_float_time()
        return {data_dict_names[0]:self.read_data(), data_dict_names[1]:self.timestamp_start, data_dict_names[2]:self.timestamp_start, data_dict_names[3]:self.read_status()}
        self.timestamp_start = self.timestamp_stop 
    
    def read_data(self):
        '''Read SRAM
        '''
        # TODO: check FIFO status (overflow) and check rx status (sync) once in a while

        fifo_size = self.get_sram_fifo_size()
        if fifo_size%2 == 1: # sometimes a read happens during writing, but we want to have a multiplicity of 32 bits
            fifo_size-=1
            #print "FIFO size odd"
        if fifo_size > 0:
            # old style:
            #fifo_data = self.device.FastBlockRead(4*fifo_size/2)
            #data_words = struct.unpack('>'+fifo_size/2*'I', fifo_data)
            return np.fromstring(self.device.FastBlockRead(4*fifo_size/2).tostring(), dtype=np.dtype('>u4'))
        else:
            return np.array([], dtype=np.dtype('>u4')) # create empty array
            #return np.empty(0, dtype=np.dtype('>u4')) # FIXME: faster?
        
    def read_status(self):
        return 0

    def reset_sram_fifo(self):
        logging.info('Resetting SRAM FIFO')
        self.timestamp_start = get_float_time()
        self.device.WriteExternal(address = self.sram_base_address[0], data = [0])
        if self.get_sram_fifo_size() != 0:
            logging.warning('SRAM FIFO size not zero')
        
    def get_sram_fifo_size(self):
        retfifo = self.device.ReadExternal(address = self.sram_base_address[0]+1, size = 3)
        retfifo.reverse() # FIXME: enable for new firmware
        return struct.unpack('I', retfifo.tostring() + '\x00' )[0]
                                                
    def reset_rx(self, index = None):
        logging.info('Resetting RX')
        if index == None:
            index = self.rx_base_address.iterkeys()
        filter(lambda i: self.device.WriteExternal(address = self.rx_base_address[i], data = [0]), index)
        # since WriteExternal returns nothing, filter returns empty list

    def get_rx_sync_status(self, index = None):
        if index == None:
            index = self.rx_base_address.iterkeys()
        return map(lambda i: True if (self.device.ReadExternal(address = self.rx_base_address[i]+1, size = 1)[0])&0x1 == 1 else False, index)

    def get_rx_8b10b_error_count(self, index = None):
        if index == None:
            index = self.rx_base_address.iterkeys()
        return map(lambda i: self.device.ReadExternal(address = self.rx_base_address[i]+4, size = 1)[0], index)

    def get_rx_fifo_discard_count(self, index = None):
        if index == None:
            index = self.rx_base_address.iterkeys()
        return map(lambda i: self.device.ReadExternal(address = self.rx_base_address[i]+5, size = 1)[0], index)

class ArrayConverter(object):
    def __init__(self, filter_func=None, converter_func=None, array=None):
        self.filter_func = filter_func
        self.converter_func = converter_func
        self.array = array
        if self.array is not None:
            self.convert()
        else:
            self.data = None
        
    def convert(self, array=None):
        if array is not None:
            self.data = array
        elif self.array is not None:
            self.data = self.array
        else:
            raise ValueError('no array available')
        if self.filter_func is not None:
            self.data = self.data[self.filter_func(self.data)]
        if self.converter_func is not None:
            self.data = self.converter_func(self.data)
        return self

    @classmethod
    def from_data_deque(cls, data_deque, filter_func=None, converter_func=None, clear_deque=False):
        def concatenate_data_deque_to_array(data_deque):
            return np.concatenate([item[data_dict_names[0]] for item in data_deque])
        data_array = concatenate_data_deque_to_array(data_deque)
        if clear_deque:
            data_deque.clear()
        return cls(filter_func, converter_func, data_array)

def is_data_from_channel(value, channel):
    '''Select data from channel
    
    Example:
    f_ch3 = functoools.partial(is_data_from_channel, channel=3) # recommended
    l_ch4 = lambda x: is_data_from_channel(x, channel=4)
    
    Note: trigger data not included
    '''
    if channel>0:
        return np.equal(np.right_shift(np.bitwise_and(value, 0x7F000000), 24), channel)
    else:
        raise ValueError('invalid channel number')
    
def is_data_record(value):
    return np.logical_and(np.greater_equal(np.bitwise_and(value, 0x00FFFFFF), 131328), np.less_equal(np.bitwise_and(value, 0x00FFFFFF), 10572030))

def is_data_header(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 15269888)
                    
def is_trigger_data(value):
    '''Select trigger data (trigger number)
    '''
    return np.equal(np.bitwise_and(value, 0x80000000), 0x80000000)

def get_col_row_tot_array_from_data_record_array(array):
    def get_col_row_tot_1_array_from_data_record_array(value):
        return np.right_shift(np.bitwise_and(value, 0x00FE0000), 17), np.right_shift(np.bitwise_and(value, 0x0001FF00), 8), np.right_shift(np.bitwise_and(value, 0x000000F0), 4)
#         return (value & 0xFE0000)>>17, (value & 0x1FF00)>>8, (value & 0x0000F0)>>4 # numpy.vectorize()
    
    def get_col_row_tot_2_array_from_data_record_array(value):
        return np.right_shift(np.bitwise_and(value, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(value, 0x0001FF00), 8), 1), np.bitwise_and(value, 0x0000000F)
#         return (value & 0xFE0000)>>17, ((value & 0x1FF00)>>8)+1, (value & 0x0000F) # numpy.vectorize()

    col_row_tot_1_array = np.column_stack(get_col_row_tot_1_array_from_data_record_array(array))
    col_row_tot_2_array = np.column_stack(get_col_row_tot_2_array_from_data_record_array(array))
#     print col_row_tot_1_array, col_row_tot_1_array.shape, col_row_tot_1_array.dtype
#     print col_row_tot_2_array, col_row_tot_2_array.shape, col_row_tot_2_array.dtype
    # interweave array here
    col_row_tot_array = np.vstack((col_row_tot_1_array.T, col_row_tot_2_array.T)).reshape((3, -1),order='F').T # http://stackoverflow.com/questions/5347065/interweaving-two-numpy-arrays
#     print col_row_tot_array, col_row_tot_array.shape, col_row_tot_array.dtype
    # remove ToT > 14 (late hit, no hit) from array, remove row > 336 in case we saw hit in row 336 (no double hit possible)
    try:
        col_row_tot_array_filtered = col_row_tot_array[col_row_tot_array[:,2]<14] #[np.logical_and(col_row_tot_array[:,2]<14, col_row_tot_array[:,1]<=336)]
#         print col_row_tot_array_filtered, col_row_tot_array_filtered.shape, col_row_tot_array_filtered.dtype
    except IndexError:
        logging.warning('Array is empty')
        return np.array([], dtype=np.dtype('>u4')), np.array([], dtype=np.dtype('>u4')), np.array([], dtype=np.dtype('>u4'))
    return col_row_tot_array_filtered[:,0], col_row_tot_array_filtered[:,1], col_row_tot_array_filtered[:,2] # column, row, ToT

def get_col_row_array_from_data_record_array(array):
    col, row, _ = get_col_row_tot_array_from_data_record_array(array)
    return col, row
 
def get_row_col_array_from_data_record_array(array):
    col, row, _ = get_col_row_tot_array_from_data_record_array(array)
    return row, col
 
def get_tot_array_from_data_record_array(array):
    _, _, tot = get_col_row_tot_array_from_data_record_array(array)
    return tot

def get_col_row_iterator_from_data_records(array): # generator
    for item in np.nditer(array):#, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.right_shift(np.bitwise_and(item, 0x0001FF00), 8)
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1)
        
def get_row_col_iterator_from_data_records(array): # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), np.right_shift(np.bitwise_and(item, 0x00FE0000), 17)
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1), np.right_shift(np.bitwise_and(item, 0x00FE0000), 17)
        
def get_col_row_tot_iterator_from_data_records(array): # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), np.right_shift(np.bitwise_and(item, 0x000000F0), 4) # col, row, ToT1
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1), np.bitwise_and(item, 0x0000000F) # col, row+1, ToT2
            
def get_tot_iterator_from_data_records(array): # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x000000F0), 4) # ToT1
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.bitwise_and(item, 0x0000000F) # ToT2
            
# TODO: add class that support with statement
def save_raw_data(data_deque, filename, title="", mode = "a", scan_parameters={}): # mode="r+" to append data, file must exist, "w" to overwrite file, "a" to append data, if file does not exist it is created
    if os.path.splitext(filename)[1].strip().lower() != ".h5":
        filename = os.path.splitext(filename)[0]+".h5"
#     if os.path.isfile(filename):
#         logging.warning('File already exists: %s' % filename)
    logging.info('Saving raw data: %s' % filename)
    if not data_deque:
        logging.warning('Deque is empty')
    scan_param_descr = dict([(key, tb.UInt32Col(pos=idx)) for idx, key in enumerate(dict.iterkeys(scan_parameters))])
    #raw_data = np.concatenate((data_dict['raw_data'] for data_dict in data))
    filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
    with tb.openFile(filename, mode = mode, title = title) as raw_data_file:
        try:
            raw_data_earray = raw_data_file.createEArray(raw_data_file.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data) # expectedrows = ???
        except tb.exceptions.NodeError:
            raw_data_earray = raw_data_file.getNode(raw_data_file.root, name = 'raw_data')
        try:
            meta_data_table = raw_data_file.createTable(raw_data_file.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables)
        except tb.exceptions.NodeError:
            meta_data_table = raw_data_file.getNode(raw_data_file.root, name = 'meta_data')
        row_meta = meta_data_table.row
        if scan_parameters:
            try:
                scan_param_table = raw_data_file.createTable(raw_data_file.root, name = 'scan_parameters', description = scan_param_descr, title = 'scan_parameters', filters = filter_tables)
            except tb.exceptions.NodeError:
                scan_param_table = raw_data_file.getNode(raw_data_file.root, name = 'scan_parameters')
            row_scan_param = scan_param_table.row
        total_words = raw_data_earray.nrows # needed to calculate start_index and stop_index
        while True:
            try:
                item = data_deque.popleft()
            except IndexError:
                break
            raw_data = item[data_dict_names[0]]
            len_raw_data = raw_data.shape[0]
            raw_data_earray.append(raw_data)
            row_meta['timestamp'] = item[data_dict_names[1]] # TODO: support for timestamp_stop
            row_meta['error'] = item[data_dict_names[3]]
            row_meta['length'] = len_raw_data
            row_meta['start_index'] = total_words
            total_words += len_raw_data
            row_meta['stop_index'] = total_words
            row_meta.append()
            if scan_parameters:
                for key, value in dict.iteritems(scan_parameters):
                    row_scan_param[key] = value
                row_scan_param.append()
        raw_data_earray.flush()
        meta_data_table.flush()
        if scan_parameters:
            scan_param_table.flush()
