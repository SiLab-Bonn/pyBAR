from functools import wraps
from time import time

def timed(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time()
        result = f(*args, **kwargs)
        elapsed = time() - start
        print "%s took %fs to finish" % (f.__name__, elapsed)
        return result
    return wrapper


import logging
import struct
import itertools
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

data_deque_dict_names = ["data", "timestamp_start", "timestamp_stop", "error"]

class Readout(object):
    def __init__(self, device):
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
        self.worker_thread.daemon = True
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
        sync_status = self.get_rx_sync_status()
        logging.info('Data queue size: %d' % len(self.data))#.qsize())
        logging.info('SRAM FIFO size: %d' % self.get_sram_fifo_size())
        logging.info('Channel:                     %s', " | ".join([('CH%d' % channel).rjust(3) for channel in range(1, 5, 1)]))
        logging.info('RX FIFO sync:                %s', " | ".join(["YES".rjust(3) if status == True else "NO".rjust(3) for status in sync_status]))
        logging.info('RX FIFO discard counter:     %s', " | ".join([repr(count).rjust(3) for count in self.get_rx_fifo_discard_count()]))
        logging.info('RX FIFO 8b10b error counter: %s', " | ".join([repr(count).rjust(3) for count in self.get_rx_8b10b_error_count()]))
        return sync_status
    
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
            if data[data_deque_dict_names[0]].shape[0]>0: # TODO: make it optional
                self.data.append(data)#put({'timestamp':get_float_time(), 'raw_data':filtered_data_words, 'error':0})
                        
    def read_data_dict(self, append=True):
        '''Read single to read SRAM once
        
        can be used without threading
        '''
        # TODO: check FIFO status (overflow) and check rx status (sync) once in a while
        self.timestamp_stop = get_float_time()
        return {data_deque_dict_names[0]:self.read_data(), data_deque_dict_names[1]:self.timestamp_start, data_deque_dict_names[2]:self.timestamp_start, data_deque_dict_names[3]:self.read_status()}
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

class DataConverter(object):
    def __init__(self, filter_func=None, converter_func=None, data_deque=None):
        self.filter_func = filter_func
        self.converter_func = converter_func
        self.data_deque = data_deque
        self.data = deque()
        if self.data_deque is not None:
            self.convert()
        
    def convert(self, data_deque=None, clear_deque=False, concatenate=False):
        if data_deque is not None:
            data = list(data_deque)
            if clear_deque:
                data_deque.clear()
        elif self.array is not None:
            data = list(self.data_deque)
            if clear_deque:
                self.data_deque.clear()
        else:
            raise ValueError('no data available')
        if concatenate:
            data_array = data_array_from_data_dict_iterable(data, filter_func=self.filter_func, converter_func=self.converter_func)
            self.data.append({data_deque_dict_names[0]:data_array, data_deque_dict_names[1]:data[0][data_deque_dict_names[1]], data_deque_dict_names[2]:data[-1][data_deque_dict_names[2]], data_deque_dict_names[3]:reduce(lambda x,y: x|y, [item[data_deque_dict_names[3]] for item in data])})
        else:
            for item in data:
                data_array = data_array_from_data_dict_iterable((item,), filter_func=self.filter_func, converter_func=self.converter_func)
                self.data.append({data_deque_dict_names[0]:data_array, data_deque_dict_names[1]:item[data_deque_dict_names[1]], data_deque_dict_names[2]:item[data_deque_dict_names[2]], data_deque_dict_names[3]:item[data_deque_dict_names[3]]})
        return self

def convert_data_array(array, filter_func=None, converter_func=None):
    '''Filter and convert data array (numpy.ndarray)
    
    Parameters
    ----------
    array : numpy.array
        Raw data array.
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.
    
    Returns
    -------
    array of specified dimension (converter_func) and content (filter_func)    
    '''
#     if filter_func != None:
#         if not hasattr(filter_func, '__call__'):
#             raise ValueError('Filter is not callable')
    if filter_func:
        array = array[filter_func(array)]
#     if converter_func != None:
#         if not hasattr(converter_func, '__call__'):
#             raise ValueError('Converter is not callable')
    if converter_func:
        array = converter_func(array)
    return array

def data_array_from_data_dict_iterable(data_dict_iterable, clear_deque=False):
    '''Convert data dictionary iterable (e.g. data deque)
    
    Parameters
    ----------
    data_dict_iterable : iterable
        Iterable (e.g. list, deque, ...) where each element is a dict with following keys: "data", "timestamp_start", "timestamp_stop", "error"
    clear_deque : bool
        Clear deque when returning.
    
    Returns
    -------
    concatenated data array (numpy.ndarray)
    '''
    try:
        data_array = np.concatenate([item[data_deque_dict_names[0]] for item in data_dict_iterable])
    except ValueError:
        data_array = np.array([], dtype=np.dtype('>u4'))
    if clear_deque:
        data_dict_iterable.clear()
    return data_array
    
def data_dict_list_from_data_dict_iterable(data_dict_iterable, filter_func=None, converter_func=None, concatenate=False, clear_deque=False): # TODO: implement concatenate
    '''Convert data dictionary iterable (e.g. data deque)
    
    Parameters
    ----------
    data_dict_iterable : iterable
        Iterable (e.g. list, deque, ...) where each element is a dict with following keys: "data", "timestamp_start", "timestamp_stop", "error"
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.
    concatenate: bool
        Concatenate input arrays. If true, returns single dict.
    clear_deque : bool
        Clear deque when returning.
    
    Returns
    -------
    data dictionary list of the form [{"data":converted_data, "timestamp_start":ts_start, "timestamp_stop":ts_stop, "error":error}, {...}, ...]
    '''
    data_dict_list = []
    for item in data_dict_iterable:
        data_dict_list.append({data_deque_dict_names[0]:convert_data_array(item[data_deque_dict_names[0]], filter_func=filter_func, converter_func=converter_func), data_deque_dict_names[1]:item[data_deque_dict_names[1]], data_deque_dict_names[2]:item[data_deque_dict_names[2]], data_deque_dict_names[3]:item[data_deque_dict_names[3]]})
    if clear_deque:
        data_dict_iterable.clear()
    return data_dict_list

def is_data_from_channel(channel=4): # function factory
    '''Select data from channel
    
    Parameters:
    channel : int
        Channel number (4 is default channel on Single Chip Card)
    
    Returns:
    Function
    
    Usage:
    # 1
    is_data_from_channel_4 = is_data_from_channel(4)
    data_from_channel_4 = data_array[is_data_from_channel_4(data_array)]
    # 2
    filter_func = np.logical_and(is_data_record, is_data_from_channel(3))
    data_record_from_channel_3 = data_array[filter_func(data_array)]
    # 3
    is_raw_data_from_channel_3 = is_data_from_channel(3)(raw_data)
    
    Similar to:
    f_ch3 = functoools.partial(is_data_from_channel, channel=3)
    l_ch4 = lambda x: is_data_from_channel(x, channel=4)
    
    Note:
    Trigger data not included
    '''
    if channel>0:
        def f(value):
            return np.equal(np.right_shift(np.bitwise_and(value, 0x7F000000), 24), channel)
        f.__name__ = "is_data_from_channel_"+str(channel) # or use inspect module: inspect.stack()[0][3]
        return f
    else:
        raise ValueError('invalid channel number')
    
def logical_and(f1, f2): # function factory
    '''Logical and from functions.
    
    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.
        
    Returns
    -------
    Function
    
    Examples
    --------
    filter_func=logical_and(is_data_record,is_data_from_channel(4)) # new filter function
    filter_func(array) # array that has Data Records from channel 4
    '''
    def f(value):
        return np.logical_and(f1(value), f2(value))
    f.__name__ = f1.__name__+"_and_"+f2.__name__
    return f

def logical_or(f1, f2): # function factory
    '''Logical or from functions.
    
    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.
        
    Returns
    -------
    Function
    '''
    def f(value):
        return np.logical_or(f1(value), f2(value))
    f.__name__ = f1.__name__+"_or_"+f2.__name__
    return f

def logical_not(f): # function factory
    '''Logical not from functions.
    
    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.
        
    Returns
    -------
    Function
    '''
    def f(value):
        return np.logical_not(f(value))
    f.__name__ = "not_"+f.__name__
    return f

def logical_xor(f1, f2): # function factory
    '''Logical xor from functions.
    
    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.
        
    Returns
    -------
    Function
    '''
    def f(value):
        return np.logical_xor(f1(value), f2(value))
    f.__name__ = f1.__name__+"_xor_"+f2.__name__
    return f
    
def is_data_record(value):
    return np.logical_and(np.logical_and(np.less_equal(np.bitwise_and(value, 0x00FE0000), 0x00A00000), np.less_equal(np.bitwise_and(value, 0x0001FF00), 0x00015000)), np.logical_and(np.not_equal(np.bitwise_and(value, 0x00FE0000), 0x00000000), np.not_equal(np.bitwise_and(value, 0x0001FF00), 0x00000000)))

def is_data_header(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 15269888)
                    
def is_trigger_data(value):
    '''Select trigger data (trigger number)
    '''
    return np.equal(np.bitwise_and(value, 0x80000000), 0x80000000)

def get_col_row_tot_array_from_data_record_array(array):
    '''Convert raw data array to column, row, and ToT array
    
    Parameters
    ----------
    array : numpy.array
        Raw data array.
    
    Returns
    -------
    Tuple of arrays.
    '''
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
        #logging.warning('Array is empty')
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

def open_raw_data_file(filename, mode="w", title="", scan_parameters=[], **kwargs):
    '''Mimics pytables.open_file()/openFile()
    
    Returns:
    RawDataFile Object
    '''
    return RawDataFile(filename=filename, mode =mode, title=title, scan_parameters=scan_parameters, **kwargs)
            
class RawDataFile(object):
    '''Saving raw data file from data dictionary iterable (e.g. data deque)
    
    TODO: Python 3.x support for contextlib.ContextDecorator
    '''
    def __init__(self, filename, mode="w", title="", scan_parameters=[], **kwargs): # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created):
        self.filename = filename
        self.scan_parameters = scan_parameters
        self.raw_data_earray = None
        self.meta_data_table = None
        if self.scan_parameters:
            self.scan_param_table = None
        self.raw_data_file_h5 = None
        self.open(mode, title)
    
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False # do not hide exceptions
    
    def open(self, mode='w', title='', **kwargs):
        if os.path.splitext(self.filename)[1].strip().lower() != ".h5":
            self.filename = os.path.splitext(self.filename)[0]+".h5"
        if os.path.isfile(self.filename) and mode in ('r+', 'a'):
            logging.info('Appending raw data: %s' % self.filename)
        else:
            logging.info('Saving raw data: %s' % self.filename)

        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        self.raw_data_file_h5 = tb.openFile(self.filename, mode = mode, title = title, **kwargs)
        try:
            self.raw_data_earray = self.raw_data_file_h5.createEArray(self.raw_data_file_h5.root, name = 'raw_data', atom = tb.UIntAtom(), shape = (0,), title = 'raw_data', filters = filter_raw_data) # expectedrows = ???
        except tb.exceptions.NodeError:
            self.raw_data_earray = self.raw_data_file_h5.getNode(self.raw_data_file_h5.root, name = 'raw_data')
        try:
            self.meta_data_table = self.raw_data_file_h5.createTable(self.raw_data_file_h5.root, name = 'meta_data', description = MetaTable, title = 'meta_data', filters = filter_tables)
        except tb.exceptions.NodeError:
            self.meta_data_table = self.raw_data_file_h5.getNode(self.raw_data_file_h5.root, name = 'meta_data')
        if self.scan_parameters:
            try:
                scan_param_descr = dict([(key, tb.UInt32Col(pos=idx)) for idx, key in enumerate(self.scan_parameters)])
                self.scan_param_table = self.raw_data_file_h5.createTable(self.raw_data_file_h5.root, name = 'scan_parameters', description = scan_param_descr, title = 'scan_parameters', filters = filter_tables)
            except tb.exceptions.NodeError:
                self.scan_param_table = self.raw_data_file_h5.getNode(self.raw_data_file_h5.root, name = 'scan_parameters')
    
    def close(self):
        self.flush()
        logging.info('Closing raw data file: %s' % self.filename)
        self.raw_data_file_h5.close()
            
    def append(self, data_dict_iterable, scan_parameters={}, clear_deque=False, flush=True, **kwargs):
#         if not data_dict_iterable:
#             logging.warning('Iterable is empty')
        row_meta = self.meta_data_table.row
        if scan_parameters:
            row_scan_param = self.scan_param_table.row
        
        total_words_before = self.raw_data_earray.nrows
        
        def append_item(item):
            total_words = self.raw_data_earray.nrows
            raw_data = item[data_deque_dict_names[0]]
            len_raw_data = raw_data.shape[0]
            self.raw_data_earray.append(raw_data)
            row_meta['timestamp'] = item[data_deque_dict_names[1]] # TODO: support for timestamp_stop
            row_meta['error'] = item[data_deque_dict_names[3]]
            row_meta['length'] = len_raw_data
            row_meta['start_index'] = total_words
            total_words += len_raw_data
            row_meta['stop_index'] = total_words
            row_meta.append()
            if self.scan_parameters:
                for key, value in dict.iteritems(scan_parameters):
                    row_scan_param[key] = value
                row_scan_param.append()
        
#         if clear_deque:
#             while True:
#                 try:
#                     item = data_dict_iterable.popleft()
#                 except IndexError:
#                     break
#                 append_item(item)
# 
#         else:
        for item in data_dict_iterable:
            append_item(item)
            
        total_words_after = self.raw_data_earray.nrows
        if total_words_after==total_words_before:
            logging.info('Nothing to append: %s' % self.filename)
            
        if clear_deque:
            data_dict_iterable.clear()
            
        if flush:
            self.flush()
                
    def flush(self):
        self.raw_data_earray.flush()
        self.meta_data_table.flush()
        if self.scan_parameters:
            self.scan_param_table.flush()
        
            
def save_raw_data_from_data_dict_iterable(data_dict_iterable, filename, mode='a', title='', scan_parameters={}, **kwargs): # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created
    '''Writing raw data file from data dictionary iterable (e.g. data deque)
    
    If you need to write raw data once in a while this function may make it easy for you.
    '''
    with open_raw_data_file(filename, mode='a', title='', scan_parameters=list(dict.iterkeys(scan_parameters)), **kwargs) as raw_data_file:
        raw_data_file.append(data_dict_iterable, scan_parameters=scan_parameters, **kwargs)
