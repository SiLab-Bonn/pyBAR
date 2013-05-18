import time
import os
import logging

#import usb.core

from threading import Event, Lock

from pySiLibUSB.SiLibUSB import SiUSBDevice

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from scan_utils import FEI4ScanUtils
#from fei4.output import FEI4Record
from daq.readout_utils import ReadoutUtils
from daq.readout import Readout
from utils.utils import convert_to_int


chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'


class ScanBase(object):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "base_scan", outdir = ""):
        if device is not None:
            #if isinstance(device, usb.core.Device):
            if isinstance(device, SiUSBDevice):
                self.device = device
            else:
                raise TypeError('Device has wrong type')
        else:
            self.device = SiUSBDevice()
        print 'Found USB board with ID', self.device.GetBoardId()
        if bit_file != None:
            print 'Programming FPGA...'
            print bit_file
            self.device.DownloadXilinx(bit_file)
            time.sleep(1)
            print 'Done!'
            
        self.readout = Readout(self.device)
        self.readout_utils = ReadoutUtils(self.device)

        self.register = FEI4Register(config_file, definition_file = definition_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout_utils, self.register)
        self.scan_utils = FEI4ScanUtils(self.register, self.register_utils)
        
        self.outdir = outdir
        self.scan_identifier = scan_identifier
        self.scan_number = None
        self.scan_data_path = None
        
        self.lock = Lock()
        
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        
    def configure(self):
        print 'Configure FE...'
        #scan.register.load_configuration_file(config_file)
        self.register_utils.configure_all(same_mask_for_all_dc = False)
        print 'Done!'
        
    def start(self, configure = True):
        self.stop_thread_event.clear()
        
        self.lock.acquire()
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)
        
        with open(os.path.join(self.outdir, self.scan_identifier+".cfg"), "a+") as f:
            scan_numbers = [int(number) for number in f.readlines() if convert_to_int(number) != None]
            if len(scan_numbers) == 0:
                self.scan_number = 0
            else:
                self.scan_number = max(scan_numbers)+1
            f.write(str(self.scan_number)+'\n')
        
        self.scan_data_path = os.path.join(self.outdir, self.scan_identifier+"_"+str(self.scan_number))
        self.lock.release()
        
        if configure:
            self.configure()

        print 'Reset Rx...'
        self.readout_utils.reset_rx()
        print 'Done!'
        
        print 'Reset SRAM FIFO...'
        self.readout_utils.reset_sram_fifo()
        print 'Done!'
        
    def worker(self):
        pass
    
    def scan(self):
        pass