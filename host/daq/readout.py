import struct
import itertools
import time
from threading import Thread, Event
from Queue import Queue
#from multiprocessing import Process as Thread
#from multiprocessing import Event as Event 
#from multiprocessing import Queue as Queue

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
    
    def start(self):
        self.data_queue.empty()
        self.stop_thread_event.clear()
        self.worker_thread = Thread(target=self.worker)
        self.worker_thread.start()
    
    def stop(self):
        self.stop_thread_event.set()
        if self.worker_thread != None:
            self.worker_thread.join()
            self.worker_thread = None
    
    def worker(self):
        '''Reading thread to continuously reading SRAM
        
        Worker thread function uses read_once()
        ''' 
        while self.stop_thread_event.wait(0.05) or not self.stop_thread_event.is_set(): # TODO: this is probably what you need to reduce processor cycles
            if self.stop_thread_event.is_set():
                break
#        while not self.stop_thread_event.is_set():
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

        fifo_size = self.get_fifo_size()
        #print 'SRAM FIFO SIZE: ' + str(fifo_size)
        if fifo_size%2 == 1: # sometimes a read happens during writing, but we want to have a multiplicity of 32 bits
            fifo_size-=1
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
            
    def get_fifo_size(self):
        retfifo = self.device.ReadExternal(address = 0x8101, size = 3)
        return struct.unpack('I', retfifo.tostring() + '\x00' )[0] # TODO optimize, remove tostring() ?
            
    def get_lost_data_count(self):
        return self.device.ReadExternal(address = 0x8005, size = 1)[0]
    
    def get_8b10b_code_error_count(self):
        return self.device.ReadExternal(address = 0x8004, size = 1)[0]

    def no_filter(self, words):
        for word in words:
            yield word
            
    def data_record_filter(self, words):
        for word in words:
            if word >= 131328 and word <= 10572030:
                yield word
        
    def data_header_filter(self, words):
        for word in words:
            header = struct.unpack(4*'B', struct.pack('I', word))[2]
            if header == 233:
                yield word
            