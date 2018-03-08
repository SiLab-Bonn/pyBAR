import logging

from matplotlib.backends.backend_pdf import PdfPages

from pybar.run_manager import RunManager
from pybar.scans.tune_gdac import GdacTuning
from pybar.scans.tune_feedback import FeedbackTuning
from pybar.scans.tune_tdac import TdacTuning
from pybar.scans.tune_fdac import FdacTuning
from pybar.analysis.plotting.plotting import plot_three_way


class Fei4Tuning(GdacTuning, TdacTuning, FeedbackTuning, FdacTuning):
    '''Fully automatic FEI4 Tuning

    This is a meta script implementing GDAC, TDAC, Feedback and FDAC tuning in a single tuning script.
    Values are given in units of PlsrDAC.

    Note:
    C_Low: nominally 1.9fF / measured* 2fF
    C_High: nominally 3.8fF / measured* 4.1fF
    c_Low + C_High: nominally 5.7fF / measured* 6.1fF

    PlsrDAC: ~1.5mV/DAC

    C_Low: 18.7e / 19.7e
    C_High: 35.6e / 38.4e
    C_Low + C_High: 53e / 57e

    *) measurements from IBL wafer probing
    '''
    _default_run_conf = {
        # tuning parameters
        "target_threshold": 30,  # target threshold
        "target_charge": 280,  # target charge
        "target_tot": 5,  # target ToT
        "global_iterations": 4,  # the number of iterations to do for the global tuning, 0: only global threshold (GDAC) is tuned, -1 or None: no global tuning
        "local_iterations": 3,  # the number of iterations to do for the local tuning, 0: only local threshold (TDAC) is tuned, -1 or None: no local tuning
        "reset_local_dacs": True,  # if True, reset pixels registers to the middle of the DAC range before the global tuning starts
        "fail_on_warning": True,  # do not continue tuning if a global tuning fails
        # GDAC
        "gdac_tune_bits": range(7, -1, -1),  # GDAC bits to change during tuning
        "gdac_lower_limit": 30,  # set GDAC lower limit to prevent FEI4 from becoming noisy, set to 0 or None to disable
        "n_injections_gdac": 50,  # number of injections per GDAC bit setting
        "max_delta_threshold": 15,  # minimum difference to the target_threshold to abort the tuning, in percent of n_injections_gdac
        "enable_mask_steps_gdac": [0],  # mask steps to do per GDAC setting, 1 step is sufficient and saves time
        # Feedback
        "feedback_tune_bits": range(7, -1, -1),
        "n_injections_feedback": 50,
        "max_delta_tot": 0.1,
        "enable_mask_steps_feedback": [0],  # mask steps to do per PrmpVbpf setting, 1 step is sufficient and saves time
        # TDAC
        "tdac_tune_bits": range(4, -1, -1),
        "n_injections_tdac": 100,
        # FDAC
        "fdac_tune_bits": range(3, -1, -1),
        "n_injections_fdac": 30,
        # general
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "scan_parameters": [('GDAC', -1), ('TDAC', -1), ('PrmpVbpf', -1), ('FDAC', -1), ('global_step', 0), ('local_step', 0)],
        # plotting
        "make_plots": True,  # plots for all scan steps are created
        "plot_intermediate_steps": False,  # plot intermediate steps (takes time)
        "plots_filename": None,  # file name to store the plot to, if None show on screen
        # other
        "mask_steps": 3,  # mask steps, be carefull PlsrDAC injects different charge for different mask steps
        "same_mask_for_all_dc": True  # Increases scan speed, should be deactivated for very noisy FE
    }

    def configure(self):
        super(Fei4Tuning, self).configure()

        # overwrite pixel registers and set them to center postion before a global tuning
        if self.reset_local_dacs and self.global_iterations:
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            # TDAC
            tdac_center = 2 ** self.register.pixel_registers['TDAC']['bitlength'] / 2
            self.register.set_pixel_register_value('TDAC', tdac_center)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='TDAC'))
            # FDAC
            fdac_center = 2 ** self.register.pixel_registers['FDAC']['bitlength'] / 2
            self.register.set_pixel_register_value('FDAC', fdac_center)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='FDAC'))
            commands.extend(self.register.get_commands("RunMode"))
            self.register_utils.send_commands(commands)


    def scan(self):
        '''Metascript that calls other scripts to tune the FE.

        Parameters
        ----------
        cfg_name : string
            Name of the config to be created. This config holds the tuning results.
        target_threshold : int
            The target threshold value in PlsrDAC.
        target_charge : int
            The target charge in PlsrDAC value to tune to.
        target_tot : float
            The target tot value to tune to.
        global_iterations : int
            Defines how often global threshold (GDAC) / global feedback (PrmpVbpf) current tuning is repeated.
            -1 or None: Global tuning is disabled
            0: Only global threshold tuning
            1: GDAC -> PrmpVbpf -> GDAC
            2: GDAC -> PrmpVbpf -> GDAC -> PrmpVbpf -> GDAC
            ...
        local_iterations : int
            Defines how often local threshold (TDAC) / feedback current (FDAC) tuning is repeated.
            -1 or None: Local tuning is disabled
            0: Only local threshold tuning
            1: TDAC -> FDAC -> TDAC
            2: TDAC -> FDAC -> TDAC -> FDAC -> TDAC
            ...
        '''
        if self.global_iterations is None:
            self.global_iterations = -1
        if self.local_iterations is None:
            self.local_iterations = -1

        if self.make_plots:
            self.plots_filename = PdfPages(self.output_filename + '.pdf')
        else:
            self.plots_filename = None

        for iteration in range(0, self.global_iterations):  # tune iteratively with decreasing range to save time
            if self.stop_run.is_set():
                break
            logging.info("Global tuning step %d / %d", iteration + 1, self.global_iterations)
            self.set_scan_parameters(global_step=self.scan_parameters.global_step + 1)
            GdacTuning.scan(self)
            if self.stop_run.is_set():
                break
            self.set_scan_parameters(global_step=self.scan_parameters.global_step + 1)
            FeedbackTuning.scan(self)

        if self.global_iterations >= 0 and not self.stop_run.is_set():
            self.set_scan_parameters(global_step=self.scan_parameters.global_step + 1)
            GdacTuning.scan(self)

            Vthin_AC = self.register.get_global_register_value("Vthin_AltCoarse")
            Vthin_AF = self.register.get_global_register_value("Vthin_AltFine")
            PrmpVbpf = self.register.get_global_register_value("PrmpVbpf")
            logging.info("Results of global threshold tuning: Vthin_AltCoarse / Vthin_AltFine = %d / %d", Vthin_AC, Vthin_AF)
            logging.info("Results of global feedback tuning: PrmpVbpf = %d", PrmpVbpf)

        for iteration in range(0, self.local_iterations):
            if self.stop_run.is_set():
                break
            logging.info("Local tuning step %d / %d", iteration + 1, self.local_iterations)
            self.set_scan_parameters(local_step=self.scan_parameters.local_step + 1)
            TdacTuning.scan(self)
            if self.stop_run.is_set():
                break
            self.set_scan_parameters(local_step=self.scan_parameters.local_step + 1)
            FdacTuning.scan(self)

        if self.local_iterations >= 0 and not self.stop_run.is_set():
            self.set_scan_parameters(local_step=self.scan_parameters.local_step + 1)
            TdacTuning.scan(self)

    def analyze(self):
        if self.global_iterations > 0:
            FeedbackTuning.analyze(self)
        if self.global_iterations >= 0:
            GdacTuning.analyze(self)

        if self.local_iterations > 0:
            FdacTuning.analyze(self)
        if self.local_iterations >= 0:
            TdacTuning.analyze(self)

        if self.make_plots:
            if self.local_iterations > 0:
                plot_three_way(hist=self.tot_mean_best.transpose(), title="Mean ToT after last FDAC tuning", x_axis_title='Mean ToT', filename=self.plots_filename)
                plot_three_way(hist=self.register.get_pixel_register_value("FDAC").transpose(), title="FDAC distribution after last FDAC tuning", x_axis_title='FDAC', filename=self.plots_filename, maximum=16)
            if self.local_iterations >= 0:
                plot_three_way(hist=self.occupancy_best.transpose(), title="Occupancy after tuning", x_axis_title='Occupancy', filename=self.plots_filename, maximum=100)
                plot_three_way(hist=self.register.get_pixel_register_value("TDAC").transpose(), title="TDAC distribution after complete tuning", x_axis_title='TDAC', filename=self.plots_filename, maximum=32)

            self.plots_filename.close()

if __name__ == "__main__":
    RunManager('configuration.yaml').run_run(Fei4Tuning)
