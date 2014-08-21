from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from analysis.analyze_raw_data import AnalyzeRawData
from fei4.register_utils import invert_pixel_mask

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "mask_steps": 3,
    "repeat_command": 100,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_range": (0, 100),
    "scan_parameter_stepsize": 1,
    "use_enable_mask": False,
    "enable_shift_masks": ["Enable", "C_High", "C_Low"],
    "disable_shift_masks": []
}


class ThresholdScan(ScanBase):
    scan_id = "threshold_scan"

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        repeat_command : int
            Number of injections per scan step.
        scan_parameter : string
            Name of global register.
        scan_parameter_range : list, tuple
            Specify the minimum and maximum value for scan parameter range. Upper value not included.
        scan_parameter_stepsize : int
            The minimum step size of the parameter. Used when start condition is not triggered.
        use_enable_mask : bool
            Use enable mask for masking pixels.
        '''
        if self.scan_parameter_range is None or not self.scan_parameter_range:
            scan_parameter_values = range(0, (2 ** self.register.get_global_register_objects(name=[self.scan_parameter])[0].bitlength), self.scan_parameter_stepsize)
        else:
            scan_parameter_values = range(self.scan_parameter_range[0], self.scan_parameter_range[1], self.scan_parameter_stepsize)
        logging.info("Scanning %s from %d to %d" % (self.scan_parameter, scan_parameter_values[0], scan_parameter_values[-1]))

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id, scan_parameters=[self.scan_parameter]) as raw_data_file:

            for scan_parameter_value in scan_parameter_values:
                if self.stop_thread_event.is_set():
                    break
                logging.info('Scan step: %s %d' % (self.scan_parameter, scan_parameter_value))

                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(self.scan_parameter, scan_parameter_value)
                commands.extend(self.register.get_commands("wrregister", name=[self.scan_parameter]))
                self.register_utils.send_commands(commands)

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
                self.scan_loop(cal_lvl1_command, repeat_command=self.repeat_command, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None)

                self.readout.stop(timeout=10)

                # saving data
                raw_data_file.append(self.readout.data, scan_parameters={self.scan_parameter: scan_parameter_value})

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = 100
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)

if __name__ == "__main__":
    import configuration
    scan = ThresholdScan(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=True, **local_configuration)
    scan.stop()
