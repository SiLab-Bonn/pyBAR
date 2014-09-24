''' The speed up version of the normal threshold scan where the first and the last PlsrDAC setting is determined automatically to minimize the scan time. The step size is changed automatically.
'''
import numpy as np
import logging
from scan.scan import ScanBase
from daq.readout import get_col_row_array_from_data_record_array, convert_data_array, is_data_record, data_array_from_data_iterable
from analysis.analyze_raw_data import AnalyzeRawData
from fei4.register_utils import invert_pixel_mask
from scan.scan_utils import scan_loop

from scan.run_manager import RunManager


class FastThresholdScan(ScanBase):
    _scan_id = "fast_threshold_scan"
    _default_scan_configuration = {
        "n_injections": 100,  # how often one injects per PlsrDAC setting and pixel
        "scan_parameters": {'PlsrDAC': (None, 100)},  # the min/max PlsrDAC values used during scan
        "mask_steps": 3,  # define how many pixels are injected to at once, 3 means every 3rd pixel of a double column
        "enable_mask_steps": None,  # list of the mask steps to be used; None: use all pixels
        "step_size": 2,  # the increase of the PlstrDAC if the Scurve start was found
        "search_distance": 10,  # the increase of the PlstrDAC if the Scurve start is not found yet
        "minimum_data_points": 20,  # the minimum PlsrDAC settings for one S-Curve
        "ignore_columns": (1, 78, 79, 80),  # columns which data should be ignored
        "use_enable_mask": False
    }
    scan_parameter_start = 0  # holding last start value (e.g. used in GDAC threshold scan)

    def configure(self):
        pass

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        n_injections : int
            Number of injections per scan step.
        scan_parameters : dict
            Dictionary containing scan parameters.
        step_size : int
            The minimum step size of the parameter. Used when start condition is not triggered.
        search_distance : int
            The parameter step size if the start condition is not triggered.
        minimum_data_points : int
            The minimum data points that are taken for sure until scan finished. Saves also calculation time.
        ignore_columns : list, tuple
            All columns that are neither scanned nor taken into account to set the scan range are mentioned here. Usually the edge columns are ignored. From 1 to 80.
        use_enable_mask : bool
            Use enable mask for masking pixels.
        '''
        self.start_condition_triggered = False  # set to true if the start condition is true once
        self.stop_condition_triggered = False  # set to true if the stop condition is true once

        self.start_at = 0.01  # if more than start_at*activated_pixel see at least one hit the precise scanning is started
        self.stop_at = 0.99  # if more than stop_at*activated_pixel see the maximum numbers of injection, the scan is stopped

        self.record_data = False  # set to true to activate data storage, so far not everything is recorded to ease data analysis

        scan_parameter_range = [0, (2 ** self.register.get_global_register_objects(name=['PlsrDAC'])[0].bitlength)]
        if self.scan_parameters.PlsrDAC[0]:
            scan_parameter_range[0] = self.scan_parameters.PlsrDAC[0]
        if self.scan_parameters.PlsrDAC[1]:
            scan_parameter_range[1] = self.scan_parameters.PlsrDAC[1]
        logging.info("Scanning %s from %d to %d" % ('PlsrDAC', scan_parameter_range[0], scan_parameter_range[1]))
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
        logging.info("Use DCs: %s" % str(enable_double_columns))

        self.select_arr_columns = range(0, 80)
        for column in self.ignore_columns:
            self.select_arr_columns.remove(column - 1)

        while self.scan_parameter_value <= scan_parameter_range[1]:  # scan as long as scan parameter is smaller than defined maximum
            if self.stop_run.is_set():
                break
            if self.record_data:
                logging.info("Scan step %d (%s %d)" % (self.data_points, 'PlsrDAC', self.scan_parameter_value))

            commands = []
            commands.extend(self.register.get_commands("confmode"))
            self.register.set_global_register_value('PlsrDAC', self.scan_parameter_value)
            commands.extend(self.register.get_commands("wrregister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)

            with self.readout(PlsrDAC=self.scan_parameter_value):
                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
                scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=self.enable_mask_steps, enable_double_columns=enable_double_columns, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_Low", "C_High"], restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=False)

            if not self.start_condition_triggered or self.data_points > self.minimum_data_points:  # speed up, only create histograms when needed. Python is much too slow here.
                if not self.start_condition_triggered and not self.record_data:
                    logging.info('Testing for start condition: %s %d' % ('PlsrDAC', self.scan_parameter_value))
                if not self.stop_condition_triggered and self.record_data:
                    logging.info('Testing for stop condition: %s %d' % ('PlsrDAC', self.scan_parameter_value))
                occupancy_array = np.histogram2d(*convert_data_array(data_array_from_data_iterable(self.data_readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])[0]
                self.scan_condition(occupancy_array)

            # start condition is met for the first time
            if self.start_condition_triggered and not self.record_data:
                self.scan_parameter_value = self.scan_parameter_value - self.search_distance + self.step_size
                if self.scan_parameter_value < 0:
                    self.scan_parameter_value = 0
                logging.info('Starting threshold scan at %s %d' % ('PlsrDAC', self.scan_parameter_value))
                self.scan_parameter_start = self.scan_parameter_value
                self.record_data = True
                continue

            # saving data
            if self.record_data:
                self.data_points = self.data_points + 1
                self.raw_data_file.append(self.data_readout.data, scan_parameters={'PlsrDAC': self.scan_parameter_value})

            # stop condition is met for the first time
            if self.stop_condition_triggered and self.record_data:
                logging.info('Stopping threshold scan at %s %d' % ('PlsrDAC', self.scan_parameter_value))
                break

            # increase scan parameter value
            if not self.start_condition_triggered:
                self.scan_parameter_value = self.scan_parameter_value + self.search_distance
            else:
                self.scan_parameter_value = self.scan_parameter_value + self.step_size

        if self.scan_parameter_value >= scan_parameter_range[1]:
            logging.warning("Reached maximum of scan parameter range... stopping scan" % (scan_parameter_range[1],))

    def scan_condition(self, occupancy_array):
        occupancy_array_select = occupancy_array[self.select_arr_columns, :]  # only select not ignored columns
        # stop precise scanning actions
        pixels_with_full_hits = np.ma.array(occupancy_array_select, mask=(occupancy_array_select >= self.n_injections))  # select pixels that see all injections
        pixels_with_full_hits_count = np.ma.count_masked(pixels_with_full_hits)  # count pixels that see all injections
        stop_pixel_cnt = int(np.product(occupancy_array_select.shape) * self.stop_at)
        if pixels_with_full_hits_count >= stop_pixel_cnt and not self.stop_condition_triggered:  # stop precise scanning if this triggers
            logging.info("Triggering stop condition: %d pixel(s) with %d hits or more >= %d pixel(s)" % (pixels_with_full_hits_count, self.n_injections, stop_pixel_cnt))
            self.stop_condition_triggered = True
        # start precise scanning actions
        pixels_with_hits = np.ma.array(occupancy_array_select, mask=(occupancy_array_select != 0))  # select pixels that see at least one hit
        pixels_with_hits_count = np.ma.count_masked(pixels_with_hits)  # count pixels that see hits
        start_pixel_cnt = int(np.product(occupancy_array_select.shape) * self.start_at)
        if pixels_with_hits_count >= start_pixel_cnt and not self.start_condition_triggered:  # start precise scanning if this is true
            logging.info("Triggering start condition: %d pixel(s) with more than 0 hits >= %d pixel(s)" % (pixels_with_hits_count, start_pixel_cnt))
            self.start_condition_triggered = True

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.data_readout.start(reset_sram_fifo=True, clear_buffer=True, callback=None, errback=self.handle_err)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = self.n_injections
            analyze_raw_data.interpreter.set_warning_output(True)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()


if __name__ == "__main__":
    scan_mngr = RunManager('configuration.yaml')
    scan = FastThresholdScan(**scan_mngr.conf)
    scan()
