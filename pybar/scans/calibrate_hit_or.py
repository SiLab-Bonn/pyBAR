"""A script that changes a scan parameter (usually PlsrDAC, in inner loop) in a certain range for selected pixels and measures the length of the hit OR signal with the FPGA TDC.
This calibration can be used to measure charge information for single pixels with higher precision than with the quantized TOT information.
"""
import logging
import numpy as np
import tables as tb
import progressbar

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from pybar.fei4.register_utils import make_pixel_mask_from_col_row, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.analysis_utils import get_scan_parameter, get_unique_scan_parameter_combinations, get_scan_parameters_table_from_meta_data, get_ranges_from_array
from pybar.analysis.analyze_raw_data import AnalyzeRawData


def create_hitor_calibration(output_filename):
    logging.info('Analyze and plot results of %s', output_filename)

    def plot_calibration(col_row_combinations, scan_parameter, calibration_data, filename):  # Result calibration plot function
        for index, (column, row) in enumerate(col_row_combinations):
            logging.info("Plot calibration for pixel " + str(column) + '/' + str(row))
            fig = Figure()
            FigureCanvas(fig)
            ax = fig.add_subplot(111)
            fig.patch.set_facecolor('white')
            ax.grid(True)
            ax.errorbar(scan_parameter, calibration_data[column - 1, row - 1, :, 0] * 25. + 25., yerr=[calibration_data[column - 1, row - 1, :, 2] * 25, calibration_data[column - 1, row - 1, :, 2] * 25], fmt='o', label='FE-I4 ToT [ns]')
            ax.errorbar(scan_parameter, calibration_data[column - 1, row - 1, :, 1] * 1.5625, yerr=[calibration_data[column - 1, row - 1, :, 3] * 1.5625, calibration_data[column - 1, row - 1, :, 3] * 1.5625], fmt='o', label='TDC ToT [ns]')
            ax.set_title('Calibration for pixel ' + str(column) + '/' + str(row))
            ax.set_xlabel('Charge [PlsrDAC]')
            ax.set_ylabel('TOT')
            ax.legend(loc=0)
            filename.savefig(fig)
            if index > 100:  # stop for too many plots
                logging.info('Do not create pixel plots for more than 100 pixels to safe time')
                break

    with AnalyzeRawData(raw_data_file=output_filename, create_pdf=True) as analyze_raw_data:  # Interpret the raw data file
        analyze_raw_data.create_occupancy_hist = False  # too many scan parameters to do in ram histograming
        analyze_raw_data.create_hit_table = True
        analyze_raw_data.create_tdc_hist = True
        analyze_raw_data.align_at_tdc = True  # align events at TDC words, first word of event has to be a tdc word
        analyze_raw_data.interpret_word_table()
        analyze_raw_data.interpreter.print_summary()
        analyze_raw_data.plot_histograms()
        n_injections = analyze_raw_data.n_injections  # store number of injections for later cross check

    with tb.open_file(output_filename + '_interpreted.h5', 'r') as in_file_h5:  # Get scan parameters from interpreted file
        meta_data = in_file_h5.root.meta_data[:]
        hits = in_file_h5.root.Hits[:]
        scan_parameters_dict = get_scan_parameter(meta_data)
        inner_loop_parameter_values = scan_parameters_dict[next(reversed(scan_parameters_dict))]  # inner loop parameter name is unknown
        scan_parameter_names = scan_parameters_dict.keys()
        col_row_combinations = get_unique_scan_parameter_combinations(in_file_h5.root.meta_data[:], scan_parameters=('column', 'row'), scan_parameter_columns_only=True)

        meta_data_table_at_scan_parameter = get_unique_scan_parameter_combinations(meta_data, scan_parameters=scan_parameter_names)
        parameter_values = get_scan_parameters_table_from_meta_data(meta_data_table_at_scan_parameter, scan_parameter_names)
        event_number_ranges = get_ranges_from_array(meta_data_table_at_scan_parameter['event_number'])
        event_ranges_per_parameter = np.column_stack((parameter_values, event_number_ranges))
        event_numbers = hits['event_number'].copy()  # create contigous array, otherwise np.searchsorted too slow, http://stackoverflow.com/questions/15139299/performance-of-numpy-searchsorted-is-poor-on-structured-arrays

        with tb.openFile(output_filename + "_calibration.h5", mode="w") as calibration_data_file:
            logging.info('Create calibration')
            output_pdf = PdfPages(output_filename + "_calibration.pdf")
            calibration_data = np.zeros(shape=(80, 336, len(inner_loop_parameter_values), 4), dtype='f4')  # result of the calibration is a histogram with col_index, row_index, plsrDAC value, mean discrete tot, rms discrete tot, mean tot from TDC, rms tot from TDC

            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(event_ranges_per_parameter), term_width=80)
            progress_bar.start()

            for index, (parameter_values, event_start, event_stop) in enumerate(event_ranges_per_parameter):
                if event_stop is None:  # happens for the last chunk
                    event_stop = hits[-1]['event_number']
                array_index = np.searchsorted(event_numbers, np.array([event_start, event_stop]))
                actual_hits = hits[array_index[0]:array_index[1]]
                actual_col, actual_row, parameter_value = parameter_values

                if len(hits[np.logical_and(actual_hits['column'] != actual_col, actual_hits['row'] != actual_row)]):
                    logging.warning('There are %d hits from not selected pixels in the data', len(actual_hits[np.logical_and(actual_hits['column'] != actual_col, actual_hits['row'] != actual_row)]))

                actual_hits = actual_hits[np.logical_and(actual_hits['column'] == actual_col, actual_hits['row'] == actual_row)]
                actual_tdc_hits = actual_hits[(actual_hits['event_status'] & 0b0000111110011100) == 0b0000000100000000]  # only take hits from good events (one TDC word only, no error)
                actual_tot_hits = actual_hits[(actual_hits['event_status'] & 0b0000100010011100) == 0b0000000000000000]  # only take hits from good events for tot
                tot, tdc = actual_tot_hits['tot'], actual_tdc_hits['TDC']

                if tdc.shape[0] != n_injections and index == event_ranges_per_parameter.shape[0] - 1:
                    logging.warning('There are %d != %d TDC hits for %s = %s', tdc.shape[0], n_injections, str(scan_parameter_names), str(parameter_values))

                inner_loop_scan_parameter_index = np.where(parameter_value == inner_loop_parameter_values)[0][0]  # translate the scan parameter value to an index for the result histogram
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 0] = np.mean(tot)
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 1] = np.mean(tdc)
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 2] = np.std(tot)
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 3] = np.std(tdc)

                progress_bar.update(index)

            calibration_data_out = calibration_data_file.createCArray(calibration_data_file.root, name='HitOrCalibration', title='Hit OR calibration data', atom=tb.Atom.from_dtype(calibration_data.dtype), shape=calibration_data.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            calibration_data_out[:] = calibration_data
            calibration_data_out.attrs.dimensions = scan_parameter_names
            calibration_data_out.attrs.scan_parameter_values = inner_loop_parameter_values
            plot_calibration(col_row_combinations, scan_parameter=inner_loop_parameter_values, calibration_data=calibration_data, filename=output_pdf)
            output_pdf.close()
            progress_bar.finish()


class HitOrCalibration(Fei4RunBase):

    ''' Hit Or calibration scan
    '''
    _default_run_conf = {
        "repeat_command": 200,
        "injection_delay": 5000,  # for really low feedbacks (ToT >> 300 ns) one needs to increase the injection delay
        "scan_parameters": [('column', None),
                            ('row', None),
                            ('PlsrDAC', [40, 50, 60, 80, 130, 180, 230, 280, 340, 440, 540, 640, 740])],  # 0 400 sufficient
        "reset_rx_on_error": True,
        "plot_tdc_histograms": False,
        "pixels": (np.dstack(np.where(make_box_pixel_mask_from_col_row([40, 41], [150, 151]) == 1)) + 1).tolist()[0],  # list of (col, row) tupels. From 1 to 80/336.
        "enable_masks": ["Enable", "C_Low", "C_High"],
        "disable_masks": ["Imon"]
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("Trig_Count", 6)  # decrease trigger count to reduce data
        self.register.set_global_register_value("Trig_Lat", 215)  # adjust delay for smaller bcid window
        self.register.set_global_register_value("ErrorMask", 1536)  # deactivate hit bus service record
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count", "ErrorMask"]))
        self.register_utils.send_commands(commands)

    def scan(self):
        def write_double_column(column):
            return (column - 1) / 2

        def inject_double_column(column):
            if column == 80:
                return 39
            else:
                return (column) / 2

        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.injection_delay)[0]
        scan_par_name = self.scan_parameters._fields[-1]  # scan parameter is in inner loop
        scan_parameters_values = self.scan_parameters[-1][:]  # create deep copy of scan_parameters, they are overwritten in self.readout

        logging.info("Scanning %d pixels" % len(self.pixels))
        for pixel_index, pixel in enumerate(self.pixels):
            if self.stop_run.is_set():
                break

            column = pixel[0]
            row = pixel[1]
            logging.info('Scanning pixel: %d / %d (column / row)', column, row)
            if pixel_index:
                dcs = [write_double_column(column)]
                dcs.append(write_double_column(self.pixels[pixel_index - 1][0]))
            else:
                dcs = []
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            single_pixel_enable_mask = make_pixel_mask_from_col_row([column], [row])
            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, single_pixel_enable_mask), self.enable_masks)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=self.enable_masks, joint_write=True))
            single_pixel_disable_mask = make_pixel_mask_from_col_row([column], [row], default=1, value=0)
            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, single_pixel_disable_mask), self.disable_masks)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=self.disable_masks, joint_write=True))
            self.register.set_global_register_value("Colpr_Addr", inject_double_column(column))
            commands.append(self.register.get_commands("WrRegister", name=["Colpr_Addr"])[0])
            self.register_utils.send_commands(commands)
            # self.fifo_readout.reset_sram_fifo()  # after mask shifting you have AR VR in SRAM that are not of interest but reset takes a long time, so ignore the warning

            self.dut['TDC']['ENABLE'] = True
            for scan_parameter_value in scan_parameters_values:
                if self.stop_run.is_set():
                    break

                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                self.register.set_global_register_value(scan_par_name, scan_parameter_value)
                commands.extend(self.register.get_commands("WrRegister", name=[scan_par_name]))
                commands.extend(self.register.get_commands("RunMode"))
                self.register_utils.send_commands(commands)

                self.dut['TDC']['EN_ARMING'] = True
                with self.readout(column=column, row=row, **{scan_par_name: scan_parameter_value}):
                    self.register_utils.send_command(command=cal_lvl1_command, repeat=self.repeat_command)

                self.dut['TDC']['EN_ARMING'] = False
            self.dut['TDC']['ENABLE'] = False

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), new_file=['column'], flush=False)  # Create new file for each scan parameter change

    def analyze(self):
        create_hitor_calibration(self.output_filename)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(HitOrCalibration)
