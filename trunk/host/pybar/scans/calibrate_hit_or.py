"""A script that changes a scan parameter (usually PlsrDAC) in a certain range for selected pixels and measures the length of the hit OR signal with the FPGA TDC.
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
from fei4.register_utils import make_pixel_mask_from_col_row, make_box_pixel_mask_from_col_row

import logging


local_configuration = {
    "repeat_command": 10000,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_values": [i for j in (range(40, 70, 5), range(70, 100, 10), range(100, 600, 20), range(600, 801, 40)) for i in j],  # list of scan parameters to use
    "plot_tdc_histograms": False,
    "pixels": (np.dstack(np.where(make_box_pixel_mask_from_col_row([40, 40], [150, 150]) == 1)) + 1)[0],  # list of (col, row) tupels. From 1 to 80/336.
    "enable_masks": ["Enable", "C_Low", "C_High"],
    "disable_masks": ["Imon"]
}


class HitOrCalibration(ScanBase):
    scan_id = "hit_or_calibration"

    def scan(self):
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
        def write_double_column(column):
            return (column - 1) / 2

        def inject_double_column(column):
            if column == 80:
                return 39
            else:
                return (column) / 2

        cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=600)[0]
        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id, scan_parameters=[self.scan_parameter, 'column', 'row']) as raw_data_file:
            for index, pixel in enumerate(self.pixels):
                column = pixel[0]
                row = pixel[1]
                logging.info('Scanning pixel: %d / %d (column / row)' % (column, row))
                if index:
                    dcs = [write_double_column(column)]
                    dcs.append(write_double_column(self.pixels[index - 1][0]))
                else:
                    dcs = []
                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                single_pixel_enable_mask = make_pixel_mask_from_col_row([column], [row])
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, single_pixel_enable_mask), self.enable_masks)
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=self.enable_masks))
                single_pixel_disable_mask = make_pixel_mask_from_col_row([column], [row], default=1, value=0)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, single_pixel_disable_mask), self.disable_masks)
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=self.disable_masks))
                self.register.set_global_register_value("Colpr_Addr", inject_double_column(column))
                commands.append(self.register.get_commands("WrRegister", name=["Colpr_Addr"])[0])
                self.register_utils.send_commands(commands)
                for scan_parameter_value in self.scan_parameter_values:
                    if self.stop_thread_event.is_set():
                        break
                    logging.info('Scan step: %s %d' % (self.scan_parameter, scan_parameter_value))

                    commands = []
                    commands.extend(self.register.get_commands("ConfMode"))
                    self.register.set_global_register_value(self.scan_parameter, scan_parameter_value)
                    commands.extend(self.register.get_commands("WrRegister", name=[self.scan_parameter]))
                    commands.extend(self.register.get_commands("RunMode"))
                    self.register_utils.send_commands(commands)
                    # activate TDC arming
                    self.dut['tdc_rx2']['EN_ARMING'] = True
                    self.readout.start()
                    self.dut['tdc_rx2']['ENABLE'] = True
                    self.register_utils.send_command(command=cal_lvl1_command, repeat=self.repeat_command)
                    self.dut['tdc_rx2']['ENABLE'] = False
                    self.readout.stop()

                    # saving data
                    raw_data_file.append(self.readout.data, scan_parameters={self.scan_parameter: scan_parameter_value, 'column': column, 'row': row})

    def analyze(self):
        logging.info('Analyze and plot results')

        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:  # interpreting results
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_tdc_hist = True
            analyze_raw_data.interpreter.use_tdc_word(True)  # align events at TDC words, first word of event has to be a tdc word
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)

        with tb.openFile(self.scan_data_filename + "_calibration.h5", mode="w") as calibration_data_file:  # creation of a calibration: charge [PlsrDAC] <-> TOT [ns] per pixel; TOT is taken from the discrete hit tot info and the Oszi histogram
            output_pdf = PdfPages(self.scan_data_filename + "_calibration.pdf")
            logging.info('Calculate mean TOT from hit info and TDC')
            with tb.openFile(self.scan_data_filename + "_interpreted.h5", mode="r+") as in_hit_file_h5:  # open interpreted data file to access the hit table for tot histograming
                analysis_utils.index_event_number(in_hit_file_h5.root.Hits)  # create index to efficiently work on data based on event numbers
                meta_data_array = in_hit_file_h5.root.meta_data[:]  # get the meta data array to select be able to select hits per scan parameter
                scan_parameter_values = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array, scan_parameter_columns_only=True)  # get the PlsrDAC/col/row values
                event_numbers = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array)['event_number']  # get the event numbers in meta_data where the scan parameters have different settings
                plsr_dacs = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array, scan_parameters=['PlsrDAC'], scan_parameter_columns_only=True)['PlsrDAC']
                parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_ranges_from_array(event_numbers)))  # list with entries [scan_parameter_value, start_event_number, stop_event_number]
                calibration_data = np.zeros(shape=(80, 336, plsr_dacs.shape[0], 4), dtype='f4')  # result of the calibration is a histogram with col_index, row_index, plsrDAC value, mean discrete tot, rms discrete tot, mean tot from TDC, rms tot from TDC
                start_index = 0
                for scan_parameter_value, start_event_number, stop_event_number in parameter_ranges:  # loop over the different PlsrDAC/col/row settings
                    column = scan_parameter_value[1]
                    row = scan_parameter_value[2]
                    logging.info("Analyze TDC words for pixel " + str(column) + "/" + str(row) + " and PlsrDAC " + str(scan_parameter_value[0]))
                    scan_parameter_index = np.where(plsr_dacs == scan_parameter_value[0])  # translate the scan parameter value to an index for the result histogram
                    tot_mean = []
                    tdc_mean = []
                    for index, (hits, start_index) in enumerate(analysis_utils.data_aligned_at_events(in_hit_file_h5.root.Hits, start_event_number=start_event_number, stop_event_number=stop_event_number, start=start_index)):  # loop over hits for one PlsrDAC setting in chunks
                        if index > 0:
                            logging.warning('Did not read the data of a parameter setting in one chunk, the calculated mean and RMS values will be wrong')
                            break
                        hits = hits[(hits['event_status'] & 0b0000011110001000) == 0b0000000100000000]   # only take hits from good events (one TDC word only, no error)
                        tot_mean.append(np.mean(hits["tot"]))
                        tdc_mean.append(np.mean(hits["TDC"]))
                        tot_std = np.std(hits["tot"])
                        tdc_std = np.std(hits["TDC"])
                        if self.plot_tdc_histograms:
                            plotting.plot_1d_hist(np.histogram(hits["TDC"], range=(0, 4095), bins=4096)[0], title="TDC histogram for pixel " + str(column) + "/" + str(row) + " and PlsrDAC " + str(scan_parameter_value[0]) + " (" + str(len(hits["TDC"])) + " entrie(s))", x_axis_title="TDC", y_axis_title="#", filename=output_pdf)

                    if len(tot_mean) != 0:
                        calibration_data[column - 1, row - 1, scan_parameter_index, 0] = tot_mean[0]  # just add data of the selected pixel
                        calibration_data[column - 1, row - 1, scan_parameter_index, 1] = tot_std
                        calibration_data[column - 1, row - 1, scan_parameter_index, 2] = tdc_mean[0]  # just add data of the selected pixel
                        calibration_data[column - 1, row - 1, scan_parameter_index, 3] = tdc_std
                    else:
                        logging.warning('No hits found, omit histograming')
                self.plot_calibration(plsrdac=plsr_dacs, calibration_data=calibration_data, filename=output_pdf)
                calibration_data_out = calibration_data_file.createCArray(calibration_data_file.root, name='HitOrCalibration', title='Hit OR calibration data', atom=tb.Atom.from_dtype(calibration_data.dtype), shape=calibration_data.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                calibration_data_out[:] = calibration_data
            output_pdf.close()

    def plot_calibration(self, plsrdac, calibration_data, filename=None):
        for pixel in self.pixels:
            column = pixel[0]
            row = pixel[1]
            logging.info("Plot calibration for pixel " + str(column) + '/' + str(row))
            plt.errorbar(plsrdac, calibration_data[column - 1, row - 1, :, 0] * 25. + 25., yerr=[calibration_data[column - 1, row - 1, :, 1] * 25, calibration_data[column - 1, row - 1, :, 1] * 25], fmt='o')
            plt.errorbar(plsrdac, calibration_data[column - 1, row - 1, :, 2], yerr=[calibration_data[column - 1, row - 1, :, 3], calibration_data[column - 1, row - 1, :, 3]], fmt='o')
            plt.title('Calibration for pixel ' + str(column) + '/' + str(row) + '; ' + str(self.repeat_command) + ' injections per PlsrDAC')
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
    scan = HitOrCalibration(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=False, **local_configuration)
    scan.stop()
