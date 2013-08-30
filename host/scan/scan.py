import time
import os
import logging

#import usb.core

from threading import Thread, Event, Lock, Timer

from SiLibUSB import SiUSBDevice

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from scan_utils import FEI4ScanUtils
#from fei4.output import FEI4Record
from daq.readout_utils import ReadoutUtils
from daq.readout import Readout
from utils.utils import convert_to_int

logging.basicConfig(level=logging.INFO, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class ScanBase(object):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "base_scan", scan_data_path = None):
        if device is not None:
            #if isinstance(device, usb.core.Device):
            if isinstance(device, SiUSBDevice):
                self.device = device
            else:
                raise TypeError('Device has wrong type')
        else:
            self.device = SiUSBDevice()
        logging.info('Found USB board with ID %s', self.device.identifier)
        if bit_file != None:
            logging.info('Programming FPGA: %s' % bit_file)
            self.device.DownloadXilinx(bit_file)
            time.sleep(1)
            
        self.readout = Readout(self.device)
        self.readout_utils = ReadoutUtils(self.device)

        self.register = FEI4Register(config_file, definition_file = definition_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout_utils, self.register)
        self.scan_utils = FEI4ScanUtils(self.register, self.register_utils)
        
        if scan_data_path == None:
            self.scan_data_path = os.getcwd()
        else:
            self.scan_data_path = scan_data_path
        self.scan_identifier = scan_identifier.lstrip('/\\') # remove leading slashes, prevent problems with os.path.join
        self.scan_number = None
        self.scan_data_filename = None
        
        self.lock = Lock()
        
        self.scan_thread = None
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        self.use_thread = None
        
    def configure(self):
        logging.info('Configuring FE')
        #scan.register.load_configuration_file(config_file)
        self.register_utils.configure_all(same_mask_for_all_dc = False)
        
    def start(self, configure = True, use_thread = False, **kwargs): # TODO: in Python 3 use def func(a,b,*args,kw1=None,**kwargs)
        self.use_thread = use_thread
        if self.scan_thread != None:
            raise RuntimeError('Thread is not None')
        self.lock.acquire()
        if not os.path.exists(self.scan_data_path):
            os.makedirs(self.scan_data_path)
        
        with open(os.path.join(self.scan_data_path, self.scan_identifier+".cfg"), "a+") as f:
            scan_numbers = [int(number) for number in f.readlines() if convert_to_int(number) != None]
            if len(scan_numbers) == 0:
                self.scan_number = 0
            else:
                self.scan_number = max(scan_numbers)+1
            f.write(str(self.scan_number)+'\n')
        
        self.scan_data_filename = os.path.join(self.scan_data_path, self.scan_identifier+"_"+str(self.scan_number))
        self.lock.release()
        
        if configure:
            self.configure()

        self.readout.reset_rx()
#        self.readout.reset_sram_fifo()
        self.readout.print_readout_status()
        
        self.stop_thread_event.clear()
        
        logging.info('Starting scan %s with ID %d (output path: %s)' % (self.scan_identifier, self.scan_number, self.scan_data_path))
        if use_thread:
            self.scan_thread = Thread(target=self.scan, name='%s with ID %d' % (self.scan_identifier, self.scan_number), kwargs=kwargs)#, args=kwargs)
            self.scan_thread.start()
        else:
            self.scan(**kwargs)
 
    def stop(self, timeout = None):
        scan_completed = True
        if (self.scan_thread is not None) ^ self.use_thread:
            if self.scan_thread is None:
                raise RuntimeError('Thread is None')
            else:
                raise RuntimeError('Thread is not None')
        if self.scan_thread is not None:
            if timeout > 0:
                wait_timeout_event = Event()
                wait_timeout_event.clear()
                    
                def set_timeout_event(timeout_event, timeout):
                    timer = Timer(timeout, timeout_event.set)
                    timer.start()
                
                timeout_thread = Thread(target=set_timeout_event, args=[wait_timeout_event, timeout])
                timeout_thread.start()
                
                while self.scan_thread.is_alive() and not wait_timeout_event.wait(1):
                    pass
                if wait_timeout_event.is_set():
                    logging.warning('Scan timeout after %.1f second(s)' % timeout)
                    scan_completed = False
                else:
                    wait_timeout_event.set()
                timeout_thread.join()
            self.stop_thread_event.set()
            self.scan_thread.join()
            self.scan_thread = None
            self.use_thread = None
        logging.info('Stopped scan %s with ID %d' % (self.scan_identifier, self.scan_number))
        self.readout.print_readout_status()
        
        return scan_completed
    
    def scan(self, **kwargs):
        raise NotImplementedError('Scan not implemented')
