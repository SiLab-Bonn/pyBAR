import logging

from matplotlib.backends.backend_pdf import PdfPages

from pybar.run_manager import RunManager
from pybar.scans.tune_gdac import GdacTuning
from pybar.scans.tune_feedback import FeedbackTuning
from pybar.scans.tune_tdac import TdacTuning
from pybar.scans.tune_fdac import FdacTuning
from pybar.analysis.plotting.plotting import plotThreeWay


class Fei4Tuning(GdacTuning, TdacTuning, FeedbackTuning, FdacTuning):
    '''Fully automatic FEI4 Tuning

    This is a meta script implementing GDAC, TDAC, Feedback and FDAC tuning in a single tuning script.
    Values are given in units of PlsrDAC.
    '''
    _scan_id = "fei4_tuning"
    _default_scan_configuration = GdacTuning._default_scan_configuration
    _default_scan_configuration.update(TdacTuning._default_scan_configuration)
    _default_scan_configuration.update(FeedbackTuning._default_scan_configuration)
    _default_scan_configuration.update(FdacTuning._default_scan_configuration)
    _default_scan_configuration.update({
        "scan_parameters": {'GDAC': -1, 'TDAC': -1, 'PrmpVbpf': -1, 'FDAC': -1, 'global_step': 0, 'local_step': 0},
        "global_iterations": 4,  # the number of iterations to do for the global tuning, 0 means only threshold is tuned, negative that no global tuning is done
        "local_iterations": 3,  # the number of iterations to do for the local tuning, 0 means only threshold is tuned, negative that no local tuning is done
        "create_plots": True  # plots for all scan steps are created
    })

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_High'))
        commands.extend(self.register.get_commands("runmode"))
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
        target_tot : int
            The target tot value to tune to.
        global_iterations : int
            Defines how often global threshold/global feedback current tuning is repeated.
            -1: the global tuning is disabled
            0: the global tuning consists of the global threshold tuning only
            1: global threshold/global feedback current/global threshold tuning
            2: global threshold/global feedback current/global threshold tuning/global feedback current/global threshold tuning
            ...
        local_iterations : int
            Defines how often local threshold (TDAC) / feedback current (FDAC) tuning is repeated.
                -1: the local tuning is disabled
                0: the local tuning consists of the local threshold tuning only (TDAC)
                1: TDAC/FDAC/TDAC
                2: TDAC/FDAC/TDAC/FDAC/TDAC
                ...
        '''

        difference_bit = 1

        if self.create_plots:
            self.plots_filename = PdfPages(self.output_filename + '.pdf')
        else:
            self.plots_filename

        start_bit = 7
        for iteration in range(0, self.global_iterations):  # tune iteratively with decreasing range to save time
            logging.info("Global tuning step %d / %d" % (iteration + 1, self.global_iterations))
            start_bit = 7 - difference_bit * iteration
            self.set_scan_parameters(global_step=self.scan_parameters.global_step + 1)
            self.gdac_tune_bits = range(start_bit, -1, -1)
            GdacTuning.scan(self)
            self.set_scan_parameters(global_step=self.scan_parameters.global_step + 1)
            self.feedback_tune_bits = range(start_bit, -1, -1)
            FeedbackTuning.scan(self)

        if self.global_iterations > 0:
            self.set_scan_parameters(global_step=self.scan_parameters.global_step + 1)
            self.gdac_tune_bits = range(start_bit, -1, -1)
            GdacTuning.scan(self)

        Vthin_AC = self.register.get_global_register_value("Vthin_AltCoarse")
        Vthin_AF = self.register.get_global_register_value("Vthin_AltFine")
        PrmpVbpf = self.register.get_global_register_value("PrmpVbpf")
        logging.info("Results of global threshold tuning: Vthin_AltCoarse / Vthin_AltFine = %d / %d" % (Vthin_AC, Vthin_AF))
        logging.info("Results of global feedback tuning: PrmpVbpf = %d" % (PrmpVbpf,))

        difference_bit = int(5 / (self.local_iterations if self.local_iterations > 0 else 1))

        start_bit = 4
        for iteration in range(0, self.local_iterations):
            logging.info("Local tuning step %d / %d" % (iteration + 1, self.local_iterations))
            start_bit = 4  # - difference_bit * iteration
            self.tdac_tune_bits = range(start_bit, -1, -1)
            TdacTuning.scan(self)
            self.fdac_tune_bits = range(start_bit - 1, -1, -1)
            FdacTuning.scan(self)

        if self.local_iterations > 0:
            self.tdac_tune_bits = range(start_bit, -1, -1)
            TdacTuning.scan(self)

    def analyze(self):
        GdacTuning.analyze(self)
        FeedbackTuning.analyze(self)
        TdacTuning.analyze(self)
        FdacTuning.analyze(self)

        if self.create_plots:
            if(self.local_iterations > 0):
                plotThreeWay(hist=self.register.get_pixel_register_value("FDAC").transpose(), title="FDAC distribution after last FDAC tuning", x_axis_title='FDAC', filename=self.plots_filename, maximum=16)
                plotThreeWay(hist=self.tot_mean_best.transpose(), title="Mean ToT after last FDAC tuning", x_axis_title='mean ToT', filename=self.plots_filename)
            if(self.global_iterations > 0):
                plotThreeWay(hist=self.register.get_pixel_register_value("TDAC").transpose(), title="TDAC distribution after complete tuning", x_axis_title='TDAC', filename=self.plots_filename, maximum=32)
                plotThreeWay(hist=self.occupancy_best.transpose(), title="Occupancy after complete tuning", x_axis_title='Occupancy', filename=self.plots_filename, maximum=100)
            self.plots_filename.close()

if __name__ == "__main__":
    join = RunManager('../configuration.yaml').run_run(Fei4Tuning)
    join()
