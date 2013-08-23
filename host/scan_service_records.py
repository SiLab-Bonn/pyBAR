"""Reads the actual service records. The FPGA/FE will not be configured in this scan. It has to be already configured.

"""
from scan.scan import ScanBase

class ServiceRecordScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "service_record_scan", outdir = None):
        super(ServiceRecordScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(ServiceRecordScan, self).start(configure)
        
        print 'Reading Service Records...'
        for service_record in scan.register_utils.read_service_records():
            print service_record
       
if __name__ == "__main__":
    import scan_configuration    
    scan = ServiceRecordScan(config_file = scan_configuration.config_file, bit_file = None, outdir = scan_configuration.outdir)
    scan.start(configure = False)
