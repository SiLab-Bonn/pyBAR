"""Reads the FE Service Records. The FE will not be configured in this scan because this will reset any Service Record counter. The FE has to be already configured.

"""
from scan.scan import ScanBase
from daq.readout import save_raw_data_from_data_dict_iterable, FEI4Record
from analysis.analyze_raw_data import AnalyzeRawData

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class TestServiceRecords(ScanBase):
    scan_id = "service_record_test"

    def scan(self, **kwargs):
        self.register.create_restore_point()

        self.readout.reset_sram_fifo()

        self.register_utils.reset_service_records()

        # saving data
        data_dict = self.readout.read_data_dict()
        save_raw_data_from_data_dict_iterable((data_dict,), filename=self.scan_data_filename, title=self.scan_id)

        # debug
#         for data in data_dict["data"]:
#             print FEI4Record(data, chip_flavor=self.register.chip_flavor)

        self.register.restore()
        self.register_utils.configure_global()

    def analyze(self):
        output_file = scan.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_occupancy_hist = False  # creates a colxrow histogram with accumulated hits for each scan parameter
            analyze_raw_data.create_tot_hist = False  # creates a ToT histogram
            analyze_raw_data.create_rel_bcid_hist = False  # creates a histogram with the relative BCID of the hits
            analyze_raw_data.create_service_record_hist = True  # creates a histogram with all SR send out from the FE
            analyze_raw_data.create_error_hist = False  # creates a histogram summing up the event errors that occurred
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)
#             analyze_raw_data.interpreter.print_summary()


if __name__ == "__main__":
    import configuration
    scan = TestServiceRecords(**configuration.default_configuration)
    scan.start(configure=False)
    scan.stop()
    scan.analyze()
