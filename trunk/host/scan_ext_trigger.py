import time
import logging
import math
import numpy as np
from threading import Timer
from scan.scan import ScanBase
from scan.run_manager import RunManager
from fei4.register_utils import make_box_pixel_mask_from_col_row, invert_pixel_mask
from analysis.analyze_raw_data import AnalyzeRawData


class ExtTriggerScan(ScanBase):
    _scan_id = "ext_trigger_scan"
    _default_scan_configuration = {
        "trigger_mode": 0,
        "trigger_latency": 232,
        "trigger_delay": 14,
        "col_span": [1, 80],
        "row_span": [1, 336],
        "overwrite_mask": False,
        "use_enable_mask": True,
        "no_data_timeout": 10,  # in seconds
        "scan_timeout": 60,  # in seconds
        "max_triggers": 10000,
        "enable_tdc": False
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        pixel_reg = 'Enable'  # enabled pixels set to 1
        mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)  # 1 for selected columns, else 0
        if self.overwrite_mask:
            pixel_mask = mask
        else:
            pixel_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, pixel_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        pixel_reg = 'Imon'  # disabled pixels set to 1
        if self.use_enable_mask:
            self.register.set_pixel_register_value(pixel_reg, invert_pixel_mask(self.register.get_pixel_register_value('Enable')))
        mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span, default=1, value=0)  # 0 for selected columns, else 1
        if self.overwrite_mask:
            pixel_mask = mask
        else:
            pixel_mask = np.logical_or(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, pixel_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        self.register.set_global_register_value("Trig_Lat", self.trigger_latency)  # set trigger latency
#         self.register.set_global_register_value("Trig_Count", 0)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        # setting FE into runmode
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

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
            FE global register Trig_Lat.
            Some ballpark estimates:
            External scintillator/TLU/Hitbus: 232 (default)
            FE/USBpix Self-Trigger: 220
        trigger_delay : int
            Delay between trigger and LVL1 command.
            Some ballpark estimates:
            Hitbus: 0
            else: 14 (default)
        col_span : list, tuple
            Column range (from minimum to maximum value). From 1 to 80.
        row_span : list, tuple
            Row range (from minimum to maximum value). From 1 to 336.
        overwrite_mask : bool
            If true the Enable and Imon (Hitbus/HitOR) mask will be overwritten by the mask defined by col_span and row_span.
        use_enable_mask : bool
            If true use Enable mask for Imon (Hitbus/HitOR) mask. Enable mask will be inverted, Hitbus will activated where pixels are enabled. Otherwise use mask from config file.
        timeout_no_data : int
            In seconds; if no data, stop scan after given time.
        scan_timeout : int
            In seconds; stop scan after given time.
        max_triggers : int
            Maximum number of triggers to be taken.
        enable_tdc : bool
            Enable for Hit-OR TDC (time-to-digital-converter) measurement. In this mode the Hit-Or/Hitbus output of the FEI4 has to be connected to USBpix Hit-OR input on the Single Chip Adapter Card.
        '''
        # preload command
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=200)[0]
        self.register_utils.set_command(lvl1_command)

        with self.readout():
            show_trigger_message_at = 10 ** (int(math.floor(math.log10(self.max_triggers) - math.log10(3) / math.log10(10))))
            current_trigger_number = 0
            last_trigger_number = 0
            while not self.stop_run.wait(1.0):
                print self.data_readout.data_words_per_second()
                current_trigger_number = self.dut['tlu']['TRIGGER_COUNTER']
                if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
                    logging.info('Collected triggers: %d', current_trigger_number)
                last_trigger_number = current_trigger_number
                if self.max_triggers is not None and current_trigger_number >= self.max_triggers:
                    self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)

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
        self.timer = Timer(self.scan_timeout, self.stop, kwargs={'msg': 'Scan timeout was reached'})
        self.data_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=None)#self.no_data_timeout)
        self.dut['tdc_rx2']['ENABLE'] = self.enable_tdc
        self.dut['tlu']['TRIGGER_MODE'] = self.trigger_mode
        self.dut['tlu']['TRIGGER_COUNTER'] = 0
        self.dut['cmd']['EN_EXT_TRIGGER'] = True
        self.timer.start()

    def stop_readout(self):
        self.timer.cancel()
        self.dut['tdc_rx2']['ENABLE'] = False
        self.dut['cmd']['EN_EXT_TRIGGER'] = False
        self.dut['tlu']['TRIGGER_MODE'] = 0
        self.data_readout.stop()


if __name__ == "__main__":
    wait = RunManager.run_run(ExtTriggerScan, 'configuration.yaml')
    wait()
