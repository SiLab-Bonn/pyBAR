import logging
from time import time
import numpy as np
import progressbar
from threading import Timer

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager


class FEI4SelfTriggerScan(Fei4RunBase):
    '''FE-I4 self-trigger scan

    Implementation of the FE-I4 self-trigger scan, internally using HitOR for self-triggering.
    '''
    _scan_id = "fei4_self_trigger_scan"
    _default_scan_configuration = {
        "trig_count": 4,  # FE-I4 trigger count, number of consecutive BCs, from 0 to 15
        "trigger_latency": 239,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220, from 0 to 255
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": False,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 10,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 60,  # timeout for scan after which the scan will be stopped, in seconds
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
        self.register.set_global_register_value("Trig_Count", 0)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        with self.readout():
            got_data = False
            start = time()
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                        self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=self.scan_timeout, poll=10).start()
                else:
                    try:
                        self.progressbar.update(time() - start)
                    except ValueError:
                        pass

        logging.info('Total amount of triggers collected: %d', self.dut['tlu']['TRIGGER_COUNTER'])

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_cluster_size_hist = True  # can be set to false to omit cluster hit creation, can save some time, standard setting is false
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()

    def set_self_trigger(self, enable=True):
        logging.info('%s FEI4 self-trigger' % ('Enable' if enable is True else "Disable"))
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("GateHitOr", 1 if enable else 0)  # enable FE self-trigger mode
        commands.extend(self.register.get_commands("wrregister", name=["GateHitOr"]))
        if enable:
            commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=self.no_data_timeout)
        self.set_self_trigger(True)

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop(msg='Scan timeout was reached')

        self.scan_timeout_timer = Timer(self.scan_timeout, self.timeout)
        if self.scan_timeout:
            self.scan_timeout_timer.start()

    def stop_readout(self):
        self.set_self_trigger(False)
        self.scan_timeout_timer.cancel()
        self.fifo_readout.stop()

if __name__ == "__main__":
    join = RunManager('../configuration.yaml').run_run(FEI4SelfTriggerScan)
    join()
