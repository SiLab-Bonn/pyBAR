from time import sleep
import logging
import os.path
from threading import Thread, Event, RLock
import numpy as np
import tables as tb
from utils.utils import get_float_time
from analysis.RawDataConverter.data_struct import MetaTableV2 as MetaTable, generate_scan_parameter_description
from basil.utils.BitLogic import BitLogic
from collections import OrderedDict, deque
from Queue import Queue, Empty
import sys
from cgi import maxlen

data_iterable = ("data", "timestamp_start", "timestamp_stop", "error")


class RxSyncError(Exception):
    pass


class EightbTenbError(Exception):
    pass


class FifoError(Exception):
    pass


class NoDataTimeout(Exception):
    pass


class StopTimeout(Exception):
    pass


class DataReadout(object):
    def __init__(self, dut):
        self.dut = dut
        self.callback = None
        self.errback = None
        self.readout_thread = None
        self.worker_thread = None
        self.watchdog_thread = None
        self.readout_interval = 0.05
        self._moving_average_time_period = 10.0
        self._data_deque = deque()
        self._words_per_read = deque(maxlen=int(self._moving_average_time_period / self.readout_interval))
        self._result = Queue(maxsize=1)
        self._calculate = Event()
        self.stop_readout = Event()
        self.stop_timeout = Event()
        self.timestamp = None
        self.update_timestamp()
        self._is_running = False
        self.reset_rx()
        self.reset_sram_fifo()

    @property
    def is_running(self):
        return self._is_running

    @property
    def is_alive(self):
        if self.worker_thread:
            return self.worker_thread.is_alive()
        else:
            False

    @property
    def data(self):
        return self._data_deque

    def data_words_per_second(self):
        if self._result.full():
            self._result.get()
        self._calculate.set()
        try:
            result = self._result.get(timeout=2 * self.readout_interval)
        except Empty:
            self._calculate.clear()
            return None
        return result / float(self._moving_average_time_period)

    def start(self, callback=None, errback=None, reset_rx=False, reset_sram_fifo=False, clear_buffer=False, no_data_timeout=None):
        logging.info('Starting data readout...')
        self.callback = callback
        self.errback = errback
        if self._is_running:
            raise RuntimeError('Readout already running: use stop() before start()')
        self._is_running = True
        if reset_rx:
            self.reset_rx()
        if reset_sram_fifo:
            self.reset_sram_fifo()
        else:
            fifo_size = self.dut['sram']['FIFO_SIZE']
            if fifo_size != 0:
                logging.warning('SRAM FIFO not empty: size = %i' % fifo_size)
        self._words_per_read.clear()
        if clear_buffer:
            self._data_deque.clear()
        self.stop_readout.clear()
        self.stop_timeout.clear()
        if self.errback:
            self.watchdog_thread = Thread(target=self.watchdog, name='WatchdogThread')
            self.watchdog_thread.daemon = True
            self.watchdog_thread.start()
        if self.callback:
            self.worker_thread = Thread(target=self.worker, name='WorkerThread')
            self.worker_thread.daemon = True
            self.worker_thread.start()
        self.readout_thread = Thread(target=self.readout, name='ReadoutThread', kwargs={'no_data_timeout': no_data_timeout})
        self.readout_thread.daemon = True
        self.readout_thread.start()

    def stop(self, timeout=10.0):
        if not self._is_running:
            raise RuntimeError('Readout not running: use start() before stop()')
        self._is_running = False
        self.stop_readout.set()
        try:
            self.readout_thread.join(timeout=timeout)
            if self.readout_thread.is_alive():
                raise StopTimeout('Reached data timeout after %0.2f second(s)' % timeout)
        except StopTimeout as e:
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
        finally:
            self.stop_timeout.set()
        if self.errback:
            self.watchdog_thread.join()
        if self.callback:
            self.worker_thread.join()
        self.callback = None
        self.errback = None
        logging.info('Stopped data readout')

    def print_readout_status(self):
        sync_status = self.get_rx_sync_status()
        discard_count = self.get_rx_fifo_discard_count()
        error_count = self.get_rx_8b10b_error_count()
        logging.info('Data queue size: %d' % len(self._data_deque))
        logging.info('SRAM FIFO size: %d' % self.dut['sram']['FIFO_SIZE'])
        logging.info('Channel:                     %s', " | ".join([('CH%d' % channel).rjust(3) for channel in range(1, len(sync_status) + 1, 1)]))
        logging.info('RX sync:                     %s', " | ".join(["YES".rjust(3) if status is True else "NO".rjust(3) for status in sync_status]))
        logging.info('RX FIFO discard counter:     %s', " | ".join([repr(count).rjust(3) for count in discard_count]))
        logging.info('RX FIFO 8b10b error counter: %s', " | ".join([repr(count).rjust(3) for count in error_count]))
        if not any(self.get_rx_sync_status()) or any(discard_count) or any(error_count):
            logging.warning('RX errors detected')

    def readout(self, no_data_timeout=None):
        '''Readout thread continuously reading SRAM.

        Readout thread, which uses read_data() and appends data to self._data_deque (collection.deque).
        '''
        logging.debug('Starting %s' % (self.readout_thread.name,))
        curr_time = get_float_time()
        while not self.stop_timeout.wait(self.readout_interval):
            try:
                if no_data_timeout and curr_time + no_data_timeout < get_float_time():
                    raise NoDataTimeout('Received no data for %0.2f second(s)' % no_data_timeout)
                data = self.read_data()
            except Exception as e:
                no_data_timeout = None  # raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
            else:
                data_words = data.shape[0]
                if data_words > 0:
                    last_time, curr_time = self.update_timestamp()
                    status = 0
                    self._data_deque.append((data, last_time, curr_time, status))
                    self._words_per_read.append(data_words)
                elif self.stop_readout.is_set():
                    break
                else:
                    self._words_per_read.append(0)
            if self._calculate.is_set():
                self._calculate.clear()
                self._result.put(sum(self._words_per_read))
        if self.callback:
            self._data_deque.append(None)  # empty tuple
        logging.debug('Stopped %s' % (self.readout_thread.name,))

    def worker(self):
        '''Worker thread continuously calling callback function when data is available.
        '''
        logging.debug('Starting %s' % (self.worker_thread.name,))
        while True:
            try:
                data = self._data_deque.popleft()
            except IndexError as e:
                self.stop_readout.wait(self.readout_interval)
            else:
                if data:
                    self.callback(data)
                else:
                    break

        logging.debug('Stopped %s' % (self.worker_thread.name,))

    def watchdog(self):
        logging.debug('Starting %s' % (self.watchdog_thread.name,))
        while True:
            try:
                if not any(self.get_rx_sync_status()):
                    raise RxSyncError('No RX sync')
                if any(self.get_rx_8b10b_error_count()):
                    raise EightbTenbError('RX 8b10b error(s) detected')
                if any(self.get_rx_fifo_discard_count()):
                    raise FifoError('RX FIFO discard error(s) detected')
            except Exception as e:
                    self.errback(sys.exc_info())
            if self.stop_readout.wait(self.readout_interval * 10):
                break
        logging.debug('Stopped %s' % (self.watchdog_thread.name,))

    def read_data(self):
        '''Read SRAM and return data array

        Can be used without threading.

        Returns
        -------
        data : list
            A list of SRAM data words.
        '''
        return self.dut['sram'].get_data()

    def update_timestamp(self):
        curr_time = get_float_time()
        last_time = self.timestamp
        self.timestamp = curr_time
        return last_time, curr_time

    def read_status(self):
        raise NotImplementedError()

    def reset_sram_fifo(self):
        fifo_size = self.dut['sram']['FIFO_SIZE']
        logging.info('Resetting SRAM FIFO: size = %i' % fifo_size)
        self.update_timestamp()
        self.dut['sram']['RESET']
        sleep(0.2)  # sleep here for a while
        fifo_size = self.dut['sram']['FIFO_SIZE']
        if fifo_size != 0:
            logging.warning('SRAM FIFO not empty after reset: size = %i' % fifo_size)

    def reset_rx(self, channels=None):
        logging.info('Resetting RX')
        if channels:
            filter(lambda channel: self.dut[channel]['SOFT_RESET'], channels)
        else:
            if self.dut.name == 'usbpix':
                filter(lambda channel: self.dut[channel]['SOFT_RESET'], ['rx_1', 'rx_2', 'rx_3', 'rx_4'])
            elif self.dut.name == 'usbpix_gpac':
                filter(lambda channel: self.dut[channel]['SOFT_RESET'], ['rx_fe'])
        sleep(0.1)  # sleep here for a while

    def get_rx_sync_status(self, channels=None):
        if channels:
            return map(lambda channel: True if self.dut[channel]['READY'] else False, channels)
        else:
            if self.dut.name == 'usbpix':
                return map(lambda channel: True if self.dut[channel]['READY'] else False, ['rx_1', 'rx_2', 'rx_3', 'rx_4'])
            elif self.dut.name == 'usbpix_gpac':
                return map(lambda channel: True if self.dut[channel]['READY'] else False, ['rx_fe'])

    def get_rx_8b10b_error_count(self, channels=None):
        if channels:
            return map(lambda channel: self.dut[channel]['DECODER_ERROR_COUNTER'], channels)
        else:
            if self.dut.name == 'usbpix':
                return map(lambda channel: self.dut[channel]['DECODER_ERROR_COUNTER'], ['rx_1', 'rx_2', 'rx_3', 'rx_4'])
            elif self.dut.name == 'usbpix_gpac':
                return map(lambda channel: self.dut[channel]['DECODER_ERROR_COUNTER'], ['rx_fe'])

    def get_rx_fifo_discard_count(self, channels=None):
        if channels:
            return map(lambda channel: self.dut[channel]['LOST_DATA_COUNTER'], channels)
        else:
            if self.dut.name == 'usbpix':
                return map(lambda channel: self.dut[channel]['LOST_DATA_COUNTER'], ['rx_1', 'rx_2', 'rx_3', 'rx_4'])
            elif self.dut.name == 'usbpix_gpac':
                return map(lambda channel: self.dut[channel]['LOST_DATA_COUNTER'], ['rx_fe'])


def convert_data_array(array, filter_func=None, converter_func=None):  # TODO: add copy parameter, otherwise in-place
    '''Filter and convert raw data numpy array (numpy.ndarray)

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
    data_array : numpy.array
        Data numpy array of specified dimension (converter_func) and content (filter_func)
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


def convert_data_iterable(data_iterable, filter_func=None, converter_func=None):  # TODO: add concatenate parameter
    '''Convert raw data in data iterable.

    Parameters
    ----------
    data_iterable : iterable
        Iterable where each element is a tuple with following content: (raw data, timestamp_start, timestamp_stop, status).
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.

    Returns
    -------
    data_list : list
        Data list of the form [(converted data, timestamp_start, timestamp_stop, status), (...), ...]
    '''
    data_list = []
    for item in data_iterable:
        data_list.append((convert_data_array(item[0], filter_func=filter_func, converter_func=converter_func), item[1], item[2], item[3]))
    return data_list


def data_array_from_data_iterable(data_iterable):
    '''Convert data iterable to raw data numpy array.

    Parameters
    ----------
    data_iterable : iterable
        Iterable where each element is a tuple with following content: (raw data, timestamp_start, timestamp_stop, status).

    Returns
    -------
    data_array : numpy.array
        concatenated data array
    '''
    data_array = np.concatenate([item[0] for item in data_iterable])
    return data_array


def is_data_from_channel(channel=4):  # function factory
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
    filter_func = logical_and(is_data_record, is_data_from_channel(3))
    data_record_from_channel_3 = data_array[filter_func(data_array)]
    # 3
    is_raw_data_from_channel_3 = is_data_from_channel(3)(raw_data)

    Similar to:
    f_ch3 = functoools.partial(is_data_from_channel, channel=3)
    l_ch4 = lambda x: is_data_from_channel(x, channel=4)

    Note:
    Trigger data not included
    '''
    if channel > 0 and channel < 5:
        def f(value):
            return np.equal(np.right_shift(np.bitwise_and(value, 0x7F000000), 24), channel)
        f.__name__ = "is_data_from_channel_" + str(channel)  # or use inspect module: inspect.stack()[0][3]
        return f
    else:
        raise ValueError('Invalid channel number')


def logical_and(f1, f2):  # function factory
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
    filter_func=logical_and(is_data_record, is_data_from_channel(4))  # new filter function
    filter_func(array) # array that has Data Records from channel 4
    '''
    def f(value):
        return np.logical_and(f1(value), f2(value))
    f.__name__ = f1.__name__ + "_and_" + f2.__name__
    return f


def logical_or(f1, f2):  # function factory
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
    f.__name__ = f1.__name__ + "_or_" + f2.__name__
    return f


def logical_not(f):  # function factory
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
    f.__name__ = "not_" + f.__name__
    return f


def logical_xor(f1, f2):  # function factory
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
    f.__name__ = f1.__name__ + "_xor_" + f2.__name__
    return f


def is_fe_record(value):
    return not is_trigger_data(value) and not is_status_data(value)


def is_data_header(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111010010000000000000000)


def is_address_record(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111010100000000000000000)


def is_value_record(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111011000000000000000000)


def is_service_record(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111011110000000000000000)


def is_data_record(value):
    return np.logical_and(np.logical_and(np.less_equal(np.bitwise_and(value, 0x00FE0000), 0x00A00000), np.less_equal(np.bitwise_and(value, 0x0001FF00), 0x00015000)), np.logical_and(np.not_equal(np.bitwise_and(value, 0x00FE0000), 0x00000000), np.not_equal(np.bitwise_and(value, 0x0001FF00), 0x00000000)))


def is_trigger_word(value):
    return np.equal(np.bitwise_and(value, 0x80000000), 0b10000000000000000000000000000000)


def is_tdc_word(value):
    return np.equal(np.bitwise_and(value, 0x40000000), 0b01000000000000000000000000000000)


def is_status_data(value):
    '''Select status data
    '''
    return np.equal(np.bitwise_and(value, 0xFF000000), 0x00000000)


def is_trigger_data(value):
    '''Select trigger data (trigger number)
    '''
    return np.equal(np.bitwise_and(value, 0xFF000000), 0x80000000)


def is_tdc_data(value):
    '''Select tdc data
    '''
    return np.equal(np.bitwise_and(value, 0xF0000000), 0x40000000)


def get_address_record_address(value):
    '''Returns the address in the address record
    '''
    return np.bitwise_and(value, 0x0000EFFF)


def get_address_record_type(value):
    '''Returns the type in the address record
    '''
    return np.right_shift(np.bitwise_and(value, 0x00008000), 14)


def get_value_record(value):
    '''Returns the value in the value record
    '''
    return np.bitwise_and(value, 0x0000FFFF)

# def def get_col_row_tot_array_from_data_record_array(max_tot=14):


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
    col_row_tot_array = np.vstack((col_row_tot_1_array.T, col_row_tot_2_array.T)).reshape((3, -1), order='F').T  # http://stackoverflow.com/questions/5347065/interweaving-two-numpy-arrays
#     print col_row_tot_array, col_row_tot_array.shape, col_row_tot_array.dtype
    # remove ToT > 14 (late hit, no hit) from array, remove row > 336 in case we saw hit in row 336 (no double hit possible)
    try:
        col_row_tot_array_filtered = col_row_tot_array[col_row_tot_array[:, 2] < 14]  # [np.logical_and(col_row_tot_array[:,2]<14, col_row_tot_array[:,1]<=336)]
#         print col_row_tot_array_filtered, col_row_tot_array_filtered.shape, col_row_tot_array_filtered.dtype
    except IndexError:
        # logging.warning('Array is empty')
        return np.array([], dtype=np.dtype('>u4')), np.array([], dtype=np.dtype('>u4')), np.array([], dtype=np.dtype('>u4'))
    return col_row_tot_array_filtered[:, 0], col_row_tot_array_filtered[:, 1], col_row_tot_array_filtered[:, 2]  # column, row, ToT


def get_col_row_array_from_data_record_array(array):
    col, row, _ = get_col_row_tot_array_from_data_record_array(array)
    return col, row


def get_row_col_array_from_data_record_array(array):
    col, row, _ = get_col_row_tot_array_from_data_record_array(array)
    return row, col


def get_tot_array_from_data_record_array(array):
    _, _, tot = get_col_row_tot_array_from_data_record_array(array)
    return tot


def get_occupancy_mask_from_data_record_array(array, occupancy):
    pass  # TODO:


def get_col_row_iterator_from_data_records(array):  # generator
    for item in np.nditer(array):  # , flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.right_shift(np.bitwise_and(item, 0x0001FF00), 8)
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1)


def get_row_col_iterator_from_data_records(array):  # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), np.right_shift(np.bitwise_and(item, 0x00FE0000), 17)
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1), np.right_shift(np.bitwise_and(item, 0x00FE0000), 17)


def get_col_row_tot_iterator_from_data_records(array):  # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), np.right_shift(np.bitwise_and(item, 0x000000F0), 4)  # col, row, ToT1
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1), np.bitwise_and(item, 0x0000000F)  # col, row+1, ToT2


def get_tot_iterator_from_data_records(array):  # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x000000F0), 4)  # ToT1
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.bitwise_and(item, 0x0000000F)  # ToT2


def open_raw_data_file(filename, mode="a", title="", scan_parameters=None, **kwargs):
    '''Mimics pytables.open_file()/openFile()

    Returns:
    RawDataFile Object

    Examples:
    with open_raw_data_file(filename = self.scan_data_filename, title=self.scan_id, scan_parameters=[scan_parameter]) as raw_data_file:
        # do something here
        raw_data_file.append(self.readout.data, scan_parameters={scan_parameter:scan_parameter_value})
    '''
    return RawDataFile(filename=filename, mode=mode, title=title, scan_parameters=scan_parameters, **kwargs)


class RawDataFile(object):
    '''Raw data file object. Saving data queue to HDF5 file.
    '''
    def __init__(self, filename, mode="a", title="", scan_parameters=None, **kwargs):  # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created):
        self.lock = RLock()
        self.filename = filename
        if scan_parameters:
            self.scan_parameters = scan_parameters
        else:
            self.scan_parameters = {}
        self.raw_data_earray = None
        self.meta_data_table = None
        self.scan_param_table = None
        self.raw_data_file_h5 = None
        self.open(mode, title, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False  # do not hide exceptions

    def open(self, mode='a', title='', **kwargs):
        if os.path.splitext(self.filename)[1].strip().lower() != ".h5":
            self.filename = os.path.splitext(self.filename)[0] + ".h5"
        if os.path.isfile(self.filename) and mode in ('r+', 'a'):
            logging.info('Opening existing raw data file: %s' % self.filename)
        else:
            logging.info('Opening new raw data file: %s' % self.filename)

        filter_raw_data = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
        self.raw_data_file_h5 = tb.openFile(self.filename, mode=mode, title=title, **kwargs)
        try:
            self.raw_data_earray = self.raw_data_file_h5.createEArray(self.raw_data_file_h5.root, name='raw_data', atom=tb.UIntAtom(), shape=(0,), title='raw_data', filters=filter_raw_data)  # expectedrows = ???
        except tb.exceptions.NodeError:
            self.raw_data_earray = self.raw_data_file_h5.getNode(self.raw_data_file_h5.root, name='raw_data')
        try:
            self.meta_data_table = self.raw_data_file_h5.createTable(self.raw_data_file_h5.root, name='meta_data', description=MetaTable, title='meta_data', filters=filter_tables)
        except tb.exceptions.NodeError:
            self.meta_data_table = self.raw_data_file_h5.getNode(self.raw_data_file_h5.root, name='meta_data')
        if self.scan_parameters:
            try:
                scan_param_descr = generate_scan_parameter_description(self.scan_parameters)
                self.scan_param_table = self.raw_data_file_h5.createTable(self.raw_data_file_h5.root, name='scan_parameters', description=scan_param_descr, title='scan_parameters', filters=filter_tables)
            except tb.exceptions.NodeError:
                self.scan_param_table = self.raw_data_file_h5.getNode(self.raw_data_file_h5.root, name='scan_parameters')

    def close(self):
        with self.lock:
            self.flush()
            logging.info('Closing raw data file: %s' % self.filename)
            self.raw_data_file_h5.close()

    def append_item(self, data_tuple, scan_parameters=None, flush=True):
        with self.lock:
            total_words = self.raw_data_earray.nrows
            raw_data = data_tuple[0]
            len_raw_data = raw_data.shape[0]
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
                for key in self.scan_parameters.iterkeys():
                    self.scan_param_table.row[key] = scan_parameters[key]
                self.scan_param_table.row.append()
            elif scan_parameters:
                raise ValueError('Unknown scan parameters: %s' % ', '.join(scan_parameters.iterkeys()))
            if flush:
                self.flush()

    def append(self, data_iterable, scan_parameters=None, flush=True):
        with self.lock:
            for data_tuple in data_iterable:
                self.append_item(data_tuple, scan_parameters, flush=False)
            if flush:
                self.flush()

    def flush(self):
        with self.lock:
            self.raw_data_earray.flush()
            self.meta_data_table.flush()
            if self.scan_parameters:
                self.scan_param_table.flush()


def save_raw_data_from_data_queue(data_queue, filename, mode='a', title='', scan_parameters={}, **kwargs):  # mode="r+" to append data, raw_data_file_h5 must exist, "w" to overwrite raw_data_file_h5, "a" to append data, if raw_data_file_h5 does not exist it is created
    '''Writing raw data file from data queue

    If you need to write raw data once in a while this function may make it easy for you.
    '''
    with open_raw_data_file(filename, mode='a', title='', scan_parameters=list(dict.iterkeys(scan_parameters)), **kwargs) as raw_data_file:
        raw_data_file.append(data_queue, scan_parameters=scan_parameters, **kwargs)


class FEI4Record(object):
    """Record Object

    """
    def __init__(self, data_word, chip_flavor):
        self.record_rawdata = int(data_word)
        self.record_dict = OrderedDict()
        if not (self.record_rawdata & 0xF0000000):  # FE data
            self.record_dict.update([('channel', (self.record_rawdata & 0x0F000000) >> 24)])
            self.chip_flavor = str(chip_flavor).lower()
            self.chip_flavors = ['fei4a', 'fei4b']
            if self.chip_flavor not in self.chip_flavors:
                raise KeyError('Chip flavor is not of type {}'.format(', '.join('\'' + flav + '\'' for flav in self.chip_flavors)))
            self.record_word = BitLogic.from_value(value=self.record_rawdata, size=28)
            if is_data_header(self.record_rawdata):
                self.record_type = "DH"
                if self.chip_flavor == "fei4a":
                    self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('flag', self.record_word[15:15].tovalue()), ('lvl1id', self.record_word[14:8].tovalue()), ('bcid', self.record_word[7:0].tovalue())])
                elif self.chip_flavor == "fei4b":
                    self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('flag', self.record_word[15:15].tovalue()), ('lvl1id', self.record_word[14:10].tovalue()), ('bcid', self.record_word[9:0].tovalue())])
            elif is_address_record(self.record_rawdata):
                self.record_type = "AR"
                self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('type', self.record_word[15:15].tovalue()), ('address', self.record_word[14:0].tovalue())])
            elif is_value_record(self.record_rawdata):
                self.record_type = "VR"
                self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('value', self.record_word[15:0].tovalue())])
            elif is_service_record(self.record_rawdata):
                self.record_type = "SR"
                if self.chip_flavor == "fei4a":
                    self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('counter', self.record_word[9:0].tovalue())])
                elif self.chip_flavor == "fei4b":
                    if self.record_word[15:10].tovalue() == 14:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('lvl1id[11:5]', self.record_word[9:3].tovalue()), ('bcid[12:10]', self.record_word[2:0].tovalue())])
                    elif self.record_word[15:10].tovalue() == 15:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('skipped', self.record_word[9:0].tovalue())])
                    elif self.record_word[15:10].tovalue() == 16:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('truncation flag', self.record_word[9:9].tovalue()), ('truncation counter', self.record_word[8:4].tovalue()), ('l1req', self.record_word[3:0].tovalue())])
                    else:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('counter', self.record_word[9:0].tovalue())])
            elif is_data_record(self.record_rawdata):
                self.record_type = "DR"
                self.record_dict.update([('column', self.record_word[23:17].tovalue()), ('row', self.record_word[16:8].tovalue()), ('tot1', self.record_word[7:4].tovalue()), ('tot2', self.record_word[3:0].tovalue())])
            else:
                self.record_type = "UNKNOWN FE WORD"
                self.record_dict.update([('word', self.record_word.tovalue())])
    #             raise ValueError('Unknown data word: ' + str(self.record_word.tovalue()))
        else:
            self.record_type = "OTHER DATA WORD"
            self.record_dict.update([('word', self.record_word.tovalue())])

    def __len__(self):
        return len(self.record_dict)

    def __getitem__(self, key):
        if not (isinstance(key, (int, long)) or isinstance(key, basestring)):
            raise TypeError()
        try:
            return self.record_dict[key.lower()]
        except TypeError:
            return self.record_dict[self.record_dict.iterkeys()[int(key)]]

    def next(self):
        return self.record_dict.iteritems().next()

    def __iter__(self):
        return self.record_dict.iteritems()

    def __eq__(self, other):
        try:
            return self.record_type.lower() == other.lower()
        except:
            try:
                return self.record_type == other.record_type
            except:
                return False

    def __str__(self):
        return self.record_type + ' {}'.format(' '.join(key + ':' + str(val) for key, val in self.record_dict.iteritems()))

    def __repr__(self):
        return repr(self.__str__())
