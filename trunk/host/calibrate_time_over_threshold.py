from daq.readout import open_raw_data_file, get_col_row_tot_array_from_data_record_array, save_raw_data_from_data_dict_iterable, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel
from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from analysis.analyze_raw_data import AnalyzeRawData
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
import os.path
from analysis.plotting.plotting import plotThreeWay, plot_scurves, plot_scatter

from scan.scan import ScanBase

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "mask_steps": 3,
    "repeat_command": 100,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_range": None
}


class TimeOverThresholdScan(ScanBase):
    scan_id = "time_over_threshold_calibration"

    def scan(self, mask_steps=3, repeat_command=100, scan_parameter='PlsrDAC', scan_parameter_range=None, **kwargs):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        repeat_command : int
            Number of injections.
        scan_parameter : string
            Name of global register.
        scan_parameter_range : int
            Specify scan steps. These values will be written into global register scan_parameter.

        Note
        ----
        This scan is very similar to the threshold scan.
        This scan can also be used for ToT verification: change scan_parameter_value to desired injection charge (in units of PulsrDAC).
        '''
        if scan_parameter_range is None or not scan_parameter_range:
            scan_parameter_range = range(0, (2 ** self.register.get_global_register_objects(name=[scan_parameter])[0].bitlength) - 1)
        logging.info("Scanning %s from %d to %d" % (scan_parameter, scan_parameter_range[0], scan_parameter_range[-1]))

        output_pdf = PdfPages(os.path.join(self.scan_data_path, self.scan_data_filename) + '.pdf')
        tot_calibration = np.empty(shape=(80, 336, len(scan_parameter_range)), dtype='<f8')  # array to hold the analyzed data in ram
        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id, scan_parameters=[scan_parameter]) as raw_data_file:
            for index, scan_parameter_value in enumerate(scan_parameter_range):
                logging.info('%s at %d %s' % (scan_parameter, scan_parameter_value, ('[%d - %d]' % (scan_parameter_range[0], scan_parameter_range[-1])) if len(scan_parameter_range) > 1 else ('[%d]' % scan_parameter_range[0])))
                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(scan_parameter, scan_parameter_value)
                commands.extend(self.register.get_commands("wrregister", name=["PlsrDAC"]))
                self.register_utils.send_commands(commands)

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
                self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, use_delay=True, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=None, enable_double_columns=range(1, 37), same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=None)

                self.readout.stop()

                # plotting data
                cols, rows, tots = convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_tot_array_from_data_record_array)
                col_row_tot_hist, edges = np.histogramdd((cols, rows, tots), bins=(80, 336, 16), range=[[1, 80], [1, 336], [0, 15]])
                col_row_mean_tot_hist = np.ma.array(np.average(col_row_tot_hist, axis=2, weights=range(0, 16)) * sum(range(0, 16)) / repeat_command, mask=np.all(col_row_tot_hist == 0, axis=2))
                plotThreeWay(hist=col_row_mean_tot_hist.T, title='Mean ToT (%s = %d)' % (scan_parameter, scan_parameter_value), x_axis_title='ToT', minimum=0, maximum=15, filename=output_pdf)
                # saving data
                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value})
                tot_calibration[:, :, index] = col_row_mean_tot_hist
            # plot accumulated S-curves
            plot_scurves(occupancy_hist=tot_calibration, title='ToT to Charge Calibration', scan_parameters=scan_parameter_range, scan_parameter_name=scan_parameter, ylabel='ToT', max_occ=15, filename=output_pdf)
            output_pdf.close()

    def analyze(self):
        output_file = scan.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
#             analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)
#             analyze_raw_data.interpreter.print_summary()

if __name__ == "__main__":
    import configuration
    scan = TimeOverThresholdScan(**configuration.default_configuration)
    scan.start(use_thread=False, **local_configuration)
    scan.stop()
    scan.analyze()
