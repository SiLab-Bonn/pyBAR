"""This script uses the FE stop mode to recover all hits stored in the pixel array if a trigger is issued.
Can be used if there are correlated hits over a large time window (> 16 * 25 ns). Has the disadvantage to reduce the max trigger rate since the readout per trigger takes a rather long time.
The FE config is:
- Some delay until hits are processed
- Set FE to stop mode
- Enable FE conf mode
- FE trigger multiplication set to one
- FE trigger latency set high (== low value) to store the hits for a long time
- for each trigger do
 - stop the clock to the pixel matrix (freeze the hits)
 - enable global pulse to increase the pixel matrix clock
 - for each trigger latency value you want to read repeat:
   - goto run mode to make the FE accept trigger
   - issue a trigger
   - go back to conf mode to make the FE accept global pulse
   - issue global pulse to increase pixel matrix clock
 - disable global pulse to increase the pixel matrix clock
 - enable the clock to the pixel matrix
"""
import time
import logging
import math
import numpy as np
from fei4.register_utils import make_box_pixel_mask_from_col_row

from scan.scan import ScanBase
from daq.readout import open_raw_data_file


local_configuration = {
    "source": "TPC",
    "trigger_mode": 0,
    "trigger_latency": 5,
    "trigger_delay": 192,
    "bcid_window": 100,  # the time window hits are read from the pixel matrix, [0:256[
    "col_span": [2, 77],
    "row_span": [2, 330],
    "timeout_no_data": 10,
    "scan_timeout": 1 * 60,
    "max_triggers": 100,
    "enable_hitbus": True,
    "enable_all_pixel": False,
}


class ExtTriggerScan(ScanBase):
    scan_id = "ext_trigger_scan_stop_mode"

    def scan(self):
        '''Scan loop

        Parameters
        ----------
        trigger_mode : int
            Trigger mode. More details in basil.HL.tlu. From 0 to 3.
            0: External trigger (LEMO RX0 only, TLU port disabled (TLU port/RJ45)).
            1: TLU no handshake (automatic detection of TLU connection (TLU port/RJ45)).
            2: TLU simple handshake (automatic detection of TLU connection (TLU port/RJ45)).
            3: TLU trigger data handshake (automatic detection of TLU connection (TLU port/RJ45)).
        trigger_latency : int
            FE global register Trig_Lat. The lower the longer the hit will be stored in data buffers.
        trigger_delay : int
            Delay between trigger and stop mode command.
        bcid_window : int
            Number of trigger to be read out in stop mode.
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
        enable_tdc : bool
            Enable for Hit-OR TDC (time-to-digital-converter) measurement. In this mode the Hit-Or/Hitbus output of the FEI4 has to be connected to USBpix Hit-OR input on the Single Chip Adapter Card.
        '''
        wait_for_first_trigger = True

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_id, mode='w') as raw_data_file:
            self.readout.start()

            # Stop mode related hacks to read all hits stored with stop mode
            self.register.set_global_register_value("StopModeCnfg", 1)
            stop_mode_cmd = self.register.get_commands("WrRegister", name=["StopModeCnfg"])[0]
            self.register.set_global_register_value("StopModeCnfg", 0)
            stop_mode_off_cmd = self.register.get_commands("WrRegister", name=["StopModeCnfg"])[0]

            self.register.set_global_register_value("StopClkPulse", 1)
            stop_clock_pulse_cmd_high = self.register.get_commands("WrRegister", name=["StopClkPulse"])[0]
            self.register.set_global_register_value("StopClkPulse", 0)
            stop_clock_pulse_cmd_low = self.register.get_commands("WrRegister", name=["StopClkPulse"])[0]
#             read_register = self.register.get_commands("rdregister", name=["StopClkPulse"])[0]

            start_sequence = self.register_utils.concatenate_commands((
                self.register.get_commands("zeros", length=self.trigger_delay)[0],
                stop_mode_cmd,
                self.register.get_commands("zeros", length=20)[0],
                stop_clock_pulse_cmd_high,  # FIXME: before ConfMode?
                self.register.get_commands("zeros", length=50)[0],
                self.register.get_commands("ConfMode")[0]))

            stop_sequence = self.register_utils.concatenate_commands((
                self.register.get_commands("zeros", length=50)[0],
                stop_clock_pulse_cmd_low,
                self.register.get_commands("zeros", length=10)[0],
                stop_mode_off_cmd,
                self.register.get_commands("zeros", length=400)[0]))

            # define the command sequence to read the hits of one latency count
            one_latency_read = self.register_utils.concatenate_commands((
                self.register.get_commands("zeros", length=50)[0],
                self.register.get_commands("RunMode")[0],
                self.register.get_commands("zeros", length=50)[0],
                self.register.get_commands("LV1")[0],
                self.register.get_commands("zeros", length=2000)[0],
                self.register.get_commands("ConfMode")[0],
                self.register.get_commands("zeros", length=1000)[0],
                self.register.get_commands("globalpulse", width=0)[0],
                self.register.get_commands("zeros", length=100)[0]))

            self.dut['cmd']['CMD_REPEAT'] = self.bcid_window
            self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(start_sequence)
            self.dut['cmd']['STOP_SEQUENCE_LENGTH'] = len(stop_sequence) + 1

            # preload the command to be send for each trigger
            command = self.register_utils.concatenate_commands((start_sequence, one_latency_read, stop_sequence))

            self.register_utils.set_command(command)

            self.dut['tdc_rx2']['ENABLE'] = self.enable_tdc
            self.dut['tlu']['TRIGGER_MODE'] = self.trigger_mode
            self.dut['tlu']['TRIGGER_COUNTER'] = 0
            self.dut['tlu']['EN_WRITE_TIMESTAMP'] = True
            self.dut['cmd']['EN_EXT_TRIGGER'] = True

            show_trigger_message_at = 10 ** (int(math.floor(math.log10(self.max_triggers) - math.log10(3) / math.log10(10))))
            time_current_iteration = time.time()
            saw_no_data_at_time = time_current_iteration
            saw_data_at_time = time_current_iteration
            scan_start_time = time_current_iteration
            no_data_at_time = time_current_iteration
            time_from_last_iteration = 0
            scan_stop_time = scan_start_time + self.scan_timeout
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
                if self.max_triggers is not None and current_trigger_number >= self.max_triggers:
                    logging.info('Reached maximum triggers. Stopping Scan...')
                    self.stop_thread_event.set()
                if self.scan_timeout is not None and time_current_iteration > scan_stop_time:
                    logging.info('Reached maximum scan time. Stopping Scan...')
                    self.stop_thread_event.set()
                try:
                    raw_data_file.append((self.readout.data.popleft(),))
                except IndexError:  # no data
                    no_data_at_time = time_current_iteration
                    if self.timeout_no_data is not None and not wait_for_first_trigger and saw_no_data_at_time > (saw_data_at_time + self.timeout_no_data):
                        logging.info('Reached no data timeout. Stopping Scan...')
                        self.stop_thread_event.set()
                    elif not wait_for_first_trigger:
                        saw_no_data_at_time = no_data_at_time

                    if no_data_at_time > (saw_data_at_time + 10):
                        scan_stop_time += time_from_last_iteration
                else:
                    saw_data_at_time = time_current_iteration

                    if wait_for_first_trigger is True:
                        logging.info('Taking data...')
                        wait_for_first_trigger = False

            self.dut['tdc_rx2']['ENABLE'] = False
            self.dut['cmd']['EN_EXT_TRIGGER'] = False
            self.dut['tlu']['TRIGGER_MODE'] = 0
            logging.info('Total amount of triggers collected: %d', self.dut['tlu']['TRIGGER_COUNTER'])
            self.readout.stop()
            raw_data_file.append(self.readout.data)

    def configure(self):
        # generate mask for Enable mask
        pixel_reg = "Enable"
        mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        enable_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        if self.enable_all_pixel:
            self.register.set_pixel_register_value(pixel_reg, 1)
        else:
            self.register.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=pixel_reg))
        # generate mask for Imon mask
        pixel_reg = "Imon"
        if self.enable_hitbus:
            mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span, default=1, value=0)
            imon_mask = np.logical_or(mask, self.register.get_pixel_register_value(pixel_reg))
        else:
            imon_mask = 1
        self.register.set_pixel_register_value(pixel_reg, imon_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        self.register.set_global_register_value("Trig_Lat", self.trig_latency)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", 1)  # set number of consecutive triggers to one for stop mode readout

        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        self.register_utils.send_commands(commands)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.n_bcid = self.bcid_window
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.use_trigger_time_stamp = True
            analyze_raw_data.set_stop_mode = True
            analyze_raw_data.interpreter.use_trigger_number(True)
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
#             analyze_raw_data.interpreter.debug_events(0, 10, True)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpret_word_table(use_settings_from_file=False)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)


if __name__ == "__main__":
    import configuration
    scan = ExtTriggerScan(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=True, **local_configuration)
    scan.stop()
