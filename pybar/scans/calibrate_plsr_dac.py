"""A script that changes the PlsrDAC and measures the output voltage. The data is analyzed and fitted and stored to a PDF and configuration file.
It is necessary to add a measurement device ("Multimeter") to the Basil configuration (.yaml) file. Examples are given in dut_mio.yaml.
A Keithley SourceMeter is preferred to a Keithley Multimeter since they turn out to be more reliable.
"""
import numpy as np
import tables as tb
from pylab import polyfit, poly1d
import logging
import progressbar
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from scipy import interpolate
# from scipy import optimize
# from scipy import stats

from pybar.analysis.analysis_utils import consecutive
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import make_pixel_mask


class PlsrDacScan(Fei4RunBase):
    _default_run_conf = {
        "scan_parameters": [('PlsrDAC', range(0, 1024, 33)), ('Colpr_Addr', range(1, 39))],  # the PlsrDAC and Colpr_Addr range
        "mask_steps": 3,
        "enable_shift_masks": ["Enable", "C_High", "C_Low"]
    }

    def configure(self):
        self.dut['Multimeter'].init()
        logging.info('Initialized multimeter %s' % self.dut['Multimeter'].get_name())
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        enable_mask = make_pixel_mask(steps=self.mask_steps, shift=0, default=0, value=1)  # Activate pixels for injection, although they are not read out
        map(lambda mask_name: self.register.set_pixel_register_value(mask_name, enable_mask), self.enable_shift_masks)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=self.enable_shift_masks, joint_write=True))
        self.register.set_global_register_value('Colpr_Mode', 0)
        self.register.set_global_register_value('ExtDigCalSW', 0)
        self.register.set_global_register_value('ExtAnaCalSW', 1)  # Route Vcal to external pin
        commands.extend(self.register.get_commands("WrRegister", name=['Colpr_Mode', 'ExtDigCalSW', 'ExtAnaCalSW']))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        self.pulser_dac_parameters = self.scan_parameters.PlsrDAC
        self.colpr_addr_parameters = self.scan_parameters.Colpr_Addr

        description = [('column_address', np.uint32), ('PlsrDAC', np.int32), ('voltage', np.float)]  # output data table description
        data = self.raw_data_file.h5_file.create_table(self.raw_data_file.h5_file.root, name='plsr_dac_data', description=np.zeros((1,), dtype=description).dtype, title='Data from PlsrDAC calibration scan')

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.pulser_dac_parameters) * len(self.colpr_addr_parameters), term_width=80)
        progress_bar.start()
        progress_bar_index = 0

        for colpr_address in self.colpr_addr_parameters:
            if self.abort_run.is_set():
                break
            self.set_scan_parameters(Colpr_Addr=colpr_address)

            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value("Colpr_Addr", colpr_address)
            commands.extend(self.register.get_commands("WrRegister", name="Colpr_Addr"))
            commands.extend(self.register.get_commands("RunMode"))
            self.register_utils.send_commands(commands)

            actual_data = np.zeros(shape=(len(self.pulser_dac_parameters),), dtype=description)
            actual_data['column_address'] = colpr_address
            for index, pulser_dac in enumerate(self.pulser_dac_parameters):
                if self.abort_run.is_set():
                    break
                self.set_scan_parameters(PlsrDAC=pulser_dac)

                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                self.register.set_global_register_value("PlsrDAC", pulser_dac)
                commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
                commands.extend(self.register.get_commands("RunMode"))
                self.register_utils.send_commands(commands)

                voltage_string = self.dut['Multimeter'].get_voltage()
                voltage = float(voltage_string.split(',')[0])
                actual_data["PlsrDAC"][index] = pulser_dac
                actual_data['voltage'][index] = voltage
                logging.info('Measured %.2fV', voltage)
                progress_bar_index += 1
                progress_bar.update(progress_bar_index)
            data.append(actual_data)
        progress_bar.finish()
        data.flush()

    def analyze(self):
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            output_pdf = PdfPages(self.output_filename + '.pdf')
            data = in_file_h5.root.plsr_dac_data[:]
            # Calculate mean PlsrDAC transfer function
            mean_data = np.zeros(shape=(len(self.pulser_dac_parameters),), dtype=[("PlsrDAC", np.int32), ('voltage_mean', np.float), ('voltage_rms', np.float)])
            for index, parameter in enumerate(self.pulser_dac_parameters):
                mean_data["PlsrDAC"][index] = parameter
                mean_data['voltage_mean'][index] = data['voltage'][data["PlsrDAC"] == parameter].mean()
                mean_data['voltage_rms'][index] = data['voltage'][data["PlsrDAC"] == parameter].std()

            x, y, y_err = mean_data['PlsrDAC'], mean_data['voltage_mean'], mean_data['voltage_rms']
            if len(self.colpr_addr_parameters) == 1:
                y_err = None

            slope_fit, plateau_fit = self.plot_pulser_dac(x, y, y_err, output_pdf, title_suffix="(DC " + ", ".join([str(cols[0]) if len(cols) == 1 else (str(cols[0]) + " - " + str(cols[-1])) for cols in consecutive(self.colpr_addr_parameters)]) + ")")
            # Store result in file
            self.register.calibration_parameters['Vcal_Coeff_0'] = slope_fit[1] * 1000.0  # store in mV
            self.register.calibration_parameters['Vcal_Coeff_1'] = slope_fit[0] * 1000.0  # store in mV/DAC

            # plot per double column
            # Calculate mean PlsrDAC transfer function
            dc_data = np.zeros(shape=(len(self.colpr_addr_parameters),), dtype=[("colpr_addr", np.int32), ('Vcal_Coeff_0', np.float), ('Vcal_Coeff_1', np.float), ('Vcal_plateau', np.float)])
            for dc_index, dc_parameter in enumerate(self.colpr_addr_parameters):
                mean_data = np.zeros(shape=(len(self.pulser_dac_parameters),), dtype=[("PlsrDAC", np.int32), ('voltage_mean', np.float), ('voltage_rms', np.float)])
                for index, parameter in enumerate(self.pulser_dac_parameters):
                    mean_data["PlsrDAC"][index] = parameter
                    mean_data['voltage_mean'][index] = data['voltage'][np.logical_and(data["PlsrDAC"] == parameter, data['column_address'] == dc_parameter)].mean()
                    mean_data['voltage_rms'][index] = data['voltage'][np.logical_and(data["PlsrDAC"] == parameter, data['column_address'] == dc_parameter)].std()

                x, y, y_err = mean_data['PlsrDAC'], mean_data['voltage_mean'], mean_data['voltage_rms']
                if len(self.colpr_addr_parameters) == 1:
                    y_err = None

                slope_fit, plateau_fit = self.plot_pulser_dac(x, y, y_err, output_pdf, title_suffix="(DC " + str(dc_parameter) + ")")
                # Store result in file
                dc_data["colpr_addr"][dc_index] = dc_parameter
                dc_data['Vcal_Coeff_0'][dc_index] = slope_fit[1] * 1000.0  # offset
                dc_data['Vcal_Coeff_1'][dc_index] = slope_fit[0] * 1000.0  # slope
                dc_data['Vcal_plateau'][dc_index] = plateau_fit[0] * 1000.0  # plateau

            fig = Figure()
            FigureCanvas(fig)
            ax1 = fig.add_subplot(311)
            ax1.set_title('PlsrDAC Vcal_Coeff_0 vs. DC')
            ax1.plot(dc_data["colpr_addr"], dc_data['Vcal_Coeff_0'], 'o', label='data')
        #     ax1.plot(x, predict_y, label = str(fit_fn))
            ax1.set_ylabel('Vcal_Coeff_0 [mV]')
            ax1.set_xlabel("Colpr_Addr")
            ax1.set_xlim(-0.5, 39.5)

            ax2 = fig.add_subplot(312)
            ax2.set_title('PlsrDAC Vcal_Coeff_1 vs. DC')
            ax2.plot(dc_data["colpr_addr"], dc_data['Vcal_Coeff_1'], 'o', label='data')
            ax2.set_ylabel('Vcal_Coeff_1 [mV/DAC]')
            ax2.set_xlabel("Colpr_Addr")
            ax2.set_xlim(-0.5, 39.5)

            ax2 = fig.add_subplot(313)
            ax2.set_title('PlsrDAC Plateau vs. DC')
            ax2.plot(dc_data["colpr_addr"], dc_data['Vcal_plateau'], 'o', label='data')
            ax2.set_ylabel('Plateau [mV]')
            ax2.set_xlabel("Colpr_Addr")
            ax2.set_xlim(-0.5, 39.5)

            fig.tight_layout()
            output_pdf.savefig(fig)

            output_pdf.close()

    def plot_pulser_dac(self, x, y, y_err, pdf, title_suffix=""):
            # plot result
            fig = Figure()
            FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.errorbar(x, y, yerr=y_err, label='PlsrDAC', fmt='o')
            ax.set_title('PlsrDAC measurement %s' % title_suffix)
            ax.set_xlabel("PlsrDAC")
            ax.set_ylabel('Voltage [V]')
            ax.grid(True)
            ax.legend(loc='upper left')
            pdf.savefig(fig)

            # calculate 1st and 2nd deviation to estimate fit range
            tck = interpolate.splrep(x, y, k=3, s=0)
            xnew = np.linspace(0, 1024)

            dev_1 = interpolate.splev(x, tck, der=1)
            dev_2 = interpolate.splev(x, tck, der=2)
            # calculate slope
            slope_data_dev1 = np.where(np.greater(dev_1, [0] * len(dev_1)))[0]
            slope_data_dev2 = np.where(np.isclose(dev_2, [0] * len(dev_2), atol=2e-06))[0]
            slope_data = np.intersect1d(slope_data_dev1, slope_data_dev2, assume_unique=True)

            # index of slope fit values
            slope_idx = max(consecutive(slope_data), key=len)

            # calculate plateau
            plateau_data_dev1 = np.where(np.isclose(dev_1, [0] * len(dev_1), atol=1e-05))[0]
            plateau_data_dev2 = np.where(np.isclose(dev_2, [0] * len(dev_2), atol=2e-06))[0]
            plateau_data = np.intersect1d(plateau_data_dev1, plateau_data_dev2, assume_unique=True)

            # index of plateau fit values
            plateau_idx = max(consecutive(plateau_data), key=len)

            fig = Figure()
            FigureCanvas(fig)
            ax1 = fig.add_subplot(311)
            ax1.set_title('PlsrDAC fit range %s' % title_suffix)
            ax1.plot(x, y, 'o', label='data')
            ax1.plot(x[slope_idx], y[slope_idx], 'ro', label='fit data')
            ax1.plot(xnew, interpolate.splev(xnew, tck, der=0), label='B-spline')
            # Calculate some additional outputs
        #     slope, intercept, r_value, p_value, std_err = stats.linregress(x[idx], y[idx])
        #     predict_y = intercept + slope * x
        #     pred_error = y - predict_y
        #     degrees_of_freedom = len(x) - 2
        #     residual_std_error = np.sqrt(np.sum(pred_error**2) / degrees_of_freedom)
            slope_fit = polyfit(x[slope_idx], y[slope_idx], 1)
            slope_fit_fn = poly1d(slope_fit)
            plateau_fit = polyfit(x[plateau_idx], y[plateau_idx], 0)
            plateau_fit_fn = poly1d(plateau_fit)
        #     ax1.plot(x, predict_y, label = str(fit_fn))
            ax1.set_ylabel('Voltage [V]')
            ax1.set_xlabel("PlsrDAC")
            ax1.legend(loc='best')

            ax2 = fig.add_subplot(312)
            ax2.plot(x, dev_1, label='1st dev')
            ax2.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            ax2.set_xlabel("PlsrDAC")
            ax2.legend(loc='best')

            ax3 = fig.add_subplot(313)
            ax3.plot(x, dev_2, label='2st dev')
            ax3.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
            turning_point_mask = dev_2 == np.amin(dev_2)
            ax3.plot(x[turning_point_mask], dev_2[turning_point_mask], 'rx', label='Turning point')
            ax3.set_xlabel("PlsrDAC")
            ax3.legend(loc='best')
            fig.tight_layout()
            pdf.savefig(fig)

            # plot and fit result
            fig = Figure()
            FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.errorbar(x, y, None, label='PlsrDAC', fmt='o')
            ax.plot(x[slope_idx], y[slope_idx], 'ro', label='PlsrDAC fit')
            ax.plot(x[plateau_idx], y[plateau_idx], 'go', label='PlsrDAC plateau')
            ax.plot(x, slope_fit_fn(x), '--k', label=str(slope_fit_fn))
            ax.plot(x, plateau_fit_fn(x), '-k', label=str(plateau_fit_fn))
            ax.set_title('PlsrDAC calibration %s' % title_suffix)
            ax.set_xlabel("PlsrDAC")
            ax.set_ylabel('Voltage [V]')
            ax.grid(True)
            ax.legend(loc='upper left')
            pdf.savefig(fig)

            return slope_fit, plateau_fit


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(PlsrDacScan)
