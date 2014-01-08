import time
import logging
import math
import numpy as np
import tables as tb
from threading import Event
from scipy.interpolate import interp1d

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from daq.readout import data_dict_list_from_data_dict_iterable, is_data_from_channel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def get_gdacs(thresholds, mean_threshold_calibration):
    interpolation = interp1d(mean_threshold_calibration['mean_threshold'], mean_threshold_calibration['gdac'], kind='slinear', bounds_error=True)
    return np.unique(interpolation(thresholds).astype(np.uint32))


class ExtTriggerGdacScan(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="scan_ext_trigger_gdac", scan_data_path=None):
        super(ExtTriggerGdacScan, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self, gdacs, mode=0, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, scan_timeout=10 * 60, max_triggers=10000):
        '''Scan loop

        Parameters
        ----------
        gdacs : list, tuple
            List of GDACs to be scanned.
        mode : int
            Trigger mode. More details in daq.readout_utils. From 0 to 3.
            0: External trigger (LEMO RX0 only, TLU port disabled (TLU port/RJ45)).
            1: TLU no handshake (automatic detection of TLU connection (TLU port/RJ45)).
            2: TLU simple handshake (automatic detection of TLU connection (TLU port/RJ45)).
            3: TLU trigger data handshake (automatic detection of TLU connection (TLU port/RJ45)).
        col_span : list, tuple
            Column range (from minimum to maximum value). From 1 to 80.
        row_span : list, tuple
            Row range (from minimum to maximum value). From 1 to 336.
        timeout_no_data : int
            In seconds; if no data, stop scan after given time.
        scan_timeout : int
            In seconds; stop scan after given time.
        max_triggers : int
            Maximum number of triggers to be taken.
        '''
        logging.info('Start GDAC source scan from %d to %d in %d steps' % (np.amin(gdac_range), np.amax(gdac_range), len(gdac_range)))
        logging.info('Estimated scan time %dh' % (len(gdac_range) * scan_timeout / 3600.))

        self.stop_loop_event = Event()
        self.stop_loop_event.clear()

        pixel_reg = "Enable"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        enable_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # generate mask for Imon mask
        pixel_reg = "Imon"
        imon_mask = 1
        self.register.set_pixel_register_value(pixel_reg, imon_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
#         self.register.set_global_register_value("Trig_Lat", 232)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", 0)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        # setting FE into runmode
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)
        
        wait_for_first_trigger_setting = True  # needed to reset this for a new GDAC

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=["GDAC"]) as raw_data_file:
            for gdac_value in gdac_range:
                if self.stop_thread_event.is_set():
                    break
                self.stop_loop_event.clear()
                self.register_utils.set_gdac(gdac_value)
                self.readout.start()
                wait_for_first_trigger = wait_for_first_trigger_setting
                # preload command
                lvl1_command = self.register.get_commands("zeros", length=14)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=1000)[0]
                self.register_utils.set_command(lvl1_command)
                # setting up external trigger
                self.readout_utils.configure_trigger_fsm(mode=0, trigger_data_msb_first=False, disable_veto=False, trigger_data_delay=0, trigger_clock_cycles=16, enable_reset=False, invert_lemo_trigger_input=False, trigger_low_timeout=0)
                self.readout_utils.configure_command_fsm(enable_ext_trigger=True, diable_clock=False, disable_command_trigger=False)

                show_trigger_message_at = 10 ** (int(math.ceil(math.log10(max_triggers))) - 1)
                last_iteration = time.time()
                saw_no_data_at_time = last_iteration
                saw_data_at_time = last_iteration
                scan_start_time = last_iteration
                no_data_at_time = last_iteration
                time_from_last_iteration = 0
                scan_stop_time = scan_start_time + scan_timeout
                current_trigger_number = 0
                last_trigger_number = 0
                self.readout_utils.set_trigger_number(0)
                while not self.stop_loop_event.is_set() and not self.stop_thread_event.wait(self.readout.readout_interval):
                    current_trigger_number = self.readout_utils.get_trigger_number()
                    if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
                        logging.info('Collected triggers: %d', current_trigger_number)
                    last_trigger_number = current_trigger_number
                    if max_triggers is not None and current_trigger_number >= max_triggers:
                        logging.info('Reached maximum triggers. Stopping Scan...')
                        self.stop_loop_event.set()
                    if scan_start_time is not None and time.time() > scan_stop_time:
                        logging.info('Reached maximum scan time. Stopping Scan...')
                        self.stop_loop_event.set()
                    time_from_last_iteration = time.time() - last_iteration
                    last_iteration = time.time()
                    while True:
                        try:
                            raw_data_file.append((self.readout.data.popleft(),), scan_parameters={"GDAC": gdac_value})
                        except IndexError:  # no data
                            no_data_at_time = last_iteration
                            if wait_for_first_trigger == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                                logging.info('Reached no data timeout. Stopping Scan...')
                                self.stop_loop_event.set()
                            elif wait_for_first_trigger == False:
                                saw_no_data_at_time = no_data_at_time

                            if no_data_at_time > (saw_data_at_time + 10):
                                scan_stop_time += time_from_last_iteration
                            break  # jump out while loop

                        saw_data_at_time = last_iteration

                        if wait_for_first_trigger == True:
                            logging.info('Taking data...')
                            wait_for_first_trigger = False

                self.readout_utils.configure_command_fsm(enable_ext_trigger=False)
                self.readout_utils.configure_trigger_fsm(mode=0)
    
                logging.info('Total amount of triggers collected: %d for GDAC %d' % (self.readout_utils.get_trigger_number(), gdac_value))
    
                self.readout.stop()
    
                raw_data_file.append(self.readout.data)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.max_tot_value = 13
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.create_cluster_table = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename, maximum='maximum')


if __name__ == "__main__":
    import configuration

#     gdacs = range(100, 5001, 15)  # GDAC range set manually

    # GDAC settings can be set automatically from the calibration with equidistant thresholds
    input_file_calibration = 'data/calibrate_threshold_gdac_SCC_99.h5'  # the file with the GDAC <-> PlsrDAC calibration
    threshold_range = np.arange(19, 280, 0.8)  # threshold range in PlsrDAC to scan
    with tb.openFile(input_file_calibration, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
        gdacs = get_gdacs(threshold_range, in_file_calibration_h5.root.MeanThresholdCalibration[:])

    scan = ExtTriggerGdacScan(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.start(configure=True, use_thread=True, gdacs=gdacs, mode=0, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, scan_timeout=10 * 60, max_triggers=10000)
    scan.stop()
    scan.analyze()
