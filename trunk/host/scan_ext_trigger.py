import time
import logging
import math
import numpy as np

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "mode": 0,
    "trigger_latency": 232,
    "trigger_delay": 14,
    "col_span": [1, 80],
    "row_span": [1, 336],
    "timeout_no_data": 10,
    "scan_timeout": 1 * 60,
    "max_triggers": 10000,
    "enable_hitbus": False
}


class ExtTriggerScan(ScanBase):
    scan_identifier="ext_trigger_scan"

    def scan(self, mode=0, trigger_latency=232, trigger_delay=14, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, scan_timeout=10 * 60, max_triggers=10000, enable_hitbus=False, **kwargs):
        '''Scan loop

        Parameters
        ----------
        mode : int
            Trigger mode. More details in daq.readout_utils. From 0 to 3.
            0: External trigger (LEMO RX0 only, TLU port disabled (TLU port/RJ45)).
            1: TLU no handshake (automatic detection of TLU connection (TLU port/RJ45)).
            2: TLU simple handshake (automatic detection of TLU connection (TLU port/RJ45)).
            3: TLU trigger data handshake (automatic detection of TLU connection (TLU port/RJ45)).
        trigger_latency : int
            FE global register Trig_Lat.
            Some ballpark estimates:
            External scintillator/TLU: 232
            FE Hit-OR: 216
        trigger_delay : int
            Delay between trigger and LVL1 command.
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
        enable_hitbus : bool
            Enable Hitbus (Hit OR) for columns and rows given by col_span and row_span.
        '''
        # generate mask for Enable mask
        pixel_reg = "Enable"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        enable_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # generate mask for Imon mask
        pixel_reg = "Imon"
        if enable_hitbus:
            mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)
            imon_mask = np.logical_or(mask, self.register.get_pixel_register_value(pixel_reg))
        else:
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
        self.register.set_global_register_value("Trig_Lat", trigger_latency)  # set trigger latency
#         self.register.set_global_register_value("Trig_Count", 0)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        # setting FE into runmode
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

        wait_for_first_trigger = True

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, mode='w') as raw_data_file:
            self.readout.start()
            # preload command
            lvl1_command = self.register.get_commands("zeros", length=trigger_delay)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=200)[0]
            self.register_utils.set_command(lvl1_command)
            # setting up external trigger
            self.readout_utils.configure_trigger_fsm(mode=mode, trigger_data_msb_first=False, disable_veto=False, trigger_data_delay=0, trigger_clock_cycles=16, enable_reset=False, invert_lemo_trigger_input=False, force_use_rj45=False, trigger_low_timeout=10, reset_trigger_counter=True)
            self.readout_utils.configure_command_fsm(enable_ext_trigger=True, neg_edge=False, diable_clock=False, disable_command_trigger=False)

            show_trigger_message_at = 10 ** (int(math.floor(math.log10(max_triggers) - math.log10(3) / math.log10(10))))
            time_current_iteration = time.time()
            saw_no_data_at_time = time_current_iteration
            saw_data_at_time = time_current_iteration
            scan_start_time = time_current_iteration
            no_data_at_time = time_current_iteration
            time_from_last_iteration = 0
            scan_stop_time = scan_start_time + scan_timeout
            current_trigger_number = 0
            last_trigger_number = 0
            while not self.stop_thread_event.wait(self.readout.readout_interval):
                time_last_iteration = time_current_iteration
                time_current_iteration = time.time()
                time_from_last_iteration = time_current_iteration - time_last_iteration
                current_trigger_number = self.readout_utils.get_trigger_number()
                if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
                    logging.info('Collected triggers: %d', current_trigger_number)
                    if not any(self.readout.get_rx_sync_status()):
                        self.stop_thread_event.set()
                        logging.error('No RX sync. Stopping Scan...')
                    if any(self.readout.get_rx_8b10b_error_count()):
                        self.stop_thread_event.set()
                        logging.error('RX 8b10b error(s) detected. Stopping Scan...')
                    if any(self.readout.get_rx_fifo_discard_count()):
                        self.stop_thread_event.set()
                        logging.error('RX FIFO discard error(s) detected. Stopping Scan...')
                last_trigger_number = current_trigger_number
                if max_triggers is not None and current_trigger_number >= max_triggers:
                    logging.info('Reached maximum triggers. Stopping Scan...')
                    self.stop_thread_event.set()
                if scan_timeout is not None and time_current_iteration > scan_stop_time:
                    logging.info('Reached maximum scan time. Stopping Scan...')
                    self.stop_thread_event.set()
                try:
                    raw_data_file.append((self.readout.data.popleft(),))
                except IndexError:  # no data
                    no_data_at_time = time_current_iteration
                    if timeout_no_data is not None and not wait_for_first_trigger and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                        logging.info('Reached no data timeout. Stopping Scan...')
                        self.stop_thread_event.set()
                    elif not wait_for_first_trigger:
                        saw_no_data_at_time = no_data_at_time

                    if no_data_at_time > (saw_data_at_time + 10):
                        scan_stop_time += time_from_last_iteration
                else:
                    saw_data_at_time = time_current_iteration

                    if wait_for_first_trigger == True:
                        logging.info('Taking data...')
                        wait_for_first_trigger = False

            self.readout_utils.configure_command_fsm(enable_ext_trigger=False)
            self.readout_utils.configure_trigger_fsm(mode=0)
            logging.info('Total amount of triggers collected: %d', self.readout_utils.get_trigger_number())
            self.readout.stop()
            raw_data_file.append(self.readout.data)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.create_cluster_table = False
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)


if __name__ == "__main__":
    import configuration
    scan = ExtTriggerScan(**configuration.device_configuration)
    scan.start(use_thread=True, **scan_configuration)
    scan.stop()
    scan.analyze()
