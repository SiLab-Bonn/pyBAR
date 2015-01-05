import logging
import numpy as np
import tables as tb
import progressbar
from time import time

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import make_box_pixel_mask_from_col_row, invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy


class NoiseOccupancyScan(Fei4RunBase):
    '''Noise occupancy scan detecting and masking noisy pixels.

    Note
    ----
    The total number of triggers which will be sent to the FE are <triggers> * <trig_count> (consecutive LVL1).
    To achieve a broader TDAC distribution it is necessary to decrease TdacVbp.
    '''
    _default_run_conf = {
        "occupancy_limit": 10 ** (-5),  # 0 will mask any pixel with occupancy greater than zero
        "n_triggers": 10000000,  # total number of triggers which will be sent to the FE. From 1 to 4294967295 (32-bit unsigned int).
        "trig_count": 1,  # FE global register Trig_Count
        "trigger_rate_limit": 500,  # artificially limiting the trigger rate, in BCs (25ns)
        "disable_for_mask": ['Enable'],  # list of masks for which noisy pixels will be disabled
        "enable_for_mask": ['Imon'],  # list of masks for which noisy pixels will be disabled
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": False,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 10,  # no data timeout after which the scan will be aborted, in seconds
        "overwrite_mask": False  # if True, overwrite existing masks
    }

    def configure(self):
        if self.trig_count == 0:
            self.consecutive_lvl1 = (2 ** self.register.global_registers['Trig_Count']['bitlength'])
        else:
            self.consecutive_lvl1 = self.trig_count
        if self.occupancy_limit * self.n_triggers * self.consecutive_lvl1 < 1.0:
            logging.warning('Number of triggers too low for given occupancy limit. Any noise hit will lead to a masked pixel.')

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
#         self.register.set_global_register_value("Trig_Lat", self.trigger_latency)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", self.trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Count"]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        # preload command
        lvl1_command = self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.total_scan_time = int(lvl1_command.length() * 25 * (10 ** -9) * self.n_triggers)
        logging.info('Estimated scan time: %ds' % self.total_scan_time)

        with self.readout():
            got_data = False
            start = time()
            self.register_utils.send_command(lvl1_command, repeat=self.n_triggers, wait_for_finish=False, set_length=True, clear_memory=False)
            while not self.stop_run.wait(1.0):
                if self.register_utils.is_ready:
                    if got_data:
                        self.progressbar.finish()
                    self.stop('Finished sending %d triggers' % self.n_triggers)
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                        self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=self.total_scan_time, poll=10, term_width=80).start()
                else:
                    try:
                        self.progressbar.update(time() - start)
                    except ValueError:
                        pass

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_hit_table = False
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()
            with tb.open_file(analyze_raw_data._analyzed_data_file, 'r') as out_file_h5:
                occ_hist = out_file_h5.root.HistOcc[:, :, 0].T
            self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
            # noisy pixels are set to 1
            if self.trig_count == 0:
                consecutive_lvl1 = (2 ** self.register.global_registers['Trig_Count']['bitlength'])
            else:
                consecutive_lvl1 = self.trig_count
            self.occ_mask[occ_hist > self.occupancy_limit * self.n_triggers * consecutive_lvl1] = 1
            # make inverse
            self.inv_occ_mask = invert_pixel_mask(self.occ_mask)
            if self.overwrite_mask:
                for mask in self.disable_for_mask:
                    self.register.set_pixel_register_value(mask, self.inv_occ_mask)
            else:
                for mask in self.disable_for_mask:
                    enable_mask = np.logical_and(self.inv_occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, enable_mask)

            if self.overwrite_mask:
                for mask in self.enable_for_mask:
                    self.register.set_pixel_register_value(mask, self.occ_mask)
            else:
                for mask in self.enable_for_mask:
                    disable_mask = np.logical_or(self.occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, disable_mask)
            plot_occupancy(self.occ_mask.T, title='Noisy Pixels', z_max=1, filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.occ_mask.T, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.disable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.enable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=self.no_data_timeout)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(NoiseOccupancyScan)
