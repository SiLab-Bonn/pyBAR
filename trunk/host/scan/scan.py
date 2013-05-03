import time

from SiLibUSB import SiUSBDevice

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from scan_utils import FEI4ScanUtils
#from fei4.output import FEI4Record
from daq.readout_utils import ReadoutUtils
from daq.readout import Readout


chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'


class ScanBase(object):
    def __init__(self, config_file, bit_file = None):
        self.device = None
        self.device = SiUSBDevice()
        if bit_file != None:
            print 'Programming FPGA...'
            self.device.DownloadXilinx(bit_file)
            time.sleep(1)
            print 'Done!'
            
        self.readout = Readout(self.device)
        self.readout_utils = ReadoutUtils(self.device)

        self.register = FEI4Register(config_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout_utils, self.register)
        self.scan_utils = FEI4ScanUtils(self.register, self.register_utils)
        
        print 'Configure FE...'
        #scan.register.load_configuration_file(config_file)
        self.register_utils.configure_all(same_mask_for_all_dc = True)
        print 'Done!'
        
        print 'Reset Rx...'
        self.readout_utils.reser_rx()
        print 'Done!'
        
        print 'Reset SRAM FIFO...'
        self.readout_utils.reset_sram_fifo()
        print 'Done!'
        
                