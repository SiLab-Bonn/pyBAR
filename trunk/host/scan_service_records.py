"""Reads the actual service records. The FPGA/FE will not be configured in this scan. It has to be already configured.

"""
from scan.scan import ScanBase

class ServiceRecordsScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_service_records", scan_data_path = None):
        super(ServiceRecordsScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def start(self, configure = True):
        super(ServiceRecordsScan, self).start(configure)
        
        print 'Reading Service Records...'
        for service_record in scan.register_utils.read_service_records():
            print service_record
       
if __name__ == "__main__":
    import configuration
    scan = ServiceRecordsScan(config_file = configuration.config_file, bit_file = None, scan_data_path = configuration.scan_data_path)
    scan.start(configure = False)
