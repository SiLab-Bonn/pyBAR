import logging
from time import time
from collections import deque

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
from scipy import stats

import progressbar

from pybar.daq.readout_utils import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_iterable, is_fe_word, is_data_record, logical_and
# from pybar.daq.readout_utils import data_array_from_data_iterable
# from pybar_fei4_interpreter.data_interpreter import PyDataInterpreter
# from pybar_fei4_interpreter.data_histograming import PyDataHistograming
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import make_box_pixel_mask_from_col_row, invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy, plot_three_way, hist_quantiles


class ThresholdBaselineTuning(Fei4RunBase):
    '''Threshold Baseline Tuning aka Noise Tuning

    Tuning the FEI4 to the lowest possible threshold (GDAC and TDAC). Feedback current will not be tuned.
    NOTE: In case of RX errors decrease the trigger frequency (= increase trigger_rate_limit), or reduce the number of triggers
    NOTE: To increase the TDAC range, decrease TdacVbp.
    '''
    _default_run_conf = {
        "occupancy_limit": 1 * 10 ** (-5),  # occupancy limit, when reached, the TDAC will be decreased (threshold increased). 0 will mask any pixel with occupancy greater than zero. Occupancy limit 10^-5 is default for IBL (see ATLAS IBL TDR)
        "start_gdac": 120,  # start value of GDAC tuning
        "gdac_lower_limit": 0,  # set GDAC lower limit to prevent FEI4 from becoming noisy, set to 0 or None to disable
        "scan_parameters": [('Vthin_AltFine', None), ('TDAC_step', None)],  # the Vthin_AltFine range, number of steps (repetition at constant Vthin_AltFine)
        "refine_tuning": True,  # undertake additional TDAC tuning steps, might increase threshold but will reduce noise occupancy to a minimum
        "plot_n_steps": 5,  # store and plot n last steps
        "disabled_pixels_limit": 0.01,  # limit of disabled pixels, fraction of all pixels
        "use_enable_mask": False,  # if True, enable mask from config file anded with mask (from col_span and row_span), if False use mask only for enable mask
        "n_triggers": 10000,  # total number of trigger sent to FE
        "trigger_rate_limit": 500,  # artificially limiting the trigger rate, in BCs (25ns)
        "trig_count": 1,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "col_span": [1, 80],  # column range (from minimum to maximum value). From 1 to 80.
        "row_span": [1, 336],  # row range (from minimum to maximum value). From 1 to 336.
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # GDAC
        self.gdac_range = [self.register.get_global_register_value("Vthin_AltFine"), 0]  # default GDAC range
        if self.start_gdac is not None:
            self.gdac_range[0] = min(self.start_gdac, 2 ** self.register.global_registers['Vthin_AltFine']['bitlength'])
        if self.gdac_lower_limit is not None:
            self.gdac_range[1] = max(self.gdac_lower_limit, 0)
        self.register.set_global_register_value("Vthin_AltFine", self.gdac_range[0])  # set to start threshold value
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
        enabled_pixels = self.register.get_pixel_register_value('Enable').sum()
        preselected_pixels = invert_pixel_mask(self.register.get_pixel_register_value('Enable')).sum()
        disabled_pixels_limit_cnt = int(self.disabled_pixels_limit * self.register.get_pixel_register_value('Enable').sum())
        abs_occ_limit = stats.poisson.ppf(0.5, mu=self.occupancy_limit * self.n_triggers * self.consecutive_lvl1)
        logging.info('The pixel threshold will be increased when occpancy >%d' % abs_occ_limit)
        total_occ_limit = int(self.occupancy_limit * self.n_triggers * self.consecutive_lvl1 * enabled_pixels)
        # Sum of PMF of Poisson distribution (k>0)
        n_expected_pixel_hits = int((1.0 - stats.poisson.pmf(k=0, mu=self.occupancy_limit * self.n_triggers * self.consecutive_lvl1)) * enabled_pixels)
        logging.info('The global threshold will be decreased when total occupancy is <=%d and pixel with hits <=%d' % (total_occ_limit, n_expected_pixel_hits))
        max_tdac_steps = max(1, int(np.ceil((1 / self.occupancy_limit) / (self.n_triggers * self.consecutive_lvl1) * (1 / (1 - 0.5)))))
        tdac_center = 2 ** self.register.pixel_registers['TDAC']['bitlength'] / 2
        lvl1_command = self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        total_scan_time = int(lvl1_command.length() * 25 * (10 ** -9) * self.n_triggers)

        self.threshold = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.tdac_step = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.tdac = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.new_tdac = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.enable_mask = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.new_enable_mask = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.occupancy_hist = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)
        self.occupancy_mask = deque([None] * (self.plot_n_steps + 2), maxlen=self.plot_n_steps + 2)

#         interpreter = PyDataInterpreter()
#         histogram = PyDataHistograming()
#         interpreter.set_trig_count(self.trig_count)
#         interpreter.set_warning_output(False)
#         histogram.set_no_scan_parameter()
#         histogram.create_occupancy_hist(True)
        coarse_threshold = [self.gdac_range[0]]
        reached_pixels_limit_cnt = False
        reached_tdac_center = False
        reached_gdac_lower_limit = False
        do_refine_tuning = False
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
            tdac_step = 1
            while True:  # inner loop
                if self.stop_run.is_set():
                    break
#                 histogram.reset()

                logging.info('TDAC step %d at Vthin_AltFine %d', tdac_step, reg_val)
#                 logging.info('Estimated scan time: %ds', total_scan_time)

                with self.readout(Vthin_AltFine=reg_val, TDAC_step=tdac_step, reset_sram_fifo=True, fill_buffer=True, clear_buffer=True, callback=self.handle_data):
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
                enable_mask = self.register.get_pixel_register_value('Enable')
                new_enable_mask = np.logical_and(enable_mask, invert_pixel_mask(disable_pixel_mask))
                if np.logical_and(occ_mask > 0, enable_mask == 0).sum():
                    logging.warning('Received data from disabled pixels')
#                     disabled_pixels += disable_pixel_mask.sum()  # can lead to wrong values if the enable reg is corrupted
                disabled_pixels = invert_pixel_mask(new_enable_mask).sum() - preselected_pixels
                logging.info('Found %d noisy pixels', occ_mask.sum())
                logging.info('Increasing threshold of %d pixel(s)', decrease_pixel_mask.sum())
                logging.info('Disabling %d pixel(s), total number of disabled pixel(s): %d', disable_pixel_mask.sum(), disabled_pixels)

                # increasing threshold before writing TDACs to avoid FE becoming noisy
                self.register.set_global_register_value("Vthin_AltFine", self.gdac_range[0])
                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine"]))
                self.register_utils.send_commands(commands)
                # writing TDAC
                new_tdac_reg = tdac_reg.copy()
                new_tdac_reg[decrease_pixel_mask] -= 1  # smaller TDAC translates to higher threshold
                self.register.set_pixel_register_value('TDAC', new_tdac_reg)
                self.register.set_pixel_register_value('Enable', new_enable_mask)
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

                if (not do_refine_tuning and occ_hist.sum() <= total_occ_limit and occ_mask.sum() <= n_expected_pixel_hits) or (tdac_step >= max_tdac_steps):
                    logging.info('Stop tuning TDACs at Vthin_AltFine %d', reg_val)
                    self.threshold.appendleft(self.register.get_global_register_value("Vthin_AltFine"))
                    self.tdac_step.appendleft(tdac_step)
                    self.tdac.appendleft(tdac_reg)
                    self.new_tdac.appendleft(new_tdac_reg)
                    self.enable_mask.appendleft(enable_mask)
                    self.new_enable_mask.appendleft(new_enable_mask)
                    self.occupancy_hist.appendleft(occ_hist.copy())
                    self.occupancy_mask.appendleft(occ_mask.copy())
                    if not do_refine_tuning and np.mean(new_tdac_reg[new_enable_mask]) <= tdac_center + (1 if self.refine_tuning else 0):
                        reached_tdac_center = True
                    if not do_refine_tuning and disabled_pixels > disabled_pixels_limit_cnt:
                        reached_pixels_limit_cnt = True
                        logging.info('Limit of disabled pixels reached: %d (limit %d).' % (disabled_pixels, disabled_pixels_limit_cnt))
                    if not do_refine_tuning and reg_val <= self.gdac_range[1]:
                        reached_gdac_lower_limit = True
                    break
                else:
                    logging.info('Continue tuning TDACs at Vthin_AltFine %d', reg_val)
                # increase scan parameter counter
                tdac_step += 1

            if not self.refine_tuning and (reached_pixels_limit_cnt or reached_tdac_center or reached_gdac_lower_limit):
                pass  # will exit loop
            elif do_refine_tuning:
                logging.info("Finished TDAC refine tuning.")
            elif reached_pixels_limit_cnt or reached_tdac_center or reached_gdac_lower_limit:
                do_refine_tuning = True
                logging.info("Starting TDAC refine tuning...")
                coarse_threshold.append(reg_val - 1)
                abs_occ_limit = stats.poisson.ppf(0.99, mu=self.occupancy_limit * self.n_triggers * self.consecutive_lvl1)
                logging.info('The pixel threshold will be increased when occpancy >%d' % abs_occ_limit)
                max_tdac_steps = max(1, int(np.ceil((1 / self.occupancy_limit) / (self.n_triggers * self.consecutive_lvl1) * (1 / (1 - 0.99)))))
            else:
                coarse_threshold.append(reg_val - 1)

    def analyze(self):
        self.register.set_global_register_value("Vthin_AltFine", self.threshold[0])
        self.register.set_pixel_register_value('TDAC', self.new_tdac[0])
        self.register.set_pixel_register_value('Enable', self.new_enable_mask[0])  # use enable mask from the lowest point to mask bad pixels
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
            last_step = None
            for step in range(self.plot_n_steps, -1, -1):
                if self.threshold[step] is not None:
                    plot_occupancy(self.occupancy_hist[step].T, title='Occupancy at Vthin_AltFine %d Step %d' % (self.threshold[step], self.tdac_step[step]), filename=analyze_raw_data.output_pdf)
                    plot_fancy_occupancy(self.occupancy_hist[step].T, filename=analyze_raw_data.output_pdf)
                    plot_occupancy(self.occupancy_mask[step].T, title='Noisy pixels at Vthin_AltFine %d Step %d' % (self.threshold[step], self.tdac_step[step]), z_max=1, filename=analyze_raw_data.output_pdf)
                    plot_fancy_occupancy(self.occupancy_mask[step].T, filename=analyze_raw_data.output_pdf)
                    plot_three_way(self.tdac[step].T, title='TDAC at Vthin_AltFine %d Step %d' % (self.threshold[step], self.tdac_step[step]), x_axis_title="TDAC", filename=analyze_raw_data.output_pdf, maximum=31, bins=32)
                    plot_occupancy(self.tdac[step].T, title='TDAC at Vthin_AltFine %d Step %d' % (self.threshold[step], self.tdac_step[step]), z_max=31, filename=analyze_raw_data.output_pdf)
                    plot_occupancy(self.enable_mask[step].T, title='Enable mask at Vthin_AltFine %d Step %d' % (self.threshold[step], self.tdac_step[step]), z_max=1, filename=analyze_raw_data.output_pdf)
                    # adding Poisson statistics plots
                    fig = Figure()
                    FigureCanvas(fig)
                    ax = fig.add_subplot(111)
                    ax.set_title("Hit statistics")
                    hist, bin_edges = np.histogram(self.occupancy_hist[step], bins=np.arange(0.0, np.max(self.occupancy_hist[step]) + 1, 1.0))
                    _, idx = hist_quantiles(hist, [0.0, 0.9], return_indices=True)
                    bins = np.arange(0, np.maximum(bin_edges[idx[1]], stats.poisson.ppf(0.9999, mu=self.occupancy_limit * self.n_triggers * self.consecutive_lvl1)) + 1, 1)
                    ax.hist(self.occupancy_hist[step].flatten(), bins=bins, align='left', alpha=0.5, label="Measured occupancy")
                    ax.bar(x=bins[:-1], height=stats.poisson.pmf(k=bins[:-1], mu=self.occupancy_limit * self.n_triggers * self.consecutive_lvl1) * self.enable_mask[step].sum(), alpha=0.5, width=1.0, color="r", label="Expected occupancy (Poisson statistics)")
                    # ax.hist(stats.poisson.rvs(mu=self.occupancy_limit * self.n_triggers * self.consecutive_lvl1, size=self.enable_mask[step].sum()), bins=bins, align='left', alpha=0.5, label="Expected occupancy (Poisson statistics)")
                    ax.set_xlabel('#Hits')
                    ax.set_ylabel('#Pixels')
                    ax.legend()
                    analyze_raw_data.output_pdf.savefig(fig)
                    last_step = step
            if last_step is not None:
                plot_three_way(self.new_tdac[last_step].T, title='Final TDAC after Vthin_AltFine %d Step %d' % (self.threshold[last_step], self.tdac_step[last_step]), x_axis_title="TDAC", filename=analyze_raw_data.output_pdf, maximum=31, bins=32)
                plot_occupancy(self.new_tdac[last_step].T, title='Final TDAC after Vthin_AltFine %d Step %d' % (self.threshold[last_step], self.tdac_step[last_step]), z_max=31, filename=analyze_raw_data.output_pdf)
                plot_occupancy(self.new_enable_mask[last_step].T, title='Final Enable mask after Vthin_AltFine %d Step %d' % (self.threshold[last_step], self.tdac_step[last_step]), z_max=1, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    RunManager('configuration.yaml').run_run(ThresholdBaselineTuning)
