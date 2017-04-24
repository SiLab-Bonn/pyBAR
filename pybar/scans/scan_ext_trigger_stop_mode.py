import logging
from time import time
from threading import Timer

import progressbar
import numpy as np

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

    Note:
    Set up trigger in DUT configuration file (e.g. dut_configuration_mio.yaml).
    '''
    _default_run_conf = {
        "trigger_latency": 5,  # FE global register Trig_Lat. The lower the value the longer the hit data will be stored in data buffer
        "trigger_delay": 192,  # delay between trigger and stop mode command
        "readout_delay": 2000,  # delay after trigger to record hits, the lower the faster the readout; total readout time per track is about (800 + (1300 + readout_delay) * bcid_window) * 25 ns
        "trig_count": 100,  # Number of consecurive time slices to be read, from 1 to 256
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": True,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 30,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 60,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": 10,  # maximum triggers after which the scan will be stopped, if 0, no maximum triggers are set
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
            self.register.get_commands("zeros", length=self.readout_delay)[0],
            self.register.get_commands("ConfMode")[0],
            self.register.get_commands("zeros", length=1000)[0],
            self.register.get_commands("GlobalPulse", Width=0)[0],
            self.register.get_commands("zeros", length=100)[0]))

        self.dut['CMD']['CMD_REPEAT'] = self.trig_count
        self.dut['CMD']['START_SEQUENCE_LENGTH'] = len(start_sequence)
        self.dut['CMD']['STOP_SEQUENCE_LENGTH'] = len(stop_sequence) + 1

        # preload the command to be send for each trigger
        command = self.register_utils.concatenate_commands((start_sequence, one_latency_read, stop_sequence))

        self.register_utils.set_command(command)

        with self.readout(no_data_timeout=self.no_data_timeout, **self.scan_parameters._asdict()):
            got_data = False
            start = time()
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                        if self.max_triggers:
                            self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=self.max_triggers, poll=10, term_width=80).start()
                        else:
                            self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=self.scan_timeout, poll=10, term_width=80).start()
                else:
                    triggers = self.dut['TLU']['TRIGGER_COUNTER']
                    try:
                        if self.max_triggers:
                            self.progressbar.update(triggers)
                        else:
                            self.progressbar.update(time() - start)
                    except ValueError:
                        pass
                    if self.max_triggers and triggers >= self.max_triggers:
                        self.progressbar.finish()
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)
        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.trig_count = self.trig_count  # set number of BCID to overwrite the number deduced from the raw data file
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.trigger_data_format = 1  # time stamp only
            analyze_raw_data.set_stop_mode = True
            analyze_raw_data.align_at_trigger = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(use_settings_from_file=False)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()

    def start_readout(self, *args, **kwargs):
        super(StopModeExtTriggerScan, self).start_readout(*args, **kwargs)
        self.connect_cancel(["stop"])
        self.dut['TLU']['TRIGGER_COUNTER'] = 0
        self.dut['TLU']['MAX_TRIGGERS'] = self.max_triggers
        self.dut['CMD']['EN_EXT_TRIGGER'] = True

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop(msg='Scan timeout was reached')

        self.scan_timeout_timer = Timer(self.scan_timeout, timeout)
        if self.scan_timeout:
            self.scan_timeout_timer.start()

    def stop_readout(self, timeout=10.0):
        self.scan_timeout_timer.cancel()
        self.dut['CMD']['EN_EXT_TRIGGER'] = False
        super(StopModeExtTriggerScan, self).stop_readout(timeout=timeout)
        self.connect_cancel(["abort"])


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(StopModeExtTriggerScan)
