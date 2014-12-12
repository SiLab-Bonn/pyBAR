import logging
import numpy as np
import progressbar
from threading import Timer

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager


class StopModeExtTriggerScan(Fei4RunBase):
    '''Stop mode scan with FE-I4

    The FE stop mode is used to recover all hits stored in the pixel array if a trigger is issued.
    A long time window (up to 255 x 25ns) can be read out. The trigger rate is limited in this mode (~40Hz @ 255 time slices readout) compared to standard readout mode (100kHz).
    The FE configuration sequence:
    - Set FE trigger latency (Trig_Lat) to store the hits for a long time
    - Set FE trigger multiplication (Trig_Count) to one

    When a trigger arrives:
    - Fixed delay until all hits are processed and stored
    - Enable FE to stop mode and stop clock pulse
    - Fixed delay
    - Enable FE conf mode
    - For each time slice repeat the following steps:
        - Enable FE run mode
        - Issue a trigger
        - Enable FE conf mode
        - Issue global pulse to advance the latency counters by 1
    - Disable FE to stop mode and stop clock pulse
    '''
    _default_run_conf = {
        "trigger_mode": 0,  # trigger mode, more details in basil.HL.tlu, from 0 to 3
        "trigger_latency": 5,  # FE global register Trig_Lat. The lower the value the longer the hit data will be stored in data buffer
        "trigger_delay": 192,  # delay between trigger and stop mode command
        "bcid_window": 100,  # Number of consecurive time slices to be read, from 0 to 255
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": True,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 30,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 60,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": 10,  # maximum triggers after which the scan will be stopped, in seconds
        "enable_tdc": True  # if True, enables TDC (use RX2)
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # Enable
        enable_pixel_mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)
        if not self.overwrite_enable_mask:
            enable_pixel_mask = np.logical_and(enable_pixel_mask, self.register.get_pixel_register_value('Enable'))
        self.register.set_pixel_register_value('Enable', enable_pixel_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Enable'))
        # Imon
        if self.use_enable_mask_for_imon:
            imon_pixel_mask = invert_pixel_mask(enable_pixel_mask)
        else:
            imon_pixel_mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span, default=1, value=0)  # 0 for selected columns, else 1
            imon_pixel_mask = np.logical_or(imon_pixel_mask, self.register.get_pixel_register_value('Imon'))
        self.register.set_pixel_register_value('Imon', imon_pixel_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Imon'))
        # C_High
        self.register.set_pixel_register_value('C_High', 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        # C_Low
        self.register.set_pixel_register_value('C_Low', 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # Registers
        self.register.set_global_register_value("Trig_Lat", self.trigger_latency)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", 1)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        # Stop mode related hacks to read all hits stored with stop mode
        self.register.set_global_register_value("StopModeCnfg", 1)
        stop_mode_cmd = self.register.get_commands("WrRegister", name=["StopModeCnfg"])[0]
        self.register.set_global_register_value("StopModeCnfg", 0)
        stop_mode_off_cmd = self.register.get_commands("WrRegister", name=["StopModeCnfg"])[0]

        self.register.set_global_register_value("StopClkPulse", 1)
        stop_clock_pulse_cmd_high = self.register.get_commands("WrRegister", name=["StopClkPulse"])[0]
        self.register.set_global_register_value("StopClkPulse", 0)
        stop_clock_pulse_cmd_low = self.register.get_commands("WrRegister", name=["StopClkPulse"])[0]

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
            self.register.get_commands("GlobalPulse", Width=0)[0],
            self.register.get_commands("zeros", length=100)[0]))

        self.dut['cmd']['CMD_REPEAT'] = self.bcid_window
        self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(start_sequence)
        self.dut['cmd']['STOP_SEQUENCE_LENGTH'] = len(stop_sequence) + 1

        # preload the command to be send for each trigger
        command = self.register_utils.concatenate_commands((start_sequence, one_latency_read, stop_sequence))

        self.register_utils.set_command(command)

        with self.readout(**self.scan_parameters._asdict()):
            got_data = False
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                        self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=self.max_triggers, poll=10).start()
                else:
                    triggers = self.dut['tlu']['TRIGGER_COUNTER']
                    try:
                        self.progressbar.update(triggers)
                    except ValueError:
                        pass
                    if self.max_triggers is not None and triggers >= self.max_triggers:
                        #                         if got_data:
                        self.progressbar.finish()
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)

        logging.info('Total amount of triggers collected: %d', self.dut['tlu']['TRIGGER_COUNTER'])

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
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
            analyze_raw_data.plot_histograms()

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=self.no_data_timeout)
        self.dut['tdc_rx2']['ENABLE'] = self.enable_tdc
        self.dut['tlu']['TRIGGER_MODE'] = self.trigger_mode
        self.dut['tlu']['TRIGGER_COUNTER'] = 0
        self.dut['tlu']['EN_WRITE_TIMESTAMP'] = True
        self.dut['cmd']['EN_EXT_TRIGGER'] = True

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop(msg='Scan timeout was reached')

        self.scan_timeout_timer = Timer(self.scan_timeout, timeout)
        if self.scan_timeout:
            self.scan_timeout_timer.start()

    def stop_readout(self):
        self.scan_timeout_timer.cancel()
        self.dut['tdc_rx2']['ENABLE'] = False
        self.dut['cmd']['EN_EXT_TRIGGER'] = False
        self.dut['tlu']['TRIGGER_MODE'] = 0
        self.fifo_readout.stop()


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(StopModeExtTriggerScan)
