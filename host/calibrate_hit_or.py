"""A script that changes the PlsrDAC in a certain range for selected pixels and measures the length of the hit OR signal with the FPGA TDC.
    This calibration can be used to measure charge information for single pixels with higher precision than with the quantized TOT information.
"""
import numpy as np
import tables as tb
from scan.scan import ScanBase
from daq.readout import open_raw_data_file
import matplotlib.pyplot as plt

from analysis.analyze_raw_data import AnalyzeRawData
from analysis import analysis_utils
from analysis.plotting import plotting
from matplotlib.backends.backend_pdf import PdfPages

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "repeat_command": 10000,
    "reject_small_tot": False,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_values": [i for j in (range(40, 70, 5), range(70, 100, 10), range(100, 600, 20), range(600, 801, 40)) for i in j],  # list of scan parameters to use
    "plot_tdc_histograms": False,
    "pixels": [(30, 30), ]  # list of (col,row) tupel of pixels to use
}


class HitOrScan(ScanBase):
    scan_identifier = "hit_or_scan"

    def get_dc_and_mask_step(self, column, row):
        ''' Returns the double columns and the mask step for the given pixel in column, row coordinates '''
        return column / 2, 335 + row if column % 2 == 0 else row - 1

    def activate_tdc(self):
        self.readout_utils.configure_tdc_fsm(enable_tdc=True, enable_tdc_arming=True)

    def deactivate_tdc(self):
        self.readout_utils.configure_tdc_fsm(enable_tdc=False, enable_tdc_arming=True)

    def scan(self, pixels, reject_small_tot=False, repeat_command=100, scan_parameter='PlsrDAC', scan_parameter_values=(55, 100, 150, 250), **kwarg):
        '''Scan loop

        Parameters
        ----------
        repeat_command : int
            Number of injections per scan step.
        scan_parameter : string
            Name of global register.
        scan_parameter_range : list, tuple
            Specify the minimum and maximum value for scan parameter range. Upper value not included.
        scan_parameter_stepsize : int
            The minimum step size of the parameter. Used when start condition is not triggered.
        '''

        self.deactivate_tdc()

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter, 'column', 'row']) as raw_data_file:
            for pixel in pixels:
                column = pixel[0]
                row = pixel[1]
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

                    double_column, mask_step = self.get_dc_and_mask_step(column=column, row=row)  # translate the selected pixel into DC, mask_step info to be able to used the scan_loop

                    cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=12000)[0]
                    self.scan_loop(cal_lvl1_command, bol_function=self.activate_tdc, eol_function=self.deactivate_tdc, repeat_command=repeat_command, use_delay=True, hardware_repeat=True, mask_steps=672, enable_mask_steps=[mask_step], enable_double_columns=[double_column], same_mask_for_all_dc=False, digital_injection=False, enable_c_high=None, enable_c_low=None, disable_shift_masks=["Imon"], enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=None)

                    self.readout.stop(timeout=10)

                    # saving data
                    raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value, 'column': column, 'row': row})

    def analyze(self):
        logging.info('Analyze and plot results')

        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:  # interpreting results
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)

        with tb.openFile(scan.scan_data_filename + "_calibration.h5", mode="w") as calibration_data_file:  # creation of a calibration: charge [PlsrDAC] <-> TOT [ns] per pixel; TOT is taken from the discrete hit tot info and the Oszi histogram
            output_pdf = PdfPages(scan.scan_data_filename + "_calibration.pdf")
            logging.info('Calculate mean TOT from hit info and TDC')
            with tb.openFile(self.scan_data_filename + "_interpreted.h5", mode="r+") as in_hit_file_h5:  # open interpreted data file to access the hit table for tot histograming
                analysis_utils.index_event_number(in_hit_file_h5.root.Hits)  # create index to efficiently work on data based on event numbers
                meta_data_array = in_hit_file_h5.root.meta_data[:]  # get the meta data array to select be able to select hits per scan parameter
                scan_parameter_values = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array, selected_columns_only=True)  # get the PlsrDAC/col/row values
                event_numbers = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array)['event_number']  # get the event numbers in meta_data where the scan parameters have different settings
                parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_ranges_from_array(event_numbers)))  # list with entries [scan_parameter_value, start_event_number, stop_event_number]
                calibration_data = np.zeros(shape=(80, 336, len(scan_configuration['scan_parameter_values']), 4), dtype='f4')  # result of the calibration is a histogram with col_index, row_index, plsrDAC value, mean discrete tot, rms discrete tot, mean tot from TDC, rms tot from TDC
                start_index = 0
                for scan_parameter_value, start_event_number, stop_event_number in parameter_ranges:  # loop over the different PlsrDAC/col/row settings
                    column = scan_parameter_value[1]
                    row = scan_parameter_value[2]
                    logging.info("Analyze TDC words for pixel " + str(column) + "/" + str(row) + " and PlsrDAC " + str(scan_parameter_value[0]))
                    scan_parameter_index = scan_configuration['scan_parameter_values'].index(scan_parameter_value[0])  # translate the scan parameter value to an index for the result histogram
                    tot_mean = []
                    tdc_mean = []
                    for index, (hits, start_index) in enumerate(analysis_utils.data_aligned_at_events(in_hit_file_h5.root.Hits, start_event_number=start_event_number, stop_event_number=stop_event_number, start=start_index)):  # loop over hits for one PlsrDAC setting in chunks
                        if index > 0:
                            logging.warning('Did not read the data of a parameter setting in one chunk, the calculated mean and RMS values will be wrong')
                            break
                        tot_mean.append(np.mean(hits["tot"]))
                        tdc_mean.append(np.mean(hits["TDC"]))
                        tot_std = np.std(hits["tot"])
                        tdc_std = np.std(hits["TDC"])
                        if scan_configuration['plot_tdc_histograms']:
                            plotting.plot_1d_hist(np.histogram(hits["TDC"], range=(0, 255), bins=256)[0], title="TDC histogram for pixel " + str(column) + "/" + str(row) + " and PlsrDAC " + str(scan_parameter_value[0]), x_axis_title="TDC", y_axis_title="#", filename=output_pdf)

                    calibration_data[column - 1, row - 1, scan_parameter_index, 0] = tot_mean[0]  # just add data of the selected pixel
                    calibration_data[column - 1, row - 1, scan_parameter_index, 1] = tot_std
                    calibration_data[column - 1, row - 1, scan_parameter_index, 2] = tdc_mean[0]  # just add data of the selected pixel
                    calibration_data[column - 1, row - 1, scan_parameter_index, 3] = tdc_std
                self.plot_calibration(plsrdac=scan_configuration['scan_parameter_values'], calibration_data=calibration_data, filename=output_pdf)
                calibration_data_out = calibration_data_file.createCArray(calibration_data_file.root, name='HitOrCalibration', title='Hit OR calibration data', atom=tb.Atom.from_dtype(calibration_data.dtype), shape=calibration_data.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                calibration_data_out[:] = calibration_data
            output_pdf.close()

    def plot_calibration(self, plsrdac, calibration_data, filename=None):
        for pixel in scan_configuration['pixels']:
            column = pixel[0]
            row = pixel[1]
            logging.info("Plot calibration for pixel " + str(column) + '/' + str(row))
            plt.errorbar(plsrdac, calibration_data[column - 1, row - 1, :, 0] * 25. + 25., yerr=[calibration_data[column - 1, row - 1, :, 1] * 25, calibration_data[column - 1, row - 1, :, 1] * 25], fmt='o')
            plt.errorbar(plsrdac, calibration_data[column - 1, row - 1, :, 2], yerr=[calibration_data[column - 1, row - 1, :, 3], calibration_data[column - 1, row - 1, :, 3]], fmt='o')
            plt.title('Calibration for pixel ' + str(column) + '/' + str(row) + '; ' + str(scan_configuration['repeat_command']) + ' injections per PlsrDAC')
            plt.xlabel('charge [PlsrDAC]')
            plt.ylabel('TOT')
            plt.grid(True)
            plt.legend(['hit tot [ns]', 'TDC tot [TDC]'], loc=0)
            if filename is None:
                plt.show()
            elif type(filename) == PdfPages:
                filename.savefig()
            else:
                plt.savefig(filename)
            plt.close()


if __name__ == "__main__":
    import configuration
    scan = HitOrScan(**configuration.scc99_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()
