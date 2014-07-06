''' The speed up version of the normal threshold scan where the first and the last PlsrDAC setting is determined automatically to minimize the scan time. The step size is changed automatically.
'''
import numpy as np
import logging

from scan.scan import ScanBase
from daq.readout import open_raw_data_file, get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record
from analysis.analyze_raw_data import AnalyzeRawData

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "n_injections": 100,  # how often one injects per PlsrDAC setting and pixel
    "scan_parameter_range": (0, 100),  # the min/max PlsrDAC values used during scan
    "mask_steps": 3,  # define how many pixels are injected to at once, 3 means every 3rd pixel of a double column
    "enable_mask_steps": None,  # list of the mask steps to be used; None: use all pixels
    "scan_parameter_stepsize": 2,  # the increase of the PlstrDAC if the Scurve start was found
    "search_distance": 10,  # the increase of the PlstrDAC if the Scurve start is not found yet
    "minimum_data_points": 20,  # the minimum PlsrDAC settings for one S-Curve
    "ignore_columns": (1, 78, 79, 80),  # columns which data should be ignored
    "use_enable_mask": True
}


class FastThresholdScan(ScanBase):
    scan_id = "fast_threshold_scan"
    scan_parameter_start = 0  # holding last start value (e.g. used in GDAC threshold scan)
    data_points = 10  # holding the data points already recorded

    def scan(self, mask_steps=3, n_injections=100, scan_parameter_range=None, enable_mask_steps=None, scan_parameter_stepsize=2, search_distance=10, minimum_data_points=15, ignore_columns=(1, 78, 79, 80), command=None, use_enable_mask=False, **kwargs):
        '''Scan loop

        Parameters
        ----------
        mask_steps : int
            Number of mask steps.
        n_injections : int
            Number of injections per scan step.
        scan_parameter_range : list, tuple
            Specify the minimum and maximum value for scan parameter range. Upper value not included. Takes all bit if None.
        scan_parameter_stepsize : int
            The minimum step size of the parameter. Used when start condition is not triggered.
        search_distance : int
            The parameter step size if the start condition is not triggered.
        minimum_data_points : int
            The minimum data points that are taken for sure until scan finished. Saves also calculation time.
        ignore_columns : list, tuple
            All columns that are neither scanned nor taken into account to set the scan range are mentioned here. Usually the edge columns are ignored. From 1 to 80.
        command : bitarray.bitarray
            An arbitrary command can be defined to be send to the FE. If None: Inject + Delay + Trigger is used.
        use_enable_mask : bool
            Use enable mask for masking pixels.
        '''

        scan_parameter = 'PlsrDAC'

        self.start_condition_triggered = False  # set to true if the start condition is true once
        self.stop_condition_triggered = False  # set to true if the stop condition is true once

        self.start_at = 0.01  # if more than start_at*activated_pixel see at least one hit the precise scanning is started
        self.stop_at = 0.99  # if more than stop_at*activated_pixel see the maximum numbers of injection, the scan is stopped

        self.record_data = False  # set to true to activate data storage, so far not everything is recorded to ease data analysis

        if scan_parameter_range is None or not scan_parameter_range:
            scan_parameter_range = (0, (2 ** self.register.get_global_register_objects(name=[scan_parameter])[0].bitlength))
        logging.info("Scanning %s from %d to %d" % (scan_parameter, scan_parameter_range[0], scan_parameter_range[1]))
        self.scan_parameter_value = scan_parameter_range[0]  # set to start value
        self.search_distance = search_distance
        self.data_points = 0  # counter variable to count the data points already recorded, have to be at least minimum_data_ponts

        # calculate DCs to scan from the columns to ignore
        enable_double_columns = range(0, 40)
        if 1 in ignore_columns:
            enable_double_columns.remove(0)
        if set((78, 79, 80)).issubset(ignore_columns):
            enable_double_columns.remove(39)
        for double_column in range(1, 39):
            if set((double_column * 2, (double_column * 2) + 1)).issubset(ignore_columns):
                enable_double_columns.remove(double_column)
        logging.info("Use DCs: %s" % str(enable_double_columns))

        self.select_arr_columns = range(0, 80)
        for column in ignore_columns:
            self.select_arr_columns.remove(column - 1)

        self.n_injections = n_injections

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id, scan_parameters=[scan_parameter]) as raw_data_file:
            while self.scan_parameter_value < scan_parameter_range[1]:  # scan as long as scan parameter is smaller than defined maximum
                if self.stop_thread_event.is_set():
                    break
                if self.record_data:
                    logging.info("Scan step %d (%s %d)" % (self.data_points, scan_parameter, self.scan_parameter_value))

                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(scan_parameter, self.scan_parameter_value)
                commands.extend(self.register.get_commands("wrregister", name=[scan_parameter]))
                self.register_utils.send_commands(commands)

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] if command is None else command
                self.scan_loop(cal_lvl1_command, repeat_command=self.n_injections, hardware_repeat=True, use_delay=True, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=enable_double_columns, same_mask_for_all_dc=not use_enable_mask, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=False, mask=self.register_utils.invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if use_enable_mask else None)

                self.readout.stop()

                if not self.start_condition_triggered or self.data_points > minimum_data_points:  # speed up, only create histograms when needed. Python is much too slow here.
                    if not self.start_condition_triggered and not self.record_data:
                        logging.info('Testing for start condition: %s %d' % (scan_parameter, self.scan_parameter_value))
                    if not self.stop_condition_triggered and self.record_data:
                        logging.info('Testing for stop condition: %s %d' % (scan_parameter, self.scan_parameter_value))
                    occupancy_array = np.histogram2d(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])[0]
                    self.scan_condition(occupancy_array)

                # start condition is met for the first time
                if self.start_condition_triggered and not self.record_data:
                    self.scan_parameter_value = self.scan_parameter_value - self.search_distance + scan_parameter_stepsize
                    if self.scan_parameter_value < 0:
                        self.scan_parameter_value = 0
                    logging.info('Starting threshold scan at %s %d' % (scan_parameter, self.scan_parameter_value))
                    self.scan_parameter_start = self.scan_parameter_value
                    self.record_data = True
                    continue

                # saving data
                if self.record_data:
                    self.data_points = self.data_points + 1
                    raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: self.scan_parameter_value})

                # stop condition is met for the first time
                if self.stop_condition_triggered and self.record_data:
                    logging.info('Stopping threshold scan at %s %d' % (scan_parameter, self.scan_parameter_value))
                    break

                # increase scan parameter value
                if not self.start_condition_triggered:
                    self.scan_parameter_value = self.scan_parameter_value + self.search_distance
                else:
                    self.scan_parameter_value = self.scan_parameter_value + scan_parameter_stepsize

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

    def analyze(self, create_plots=True):
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = local_configuration["n_injections"]
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table(fei4b=self.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            if create_plots:
                analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)


if __name__ == "__main__":
    import configuration
    scan = FastThresholdScan(**configuration.default_configuration)
    scan.start(use_thread=True, **local_configuration)
    scan.stop()
    scan.analyze()
