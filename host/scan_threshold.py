from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from analysis.analyze_raw_data import AnalyzeRawData

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class ThresholdScan(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="scan_threshold", scan_data_path=None):
        super(ThresholdScan, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self, mask=3, repeat=100, scan_parameter='PlsrDAC', scan_paramter_values=None):
        '''Scan loop

        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections per scan step.
        scan_parameter : string
            Name of global register.
        scan_paramter_values : list, tuple
            Specify scan steps. These values will be written into global register scan_parameter.
        '''
        if scan_paramter_values is None:
            scan_paramter_value_list = range(0, 101, 1)  # default
        else:
            scan_paramter_value_list = list(scan_paramter_values)

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:

            for scan_paramter_value in scan_paramter_value_list:
                if self.stop_thread_event.is_set():
                    break
                logging.info('Scan step: %s %d' % (scan_parameter, scan_paramter_value))

                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(scan_parameter, scan_paramter_value)
                commands.extend(self.register.get_commands("wrregister", name=[scan_parameter]))
                self.register_utils.send_commands(commands)

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask)[0]
                self.scan_loop(cal_lvl1_command, repeat=repeat, mask=mask, mask_steps=[], double_columns=[], same_mask_for_all_dc=True, hardware_repeat=True, digital_injection=False, eol_function=None)

                self.readout.stop(timeout=10)

                # saving data
                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_paramter_value})

    def analyze(self):
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table(FEI4B=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)

if __name__ == "__main__":
    import configuration
    scan = ThresholdScan(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.start(use_thread=True, scan_paramter_values=range(0, 101, 1))
    scan.stop()
    scan.analyze()
