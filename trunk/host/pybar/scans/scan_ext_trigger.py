import logging
import numpy as np
import progressbar
from threading import Timer

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager


class ExtTriggerScan(Fei4RunBase):
    '''External trigger scan with FE-I4

    For use with external scintillator (user RX0), TLU (use RJ45), USBpix self-trigger (loop back TX2 into RX0.)
    '''
    _scan_id = "ext_trigger_scan"
    _default_scan_configuration = {
        "trigger_mode": 0,  # trigger mode, more details in basil.HL.tlu, from 0 to 3
        "trigger_latency": 232,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220
        "trigger_delay": 14,  # trigger delay, in BCs
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": False,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 10,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 60,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": 10000,  # maximum triggers after which the scan will be stopped, in seconds
        "enable_tdc": False  # if True, enables TDC (use RX2)
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        # Enable
        enable_pixel_mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)
        if not self.overwrite_enable_mask:
            enable_pixel_mask = np.logical_and(enable_pixel_mask, self.register.get_pixel_register_value('Enable'))
        self.register.set_pixel_register_value('Enable', enable_pixel_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name='Enable'))
        # Imon
        if self.use_enable_mask_for_imon:
            imon_pixel_mask = invert_pixel_mask(enable_pixel_mask)
        else:
            imon_pixel_mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span, default=1, value=0)  # 0 for selected columns, else 1
            imon_pixel_mask = np.logical_or(imon_pixel_mask, self.register.get_pixel_register_value('Imon'))
        self.register.set_pixel_register_value('Imon', imon_pixel_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name='Imon'))
        # C_High
        self.register.set_pixel_register_value('C_High', 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_High'))
        # C_Low
        self.register.set_pixel_register_value('C_Low', 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_Low'))
        # Registers
        self.register.set_global_register_value("Trig_Lat", self.trigger_latency)  # set trigger latency
#         self.register.set_global_register_value("Trig_Count", 0)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        # preload command
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=200)[0]
        self.register_utils.set_command(lvl1_command)

#         show_trigger_message_at = 10 ** (int(math.floor(math.log10(self.max_triggers) - math.log10(3) / math.log10(10))))
#         current_trigger_number = 0
#         last_trigger_number = 0

        with self.readout():
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
                    self.progressbar.finish()
                    self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)
#                 print self.fifo_readout.data_words_per_second()
#                 if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
#                     logging.info('Collected triggers: %d', current_trigger_number)

        logging.info('Total amount of triggers collected: %d', self.dut['tlu']['TRIGGER_COUNTER'])

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_source_scan_hist = True
#             analyze_raw_data.create_hit_table = True
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            if self.enable_tdc:
                analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
                analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
                analyze_raw_data.interpreter.use_tdc_word(True)  # align events at the TDC word
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=self.no_data_timeout)
        self.dut['tdc_rx2']['ENABLE'] = self.enable_tdc
        self.dut['tlu']['TRIGGER_MODE'] = self.trigger_mode
        self.dut['tlu']['TRIGGER_COUNTER'] = 0
        self.dut['cmd']['EN_EXT_TRIGGER'] = True

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop(msg='Scan timeout was reached')

        self.scan_timeout_timer = Timer(self.scan_timeout, self.timeout)
        self.scan_timeout_timer.start()

    def stop_readout(self):
        self.scan_timeout_timer.cancel()
        self.dut['tdc_rx2']['ENABLE'] = False
        self.dut['cmd']['EN_EXT_TRIGGER'] = False
        self.dut['tlu']['TRIGGER_MODE'] = 0
        self.fifo_readout.stop()


if __name__ == "__main__":
    join = RunManager('../configuration.yaml').run_run(ExtTriggerScan)
    join()
