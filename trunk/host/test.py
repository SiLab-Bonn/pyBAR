import SiLibUSB
import time

from SiLibUSB import SiUSBDevice

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from fei4.output import FEI4Record
from daq.readout_utils import ReadoutUtils

from utils.utils import bitvector_to_bytearray

#import binascii
import array
import struct
import pprint
import BitVector
from bitstring import BitArray
from tables.tests.test_array import SI1NACloseTestCase

chip_flavor = 'fei4b'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'

class TestFE(object):
    def __init__(self):
        self.device = None
        self.device = SiUSBDevice()
        
        self.readout_utils = ReadoutUtils(self.device)
        
        #self.device.DownloadXilinx(r"C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit")
        self.register = FEI4Register(config_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout_utils, self.register)

    
        
if __name__ == "__main__":
    scan = TestFE()
    print 'Programming FPGA...'
    scan.device.DownloadXilinx(r"C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit")
    time.sleep(1)
    print 'Done!'
    print 'Configure global registers...'
    scan.register_utils.configure_global()
    #scan.register.load_configuration_file(config_file)
    print 'Done!'
    
    print 'Reset Rx...'
    scan.readout_utils.reser_rx()
    print 'Done!'
    
    time.sleep(1)
    
#    total = 0
#    errors = 0
#    while True:
#        number_of_errors = scan.register_utils.test_global_register()
#        print 'Global Register Test: Found', number_of_errors, "error(s)"
#        total += 1
#        if number_of_errors > 1:
#            errors += 1
#        print 'Error (%):', errors/total*100
    
    
#    number_of_errors = scan.register_utils.test_global_register()
#    print 'Global Register Test: Found', number_of_errors, "error(s)"
#    
#    number_of_errors = scan.register_utils.test_pixel_register()
#    print 'Pixel Register Test: Found', number_of_errors, "error(s)"
#    
#    sn = scan.register_utils.read_chip_sn()
#    print "Chip S/N:", sn
    
    #time.sleep( 0.2 )  #wait until ready
    #print scan.device.ReadExternal(address = 0x8000, size = 8)
    
    print 'Reset SRAM FIFO...'
    scan.readout_utils.reset_sram_fifo()
    print 'Done!'
    
    
    
    scan.device.WriteExternal(address = 0+8, data = [0xb4,0x08,0x02])
    scan.device.WriteExternal(address = 0+3, data = [23,0])
    scan.device.WriteExternal(address = 0+1, data = [0])
    
    
    
    commands = []
    commands.extend(scan.register.get_commands("runmode"))
    scan.register_utils.send_commands(commands)
    commands = []
    commands.extend(scan.register.get_commands("lv1"))
    #commands.append(scan.register.get_commands("lv1")[0]+BitVector.BitVector(size = 1000))
    scan.register_utils.send_commands(commands)
    w = 0
    for x_ in range(40):
        for _ in range(1000):
            scan.register_utils.send_commands()
            time.sleep(0.001)
        
        print 'iter:', x_
        retfifo = scan.device.ReadExternal(address = 0x8100, size = 8)
        size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
        print 'SRAM FIFO SIZE: ' + str(size)
        w+=size
        print 'pointer:', w
        
        fifo_data = scan.device.FastBlockRead(4*size/2)
        #print 'fifo raw data:', fifo_data
        #data = struct.unpack('>'+size/2*'I', fifo_data)
        #print 'raw data words:', data
        retfifo = scan.device.ReadExternal(address = 0x8100, size = 8)
        size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
        print 'SRAM FIFO SIZE: ' + str(size)
        
        
    
    time.sleep( 1 ) #wait for ready should be
    
    retfifo = scan.device.ReadExternal(address = 0x8100, size = 8)
    size = struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0]
    print 'SRAM FIFO SIZE: ' + str(size)
    
    fifo_data = scan.device.FastBlockRead(4*size/2)
    print 'fifo raw data:', fifo_data
    data = struct.unpack('>'+size/2*'I', fifo_data)
    print 'raw data words:', data

    for word in data:
        #print FEI4Record(word, chip_flavor)
        pass
    
        
    retfifo = scan.device.ReadExternal(address = 0x8100, size = 8)
    print 'SRAM FIFO SIZE: ' + str(struct.unpack('I', retfifo[1:4].tostring() + '\x00' )[0])    
    print scan.device.ReadExternal(address = 0x8100, size = 8)