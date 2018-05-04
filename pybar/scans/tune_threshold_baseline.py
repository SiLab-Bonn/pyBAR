import logging
from time import time
import numpy as np
import progressbar
from collections import deque

from pybar.daq.readout_utils import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_iterable, is_fe_word, is_data_record, logical_and
# from pybar.daq.readout_utils import data_array_from_data_iterable
# from pybar_fei4_interpreter.data_interpreter import PyDataInterpreter
# from pybar_fei4_interpreter.data_histograming import PyDataHistograming
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import make_box_pixel_mask_from_col_row, invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy, plot_three_way


class ThresholdBaselineTuning(Fei4RunBase):
    '''Threshold Baseline Tuning aka Noise Tuning

    Tuning the FEI4 to the lowest possible threshold (GDAC and TDAC). Feedback current will not be tuned.
    NOTE: In case of RX errors decrease the trigger frequency (= increase trigger_rate_limit), or reduce the number of triggers
    NOTE: To increase the TDAC range, decrease TdacVbp.
    '''
    _default_run_conf = {
        "occupancy_limit": 1 * 10 ** (-5),  # occupancy limit, when reached the TDAC will be decreased (increasing threshold). 0 will mask any pixel with occupancy greater than zero
        "scan_parameters": [('Vthin_AltFine', (120, None)), ('TDAC_step', None), ('relaxation', 0)],  # the Vthin_AltFine range, number of steps (repetition at constant Vthin_AltFine)
        "increase_threshold": 5,  # increasing the global threshold (Vthin_AltFine) after tuning
        "disabled_pixels_limit": 0.01,  # limit of disabled pixels, fraction of all pixels
        "use_enable_mask": False,  # if True, enable mask from config file anded with mask (from col_span and row_span), if False use mask only for enable mask
        "n_triggers": 10000,  # total number of trigger sent to FE
        "trigger_rate_limit": 500,  # artificially limiting the trigger rate, in BCs (25ns)
        "trig_count": 0,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "col_span": [1, 80],  # column range (from minimum to maximum value). From 1 to 80.
        "row_span": [1, 336],  # row range (from minimum to maximum value). From 1 to 336.
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # GDAC
        self.scan_parameter_range = [self.register.get_global_register_value("Vthin_AltFine"), 0]
        if self.scan_parameters.Vthin_AltFine[0] is not None:
            self.scan_parameter_range[0] = min(self.scan_parameters.Vthin_AltFine[0], 2 ** self.register.global_registers['Vthin_AltFine']['bitlength'])
        if self.scan_parameters.Vthin_AltFine[1] is not None:
            self.scan_parameter_range[1] = max(self.scan_parameters.Vthin_AltFine[1], 0)
        self.register.set_global_register_value("Vthin_AltFine", self.scan_parameter_range[0])  # set to start threshold value
        commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
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

    def scan(self):
        if self.trig_count == 0:
            self.consecutive_lvl1 = 2 ** self.register.global_registers['Trig_Count']['bitlength']
        else:
            self.consecutive_lvl1 = self.trig_count
        abs_occ_limit = int(self.occupancy_limit * self.n_triggers * self.consecutive_lvl1)
        if abs_occ_limit <= 0:
            logging.info('Any noise hit will lead to an increased pixel threshold.')
        else:
            logging.info('The pixel threshold of any pixel with an occpancy >%d will be increased' % abs_occ_limit)

        if self.scan_parameters.TDAC_step:
            max_tdac_steps = self.scan_parameters.TDAC_step
        else:
            max_tdac_steps = 2 ** self.register.pixel_registers['TDAC']['bitlength']
        tdac_center = 2 ** self.register.pixel_registers['TDAC']['bitlength'] / 2

        lvl1_command = self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        total_scan_time = int(lvl1_command.length() * 25 * (10 ** -9) * self.n_triggers)

        preselected_pixels = invert_pixel_mask(self.register.get_pixel_register_value('Enable')).sum()
        disabled_pixels_limit_cnt = int(self.disabled_pixels_limit * self.register.get_pixel_register_value('Enable').sum())
        self.last_reg_val = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)
        self.last_step = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)
        self.last_good_threshold = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)
        self.last_good_tdac = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)
        self.last_good_enable_mask = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)
        self.last_occupancy_hist = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)
        self.last_occupancy_mask = deque([None] * (self.increase_threshold + 1), maxlen=self.increase_threshold + 1)

#         interpreter = PyDataInterpreter()
#         histogram = PyDataHistograming()
#         interpreter.set_trig_count(self.trig_count)
#         interpreter.set_warning_output(False)
#         histogram.set_no_scan_parameter()
#         histogram.create_occupancy_hist(True)
        coarse_threshold = [self.scan_parameter_range[0]]
        reached_pixels_limit_cnt = False
        reached_tdac_center = False
        relaxation = False
        for reg_val in coarse_threshold:  # outer loop, coarse tuning threshold
            if self.stop_run.is_set():
                break
            logging.info('Scanning Vthin_AltFine %d', reg_val)
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value("Vthin_AltFine", reg_val)
            commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
            # setting FE into RunMode
            commands.extend(self.register.get_commands("RunMode"))
            self.register_utils.send_commands(commands)
            tdac_step = 0
            while True:  # inner loop
                if self.stop_run.is_set():
                    break
#                 histogram.reset()

                logging.info('TDAC step %d at Vthin_AltFine %d', tdac_step, reg_val)
#                 logging.info('Estimated scan time: %ds', total_scan_time)

                with self.readout(Vthin_AltFine=reg_val, TDAC_step=tdac_step, relaxation=relaxation, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
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
                                self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.Timer()], maxval=total_scan_time, poll=10, term_width=80).start()
                        else:
                            try:
                                self.progressbar.update(time() - start)
                            except ValueError:
                                pass
                # use Numpy for analysis and histogramming
                col_arr, row_arr = convert_data_array(data_array_from_data_iterable(self.fifo_readout.data), filter_func=logical_and(is_fe_word, is_data_record), converter_func=get_col_row_array_from_data_record_array)
                occ_hist, _, _ = np.histogram2d(col_arr, row_arr, bins=(80, 336), range=[[1, 80], [1, 336]])
                occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))

                # use FEI4 interpreter for analysis and histogramming
#                 from pybar.daq.readout_utils import data_array_from_data_iterable
#                 raw_data = np.ascontiguousarray(data_array_from_data_iterable(self.read_data()), dtype=np.uint32)
#                 interpreter.interpret_raw_data(raw_data)
#                 interpreter.store_event()  # force to create latest event
#                 histogram.add_hits(interpreter.get_hits())
#                 occ_hist = histogram.get_occupancy()[:, :, 0]
#                 # noisy pixels are set to 1
#                 occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))

                occ_mask[occ_hist > abs_occ_limit] = 1

                tdac_reg = self.register.get_pixel_register_value('TDAC')
                decrease_pixel_mask = np.logical_and(occ_mask > 0, tdac_reg > 0)
                disable_pixel_mask = np.logical_and(occ_mask > 0, tdac_reg == 0)
                enable_reg = self.register.get_pixel_register_value('Enable')
                enable_mask = np.logical_and(enable_reg, invert_pixel_mask(disable_pixel_mask))
                if np.logical_and(occ_mask > 0, enable_reg == 0).sum():
                    logging.warning('Received data from disabled pixels')
#                     disabled_pixels += disable_pixel_mask.sum()  # can lead to wrong values if the enable reg is corrupted
                disabled_pixels = invert_pixel_mask(enable_mask).sum() - preselected_pixels
                if not relaxation and disabled_pixels > disabled_pixels_limit_cnt:
                    logging.info('Limit of disabled pixels reached: %d (limit %d).' % (disabled_pixels, disabled_pixels_limit_cnt))
                    reached_pixels_limit_cnt = True
                    break
                else:
                    logging.info('Found %d noisy pixels', occ_mask.sum())
                    logging.info('Increasing threshold of %d pixel(s)', decrease_pixel_mask.sum())
                    logging.info('Disabling %d pixel(s), total number of disabled pixel(s): %d', disable_pixel_mask.sum(), disabled_pixels)

                    # increasing threshold before writing TDACs to avoid FE becoming noisy
                    self.register.set_global_register_value("Vthin_AltFine", self.scan_parameter_range[0])
                    commands = []
                    commands.extend(self.register.get_commands("ConfMode"))
                    commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
                    self.register_utils.send_commands(commands)
                    # writing TDAC
                    tdac_reg[decrease_pixel_mask] -= 1
                    self.register.set_pixel_register_value('TDAC', tdac_reg)
                    self.register.set_pixel_register_value('Enable', enable_mask)
                    commands = []
                    commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='TDAC'))
                    commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Enable'))
                    self.register_utils.send_commands(commands)
                    # writing threshold value after writing TDACs
                    self.register.set_global_register_value("Vthin_AltFine", reg_val)
                    commands = []
                    commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
                    commands.extend(self.register.get_commands("RunMode"))
                    self.register_utils.send_commands(commands)

                    max_relaxation_steps = int((1.0 / self.occupancy_limit) / self.n_triggers) * 10  # use 10 times more injections than required by the noise occupancy limit to remove any noisy pixels
                    if occ_mask.sum() == 0 or (not relaxation and tdac_step >= max_tdac_steps - 1) or (relaxation and tdac_step >= max_relaxation_steps - 1):
                        logging.info('Stop tuning TDACs at Vthin_AltFine %d', reg_val)
                        self.last_reg_val.appendleft(reg_val)
                        self.last_step.appendleft(tdac_step)
                        self.last_good_threshold.appendleft(self.register.get_global_register_value("Vthin_AltFine"))
                        self.last_good_tdac.appendleft(self.register.get_pixel_register_value("TDAC"))
                        self.last_good_enable_mask.appendleft(self.register.get_pixel_register_value("Enable"))
                        self.last_occupancy_hist.appendleft(occ_hist.copy())
                        self.last_occupancy_mask.appendleft(occ_mask.copy())
                        if np.mean(tdac_reg[enable_mask]) <= tdac_center:
                            reached_tdac_center = True
                        break
                    else:
                        logging.info('Continue tuning TDACs at Vthin_AltFine %d', reg_val)
                # increase scan parameter counter
                tdac_step += 1

            if relaxation:
                if self.increase_threshold > 0:
                    logging.info('Increasing Vthin_AltFine from %d to %d', self.last_good_threshold[0], self.last_good_threshold[0] + self.increase_threshold)
                    self.register.set_global_register_value("Vthin_AltFine", self.last_good_threshold[0] + self.increase_threshold)
                    commands = []
                    commands.extend(self.register.get_commands("ConfMode"))
                    commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
                    commands.extend(self.register.get_commands("RunMode"))
                    self.register_utils.send_commands(commands)
#             elif reached_tdac_center:
#                 relaxation = True
#                 coarse_threshold.append(reg_val)
            elif reached_pixels_limit_cnt or reached_tdac_center:
                relaxation = True
                # deque might still contain None items, so iterate over it
                changed_threshold = False
                for index in range(self.increase_threshold + 1):
                    if self.last_good_threshold[index] is not None:
                        changed_threshold = True
                        coarse_threshold.append(self.last_good_threshold[index])
                        self.register.set_global_register_value("Vthin_AltFine", self.last_good_threshold[index])
                        self.register.set_pixel_register_value('TDAC', self.last_good_tdac[index])  # use enable mask from the lowest global threshold and continue
                        self.register.set_pixel_register_value('Enable', self.last_good_enable_mask[index])  # use enable mask from the lowest global threshold and keep disabled pixels
                        # write configuration to avaoid high current states
                        commands = []
                        commands.extend(self.register.get_commands("ConfMode"))
                        commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
                        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="TDAC"))
                        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="Enable"))
                        commands.extend(self.register.get_commands("RunMode"))
                        self.register_utils.send_commands(commands)
                        break
                # if all items are None, use last threshold again
                if not changed_threshold:
                    coarse_threshold.append(reg_val)
            else:
                coarse_threshold.append(reg_val - 1)

    def analyze(self):
        self.register.set_global_register_value("Vthin_AltFine", self.last_good_threshold[0] + self.increase_threshold)
        self.register.set_pixel_register_value('TDAC', self.last_good_tdac[0])
        self.register.set_pixel_register_value('Enable', self.last_good_enable_mask[0])  # use enable mask from the lowest point to mask bad pixels
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
            for increase_threshold in range(self.increase_threshold, -1, -1):
                if self.last_good_threshold[increase_threshold] is not None:
                    plot_occupancy(self.last_occupancy_hist[increase_threshold].T, title='Occupancy at Vthin_AltFine %d Step %d' % (self.last_reg_val[increase_threshold], self.last_step[increase_threshold]), filename=analyze_raw_data.output_pdf)
                    plot_fancy_occupancy(self.last_occupancy_hist[increase_threshold].T, filename=analyze_raw_data.output_pdf)
                    plot_occupancy(self.last_occupancy_mask[increase_threshold].T, title='Noisy pixels at Vthin_AltFine %d Step %d' % (self.last_reg_val[increase_threshold], self.last_step[increase_threshold]), z_max=1, filename=analyze_raw_data.output_pdf)
                    plot_fancy_occupancy(self.last_occupancy_mask[increase_threshold].T, filename=analyze_raw_data.output_pdf)
                    plot_three_way(self.last_good_tdac[increase_threshold].T, title='TDAC at Vthin_AltFine %d Step %d' % (self.last_reg_val[increase_threshold], self.last_step[increase_threshold]), x_axis_title="TDAC", filename=analyze_raw_data.output_pdf, maximum=31, bins=32)
                    plot_occupancy(self.last_good_tdac[increase_threshold].T, title='TDAC at Vthin_AltFine %d Step %d' % (self.last_reg_val[increase_threshold], self.last_step[increase_threshold]), z_max=31, filename=analyze_raw_data.output_pdf)
                    plot_occupancy(self.last_good_enable_mask[increase_threshold].T, title='Enable mask at Vthin_AltFine %d Step %d' % (self.last_reg_val[increase_threshold], self.last_step[increase_threshold]), z_max=1, filename=analyze_raw_data.output_pdf)
                    plot_fancy_occupancy(self.last_good_enable_mask[increase_threshold].T, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    RunManager('configuration.yaml').run_run(ThresholdBaselineTuning)
