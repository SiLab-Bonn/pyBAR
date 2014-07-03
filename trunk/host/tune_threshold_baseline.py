import time
import logging
import numpy as np
from math import ceil

from analysis.plotting.plotting import plot_occupancy
from daq.readout import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "cfg_name": 'threshold_baseline_tuning',  # the name of the new config with the tuning
    "occupancy_limit": 10 ** (-5),  # 0 will mask any pixel with occupancy greater than zero
    "triggers": 100000,
    "trig_count": 1,
    "disable_for_mask": ['Enable'],
    "enable_for_mask": ['Imon'],
    "overwrite_mask": False,
    "col_span": [1, 80],
    "row_span": [1, 336],
    "timeout_no_data": 10
}


class ThresholdBaselineTuning(ScanBase):
    scan_id = "threshold_basline_tuning"

    def scan(self, cfg_name='noise_occ_tuning', occupancy_limit=10 ** (-7), noisy_pixel_limit=0.01, triggers=1000000, trig_count=1, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, **kwargs):
        '''Masking pixels with occupancy above certain limit.

        Parameters
        ----------
        occupancy_limit : float
            Occupancy limit which is multiplied with measured number of hits for each pixel. Any pixel above 1 will be masked.
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
        # TDAC
        tdac_median = np.median(self.register.get_pixel_register_value('TDAC'))
        tdac_max = 2 ** self.register.get_pixel_register_objects(name=['TDAC'])[0].bitlength - 1
        threshold_correction = 4 * ceil(tdac_max - tdac_median)
        if threshold_correction < 0.0:
            threshold_correction = 0.0
        pixel_reg = "TDAC"
        commands.extend(self.register.get_commands("confmode"))
        print 'TDAC max', tdac_max
        self.register.set_pixel_register_value(pixel_reg, tdac_max)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        pixel_reg = "Enable"
        commands.extend(self.register.get_commands("confmode"))
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

        print 'threshold', self.register.get_global_register_value("Vthin_AltFine"), 'correction', threshold_correction
        vthin_alt_fine_max = 2 ** self.register.get_global_register_objects(name=["Vthin_AltFine"])[0].bitlength - 1
        if self.register.get_global_register_value("Vthin_AltFine") + threshold_correction > vthin_alt_fine_max:
            corrected_threshold = vthin_alt_fine_max
        else:
            corrected_threshold = self.register.get_global_register_value("Vthin_AltFine") + threshold_correction

        for reg_val in range(int(corrected_threshold), -1, -1):
            print reg_val
            self.stop_thread_event.clear()
            logging.info('Scanning Vthin_AltFine %d' % reg_val)
            commands.extend(self.register.get_commands("confmode"))
            self.register.set_global_register_value("Vthin_AltFine", reg_val)  # set number of consecutive triggers
            commands.extend(self.register.get_commands("wrregister", name=["Vthin_AltFine"]))
            # setting FE into runmode
            commands.extend(self.register.get_commands("runmode"))
            self.register_utils.send_commands(commands)

            self.col_arr = np.array([], dtype=np.dtype('>u1'))
            self.row_arr = np.array([], dtype=np.dtype('>u1'))

            with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id) as raw_data_file:
                self.readout.start()

                # preload command
                command_delay = 400  # 100kHz
                lvl1_command = self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", length=command_delay)[0]
                commnd_lenght = lvl1_command.length()
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
                        raw_data_file.append(data)
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
                print occ_hist
                self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
                # noisy pixels are set to 1
                self.occ_mask[occ_hist > occupancy_limit * triggers * consecutive_lvl1] = 1
                print self.occ_mask.sum()
                plot_occupancy(occ_hist.T, title='Occupancy', filename=scan.scan_data_filename + '_noise_occ_' + str(reg_val) + '.pdf')

                tdac_reg = self.register.get_pixel_register_value('TDAC')
                decrease_pixel_mask = np.logical_and(self.occ_mask > 0, tdac_reg > 0)
                noise_pixel_mask = np.logical_and(self.occ_mask > 0, tdac_reg == 0)
                plot_occupancy(tdac_reg.T, title='TDAC', filename=scan.scan_data_filename + '_TDAC_' + str(reg_val) + '.pdf')
                noisy_pixels = noise_pixel_mask.sum()
                print 'NOISY untuned pixels', self.occ_mask.sum(), 'Noisy pixels', noisy_pixels, 'Noisy tuned pixels', decrease_pixel_mask.sum(), 'limit', noisy_pixel_limit * occ_hist.shape[0] * occ_hist.shape[1]
                if noisy_pixels > noisy_pixel_limit * occ_hist.shape[0] * occ_hist.shape[1]:
                    self.register.restore()
                    self.register.set_global_register_value("Vthin_AltFine", reg_val - 1)
                    self.register.set_pixel_register_value('TDAC', tdac_reg)
                    scan.register.save_configuration(cfg_name)
                    break
                else:
                    tdac_reg[decrease_pixel_mask] -= 1  # TODO
                    self.register.set_pixel_register_value('TDAC', tdac_reg)
                    commands = []
                    commands.extend(self.register.get_commands("confmode"))
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name='TDAC'))
                    commands.extend(self.register.get_commands("runmode"))
                    self.register_utils.send_commands(commands)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename, analyzed_data_file=output_file, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_source_scan_hist = True
#             analyze_raw_data.create_hit_table = True
#             analyze_raw_data.interpreter.debug_events(0, 0, True)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
            plot_occupancy(self.occ_mask.T, title='Noisy Pixels', z_max=1, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    import configuration
    scan = ThresholdBaselineTuning(**configuration.default_configuration)
    scan.start(use_thread=False, **local_configuration)
    scan.stop()
#     scan.analyze()
#    scan.register.save_configuration()
