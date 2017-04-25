import logging
from time import sleep, time
from threading import Thread, Event
from collections import deque
from Queue import Queue, Empty
import sys

import numpy as np

from pybar.utils.utils import get_float_time
from pybar.daq.readout_utils import is_fe_word, is_data_record, is_data_header, logical_or, logical_and, convert_data_iterable


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


class FifoReadout(object):
    def __init__(self, dut):
        self.dut = dut
        self.callback = None
        self.errback = None
        self.readout_thread = None
        self.worker_thread = None
        self.watchdog_thread = None
        self.fill_buffer = False
        self.filter_func = None
        self.converter_func = None
        self.enabled_fe_channels = None
        self.enabled_m26_channels = None
        self.readout_interval = 0.05
        self._moving_average_time_period = 10.0
        self._data_deque = deque()
        self._data_buffer = deque()
        self._words_per_read = deque(maxlen=int(self._moving_average_time_period / self.readout_interval))
        self._result = Queue(maxsize=1)
        self._calculate = Event()
        self.stop_readout = Event()
        self.force_stop = Event()
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
        if self.fill_buffer:
            return self._data_buffer
        else:
            logging.warning('Data requested but software data buffer not active')

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

    def start(self, callback=None, errback=None, reset_rx=False, reset_sram_fifo=False, clear_buffer=False, fill_buffer=False, no_data_timeout=None, filter_func=None, converter_func=None, enabled_fe_channels=None, enabled_m26_channels=None):
        self.filter_func = filter_func
        self.converter_func = converter_func
        self.enabled_fe_channels = enabled_fe_channels
        self.enabled_m26_channels = enabled_m26_channels
        if self._is_running:
            raise RuntimeError('Readout already running: use stop() before start()')
        self._is_running = True
        logging.info('Starting FIFO readout...')
        self.callback = callback
        self.errback = errback
        self.fill_buffer = fill_buffer
        if reset_rx:
            self.reset_rx()
        if reset_sram_fifo:
            self.reset_sram_fifo()
        else:
            fifo_size = self.dut['SRAM']['FIFO_SIZE']
            raw_data = self.read_data()
            dh_dr_select = logical_and(is_fe_word, logical_or(is_data_record, is_data_header))
            if np.count_nonzero(dh_dr_select(raw_data)) != 0:
                logging.warning('SRAM FIFO containing events when starting FIFO readout: FIFO_SIZE = %i', fifo_size)
        self._words_per_read.clear()
        if clear_buffer:
            self._data_deque.clear()
            self._data_buffer.clear()
        self.stop_readout.clear()
        self.force_stop.clear()
        if self.errback:
            self.watchdog_thread = Thread(target=self.watchdog, name='WatchdogThread')
            self.watchdog_thread.daemon = True
            self.watchdog_thread.start()
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
                if timeout:
                    raise StopTimeout('FIFO stop timeout after %0.1f second(s)' % timeout)
                else:
                    logging.warning('FIFO stop timeout')
        except StopTimeout as e:
            self.force_stop.set()
            if self.errback:
                self.errback(sys.exc_info())
            else:
                logging.error(e)
        if self.readout_thread.is_alive():
            self.readout_thread.join()
        if self.errback:
            self.watchdog_thread.join()
        self.worker_thread.join()
        self.callback = None
        self.errback = None
        logging.info('Stopped FIFO readout')

    def print_readout_status(self):
        logging.info('Data queue size: %d', len(self._data_deque))
        logging.info('SRAM FIFO size: %d', self.dut['SRAM']['FIFO_SIZE'])
        # FEI4
        enable_status = self.get_rx_enable_status()
        sync_status = self.get_rx_sync_status()
        discard_count = self.get_rx_fifo_discard_count()
        error_count = self.get_rx_8b10b_error_count(channels=None)
        if self.dut.get_modules('fei4_rx'):
            logging.info('FEI4 Channel:                     %s', " | ".join([channel.name.rjust(3) for channel in self.dut.get_modules('fei4_rx')]))
            logging.info('FEI4 RX enable:                   %s', " | ".join(["YES".rjust(3) if status is True else "NO".rjust(3) for status in enable_status]))
            logging.info('FEI4 RX sync:                     %s', " | ".join(["YES".rjust(3) if status is True else "NO".rjust(3) for status in sync_status]))
            logging.info('FEI4 RX FIFO discard counter:     %s', " | ".join([repr(count).rjust(3) for count in discard_count]))
            logging.info('FEI4 RX FIFO 8b10b error counter: %s', " | ".join([repr(count).rjust(3) for count in error_count]))
        if not any(sync_status) or any(discard_count) or any(error_count):
            logging.warning('FEI4 RX errors detected')
        # Mimosa26
        m26_discard_count = self.get_m26_rx_fifo_discard_count(channels=None)
        if self.dut.get_modules('m26_rx'):
            logging.info('M26 Channel:                 %s', " | ".join([channel.name.rjust(3) for channel in self.dut.get_modules('m26_rx')]))
            logging.info('M26 RX FIFO discard counter: %s', " | ".join([repr(count).rjust(7) for count in m26_discard_count]))
        if any(m26_discard_count):
            logging.warning('M26 RX errors detected')

    def readout(self, no_data_timeout=None):
        '''Readout thread continuously reading SRAM.

        Readout thread, which uses read_data() and appends data to self._data_deque (collection.deque).
        '''
        logging.debug('Starting %s', self.readout_thread.name)
        curr_time = get_float_time()
        time_wait = 0.0
        while not self.force_stop.wait(time_wait if time_wait >= 0.0 else 0.0):
            try:
                time_read = time()
                if no_data_timeout and curr_time + no_data_timeout < get_float_time():
                    raise NoDataTimeout('Received no data for %0.1f second(s)' % no_data_timeout)
                raw_data = self.read_data()
            except Exception:
                no_data_timeout = None  # raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
                if self.stop_readout.is_set():
                    break
            else:
                n_data_words = raw_data.shape[0]
                if n_data_words > 0:
                    last_time, curr_time = self.update_timestamp()
                    status = 0
                    self._data_deque.append((raw_data, last_time, curr_time, status))
                    self._words_per_read.append(n_data_words)
                elif self.stop_readout.is_set():
                    break
                else:
                    self._words_per_read.append(0)
            finally:
                time_wait = self.readout_interval - (time() - time_read)
            if self._calculate.is_set():
                self._calculate.clear()
                self._result.put(sum(self._words_per_read))
        self._data_deque.append(None)  # last item, None will stop worker
        logging.debug('Stopped %s', self.readout_thread.name)

    def worker(self):
        '''Worker thread continuously calling callback function when data is available.
        '''
        logging.debug('Starting %s', self.worker_thread.name)
        while True:
            try:
                data_tuple = self._data_deque.popleft()
            except IndexError:
                self.stop_readout.wait(self.readout_interval)  # sleep a little bit, reducing CPU usage
            else:
                if data_tuple is None:  # if None then exit
                    break
                else:
                    # filter and do the conversion
                    converted_data_tuple = convert_data_iterable((data_tuple,), filter_func=self.filter_func, converter_func=self.converter_func)[0]
                    if self.callback:
                        try:
                            self.callback(converted_data_tuple)
                        except Exception:
                            self.errback(sys.exc_info())
                    if self.fill_buffer:
                        self._data_buffer.append(converted_data_tuple)

        logging.debug('Stopped %s', self.worker_thread.name)

    def watchdog(self):
        logging.debug('Starting %s', self.watchdog_thread.name)
        while True:
            try:
                if not all(self.get_rx_sync_status(channels=self.enabled_fe_channels)):
                    raise RxSyncError('FEI4 RX sync error')
                if any(self.get_rx_8b10b_error_count(channels=self.enabled_fe_channels)):
                    raise EightbTenbError('FEI4 RX 8b10b error(s) detected')
                if any(self.get_rx_fifo_discard_count(channels=self.enabled_fe_channels)):
                    raise FifoError('FEI4 RX FIFO discard error(s) detected')
                if any(self.get_m26_rx_fifo_discard_count(channels=self.enabled_m26_channels)):
                    raise FifoError('M26 RX FIFO discard error(s) detected')
            except Exception:
                self.errback(sys.exc_info())
            if self.stop_readout.wait(self.readout_interval * 10):
                break
        logging.debug('Stopped %s', self.watchdog_thread.name)

    def read_data(self):
        '''Read SRAM and return data array

        Can be used without threading.

        Returns
        -------
        data : list
            A list of SRAM data words.
        '''
        return self.dut['SRAM'].get_data()

    def update_timestamp(self):
        curr_time = get_float_time()
        last_time = self.timestamp
        self.timestamp = curr_time
        return last_time, curr_time

    def read_status(self):
        raise NotImplementedError()

    def reset_sram_fifo(self):
        fifo_size = self.dut['SRAM']['FIFO_SIZE']
        logging.info('Resetting SRAM FIFO: size = %i', fifo_size)
        self.update_timestamp()
        self.dut['SRAM']['RESET']
        sleep(0.2)  # sleep here for a while
        fifo_size = self.dut['SRAM']['FIFO_SIZE']
        if fifo_size != 0:
            logging.warning('FIFO not empty after reset: size = %i', fifo_size)

    def reset_rx(self, channels=None):
        logging.info('Resetting RX')
        if channels:
            filter(lambda channel: self.dut[channel].RX_RESET, channels)
        else:
            filter(lambda channel: channel.RX_RESET, self.dut.get_modules('fei4_rx'))
        sleep(0.1)  # sleep here for a while

    def get_rx_enable_status(self, channels=None):
        if channels:
            return map(lambda channel: True if self.dut[channel].ENABLE_RX else False, channels)
        else:
            return map(lambda channel: True if channel.ENABLE_RX else False, self.dut.get_modules('fei4_rx'))

    def get_rx_sync_status(self, channels=None):
        if channels:
            return map(lambda channel: True if self.dut[channel].READY else False, channels)
        else:
            return map(lambda channel: True if channel.READY else False, self.dut.get_modules('fei4_rx'))

    def get_rx_8b10b_error_count(self, channels=None):
        if channels:
            return map(lambda channel: self.dut[channel].DECODER_ERROR_COUNTER, channels)
        else:
            return map(lambda channel: channel.DECODER_ERROR_COUNTER, self.dut.get_modules('fei4_rx'))

    def get_rx_fifo_discard_count(self, channels=None):
        if channels:
            return map(lambda channel: self.dut[channel].LOST_DATA_COUNTER, channels)
        else:
            return map(lambda channel: channel.LOST_DATA_COUNTER, self.dut.get_modules('fei4_rx'))

    def get_m26_rx_fifo_discard_count(self, channels=None):
        if channels:
            return map(lambda channel: self.dut[channel].LOST_COUNT, channels)
        else:
            return map(lambda channel: channel.LOST_COUNT, self.dut.get_modules('m26_rx'))
            