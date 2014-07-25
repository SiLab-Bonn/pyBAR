import time
import logging
import numpy as np
from math import ceil
from os.path import splitext

from analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy, plotThreeWay
from daq.readout import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "cfg_name": 'threshold_baseline_tuning',  # the name of the new config with the tuning
    "occupancy_limit": 0,  # 0 will mask any pixel with occupancy greater than zero
    "disabled_pixels_limit": 0.01,  # in percent
    "repeat_tuning": True,
    "limit_repeat_tuning_steps": 5,
    "use_enable_mask": False,
    "triggers": 100000,
    "trig_count": 1,
    "col_span": [1, 80],
    "row_span": [1, 336],
    "timeout_no_data": 10
}


class ThresholdBaselineTuning(ScanBase):
    scan_id = "threshold_basline_tuning"

    def scan(self, cfg_name='noise_occ_tuning', occupancy_limit=0, disabled_pixels_limit=0.01, repeat_tuning=False, limit_repeat_tuning_steps=5, use_enable_mask=False, triggers=100000, trig_count=1, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, **kwargs):
        '''Masking pixels with occupancy above certain limit.

        Parameters
        ----------
        cfg_name : string
            File name of the configuration file. If None or not given, use default file name.
        occupancy_limit : float
            Occupancy limit which for each pixel. Any pixel above the limit the TDAC will be decreased (the lower TDAC value, the higher the threshold).
        disabled_pixels_limit : float
            Limit percentage of pixels, which will be disabled during tuning. Pixels will be disables when noisy and TDAC is 0 (highest possible threshold). Abort condition for baseline tuning and repeat tuning steps.
        repeat_tuning : bool
            Repeat TDAC tuning each global threshold step until no noisy pixels occur. Usually not needed, default is disabled.
        limit_repeat_tuning_steps : int
            Limit the number of TDAC tuning steps at certain threshold. None is no limit.
        use_enable_mask : bool
            Use enable mask for masking pixels.
        triggers : int
            Total number of triggers sent to FE. From 1 to 4294967295 (32-bit unsigned int).
        trig_count : int
            FE global register Trig_Count.
        col_span : list, tuple
            Column range (from minimum to maximum value). From 1 to 80.
        row_span : list, tuple
            Row range (from minimum to maximum value). From 1 to 336.
        timeout_no_data : int
            In seconds; if no data, stop scan after given time.
        scan_timeout : int
            In seconds; stop scan after given time.

        Note
        ----
        The total number of trigger is triggers * consecutive_lvl1.
        Please note that a high trigger rate leads to an effective lower threshold.
        '''
        # create restore point
        self.register.create_restore_point()
        if trig_count == 0:
            consecutive_lvl1 = (2 ** self.register.get_global_register_objects(name=['Trig_Count'])[0].bitlength)
        else:
            consecutive_lvl1 = trig_count
        if occupancy_limit * triggers * consecutive_lvl1 < 1.0:
            logging.warning('Number of triggers too low for given occupancy limit. Any noise hit will lead to a masked pixel.')

        commands = []
        commands.extend(self.register.get_commands("confmode"))
        # TDAC
        tdac_median = np.median(self.register.get_pixel_register_value('TDAC'))
        tdac_max = 2 ** self.register.get_pixel_register_objects(name=['TDAC'])[0].bitlength - 1
        threshold_correction = 4 * ceil(tdac_max - tdac_median)
        if threshold_correction < 0.0:
            threshold_correction = 0.0
        pixel_reg = "TDAC"
        self.register.set_pixel_register_value(pixel_reg, tdac_max)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        pixel_reg = "Enable"
        if use_enable_mask:
            self.register.set_pixel_register_value(pixel_reg, np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg)))
        else:
            self.register.set_pixel_register_value(pixel_reg, mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # generate mask for Imon mask
        pixel_reg = "Imon"
        self.register.set_pixel_register_value(pixel_reg, 1)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
#         self.register.set_global_register_value("Trig_Lat", 232)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Count"]))
        # setting FE into runmode
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

        vthin_alt_fine_max = 2 ** self.register.get_global_register_objects(name=["Vthin_AltFine"])[0].bitlength - 1
        if self.register.get_global_register_value("Vthin_AltFine") + threshold_correction > vthin_alt_fine_max:
            corrected_threshold = vthin_alt_fine_max
        else:
            corrected_threshold = self.register.get_global_register_value("Vthin_AltFine") + threshold_correction

        disabled_pixels_limit_cnt = int(disabled_pixels_limit * 336 * 80)
        diabled_pixels = 0

        for reg_val in range(int(corrected_threshold), -1, -1):
            self.register.create_restore_point(name=str(reg_val))
            logging.info('Scanning Vthin_AltFine %d' % reg_val)
            commands = []
            commands.extend(self.register.get_commands("confmode"))
            self.register.set_global_register_value("Vthin_AltFine", reg_val)  # set number of consecutive triggers
            commands.extend(self.register.get_commands("wrregister", name=["Vthin_AltFine"]))
            # setting FE into runmode
            commands.extend(self.register.get_commands("runmode"))
            self.register_utils.send_commands(commands)
            step = 0
            while True:
                self.stop_thread_event.clear()
                step += 1
                self.col_arr = np.array([], dtype=np.dtype('>u1'))
                self.row_arr = np.array([], dtype=np.dtype('>u1'))

                with open_raw_data_file(filename=self.scan_data_filename, scan_parameters=['Vthin_AltFine', 'Step'], title=self.scan_id) as raw_data_file:
                    self.readout.start()

                    # preload command
                    command_delay = 500  # <100kHz
                    lvl1_command = self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", length=command_delay)[0]
                    commnd_lenght = lvl1_command.length()
                    if repeat_tuning:
                        logging.info('Step %d at Vthin_AltFine %d' % (step, reg_val))
                    logging.info('Estimated scan time: %ds' % int(commnd_lenght * 25 * (10 ** -9) * triggers))
                    logging.info('Please stand by...')
                    self.register_utils.send_command(lvl1_command, repeat=triggers, wait_for_finish=False, set_length=True, clear_memory=False)

                    wait_for_first_data = False
                    last_iteration = time.time()
                    saw_no_data_at_time = last_iteration
                    saw_data_at_time = last_iteration
                    no_data_at_time = last_iteration
                    while not self.stop_thread_event.wait(self.readout.readout_interval):
                        last_iteration = time.time()
                        try:
                            data = (self.readout.data.popleft(), )
                            raw_data_file.append(data, scan_parameters={'Vthin_AltFine': reg_val, 'Step': step})
                            col_arr_tmp, row_arr_tmp = convert_data_array(data_array_from_data_dict_iterable(data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)
                            self.col_arr = np.concatenate((self.col_arr, col_arr_tmp))
                            self.row_arr = np.concatenate((self.row_arr, row_arr_tmp))
                        except IndexError:  # no data
                            no_data_at_time = last_iteration
                            if self.register_utils.is_ready:
                                self.stop_thread_event.set()
                                logging.info('Finished sending %d triggers' % triggers)
                            elif wait_for_first_data is False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                                logging.info('Reached no data timeout. Stopping Scan...')
                                self.stop_thread_event.set()
                            elif wait_for_first_data is False:
                                saw_no_data_at_time = no_data_at_time
                            elif self.reaout_utils.is_ready:
                                self.stop_thread_event.set()

                            continue

                        saw_data_at_time = last_iteration

                        if wait_for_first_data is True:
                            logging.info('Taking data...')
                            wait_for_first_data = False

                    self.readout.stop()

                    occ_hist, _, _ = np.histogram2d(self.col_arr, self.row_arr, bins=(80, 336), range=[[1, 80], [1, 336]])
                    self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
                    # noisy pixels are set to 1
                    self.occ_mask[occ_hist > occupancy_limit * triggers * consecutive_lvl1] = 1
#                     plot_occupancy(occ_hist.T, title='Occupancy', filename=self.scan_data_filename + '_noise_occ_' + str(reg_val) + '_' + str(step) + '.pdf')

                    tdac_reg = self.register.get_pixel_register_value('TDAC')
                    decrease_pixel_mask = np.logical_and(self.occ_mask > 0, tdac_reg > 0)
                    disable_pixel_mask = np.logical_and(self.occ_mask > 0, tdac_reg == 0)
                    enable_reg = self.register.get_pixel_register_value('Enable')
                    enable_mask = np.logical_and(enable_reg, self.register_utils.invert_pixel_mask(disable_pixel_mask))
                    diabled_pixels += disable_pixel_mask.sum()
#                     plot_occupancy(tdac_reg.T, title='TDAC', filename=self.scan_data_filename + '_TDAC_' + str(reg_val) + '_' + str(step) + '.pdf')
                    if diabled_pixels > disabled_pixels_limit_cnt:
                        logging.info('Limit of disabled pixels reached: %d (limit %d)... stopping scan' % (diabled_pixels, disabled_pixels_limit_cnt))
                        self.register.restore(name=str(reg_val))
                        break
                    else:
                        logging.info('Increasing threshold of %d pixel(s)' % (decrease_pixel_mask.sum(),))
                        logging.info('Disabling %d pixel(s), total number of disabled pixel(s): %d' % (disable_pixel_mask.sum(), diabled_pixels))
                        tdac_reg[decrease_pixel_mask] -= 1  # TODO
                        self.register.set_pixel_register_value('TDAC', tdac_reg)
                        self.register.set_pixel_register_value('Enable', enable_mask)
                        commands = []
                        commands.extend(self.register.get_commands("confmode"))
                        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name='TDAC'))
                        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name='Enable'))
                        commands.extend(self.register.get_commands("runmode"))
                        self.register_utils.send_commands(commands)
                        if not repeat_tuning or self.occ_mask.sum() == 0 or (repeat_tuning and limit_repeat_tuning_steps and step == limit_repeat_tuning_steps) or decrease_pixel_mask.sum() < disabled_pixels_limit_cnt:
                            self.register.clear_restore_points(name=str(reg_val))
                            self.last_tdac_distribution = self.register.get_pixel_register_value('TDAC')
                            self.last_occupancy_hist = occ_hist.copy()
                            self.last_occupancy_mask = self.occ_mask.copy()
                            self.last_reg_val = reg_val
                            self.last_step = step
                            break
                        else:
                            logging.info('Found noisy pixels... repeat tuning step for Vthin_AltFine %d' % (reg_val,))

            if diabled_pixels > disabled_pixels_limit_cnt:
                last_good_threshold = self.register.get_global_register_value("Vthin_AltFine")
                last_good_tdac = self.register.get_pixel_register_value('TDAC')
                last_good_enable_mask = self.register.get_pixel_register_value('Enable')
                self.register.restore()
                self.register.set_global_register_value("Vthin_AltFine", last_good_threshold)
                self.register.set_pixel_register_value('TDAC', last_good_tdac)
                self.register.set_pixel_register_value('Enable', last_good_enable_mask)
                self.register.save_configuration(cfg_name if cfg_name else (splitext(self.device_configuration["configuration_file"])[0] + '_' + self.scan_id))
                break

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=self.scan_data_filename, analyzed_data_file=output_file, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_source_scan_hist = True
#             analyze_raw_data.create_hit_table = True
#             analyze_raw_data.interpreter.debug_events(0, 0, True)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
            plot_occupancy(self.last_occupancy_hist.T, title='Noisy Pixels at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.last_occupancy_hist.T, filename=analyze_raw_data.output_pdf)
            plot_occupancy(self.last_occupancy_mask.T, title='Enable Mask', z_max=1, filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.last_occupancy_mask.T, filename=analyze_raw_data.output_pdf)
            plotThreeWay(self.last_tdac_distribution.T, title='TDAC at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), x_axis_title="TDAC", filename=analyze_raw_data.output_pdf, maximum=31, bins=32)
            plot_occupancy(self.last_tdac_distribution.T, title='TDAC at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), z_max=31, filename=analyze_raw_data.output_pdf)

if __name__ == "__main__":
    import configuration
    scan = ThresholdBaselineTuning(**configuration.default_configuration)
    scan.start(use_thread=False, **local_configuration)
    scan.stop()
    scan.analyze()
