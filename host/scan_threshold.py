from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from analysis.analyze_raw_data import AnalyzeRawData

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class ThresholdScan(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, device=None, scan_identifier="scan_threshold", scan_data_path=None):
        super(ThresholdScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self, mask_steps=3, repeat_command=100, scan_parameter='PlsrDAC', scan_parameter_values=None):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        repeat_command : int
            Number of injections per scan step.
        scan_parameter : string
            Name of global register.
        scan_parameter_values : list, tuple
            Specify scan steps. These values will be written into global register scan_parameter.
        '''
        if scan_parameter_values is None or not scan_parameter_values:
            scan_parameter_values = range(0, 101, 1)  # default

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:

            for scan_parameter_value in scan_parameter_values:
                if self.stop_thread_event.is_set():
                    break
                logging.info('Scan step: %s %d' % (scan_parameter, scan_parameter_value))

                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(scan_parameter, scan_parameter_value)
                commands.extend(self.register.get_commands("wrregister", name=[scan_parameter]))
                self.register_utils.send_commands(commands)

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
                self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, hardware_repeat=True, use_delay=True, mask_steps=mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=None)

                self.readout.stop(timeout=10)

                # saving data
                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value})

    def analyze(self):
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = 100
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)

if __name__ == "__main__":
    import configuration
    scan = ThresholdScan(configuration_file=configuration.configuration_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.start(use_thread=True, scan_parameter_values=range(0, 101, 1))
    scan.stop()
    scan.analyze()
