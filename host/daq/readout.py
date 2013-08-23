import struct
import itertools
import time
from threading import Thread, Event
from Queue import Queue
#from multiprocessing import Process as Thread
#from multiprocessing import Event
#from multiprocessing import Queue

from utils.utils import get_float_time

from SiLibUSB import SiUSBDevice

class Readout(object):
    def __init__(self, device, data_filter = None):
        if isinstance(device, SiUSBDevice):
            self.device = device
        else:
            raise ValueError('Device object is not compatible')
        if data_filter != None:
            if hasattr(data_filter, '__call__'):
                self.data_filter = data_filter
            else:
                raise ValueError('Filter object is not callable')
        else:
            self.data_filter = self.no_filter
        #self.filtered_data_words = None
        #self.data_words = None
        self.worker_thread = None
        self.data_queue = Queue()
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        self.readout_interval = 0.05
    
    def start(self):
        self.data_queue.empty()
        self.stop_thread_event.clear()
        self.worker_thread = Thread(target=self.worker)
        self.worker_thread.start()
    
    def stop(self, wait_for_data_timeout = 10):
        if wait_for_data_timeout > 0:
            wait_timeout_event = Event()
            wait_timeout_event.clear()
                
            def set_timeout_event(timeout_event, timeout):
                timeout_event.wait(timeout)
                timeout_event.set()
            
            timeout_thread = Thread(target=set_timeout_event, args=[wait_timeout_event, wait_for_data_timeout])
            timeout_thread.start()
            
            fifo_size = self.get_sram_fifo_size()
            old_fifo_size = -1
            while not wait_timeout_event.wait(1.5*self.readout_interval) and (old_fifo_size != fifo_size or fifo_size != 0):
                print fifo_size, old_fifo_size
                old_fifo_size = fifo_size
                fifo_size = self.get_sram_fifo_size()
            print "join"
            wait_timeout_event.set()
            timeout_thread.join()
            print "end of join"
        self.stop_thread_event.set()
        if self.worker_thread != None:
            self.worker_thread.join()
            self.worker_thread = None
        print 'Data queue size:', self.data_queue.qsize()
        print 'SRAM FIFO size:', self.get_sram_fifo_size()
        print 'RX FIFO discard counter:', self.get_rx_fifo_discard_count()
    
    def worker(self):
        '''Reading thread to continuously reading SRAM
        
        Worker thread function uses read_once()
        ''' 
        while not self.stop_thread_event.wait(self.readout_interval): # TODO: this is probably what you need to reduce processor cycles
            try:
                self.device.lock.acquire()
                #print 'read from thread' 
                filtered_data_words = self.read_once()
                self.device.lock.release()
                #map(self.data_queue.put, filtered_data_words)
                #itertools.imap(self.data_queue.put, filtered_data_words)
                raw_data = list(filtered_data_words)
                if len(raw_data)>0:
                    self.data_queue.put({'timestamp':get_float_time(), 'raw_data':raw_data, 'error':0})
            except Exception:
                self.stop_thread_event.set()
                continue
                        
    def read_once(self):
        '''Read single to read SRAM once
        
        can be used without threading
        '''
        # TODO: check fifo status (overflow) and check rx status (sync) once in a while

        fifo_size = self.get_sram_fifo_size()
        if fifo_size%2 == 1: # sometimes a read happens during writing, but we want to have a multiplicity of 32 bits
            fifo_size-=1
            #print "FIFO size odd"
        if fifo_size > 0:
            fifo_data = self.device.FastBlockRead(4*fifo_size/2)
            #print 'fifo raw data:', fifo_data
            data_words = struct.unpack('>'+fifo_size/2*'I', fifo_data)
            #print 'raw data words:', data_words
            
            #filtered_data_words = [i for i in data_words if self.filter]
            
            self.filtered_data_words = self.data_filter(data_words)
            for filterd_data_word in self.filtered_data_words: 
                yield filterd_data_word
    
    def set_filter(self, data_filter = None):
        if data_filter == None:
                self.data_filter = self.no_filter
        else:
            if hasattr(data_filter, '__call__'):
                self.data_filter = data_filter
            else:
                raise ValueError('Filter object is not callable')
            
    def get_sram_fifo_size(self):
        retfifo = self.device.ReadExternal(address = 0x8101, size = 3)
        return struct.unpack('I', retfifo.tostring() + '\x00' )[0] # TODO: optimize, remove tostring() ?

    def get_8b10b_code_error_count(self):
        value = {}
        for idx, addr in enumerate(range(0x8604, 0x8204, -0x0100)):
            value["Channel "+str(idx+1)] = self.device.ReadExternal(address = addr, size = 1)[0]
        return value
        return self.device.ReadExternal(address = addr, size = 1)[0]

    def get_rx_fifo_discard_count(self):
        value = {}
        for idx, addr in enumerate(range(0x8605, 0x8205, -0x0100)):
            value["Channel "+str(idx+1)] = self.device.ReadExternal(address = addr, size = 1)[0]
        return value

    def no_filter(self, words):
        for word in words:
            yield word
            
    def data_record_filter(self, words):
        for word in words:
            if (word & 0x00FFFFFF) >= 131328 and (word & 0x00FFFFFF) <= 10572030:
                yield word
        
    def data_header_filter(self, words):
        for word in words:
            header = struct.unpack(4*'B', struct.pack('I', word))[2]
            if header == 233:
                yield word
                
    def tlu_data_filter(self, words):
        for word in words:
            if 0x80000000 == word & 0x80000000:
                yield word
            