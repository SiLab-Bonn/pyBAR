import time
import os
import logging
import re

from threading import Thread, Event, Lock, Timer

min_pysilibusb_version = '0.1.2'
from SiLibUSB import SiUSBDevice, __version__ as pysilibusb_version
from distutils.version import StrictVersion as v
if v(pysilibusb_version)<v(min_pysilibusb_version):
    raise ImportError('Wrong pySiLibUsb version (installed=%s, minimum expected=%s)' % (pysilibusb_version, min_pysilibusb_version))

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from scan_utils import FEI4ScanUtils
#from fei4.output import FEI4Record
from daq.readout_utils import ReadoutUtils
from daq.readout import Readout
from utils.utils import convert_to_int

import signal

logging.basicConfig(level=logging.INFO, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class ScanBase(object):
    # TODO: implement callback for stop() & analyze()
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "base_scan", scan_data_path = None):
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name=='nt':
            import thread
            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True
            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)
        if device is not None:
            #if isinstance(device, usb.core.Device):
            if isinstance(device, SiUSBDevice):
                self.device = device
            else:
                raise TypeError('Device has wrong type')
        else:
            self.device = SiUSBDevice()
        logging.info('Found USB board with ID %s', self.device.board_id)
        if bit_file != None:
            logging.info('Programming FPGA: %s' % bit_file)
            self.device.DownloadXilinx(bit_file)
            time.sleep(1)
            
        self.readout = Readout(self.device)
        self.readout_utils = ReadoutUtils(self.device)

        self.register = FEI4Register(config_file, definition_file = definition_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout, self.register)
        self.scan_utils = FEI4ScanUtils(self.register, self.register_utils)
        
        if scan_data_path == None:
            self.scan_data_path = os.getcwd()
        else:
            self.scan_data_path = scan_data_path
        self.scan_identifier = scan_identifier.lstrip('/\\') # remove leading slashes, prevent problems with os.path.join
        self.scan_number = None
        self.scan_data_filename = None
        self.scan_completed = False
        
        self.lock = Lock()
        
        self.scan_thread = None
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        self.use_thread = None
        
    def configure(self):
        logging.info('Configuring FE')
        #scan.register.load_configuration_file(config_file)
        self.register_utils.configure_all(same_mask_for_all_dc=False, do_global_rest=True)
        
    def start(self, configure = True, use_thread = False, **kwargs): # TODO: in Python 3 use def func(a,b,*args,kw1=None,**kwargs)
        self.scan_completed = False
        self.use_thread = use_thread
        if self.scan_thread != None:
            raise RuntimeError('Scan thread is already running')

        self.write_scan_number()
        
        if configure:
            self.configure()

        self.readout.reset_rx()
#        self.readout.reset_sram_fifo()
        
        if not any(self.readout.print_readout_status()):
            raise NoSyncError('No data sync on any input channel')
#             logging.error('Stopping scan: no sync')
#             return
        
        self.stop_thread_event.clear()
        
        logging.info('Starting scan %s with ID %d (output path: %s)' % (self.scan_identifier, self.scan_number, self.scan_data_path))
        if use_thread:
            self.scan_thread = Thread(target=self.scan, name='%s with ID %d' % (self.scan_identifier, self.scan_number), kwargs=kwargs)#, args=kwargs)
            self.scan_thread.daemon = True # Abruptly close thread when closing main thread. Resources may not be released properly.
            self.scan_thread.start()
            logging.info('Press Ctrl-C to stop scan loop')
            signal.signal(signal.SIGINT, self.signal_handler)
        else:
            self.scan(**kwargs)
 
    def stop(self, timeout = None):
        self.scan_completed = True
        if (self.scan_thread is not None) ^ self.use_thread:
            if self.scan_thread is None:
                pass
                #logging.warning('Scan thread has already stopped')
                #raise RuntimeError('Scan thread has already stopped')
            else:
                raise RuntimeError('Thread is running where no thread was expected')
        if self.scan_thread is not None:
            
            def stop_thread():
                logging.warning('Scan timeout after %.1f second(s)' % timeout)
                self.stop_thread_event.set()
                self.scan_completed = False
                
            timeout_timer = Timer(timeout, stop_thread) # could also use shed.scheduler() here
            if timeout:
                timeout_timer.start()
            try:
                while self.scan_thread.is_alive() and not self.stop_thread_event.wait(1):
                    pass
            except IOError: # catching "IOError: [Errno4] Interrupted function call" because of wait_timeout_event.wait()
                logging.exception('Event handler problem?')
                raise

            timeout_timer.cancel()
            signal.signal(signal.SIGINT, signal.SIG_DFL) # setting default handler
            self.stop_thread_event.set()
                
            self.scan_thread.join() # SIGINT will be suppressed here
            self.scan_thread = None
        self.use_thread = None
        logging.info('Stopped scan %s with ID %d' % (self.scan_identifier, self.scan_number))
        self.readout.print_readout_status()
        
        self.device.dispose() # free USB resources
        self.write_scan_status(self.scan_completed)
        return self.scan_completed
    
    def write_scan_number(self):
        scan_numbers = {}
        self.lock.acquire()
        if not os.path.exists(self.scan_data_path):
            os.makedirs(self.scan_data_path)
        with open(os.path.join(self.scan_data_path, self.scan_identifier+".cfg"), "r") as f:
            for line in f.readlines():   
                scan_number = int(re.findall(r'\d+\s', line)[0])
                scan_numbers[scan_number] = line
        if not scan_numbers:
            self.scan_number = 0
        else:
            self.scan_number = max(dict.iterkeys(scan_numbers))+1
        scan_numbers[self.scan_number] = str(self.scan_number)+'\n'
        with open(os.path.join(self.scan_data_path, self.scan_identifier+".cfg"), "w") as f:
            for value in dict.itervalues(scan_numbers):
                f.write(value)
        self.lock.release()
        self.scan_data_filename = os.path.join(self.scan_data_path, self.scan_identifier+"_"+str(self.scan_number))
    
    def write_scan_status(self, finished = True):
        scan_numbers = {}
        self.lock.acquire()
        with open(os.path.join(self.scan_data_path, self.scan_identifier+".cfg"), "r") as f:
            for line in f.readlines():   
                scan_number = int(re.findall(r'\d+\s', line)[0])
                if scan_number != self.scan_number:
                    scan_numbers[scan_number] = line
                else:
                    scan_numbers[scan_number] = line.strip()+(' SUCCESS\n' if finished else ' ABORTED\n') 
        with open(os.path.join(self.scan_data_path, self.scan_identifier+".cfg"), "w") as f:
            for value in dict.itervalues(scan_numbers):
                f.write(value)
        self.lock.release()
    
    @property
    def is_running(self):
        return self.scan_thread.is_alive()
    
    def scan(self, **kwargs):
        raise NotImplementedError('scan.scan() not implemented')
    
    def analyze(self, **kwargs):
        raise NotImplementedError('scan.analyze() not implemented')
    
    def signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL) # setting default handler... pressing Ctrl-C a second time will kill application
        logging.info('Pressed Ctrl-C. Stopping scan...')
        self.scan_completed = False
        self.stop_thread_event.set()

class NoSyncError(Exception):
    pass
    
from functools import wraps
def set_event_when_keyboard_interrupt(_lambda):
    '''Decorator function that sets Threading.Event() when keyboard interrupt (Ctrl+c) was raised
    
    Parameters
    ----------
    _lambda : function
        Lambda function that points to Threading.Event() object

    Returns
    -------
    wrapper : function

    Examples
    --------
    @set_event_when_keyboard_interrupt(lambda x: x.stop_thread_event)
    def scan(self, **kwargs):
        # some code
        
    Note
    ----
    Decorated functions cannot be derived.
    '''
    def wrapper(f):
        @wraps(f)
        def wrapped_f(self, *f_args, **f_kwargs):
            try:
                f(self, *f_args, **f_kwargs)
            except KeyboardInterrupt:
                #logging.info('Keyboard interrupt: setting %s' % _lambda(self).__name__)
                _lambda(self).set()
        return wrapped_f
    return wrapper
