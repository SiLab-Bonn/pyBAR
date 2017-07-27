import logging
import numpy as np

from pybar_fei4_interpreter.analysis_utils import hist_2d_index

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.daq.readout_utils import get_col_row_array_from_data_record_array, convert_data_array, is_data_record, data_array_from_data_iterable


class FastThresholdScan(Fei4RunBase):
    '''Fast threshold scan

    Implementation of a fast threshold scan checking for start and end of s-curve.
    '''
    _default_run_conf = {
        "n_injections": 100,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', (None, 100))],  # the PlsrDAC range
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "enable_mask_steps": None,  # list of mask steps to be used, if None use all mask steps
        "step_size": 2,  # step size of the PlsrDAC during scan
        "search_distance": 10,  # step size of the PlsrDAC for testing start condition
        "minimum_data_points": 20,  # PlsrDAC before testing stop condition
        "ignore_columns": (1, 78, 79, 80),  # columns, which will be ignored during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False  # PlsrDAC correction for each double column
    }
    scan_parameter_start = 0  # holding last start value (e.g. used in GDAC threshold scan)

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        self.start_condition_triggered = False  # set to true if the start condition is true once
        self.stop_condition_triggered = False  # set to true if the stop condition is true once

        self.start_at = 0.01  # if more than start_at*activated_pixel see at least one hit the precise scanning is started
        self.stop_at = 0.95  # if more than stop_at*activated_pixel see the maximum numbers of injection, the scan is stopped

        self.record_data = False  # set to true to activate data storage, so far not everything is recorded to ease data analysis

        scan_parameter_range = [0, (2 ** self.register.global_registers['PlsrDAC']['bitlength'] - 1)]
        if self.scan_parameters.PlsrDAC[0]:
            scan_parameter_range[0] = self.scan_parameters.PlsrDAC[0]
        if self.scan_parameters.PlsrDAC[1]:
            scan_parameter_range[1] = self.scan_parameters.PlsrDAC[1]
        logging.info("Scanning %s from %d to %d", 'PlsrDAC', scan_parameter_range[0], scan_parameter_range[1])
        self.scan_parameter_value = scan_parameter_range[0]  # set to start value
        self.search_distance = self.search_distance
        self.data_points = 0  # counter variable to count the data points already recorded, have to be at least minimum_data_ponts

        # calculate DCs to scan from the columns to ignore
        enable_double_columns = range(0, 40)
        if 1 in self.ignore_columns:
            enable_double_columns.remove(0)
        if set((78, 79, 80)).issubset(self.ignore_columns):
            enable_double_columns.remove(39)
        for double_column in range(1, 39):
            if set((double_column * 2, (double_column * 2) + 1)).issubset(self.ignore_columns):
                enable_double_columns.remove(double_column)
        logging.info("Use DCs: %s", str(enable_double_columns))

        self.select_arr_columns = range(0, 80)
        for column in self.ignore_columns:
            self.select_arr_columns.remove(column - 1)

        while self.scan_parameter_value <= scan_parameter_range[1]:  # scan as long as scan parameter is smaller than defined maximum
            if self.stop_run.is_set():
                break

            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value('PlsrDAC', self.scan_parameter_value)
            commands.extend(self.register.get_commands("WrRegister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)

            with self.readout(PlsrDAC=self.scan_parameter_value, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data if self.record_data else None):
                cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=self.enable_mask_steps, enable_double_columns=enable_double_columns, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

            if not self.start_condition_triggered or self.data_points > self.minimum_data_points:  # speed up, only create histograms when needed. Python is much too slow here.
                if not self.start_condition_triggered and not self.record_data:
                    logging.info('Testing for start condition: %s %d', 'PlsrDAC', self.scan_parameter_value)
                if not self.stop_condition_triggered and self.record_data:
                    logging.info('Testing for stop condition: %s %d', 'PlsrDAC', self.scan_parameter_value)

                col, row = convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)
                if np.any(np.logical_and(col < 1, col > 80)) or np.any(np.logical_and(row < 1, row > 336)):  # filter bad data records that can happen
                    logging.warning('There are undefined %d data records (e.g. random data)', np.count_nonzero(np.logical_and(col < 1, col > 80)) + np.count_nonzero(np.logical_and(row < 1, row > 336)))
                    col, row = col[np.logical_and(col > 0, col <= 80)], row[np.logical_and(row > 0, row <= 336)]
                occupancy_array = hist_2d_index(col - 1, row - 1, shape=(80, 336))
                self.scan_condition(occupancy_array)

            # start condition is met for the first time
            if self.start_condition_triggered and not self.record_data:
                self.scan_parameter_value = self.scan_parameter_value - self.search_distance + self.step_size
                if self.scan_parameter_value < 0:
                    self.scan_parameter_value = 0
                logging.info('Starting threshold scan at %s %d', 'PlsrDAC', self.scan_parameter_value)
                self.scan_parameter_start = self.scan_parameter_value
                self.record_data = True
                continue

            # saving data
            if self.record_data:
                self.data_points = self.data_points + 1

            # stop condition is met for the first time
            if self.stop_condition_triggered and self.record_data:
                logging.info('Stopping threshold scan at %s %d', 'PlsrDAC', self.scan_parameter_value)
                break

            # increase scan parameter value
            if not self.start_condition_triggered:
                self.scan_parameter_value = self.scan_parameter_value + self.search_distance
            else:
                self.scan_parameter_value = self.scan_parameter_value + self.step_size

        if self.scan_parameter_value >= scan_parameter_range[1]:
            logging.warning("Reached maximum of PlsrDAC range... stopping scan")

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = self.n_injections
            analyze_raw_data.interpreter.set_warning_output(True)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()

    def scan_condition(self, occupancy_array):
        occupancy_array_select = occupancy_array[self.select_arr_columns, :]  # only select not ignored columns
        # stop precise scanning actions
        pixels_with_full_hits = np.ma.array(occupancy_array_select, mask=(occupancy_array_select >= self.n_injections))  # select pixels that see all injections
        pixels_with_full_hits_count = np.ma.count_masked(pixels_with_full_hits)  # count pixels that see all injections
        stop_pixel_cnt = int(np.product(occupancy_array_select.shape) * self.stop_at)
        if pixels_with_full_hits_count >= stop_pixel_cnt and not self.stop_condition_triggered:  # stop precise scanning if this triggers
            logging.info("Triggering stop condition: %d pixel(s) with %d hits or more >= %d pixel(s)", pixels_with_full_hits_count, self.n_injections, stop_pixel_cnt)
            self.stop_condition_triggered = True
        # start precise scanning actions
        pixels_with_hits = np.ma.array(occupancy_array_select, mask=(occupancy_array_select != 0))  # select pixels that see at least one hit
        pixels_with_hits_count = np.ma.count_masked(pixels_with_hits)  # count pixels that see hits
        start_pixel_cnt = int(np.product(occupancy_array_select.shape) * self.start_at)
        if pixels_with_hits_count >= start_pixel_cnt and not self.start_condition_triggered:  # start precise scanning if this is true
            logging.info("Triggering start condition: %d pixel(s) with more than 0 hits >= %d pixel(s)", pixels_with_hits_count, start_pixel_cnt)
            self.start_condition_triggered = True

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(FastThresholdScan)
