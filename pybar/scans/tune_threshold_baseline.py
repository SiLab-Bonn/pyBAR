import logging
from time import time
import numpy as np
import progressbar

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import make_box_pixel_mask_from_col_row, invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy, plot_three_way
from pybar.daq.readout_utils import data_array_from_data_iterable
from pybar.analysis.RawDataConverter.data_interpreter import PyDataInterpreter
from pybar.analysis.RawDataConverter.data_histograming import PyDataHistograming


class ThresholdBaselineTuning(Fei4RunBase):
    '''Threshold Baseline Tuning

    Tuning the FEI4 to the lowest possible threshold (GDAC and TDAC). Feedback current will not be tuned.
    NOTE: In case of RX errors decrease the trigger frequency (= increase trigger_rate_limit)
    NOTE: To increase the TDAC range, decrease TdacVbp.
    '''
    _default_run_conf = {
        "occupancy_limit": 0,  # occupancy limit, when reached the TDAC will be decreased (increasing threshold). 0 will mask any pixel with occupancy greater than zero
        "scan_parameters": [('Vthin_AltFine', (120, None)), ('Step', 60)],  # the Vthin_AltFine range, number of steps (repetition at constant Vthin_AltFine)
        "increase_threshold": 5,  # increase the threshold in VthinAF after tuning
        "disabled_pixels_limit": 0.01,  # limit of disabled pixels, fraction of all pixels
        "use_enable_mask": False,  # if True, enable mask from config file anded with mask (from col_span and row_span), if False use mask only for enable mask
        "n_triggers": 10000,  # total number of trigger sent to FE
        "trigger_rate_limit": 500,  # artificially limiting the trigger rate, in BCs (25ns)
        "trig_count": 0,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "col_span": [1, 80],  # column range (from minimum to maximum value). From 1 to 80.
        "row_span": [1, 336],  # row range (from minimum to maximum value). From 1 to 336.
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
        # TDAC
        tdac_max = 2 ** self.register.pixel_registers['TDAC']['bitlength'] - 1
        self.register.set_pixel_register_value("TDAC", tdac_max)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="TDAC"))
        mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)
        # Enable
        if self.use_enable_mask:
            self.register.set_pixel_register_value("Enable", np.logical_and(mask, self.register.get_pixel_register_value("Enable")))
        else:
            self.register.set_pixel_register_value("Enable", mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="Enable"))
        # Imon
        self.register.set_pixel_register_value('Imon', 1)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='Imon'))
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

        self.interpreter = PyDataInterpreter()
        self.histograming = PyDataHistograming()
        self.interpreter.set_trig_count(self.trig_count)
        self.interpreter.set_warning_output(False)
        self.histograming.set_no_scan_parameter()
        self.histograming.create_occupancy_hist(True)

    def scan(self):
        scan_parameter_range = [self.register.get_global_register_value("Vthin_AltFine"), 0]
        if self.scan_parameters.Vthin_AltFine[0]:
            scan_parameter_range[0] = self.scan_parameters.Vthin_AltFine[0]
        if self.scan_parameters.Vthin_AltFine[1]:
            scan_parameter_range[1] = self.scan_parameters.Vthin_AltFine[1]
        steps = 1
        if self.scan_parameters.Step:
            steps = self.scan_parameters.Step

        lvl1_command = self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.total_scan_time = int(lvl1_command.length() * 25 * (10 ** -9) * self.n_triggers)

        disabled_pixels_limit_cnt = int(self.disabled_pixels_limit * 336 * 80)
        preselected_pixels = invert_pixel_mask(self.register.get_pixel_register_value('Enable')).sum()
        disabled_pixels = 0

        for reg_val in range(scan_parameter_range[0], scan_parameter_range[1] - 1, -1):
            if self.stop_run.is_set():
                break
            self.register.create_restore_point(name=str(reg_val))
            logging.info('Scanning Vthin_AltFine %d', reg_val)
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value("Vthin_AltFine", reg_val)  # set number of consecutive triggers
            commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
            # setting FE into RunMode
            commands.extend(self.register.get_commands("RunMode"))
            self.register_utils.send_commands(commands)
            step = 0
            while True:
                if self.stop_run.is_set():
                    break
                self.histograming.reset()
                step += 1
                logging.info('Step %d / %d at Vthin_AltFine %d', step, steps, reg_val)
                logging.info('Estimated scan time: %ds', self.total_scan_time)

                with self.readout(Vthin_AltFine=reg_val, Step=step, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
                    got_data = False
                    start = time()
                    self.register_utils.send_command(lvl1_command, repeat=self.n_triggers, wait_for_finish=False, set_length=True, clear_memory=False)
                    while not self.stop_run.wait(0.1):
                        if self.register_utils.is_ready:
                            if got_data:
                                self.progressbar.finish()
                            logging.info('Finished sending %d triggers', self.n_triggers)
                            break
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
                # Use fast C++ hit histograming to save time
                raw_data = np.ascontiguousarray(data_array_from_data_iterable(self.fifo_readout.data), dtype=np.uint32)
                self.interpreter.interpret_raw_data(raw_data)
                self.interpreter.store_event()  # force to create latest event
                self.histograming.add_hits(self.interpreter.get_hits())
                occ_hist = self.histograming.get_occupancy()[:, :, 0]
                # noisy pixels are set to 1
                occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
                occ_mask[occ_hist > self.occupancy_limit * self.n_triggers * self.consecutive_lvl1] = 1

                tdac_reg = self.register.get_pixel_register_value('TDAC')
                decrease_pixel_mask = np.logical_and(occ_mask > 0, tdac_reg > 0)
                disable_pixel_mask = np.logical_and(occ_mask > 0, tdac_reg == 0)
                enable_reg = self.register.get_pixel_register_value('Enable')
                enable_mask = np.logical_and(enable_reg, invert_pixel_mask(disable_pixel_mask))
                if np.logical_and(occ_mask > 0, enable_reg == 0).sum():
                    logging.warning('Received data from disabled pixels')
#                     disabled_pixels += disable_pixel_mask.sum()  # can lead to wrong values if the enable reg is corrupted
                disabled_pixels = invert_pixel_mask(enable_mask).sum() - preselected_pixels
                if disabled_pixels > disabled_pixels_limit_cnt:
                    logging.info('Limit of disabled pixels reached: %d (limit %d)... stopping scan' % (disabled_pixels, disabled_pixels_limit_cnt))
                    self.register.restore(name=str(reg_val))
                    break
                else:
                    logging.info('Increasing threshold of %d pixel(s)', decrease_pixel_mask.sum())
                    logging.info('Disabling %d pixel(s), total number of disabled pixel(s): %d', disable_pixel_mask.sum(), disabled_pixels)
                    tdac_reg[decrease_pixel_mask] -= 1
                    self.register.set_pixel_register_value('TDAC', tdac_reg)
                    self.register.set_pixel_register_value('Enable', enable_mask)
                    commands = []
                    commands.extend(self.register.get_commands("ConfMode"))
                    commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='TDAC'))
                    commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Enable'))
                    commands.extend(self.register.get_commands("RunMode"))
                    self.register_utils.send_commands(commands)
                    if occ_mask.sum() == 0 or step == steps or decrease_pixel_mask.sum() < disabled_pixels_limit_cnt:
                        self.register.clear_restore_points(name=str(reg_val))
                        self.last_tdac_distribution = self.register.get_pixel_register_value('TDAC')
                        self.last_occupancy_hist = occ_hist.copy()
                        self.last_occupancy_mask = occ_mask.copy()
                        self.last_reg_val = reg_val
                        self.last_step = step
                        break
                    else:
                        logging.info('Found %d noisy pixels... repeat tuning step for Vthin_AltFine %d', occ_mask.sum(), reg_val)

            if disabled_pixels > disabled_pixels_limit_cnt:
                self.last_good_threshold = self.register.get_global_register_value("Vthin_AltFine")
                self.last_good_tdac = self.register.get_pixel_register_value('TDAC')
                self.last_good_enable_mask = self.register.get_pixel_register_value('Enable')
                break

    def analyze(self):
        self.register.set_global_register_value("Vthin_AltFine", self.last_good_threshold + self.increase_threshold)
        self.register.set_pixel_register_value('TDAC', self.last_good_tdac)
        self.register.set_pixel_register_value('Enable', self.last_good_enable_mask)
        # write configuration to avaoid high current states
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="TDAC"))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="Enable"))
        self.register_utils.send_commands(commands)

        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
            plot_occupancy(self.last_occupancy_hist.T, title='Noisy Pixels at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.last_occupancy_hist.T, filename=analyze_raw_data.output_pdf)
            plot_occupancy(self.last_occupancy_mask.T, title='Occupancy Mask at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), z_max=1, filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.last_occupancy_mask.T, filename=analyze_raw_data.output_pdf)
            plot_three_way(self.last_tdac_distribution.T, title='TDAC at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), x_axis_title="TDAC", filename=analyze_raw_data.output_pdf, maximum=31, bins=32)
            plot_occupancy(self.last_tdac_distribution.T, title='TDAC at Vthin_AltFine %d Step %d' % (self.last_reg_val, self.last_step), z_max=31, filename=analyze_raw_data.output_pdf)
            plot_occupancy(self.register.get_pixel_register_value('Enable').T, title='Enable Mask', z_max=1, filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.register.get_pixel_register_value('Enable').T, filename=analyze_raw_data.output_pdf)

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(ThresholdBaselineTuning)
