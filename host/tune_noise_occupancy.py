import time
import logging
import numpy as np

from analysis.plotting.plotting import plot_occupancy
from daq.readout import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class NoiseOccupancyScan(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="scan_noise_occupancy", scan_data_path=None):
        super(NoiseOccupancyScan, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self, occupancy_limit=10 ** (-5), triggers=10000000, consecutive_lvl1=16, disable_for_mask=['Enable'], enable_for_mask=['Imon'], overwrite_mask=False, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10):
        '''Masking pixels with occupancy above certain limit.

        Parameters
        ----------
        occupancy_limit : float
            Occupancy limit which is multiplied with measured number of hits for each pixel. Any pixel above 1 will be masked.
        triggers : int
            Total number of triggers sent to FE. From 1 to 4294967295 (32-bit unsigned int).
        consecutive_lvl1 : int
            Number of consecutive LVL1 triggers. From 1 to 16.
        disable_for_mask : list, tuple
            List of masks for which noisy pixels will be disabled.
        enable_for_mask : list, tuple
            List of masks for which noisy pixels will be enabled.
        overwrite_mask : bool
            Overwrite masks (disable_for_mask, enable_for_mask) if set to true. If set to false, make a combination of existing mask and new mask.
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

        if occupancy_limit * triggers * consecutive_lvl1 < 1:
            logging.warning('Number of triggers too low for given occupancy limit')

        commands = []
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        pixel_reg = "Enable"
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_pixel_register_value(pixel_reg, mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # generate mask for Imon mask
        pixel_reg = "Imon"
#         mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)
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
        self.register.set_global_register_value("Trig_Count", (0 if consecutive_lvl1 == 16 else consecutive_lvl1))  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Count"]))
        # setting FE into runmode
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

        self.col_arr = np.array([], dtype=np.dtype('>u1'))
        self.row_arr = np.array([], dtype=np.dtype('>u1'))

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier) as raw_data_file:
            self.readout.start()

            # preload command
            lvl1_command = self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", length=2000)[0]
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
                    if wait_for_first_data == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
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

            occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
            # noisy pixels are set to 1
            occ_mask[occ_hist > occupancy_limit * triggers * consecutive_lvl1] = 1
            # make inverse
            inv_occ_mask = self.register_utils.invert_pixel_mask(occ_mask)
            if overwrite_mask:
                self.register.set_pixel_register_value(disable_for_mask, inv_occ_mask)
            else:
                for mask in disable_for_mask:
                    enable_mask = np.logical_and(inv_occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, enable_mask)

            if overwrite_mask:
                self.register.set_pixel_register_value(enable_for_mask, occ_mask)
            else:
                for mask in enable_for_mask:
                    disable_mask = np.logical_or(occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, disable_mask)

#             plot_occupancy(self.col_arr, self.row_arr, max_occ=None, filename=self.scan_data_filename + "_occupancy.pdf")

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(FEI4B=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)


if __name__ == "__main__":
    import configuration
    scan = NoiseOccupancyScan(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.start(configure=True, use_thread=True, occupancy_limit=10 ** (-5), triggers=10000000, consecutive_lvl1=16, disable_for_mask=['Enable'], enable_for_mask=['Imon'], overwrite_mask=False, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10)
    scan.stop()
    scan.analyze()
    scan.register.save_configuration(configuration.config_file)
