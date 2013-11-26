"""Reads the FE Service Records. The FE will not be configured in this scan because this will reset any Service Record counter. The FE has to be already configured.

"""
from scan.scan import ScanBase

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class TestServiceRecords(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="test_service_records", scan_data_path=None):
        super(TestServiceRecords, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self):
        logging.info('Reading Service Records...')
        for service_record in scan.register_utils.read_service_records():
            print service_record

if __name__ == "__main__":
    import configuration
    scan = TestServiceRecords(config_file=configuration.config_file, bit_file=None, scan_data_path=configuration.scan_data_path)
    scan.start(configure=False)
