import logging
from threading import Timer
import zlib

import numpy as np
import tables as tb

import progressbar

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.daq.fei4_raw_data import RawDataFile
from pybar.run_manager import RunManager
from pybar.daq import readout_utils


class ExtTriggerScan(Fei4RunBase):
    '''External trigger scan with FE-I4

    For use with external scintillator (user RX0), TLU (use RJ45), FE-I4 HitOR (USBpix self-trigger).

    Note:
    Set up trigger in DUT configuration file (e.g. dut_configuration_mio.yaml).
    '''
    _default_run_conf = {
        "trig_count": 0,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "trigger_latency": 232-14,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220
        "trigger_delay": 8,  # trigger delay, in BCs
        "trigger_rate_limit": 500,  # artificially limiting the trigger rate, in BCs (25ns)
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": True,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 20,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 60,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": 1000000000, #1000000000,  # maximum triggers after which the scan will be stopped, in seconds
        "enable_tdc": True,  # if True, enables TDC (use RX2)
        "reset_rx_on_error": True  # long scans have a high propability for ESD related data transmission errors; recover and continue here
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
        self.register.set_global_register_value("Trig_Count", self.trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        # preload command
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.register_utils.set_command(lvl1_command)

        with self.readout(**self.scan_parameters._asdict()):
            got_data = False
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                        self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=self.max_triggers, poll=10, term_width=80).start()
                else:
                    triggers = self.dut['TLU']['TRIGGER_COUNTER']
                    try:
                        self.progressbar.update(triggers)
                    except ValueError:
                        pass
                    if self.max_triggers and triggers >= self.max_triggers:
#                         if got_data:
                        self.progressbar.finish()
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)
#                 print self.fifo_readout.data_words_per_second()
#                 if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
#                     logging.info('Collected triggers: %d', current_trigger_number)

        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

    def analyze(self):
#         #own part for a splitter of the raw data
#         ndev=range(1, 5)
#
#         with tb.open_file(raw_data_file=self.output_filename, mode="r") as in_file_h5:
#
#             if self.interpreter.meta_table_v2:
#                 index_start = in_file_h5.root.meta_data.read(field='index_start')
#                 index_stop = in_file_h5.root.meta_data.read(field='index_stop')
#             else:
#                 index_start = in_file_h5.root.meta_data.read(field='start_index')
#                 index_stop = in_file_h5.root.meta_data.read(field='stop_index')
#             readout_slices = np.column_stack((index_start, index_stop))
#
#             for i in ndev:
#                 out_files = []
#                 out_files.append(RawDataFile.from_raw_data_file(input_file=in_file_h5, output_filename=self.output_filename + "_channel%d" % i, mode="w"))
#                 filters = []
#                 filters.append(readout_utils.logical_or(readout_utils.is_trigger_word, readout_utils.logical_or(readout_utils.logical_and(readout_utils.is_fe_word, readout_utils.is_data_from_channel(i)), Fei4RunBase.is_tdc_from_channel)))
#
#             scan_parameters = in_file_h5.scan_parameters.copy()
#             for read_out_index, (index_start, index_stop) in enumerate(readout_slices):
#                 raw_data = in_file_h5.root.raw_data.read(index_start, index_stop)
#                 if in_file_h5.scan_parameters:
#                     for key in in_file_h5.scan_parameters:
#                         scan_parameters[key] = in_file_h5.scan_param_table[read_out_index][key]
#                 for index, filter_f in enumerate(filters):
#                     data_ch0 = readout_utils.convert_data_iterable([raw_data], filter_func=filter_f, converter_func=None)
#                     select = np.greater(np.bitwise_and(data_ch0[0][0], 0b01110000000000000000000000000000), 0)
#                     data_ch0[0][0][select] = np.bitwise_and(data_ch0[0][0][select], 0x0FFFFFFF)
#                     data_ch0[0][0][select] = np.bitwise_or(data_ch0[0][0][select], 0x40000000)
#                     if data_ch0[0][0].size != 0:
#                         out_files[index].append_item(data_ch0[0], scan_parameters=scan_parameters)
#
#         for out_file in out_files:
#             filename = out_file.base_filename
#             out_file.close()

            with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
                analyze_raw_data.create_source_scan_hist = True
                analyze_raw_data.create_cluster_size_hist = True
                analyze_raw_data.create_cluster_tot_hist = True
                analyze_raw_data.align_at_trigger = True
                analyze_raw_data.max_cluster_size = 200000
                if self.enable_tdc:
                    analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
                    analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
                    analyze_raw_data.align_at_tdc = False  # align events at the TDC word
                analyze_raw_data.interpreter.set_warning_output(False)
                analyze_raw_data.interpret_word_table()
                analyze_raw_data.interpreter.print_summary()
                analyze_raw_data.plot_histograms()

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=self.no_data_timeout)
#        self.dut['TDC1']['ENABLE'] = self.enable_tdc
#        self.dut['TDC4']['ENABLE'] = self.enable_tdc
#        self.dut['TDC2']['ENABLE'] = self.enable_tdc
        self.dut['TDC']['ENABLE'] = self.enable_tdc
#        self.dut['TDC3']['ENABLE'] = self.enable_tdc
        self.dut['TLU']['TRIGGER_COUNTER'] = 0
        if self.max_triggers:
            self.dut['TLU']['MAX_TRIGGERS'] = self.max_triggers
        else:
            self.dut['TLU']['MAX_TRIGGERS'] = 0  # infinity triggers
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
#        self.dut['TDC1']['ENABLE'] = False
#        self.dut['TDC4']['ENABLE'] = False
#        self.dut['TDC2']['ENABLE'] = False
        self.dut['TDC']['ENABLE'] = False
#        self.dut['TDC3']['ENABLE'] = False
        self.dut['CMD']['EN_EXT_TRIGGER'] = False
        self.fifo_readout.stop(timeout=timeout)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(ExtTriggerScan)
