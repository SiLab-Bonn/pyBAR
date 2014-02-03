"""Reads the FE Service Records. The FE will not be configured in this scan because this will reset any Service Record counter. The FE has to be already configured.

"""
from scan.scan import ScanBase
from daq.readout import save_raw_data_from_data_dict_iterable, FEI4Record
from analysis.analyze_raw_data import AnalyzeRawData

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class TestServiceRecords(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(TestServiceRecords, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="test_service_records")

    def scan(self):
        self.register.create_restore_point()

        read_service_records(self)

        # saving data
        data_dict = self.readout.read_data_dict()
        save_raw_data_from_data_dict_iterable((data_dict,), filename=self.scan_data_filename, title=self.scan_identifier)

        # debug
#         for data in data_dict["data"]:
#             print FEI4Record(data, chip_flavor=self.register.chip_flavor)

        self.register.restore()
        self.register_utils.configure_global()

    def analyze(self):
        output_file = scan.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)
#             analyze_raw_data.interpreter.print_summary()


def read_service_records(self):
    logging.info('Reading Service Records...')
    commands = []
    commands.extend(self.register.get_commands("confmode"))
    self.register_utils.send_commands(commands)
    self.readout.reset_sram_fifo()
    commands = []
    self.register.set_global_register_value('ReadErrorReq', 1)
    commands.extend(self.register.get_commands("wrregister", name=['ReadErrorReq']))
    commands.extend(self.register.get_commands("globalpulse", width=0))
    self.register.set_global_register_value('ReadErrorReq', 0)
    commands.extend(self.register.get_commands("wrregister", name=['ReadErrorReq']))
    self.register_utils.send_commands(commands)


if __name__ == "__main__":
    import configuration
    scan = TestServiceRecords(**configuration.device_configuration)
    scan.start(configure=False)
    scan.stop()
    scan.analyze()
