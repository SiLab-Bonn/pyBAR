import logging
from time import sleep, time
from threading import Thread, Event
from collections import deque
from Queue import Queue, Empty
import sys

from pybar.utils.utils import get_float_time


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
        self.readout_interval = 0.05
        self._moving_average_time_period = 10.0
        self._data_deque = deque()
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
        if self._is_running:
            raise RuntimeError('Readout already running: use stop() before start()')
        self._is_running = True
        logging.info('Starting FIFO readout...')
        self.callback = callback
        self.errback = errback
        if reset_rx:
            self.reset_rx()
        if reset_sram_fifo:
            self.reset_sram_fifo()
        else:
            fifo_size = self.dut['sram']['FIFO_SIZE']
            if fifo_size != 0:
                logging.warning('SRAM FIFO not empty when starting FIFO readout: size = %i' % fifo_size)
        self._words_per_read.clear()
        if clear_buffer:
            self._data_deque.clear()
        self.stop_readout.clear()
        self.force_stop.clear()
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
                if timeout:
                    raise StopTimeout('FIFO stop timeout after %0.1f second(s)' % timeout)
                else:
                    logging.error('FIFO stop timeout')
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
        if self.callback:
            self.worker_thread.join()
        self.callback = None
        self.errback = None
        logging.info('Stopped FIFO readout')

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
        time_wait = 0.0
        while not self.force_stop.wait(time_wait if time_wait >= 0.0 else 0.0):
            try:
                time_read = time()
                if no_data_timeout and curr_time + no_data_timeout < get_float_time():
                    raise NoDataTimeout('Received no data for %0.1f second(s)' % no_data_timeout)
                data = self.read_data()
            except Exception:
                no_data_timeout = None  # raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
                if self.stop_readout.is_set():
                    break
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
            finally:
                time_wait = self.readout_interval - (time() - time_read)
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
            except IndexError:
                self.stop_readout.wait(self.readout_interval)
            else:
                if data:
                    try:
                        self.callback(data)
                    except Exception:
                        self.errback(sys.exc_info())
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
            except Exception:
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
