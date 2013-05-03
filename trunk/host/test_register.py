from scan.scan import ScanBase

chip_flavor = 'fei4b'
config_file = r'C:\Users\Jens\Desktop\Python\python_workspace\test\source\config\fei4default\configs\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'

class TestRegisters(ScanBase):
    def __init__(self, config_file, bit_file):
        super(TestRegisters, self).__init__(config_file, bit_file)

if __name__ == "__main__":
    scan = TestRegisters(config_file, bit_file)
    
    number_of_errors = scan.register_utils.test_global_register()
    print 'Global Register Test: Found', number_of_errors, "error(s)"
    
    number_of_errors = scan.register_utils.test_pixel_register()
    print 'Pixel Register Test: Found', number_of_errors, "error(s)"
    
    sn = scan.register_utils.read_chip_sn()
    print "Chip S/N:", sn
    
    print 'Reset SRAM FIFO...'
    scan.readout_utils.reset_sram_fifo()
    print 'Done!'
    