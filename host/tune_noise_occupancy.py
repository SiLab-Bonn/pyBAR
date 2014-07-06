import time
import logging
import numpy as np
from os.path import splitext

#from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from daq.readout import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "cfg_name": 'noise_occupancy_tuning',  # the name of the new config with the tuning
    "occupancy_limit": 10 ** (-5),  # 0 will mask any pixel with occupancy greater than zero
    "triggers": 10000000,
    "trig_count": 1,
    "disable_for_mask": ['Enable'],
    "enable_for_mask": ['Imon'],
    "overwrite_mask": False,
    "col_span": [1, 80],
    "row_span": [1, 336],
    "timeout_no_data": 10
}


class NoiseOccupancyScan(ScanBase):
    scan_id = "noise_occupancy_tuning"

    def scan(self, cfg_name='noise_occupancy_tuning', occupancy_limit=10 ** (-5), triggers=10000000, trig_count=1, disable_for_mask=['Enable'], enable_for_mask=['Imon'], overwrite_mask=False, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, **kwargs):
        '''Masking pixels with occupancy above certain limit.

        Parameters
        ----------
        occupancy_limit : float
            Occupancy limit which is multiplied with measured number of hits for each pixel. Any pixel above 1 will be masked.
        triggers : int
            Total number of triggers sent to FE. From 1 to 4294967295 (32-bit unsigned int).
        trig_count : int
            FE global register Trig_Count.
        disable_for_mask : list, tuple
            List of masks for which noisy pixels will be disabled.
        enable_for_mask : list, tuple
            List of masks for which noisy pixels will be enabled.
        overwrite_mask : bool
            Overwrite masks (disable_for_mask, enable_for_mask) if set to true. If set to false, make a combination of existing mask (configuration file) and generated mask (selected columns and rows), otherwise only use generated mask.
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
        self.trig_count = trig_count
        if trig_count == 0:
            consecutive_lvl1 = (2 ** self.register.get_global_register_objects(name=['Trig_Count'])[0].bitlength)
        else:
            consecutive_lvl1 = trig_count
        if occupancy_limit * triggers * consecutive_lvl1 < 1.0:
            logging.warning('Number of triggers too low for given occupancy limit. Any noise hit will lead to a masked pixel.')

        commands = []
        commands.extend(self.register.get_commands("confmode"))
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)  # 1 for selected columns, else 0
        for pixel_reg in disable_for_mask:  # enabled pixels set to 1
            if overwrite_mask:
                pixel_mask = mask
            else:
                pixel_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
            self.register.set_pixel_register_value(pixel_reg, pixel_mask)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)  # 0 for selected columns, else 1
        for pixel_reg in enable_for_mask:  # disabled pixels set to 1
            if overwrite_mask:
                pixel_mask = mask
            else:
                pixel_mask = np.logical_or(mask, self.register.get_pixel_register_value(pixel_reg))
            self.register.set_pixel_register_value(pixel_reg, pixel_mask)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
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

        self.col_arr = np.array([], dtype=np.dtype('>u1'))
        self.row_arr = np.array([], dtype=np.dtype('>u1'))

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id) as raw_data_file:
            self.readout.start()

            # preload command
            command_delay = 500  # <100kHz
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
                    #logging.info('data words')
                except IndexError:  # no data
                    #logging.info('no data words')
                    no_data_at_time = last_iteration
                    if self.register_utils.is_ready:
                        self.stop_thread_event.set()
                        logging.info('Finished sending %d triggers' % triggers)
                    elif wait_for_first_data == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                        logging.info('Reached no data timeout. Stopping Scan...')
                        self.stop_thread_event.set()
                    elif wait_for_first_data == False:
                        saw_no_data_at_time = no_data_at_time
                    elif self.reaout_utils.is_ready:
                        self.stop_thread_event.set()

                    continue

                saw_data_at_time = last_iteration

                if wait_for_first_data == True:
                    logging.info('Taking data...')
                    wait_for_first_data = False

            self.readout.stop()

        self.register.restore()

        occ_hist, _, _ = np.histogram2d(self.col_arr, self.row_arr, bins=(80, 336), range=[[1, 80], [1, 336]])

        self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
        # noisy pixels are set to 1
        self.occ_mask[occ_hist > occupancy_limit * triggers * consecutive_lvl1] = 1
        # make inverse
        self.inv_occ_mask = self.register_utils.invert_pixel_mask(self.occ_mask)
        self.disable_for_mask = disable_for_mask
        if overwrite_mask:
            for mask in disable_for_mask:
                self.register.set_pixel_register_value(mask, self.inv_occ_mask)
        else:
            for mask in disable_for_mask:
                enable_mask = np.logical_and(self.inv_occ_mask, self.register.get_pixel_register_value(mask))
                self.register.set_pixel_register_value(mask, enable_mask)

        self.enable_for_mask = enable_for_mask
        if overwrite_mask:
            for mask in enable_for_mask:
                self.register.set_pixel_register_value(mask, self.occ_mask)
        else:
            for mask in enable_for_mask:
                disable_mask = np.logical_or(self.occ_mask, self.register.get_pixel_register_value(mask))
                self.register.set_pixel_register_value(mask, disable_mask)

#         plot_occupancy(make_occupancy_hist(self.col_arr, self.row_arr), z_max=None, filename=self.scan_data_filename + "_occupancy.pdf")
        self.register.save_configuration(cfg_name if cfg_name else (splitext(self.device_configuration["configuration_file"])[0] + '_' + self.scan_id))

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename, analyzed_data_file=output_file, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.trig_count)
            analyze_raw_data.create_source_scan_hist = True
#             analyze_raw_data.create_hit_table = True
#             analyze_raw_data.interpreter.debug_events(0, 0, True)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
            plot_occupancy(self.occ_mask.T, title='Noisy Pixels', z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.disable_for_mask:
                mask_name = self.register.get_pixel_register_attributes("full_name", do_sort=True, name=[mask])[0]
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.enable_for_mask:
                mask_name = self.register.get_pixel_register_attributes("full_name", do_sort=True, name=[mask])[0]
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    import configuration
    scan = NoiseOccupancyScan(**configuration.default_configuration)
    scan.start(use_thread=False, **local_configuration)
    scan.stop()
    scan.analyze()
