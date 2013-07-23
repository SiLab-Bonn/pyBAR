""" Reads the actual service records. The FPGA/Fe will not be configured in this scan. Thus they have to be configured already.
"""
from scan.scan import ScanBase

class ServiceRecordScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "service_record_scan", outdir = None):
        super(ServiceRecordScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(ServiceRecordScan, self).start(configure)
        
        print 'Reading Service Records'
        service_records = scan.register_utils.read_service_records()
        print 'Done!'
        for service_record in service_records:
            print service_record               
if __name__ == "__main__":
    chip_flavor = 'fei4b'
    config_file = r'C:\pyats\trunk\host\config\fei4default\configs\std_cfg_'+chip_flavor+'.cfg'
    bit_file = r'C:\pyats\trunk\host\config\FPGA\top.bit'
    scan_identifier = "service_record_scan"
    outdir = r"C:\data\service_record_scan"
    
    scan = ServiceRecordScan(config_file, bit_file = None, scan_identifier = scan_identifier, outdir = outdir)
    
    scan.start(configure = False)
