import time
import logging
import math
import numpy as np
# import tables as tb
# from scipy.interpolate import interp1d
from threading import Event

from scan.scan import ScanBase
from daq.readout import open_raw_data_file
# from analysis.analyze_raw_data import AnalyzeRawData
# from analysis import analysis_utils
from fei4.register_utils import make_box_pixel_mask_from_col_row


local_configuration = {
    "source": 'Cd strong source',
    "GDAC_calibration_file": 'data//SCC_99//calibrate_threshold_gdac_SCC_99_new.h5',
    "gdacs": None,  # specifiy the GDACs to use here, if set to None they are taken from the GDAC_calibration_file
    "threshold_range": range(30, 600, 1),  # if set to None the GDAC values are not interpolated and taken from the GDAC_calibration_file directly
    "col_span": [3, 77],
    "row_span": [2, 335],
    "timeout_no_data": None,
    "scan_timeout": 1 * 60,
    "trig_latency": 238,
    "trig_count": 5
}


# load GDAC values from calibration file
# if scan.scan_configuration['gdacs'] is None:
#     def get_gdacs(thresholds, mean_threshold_calibration):  # interpolate the GDAC value at the chosen threshold positions
#         interpolation = interp1d(mean_threshold_calibration['mean_threshold'], mean_threshold_calibration['gdac'], kind='slinear', bounds_error=True)
#         return np.unique(interpolation(thresholds).astype(np.uint32))
#     with tb.openFile(scan.scan_configuration['GDAC_calibration_file'], mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
#         if scan.scan_configuration['threshold_range'] is not None:
#             scan.scan_configuration['gdacs'] = get_gdacs(scan.scan_configuration['threshold_range'], in_file_calibration_h5.root.MeanThresholdCalibration[:])
#         else:
#             scan.scan_configuration['gdacs'] = in_file_calibration_h5.root.MeanThresholdCalibration[:]['gdac']


class FEI4SelfTriggerGdacScan(ScanBase):
    scan_id = "fei4_self_trigger_gdac_scan"

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        col_span : list, tuple
            Column range (from minimum to maximum value). From 1 to 80.
        row_span : list, tuple
            Row range (from minimum to maximum value). From 1 to 336.
        timeout_no_data : int
            In seconds; if no data, stop scan after given time.
        scan_timeout : int
            In seconds; stop scan after given time.
        trig_latency : int
            FE global register Trig_Lat.
        trig_count : int
            FE global register Trig_Count.
        '''

        logging.info('Start GDAC self trigger source scan from %d to %d in %d steps' % (min(self.gdacs), max(self.gdacs), len(self.gdacs)))
        logging.info('Estimated scan time %dh' % (len(self.gdacs) * self.scan_timeout / 3600.))

        self.stop_loop_event = Event()
        self.stop_loop_event.clear()
        self.repeat_scan_step = True

        for gdac_value in self.gdacs:
            if self.stop_thread_event.is_set():
                break
            self.repeat_scan_step = True
            while self.repeat_scan_step and not self.stop_thread_event.is_set():
                with open_raw_data_file(filename=self.scan_data_filename + '_GDAC_' + str(gdac_value), title=self.scan_id, scan_parameters=["GDAC"], mode='w') as raw_data_file:
                    self.repeat_scan_step = False
                    self.stop_loop_event.clear()
                    self.register_utils.set_gdac(gdac_value)
                    self.readout.start()
                    self.set_self_trigger(True)
                    wait_for_first_data = True
                    show_trigger_message_at = 10 ** (int(math.floor(math.log10(self.scan_timeout) - math.log10(3) / math.log10(10))))
                    time_current_iteration = time.time()
                    saw_no_data_at_time = time_current_iteration
                    saw_data_at_time = time_current_iteration
                    scan_start_time = time_current_iteration
                    no_data_at_time = time_current_iteration
                    time_from_last_iteration = 0
                    scan_stop_time = scan_start_time + self.scan_timeout
                    while not self.stop_loop_event.is_set() and not self.stop_thread_event.wait(self.readout.readout_interval):
                        time_last_iteration = time_current_iteration
                        time_current_iteration = time.time()
                        time_from_last_iteration = time_current_iteration - time_last_iteration
                        if ((time_current_iteration - scan_start_time) % show_trigger_message_at < (time_last_iteration - scan_start_time) % show_trigger_message_at):
                            logging.info('Scan runtime: %d seconds', time_current_iteration - scan_start_time)
                            if not any(self.readout.get_rx_sync_status()):
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                                logging.error('No RX sync. Stopping Scan...')
                            if any(self.readout.get_rx_8b10b_error_count()):
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                                logging.error('RX 8b10b error(s) detected. Stopping Scan...')
                            if any(self.readout.get_rx_fifo_discard_count()):
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                                logging.error('RX FIFO discard error(s) detected. Stopping Scan...')
                        if self.scan_timeout is not None and time_current_iteration > scan_stop_time:
                            logging.info('Reached maximum scan time. Stopping Scan...')
                            self.stop_loop_event.set()
                        try:
                            raw_data_file.append((self.readout.data.popleft(),), scan_parameters={"GDAC": gdac_value})
                        except IndexError:  # no data
                            no_data_at_time = time_current_iteration
                            if self.timeout_no_data is not None and wait_for_first_data is False and saw_no_data_at_time > (saw_data_at_time + self.timeout_no_data):
                                logging.info('Reached no data timeout. Stopping Scan...')
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                            elif wait_for_first_data is False:
                                saw_no_data_at_time = no_data_at_time

                            if no_data_at_time > (saw_data_at_time + 10):
                                scan_stop_time += time_from_last_iteration
                        else:
                            saw_data_at_time = time_current_iteration

                            if wait_for_first_data is True:
                                logging.info('Taking data...')
                                wait_for_first_data = False

                    self.set_self_trigger(False)
                    self.readout.stop()

                    if self.repeat_scan_step:
                        self.readout.print_readout_status()
                        logging.warning('Repeating scan for GDAC %d' % (gdac_value))
                        self.register_utils.configure_all()
                        self.readout.reset_rx()
                    else:
                        raw_data_file.append(self.readout.data, scan_parameters={"GDAC": gdac_value})

                        logging.info('Total scan runtime for GDAC %d: %d seconds' % (gdac_value, (time_current_iteration - scan_start_time)))

    def configure(self):
        # generate ROI mask for Enable mask
        pixel_reg = "Enable"
        mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        enable_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=pixel_reg))
        # generate ROI mask for Imon mask
        pixel_reg = "Imon"
        mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span, default=1, value=0)
        imon_mask = np.logical_or(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, imon_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        # enable GateHitOr that enables FE self-trigger mode
        self.register.set_global_register_value("Trig_Lat", self.trig_latency)  # set trigger latency, this latency sets the hits at the first relative BCID bins
        self.register.set_global_register_value("Trig_Count", self.trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        # send commands
        self.register_utils.send_commands(commands)

    def set_self_trigger(self, enable=True):
        logging.info('%s FEI4 self-trigger' % ('Enable' if enable is True else "Disable"))
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value("GateHitOr", 1 if enable else 0)  # enable FE self-trigger mode
        commands.extend(self.register.get_commands("WrRegister", name=["GateHitOr"]))
        if enable:
            commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

if __name__ == "__main__":
    import configuration
    scan = FEI4SelfTriggerGdacScan(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=False, use_thread=True, **local_configuration)
    scan.stop()
    # for analysis run analyze_source_scan_gdac_data
