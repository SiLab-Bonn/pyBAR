"""A script that changes a scan parameter (usually PlsrDAC, innermost loop) in a certain range for selected pixels and measures the length of the HitOR signal with ToT and TDC method.
The TDC method gives higher precision charge information than the TOT method. The TDC method is limited to single pixel cluster. During the calibration only one pixel is enabled at a time.
"""
import logging
import os.path
import zlib

import numpy as np
import tables as tb

import progressbar

from pybar.fei4.register_utils import make_pixel_mask_from_col_row, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.analysis_utils import get_scan_parameter, get_unique_scan_parameter_combinations, get_scan_parameters_table_from_meta_data, get_ranges_from_array
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_scurves, plot_tot_tdc_calibration
from pybar.daq import readout_utils


def create_hitor_calibration(output_filename, plot_pixel_calibrations=False):
    '''Generating HitOr calibration file (_calibration.h5) from raw data file and plotting of calibration data.

    Parameters
    ----------
    output_filename : string
        Input raw data file name.
    plot_pixel_calibrations : bool, iterable
        If True, genearating additional pixel calibration plots. If list of column and row tuples (from 1 to 80 / 336), print selected pixels.

    Returns
    -------
    nothing
    '''
    logging.info('Analyze HitOR calibration data and plot results of %s', output_filename)

    with AnalyzeRawData(raw_data_file=output_filename, create_pdf=True) as analyze_raw_data:  # Interpret the raw data file
        analyze_raw_data.create_occupancy_hist = False  # too many scan parameters to do in ram histogramming
        analyze_raw_data.create_hit_table = True
        analyze_raw_data.create_tdc_hist = True
        analyze_raw_data.align_at_tdc = True  # align events at TDC words, first word of event has to be a tdc word
        analyze_raw_data.interpret_word_table()
        analyze_raw_data.interpreter.print_summary()
        analyze_raw_data.plot_histograms()
        n_injections = analyze_raw_data.n_injections  # use later

        meta_data = analyze_raw_data.out_file_h5.root.meta_data[:]
        scan_parameters_dict = get_scan_parameter(meta_data)
        inner_loop_parameter_values = scan_parameters_dict[next(reversed(scan_parameters_dict))]  # inner loop parameter name is unknown
        scan_parameter_names = scan_parameters_dict.keys()
#         col_row_combinations = get_unique_scan_parameter_combinations(analyze_raw_data.out_file_h5.root.meta_data[:], scan_parameters=('column', 'row'), scan_parameter_columns_only=True)

        meta_data_table_at_scan_parameter = get_unique_scan_parameter_combinations(meta_data, scan_parameters=scan_parameter_names)
        scan_parameter_values = get_scan_parameters_table_from_meta_data(meta_data_table_at_scan_parameter, scan_parameter_names)
        event_number_ranges = get_ranges_from_array(meta_data_table_at_scan_parameter['event_number'])
        event_ranges_per_parameter = np.column_stack((scan_parameter_values, event_number_ranges))
        hits = analyze_raw_data.out_file_h5.root.Hits[:]
        event_numbers = hits['event_number'].copy()  # create contigous array, otherwise np.searchsorted too slow, http://stackoverflow.com/questions/15139299/performance-of-numpy-searchsorted-is-poor-on-structured-arrays

        output_filename = os.path.splitext(output_filename)[0]
        with tb.open_file(output_filename + "_calibration.h5", mode="w") as calibration_data_file:
            logging.info('Create calibration')
            calibration_data = np.empty(shape=(80, 336, len(inner_loop_parameter_values), 4), dtype='f4')  # result of the calibration is a histogram with col_index, row_index, plsrDAC value, mean discrete tot, rms discrete tot, mean tot from TDC, rms tot from TDC
            calibration_data.fill(np.nan)

            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(event_ranges_per_parameter), term_width=80)
            progress_bar.start()

            for index, (actual_scan_parameter_values, event_start, event_stop) in enumerate(event_ranges_per_parameter):
                if event_stop is None:  # happens for the last chunk
                    event_stop = hits[-1]['event_number'] + 1
                array_index = np.searchsorted(event_numbers, np.array([event_start, event_stop]))
                actual_hits = hits[array_index[0]:array_index[1]]
                for item_index, item in enumerate(scan_parameter_names):
                    if item == "column":
                        actual_col = actual_scan_parameter_values[item_index]
                    elif item == "row":
                        actual_row = actual_scan_parameter_values[item_index]
                    elif item == "PlsrDAC":
                        plser_dac = actual_scan_parameter_values[item_index]
                    else:
                        raise ValueError("Unknown scan parameter %s" % item)

                # Only pixel of actual column/row should be in the actual data chunk but since SRAM is not cleared for each scan step due to speed reasons and there might be noisy pixels this is not always the case
                n_wrong_pixel = np.count_nonzero(np.logical_or(actual_hits['column'] != actual_col, actual_hits['row'] != actual_row))
                if n_wrong_pixel != 0:
                    logging.warning('%d hit(s) from other pixels for scan parameters %s', n_wrong_pixel, ', '.join(['%s=%s' % (name, value) for (name, value) in zip(scan_parameter_names, actual_scan_parameter_values)]))

                actual_hits = actual_hits[np.logical_and(actual_hits['column'] == actual_col, actual_hits['row'] == actual_row)]  # Only take data from selected pixel
                actual_tdc_hits = actual_hits[(actual_hits['event_status'] & 0b0000111110011100) == 0b0000000100000000]  # only take hits from good events (one TDC word only, no error)
                actual_tot_hits = actual_hits[(actual_hits['event_status'] & 0b0000100010011100) == 0b0000000000000000]  # only take hits from good events for tot
                tot, tdc = actual_tot_hits['tot'], actual_tdc_hits['TDC']

                if tdc.shape[0] < n_injections:
                    logging.info('%d of %d expected TDC hits for scan parameters %s', tdc.shape[0], n_injections, ', '.join(['%s=%s' % (name, value) for (name, value) in zip(scan_parameter_names, actual_scan_parameter_values)]))
                if tot.shape[0] < n_injections:
                    logging.info('%d of %d expected hits for scan parameters %s', tot.shape[0], n_injections, ', '.join(['%s=%s' % (name, value) for (name, value) in zip(scan_parameter_names, actual_scan_parameter_values)]))

                inner_loop_scan_parameter_index = np.where(plser_dac == inner_loop_parameter_values)[0][0]  # translate the scan parameter value to an index for the result histogram
                # numpy mean and std return nan if array is empty
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 0] = np.mean(tot)
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 1] = np.mean(tdc)
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 2] = np.std(tot)
                calibration_data[actual_col - 1, actual_row - 1, inner_loop_scan_parameter_index, 3] = np.std(tdc)

                progress_bar.update(index)
            progress_bar.finish()

            calibration_data_out = calibration_data_file.createCArray(calibration_data_file.root, name='HitOrCalibration', title='Hit OR calibration data', atom=tb.Atom.from_dtype(calibration_data.dtype), shape=calibration_data.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            calibration_data_out[:] = calibration_data
            calibration_data_out.attrs.dimensions = scan_parameter_names
            calibration_data_out.attrs.scan_parameter_values = inner_loop_parameter_values
            calibration_data_out.flush()
#             with PdfPages(output_filename + "_calibration.pdf") as output_pdf:
            plot_scurves(calibration_data[:, :, :, 0], inner_loop_parameter_values, "ToT calibration", "ToT", 15, "Charge [PlsrDAC]", filename=analyze_raw_data.output_pdf)
            plot_scurves(calibration_data[:, :, :, 1], inner_loop_parameter_values, "TDC calibration", "TDC [ns]", None, "Charge [PlsrDAC]", filename=analyze_raw_data.output_pdf)
            tot_mean_all_pix = np.nanmean(calibration_data[:, :, :, 0], axis=(0, 1))
            tot_error_all_pix = np.nanstd(calibration_data[:, :, :, 0], axis=(0, 1))
            tdc_mean_all_pix = np.nanmean(calibration_data[:, :, :, 1], axis=(0, 1))
            tdc_error_all_pix = np.nanstd(calibration_data[:, :, :, 1], axis=(0, 1))
            plot_tot_tdc_calibration(scan_parameters=inner_loop_parameter_values, tot_mean=tot_mean_all_pix, tot_error=tot_error_all_pix, tdc_mean=tdc_mean_all_pix, tdc_error=tdc_error_all_pix, filename=analyze_raw_data.output_pdf, title="Mean charge calibration of %d pixel(s)" % np.count_nonzero(~np.all(np.isnan(calibration_data[:, :, :, 0]), axis=2)))
            # plotting individual pixels
            if plot_pixel_calibrations is True:
                col_row_non_nan = np.nonzero(~np.all(np.isnan(calibration_data[:, :, :, 0]), axis=2))
                plot_pixel_calibrations = np.dstack(col_row_non_nan)[0]
            elif plot_pixel_calibrations is False:
                plot_pixel_calibrations = []
            else:  # assuming list of column / row tuples
                plot_pixel_calibrations = np.array(plot_pixel_calibrations) - 1
            for index, (column, row) in enumerate(plot_pixel_calibrations):
                if index >= 100:  # stop for too many plots
                    logging.info('Reached the limit of 100 pages')
                    break
                logging.info("Plotting charge calibration for pixel column " + str(column + 1) + " / row " + str(row + 1))
                tot_mean_single_pix = calibration_data[column, row, :, 0]
                tot_std_single_pix = calibration_data[column, row, :, 2]
                tdc_mean_single_pix = calibration_data[column, row, :, 1]
                tdc_std_single_pix = calibration_data[column, row, :, 3]
                plot_tot_tdc_calibration(scan_parameters=inner_loop_parameter_values, tot_mean=tot_mean_single_pix, tot_error=tot_std_single_pix, tdc_mean=tdc_mean_single_pix, tdc_error=tdc_std_single_pix, filename=analyze_raw_data.output_pdf, title="Charge calibration for pixel column " + str(column + 1) + " / row " + str(row + 1))


class HitOrCalibration(Fei4RunBase):
    ''' HitOR calibration scan
    '''
    _default_run_conf = {
        "n_injections": 200,  # number of injections
        "injection_delay": 5000,  # for really low feedbacks (ToT >> 300 ns) one needs to increase the injection delay
        "scan_parameters": [('column', None),
                            ('row', None),
                            ('PlsrDAC', [30, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800])],  # 0 400 sufficient for most tunings
        "reset_rx_on_error": True,  # reset RX on errors that may occur during scan
        "pixels": (np.dstack(np.where(make_box_pixel_mask_from_col_row([2, 80], [1, 336 ]) == 1)) + 1).tolist()[0],  # list of (col, row) tupels. From 1 to 80/336.
        "enable_shift_masks": ["Enable", "C_Low", "C_High"],  # enable masks shifted during scan
        "disable_shift_masks": ["Imon"],  # disable masks shifted during scan
    }
    channel=1    #Which chip do you want to calibrate: 1-5?
    if channel == 1:
        tdc="TDC"
    elif channel == 2:
        tdc="TDC1"
    elif channel == 3:
        tdc="TDC2"
    elif channel == 4:
        tdc="TDC3"
    elif channel == 5:
        tdc="TDC4"
    else:
        print"Channel out of range"
    print "You are using", tdc


    def is_tdc_from_channel(self, value):  # function factory
        if self.channel == 1:
            return np.equal(np.bitwise_and(value, 0xF0000000), 0x10000000)
        if self.channel == 2:
            return np.equal(np.bitwise_and(value, 0xF0000000), 0x20000000)
        if self.channel == 3:
            return np.equal(np.bitwise_and(value, 0xF0000000), 0x30000000)
        if self.channel == 4:
            return np.equal(np.bitwise_and(value, 0xF0000000), 0x40000000)
        if self.channel == 5:
            return np.equal(np.bitwise_and(value, 0xF0000000), 0x50000000)


    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("Trig_Count", 6)  # decrease trigger count to reduce data
        self.register.set_global_register_value("Trig_Lat", 215)  # adjust delay for smaller bcid window
        self.register.set_global_register_value("ErrorMask", 1536) # deactivate hit bus service record
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
        scan_parameter_name = self.scan_parameters._fields[-1]  # scan parameter is in inner loop
        scan_parameter_values = self.scan_parameters[-1][:]  # create deep copy of scan_parameters, they are overwritten in self.readout

        pixels_sorted = sorted(self.pixels)  # , key=lambda tup: tup[0])
        logging.info("Scanning %d pixels" % len(self.pixels))
        # use sorted pixels to prevent overwriting of raw data file when writing a file per column
        for pixel_index, pixel in enumerate(pixels_sorted):
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
            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, single_pixel_enable_mask), self.enable_shift_masks)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=self.enable_shift_masks, joint_write=True))
            single_pixel_disable_mask = make_pixel_mask_from_col_row([column], [row], default=1, value=0)
            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, single_pixel_disable_mask), self.disable_shift_masks)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=self.disable_shift_masks, joint_write=True))
            self.register.set_global_register_value("Colpr_Addr", inject_double_column(column))
            commands.append(self.register.get_commands("WrRegister", name=["Colpr_Addr"])[0])
            self.register_utils.send_commands(commands)

            self.dut[self.tdc]['ENABLE'] = True
            self.dut[self.tdc]['EN_NO_WRITE_TRIG_ERR'] = False  # Do not trigger TDC words
            for scan_parameter_value in scan_parameter_values:
                if self.stop_run.is_set():
                    break

                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                self.register.set_global_register_value(scan_parameter_name, scan_parameter_value)
                commands.extend(self.register.get_commands("WrRegister", name=[scan_parameter_name]))
                commands.extend(self.register.get_commands("RunMode"))
                self.register_utils.send_commands(commands)

                self.dut[self.tdc]['EN_ARMING'] = True
                with self.readout(reset_sram_fifo=False, clear_buffer=False, column=column, row=row, **{scan_parameter_name: scan_parameter_value}):
                    self.register_utils.send_command(command=cal_lvl1_command, repeat=self.n_injections)
                self.dut[self.tdc]['EN_ARMING'] = False

            self.dut[self.tdc]['ENABLE'] = False




    def handle_data(self, data):
        filter_ch0 = readout_utils.logical_or(readout_utils.is_trigger_word, readout_utils.logical_or(readout_utils.logical_and(readout_utils.is_fe_word, readout_utils.is_data_from_channel(1)), self.is_tdc_from_channel))
        data_ch0 = readout_utils.convert_data_iterable([data], filter_func=filter_ch0, converter_func=None)
        select = np.greater(np.bitwise_and(data_ch0[0][0], 0b01110000000000000000000000000000), 0)
        data_ch0[0][0][select] = np.bitwise_and(data_ch0[0][0][select], 0x0FFFFFFF)
        data_ch0[0][0][select] = np.bitwise_or(data_ch0[0][0][select], 0x40000000)
        self.raw_data_file.append_item(data_ch0[0], scan_parameters=self.scan_parameters._asdict(), new_file=['column'], flush=True)
        #self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), new_file=['column'], flush=True)  # Create new file for each scan parameter change

    def analyze(self):
        create_hitor_calibration(self.output_filename, plot_pixel_calibrations=True)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(HitOrCalibration)
