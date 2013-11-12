from scan.scan import ScanBase

class TestRegisters(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "test_register", scan_data_path = None):
        super(TestRegisters, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)

    def scan(self, **kwargs):
        number_of_errors = self.register_utils.test_global_register()
        print 'Global Register Test: Found', number_of_errors, "error(s)"
        
        number_of_errors = self.register_utils.test_pixel_register()
        print 'Pixel Register Test: Found', number_of_errors, "error(s)"
        
        sn = self.register_utils.read_chip_sn()
        print "Chip S/N:", sn

if __name__ == "__main__":
    import configuration
    scan = TestRegisters(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start()
    scan.stop()