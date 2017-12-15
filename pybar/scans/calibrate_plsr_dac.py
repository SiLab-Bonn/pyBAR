"""A script that changes the PlsrDAC and measures the output voltage. The data is analyzed and fitted and stored to a PDF and configuration file.
It is necessary to add a measurement device ("Multimeter") to the Basil configuration (.yaml) file. Examples are given in dut_mio.yaml.
A Keithley SourceMeter is preferred to a Keithley Multimeter since they turn out to be more reliable.
Note:
 * Use the same enable_shift_masks and mask_steps value for all other scans (e.g. tuning).
 * In case of FE-I4A, deselect outermost double columns (0 and 39): change 'Colpr_Addr' scan parameter to range(1, 39).
"""
import logging

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
import tables as tb
from scipy import interpolate
from scipy import optimize
# from pylab import polyfit, poly1d

import progressbar

from pybar.analysis.analysis_utils import consecutive
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import make_pixel_mask


class PlsrDacCalibration(Fei4RunBase):
    _default_run_conf = {
        "scan_parameters": [('PlsrDAC', range(0, 1024, 33)), ('Colpr_Addr', range(0, 40))],  # the PlsrDAC and Colpr_Addr range
        "mask_steps": 3,
        "repeat_measurements": 10,
        "enable_shift_masks": ["Enable", "C_High", "C_Low"]
    }

    def configure(self):
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

        description = np.dtype([('colpr_addr', np.uint32), ('PlsrDAC', np.int32), ('voltage', np.float)])  # output data table description, native NumPy dtype
        data = self.raw_data_file.h5_file.create_table(self.raw_data_file.h5_file.root, name='plsr_dac_data', description=description, title='Data from PlsrDAC calibration scan')

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.pulser_dac_parameters) * len(self.colpr_addr_parameters) * self.repeat_measurements, term_width=80)
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

            for pulser_dac in self.pulser_dac_parameters:
                if self.abort_run.is_set():
                    break
                self.set_scan_parameters(PlsrDAC=pulser_dac)
                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                self.register.set_global_register_value("PlsrDAC", pulser_dac)
                commands.extend(self.register.get_commands("WrRegister", name="PlsrDAC"))
                commands.extend(self.register.get_commands("RunMode"))
                self.register_utils.send_commands(commands)

                actual_data = np.zeros(shape=(self.repeat_measurements,), dtype=description)
                actual_data['colpr_addr'] = colpr_address
                actual_data["PlsrDAC"] = pulser_dac

                for index, pulser_dac in enumerate(range(self.repeat_measurements)):
                    voltage_string = self.dut['Multimeter'].get_voltage()
                    voltage = float(voltage_string.split(',')[0])

                    actual_data['voltage'][index] = voltage
#                     logging.info('Measured %.2fV', voltage)
                    progress_bar_index += 1
                    progress_bar.update(progress_bar_index)
                # append data to HDF5 file
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

            slope_fit, slope_err, plateau_fit, plateau_err = plot_pulser_dac(mean_data['PlsrDAC'], mean_data['voltage_mean'], mean_data['voltage_rms'], output_pdf, title_suffix="(DC " + ", ".join([str(cols[0]) if len(cols) == 1 else (str(cols[0]) + " - " + str(cols[-1])) for cols in consecutive(self.colpr_addr_parameters)]) + ")")
            self.register.calibration_parameters['Vcal_Coeff_0'] = np.nan_to_num(slope_fit[0] * 1000.0)  # store in mV
            self.register.calibration_parameters['Vcal_Coeff_1'] = np.nan_to_num(slope_fit[1] * 1000.0)  # store in mV/DAC

            # plot per double column
            # Calculate mean PlsrDAC transfer function
            # TODO: Store result in file
            dc_data_stability = np.zeros(shape=(len(self.colpr_addr_parameters) * len(self.pulser_dac_parameters),), dtype=[("colpr_addr", np.int32), ("PlsrDAC", np.int32), ('voltage_mean', np.float), ('voltage_rms', np.float)])
            dc_data = np.zeros(shape=(len(self.colpr_addr_parameters),), dtype=[("colpr_addr", np.int32), ('Vcal_Coeff_0', np.float), ('Vcal_Coeff_1', np.float), ('Vcal_Coeff_0_err', np.float), ('Vcal_Coeff_1_err', np.float), ('Vcal_plateau', np.float), ('Vcal_plateau_err', np.float)])
            for dc_index, dc_parameter in enumerate(self.colpr_addr_parameters):
                mean_data = np.zeros(shape=(len(self.pulser_dac_parameters),), dtype=[("PlsrDAC", np.int32), ('voltage_mean', np.float), ('voltage_rms', np.float)])
                for index, parameter in enumerate(self.pulser_dac_parameters):
                    mean_data["PlsrDAC"][index] = parameter
                    mean_data['voltage_mean'][index] = data['voltage'][np.logical_and(data["PlsrDAC"] == parameter, data['colpr_addr'] == dc_parameter)].mean()
                    mean_data['voltage_rms'][index] = data['voltage'][np.logical_and(data["PlsrDAC"] == parameter, data['colpr_addr'] == dc_parameter)].std()

                dc_data_stability["colpr_addr"][dc_index * len(self.pulser_dac_parameters):(dc_index + 1) * len(self.pulser_dac_parameters)] = dc_parameter
                dc_data_stability["PlsrDAC"][dc_index * len(self.pulser_dac_parameters):(dc_index + 1) * len(self.pulser_dac_parameters)] = mean_data["PlsrDAC"]
                dc_data_stability["voltage_mean"][dc_index * len(self.pulser_dac_parameters):(dc_index + 1) * len(self.pulser_dac_parameters)] = mean_data['voltage_mean']
                dc_data_stability["voltage_rms"][dc_index * len(self.pulser_dac_parameters):(dc_index + 1) * len(self.pulser_dac_parameters)] = mean_data['voltage_rms']

                slope_fit, slope_err, plateau_fit, plateau_err = plot_pulser_dac(mean_data['PlsrDAC'], mean_data['voltage_mean'], mean_data['voltage_rms'], output_pdf, title_suffix="(DC " + str(dc_parameter) + ")")
                dc_data["colpr_addr"][dc_index] = dc_parameter
                dc_data['Vcal_Coeff_0'][dc_index] = slope_fit[0] * 1000.0  # offset
                dc_data['Vcal_Coeff_1'][dc_index] = slope_fit[1] * 1000.0  # slope
                dc_data['Vcal_Coeff_0_err'][dc_index] = slope_err[0] * 1000.0  # offset error
                dc_data['Vcal_Coeff_1_err'][dc_index] = slope_err[1] * 1000.0  # slope error
                dc_data['Vcal_plateau'][dc_index] = plateau_fit[0] * 1000.0  # plateau
                dc_data['Vcal_plateau_err'][dc_index] = plateau_err[0] * 1000.0  # plateau error

            for index, parameter in enumerate(self.pulser_dac_parameters):
                fig = Figure()
                FigureCanvas(fig)
                ax = fig.add_subplot(111)
                ax.set_title('PlsrDAC Voltage vs. DC at PlsrDAC %d' % parameter)
                ax.errorbar(dc_data_stability["colpr_addr"][dc_data_stability['PlsrDAC'] == parameter], dc_data_stability['voltage_mean'][dc_data_stability['PlsrDAC'] == parameter], yerr=dc_data_stability['voltage_rms'][dc_data_stability['PlsrDAC'] == parameter], fmt='o', label='PlsrDAC Voltage')
                ax.set_ylabel('Voltage [V]')
                ax.set_xlabel("Colpr_Addr")
                ax.set_xlim(-0.5, 39.5)
                output_pdf.savefig(fig)

            fig = Figure()
            FigureCanvas(fig)
            ax1 = fig.add_subplot(311)
            ax1.set_title('PlsrDAC Vcal_Coeff_0 vs. DC')
            ax1.errorbar(dc_data["colpr_addr"], dc_data['Vcal_Coeff_0'], yerr=dc_data['Vcal_Coeff_0_err'], fmt='o', label='Vcal_Coeff_0')
            ax1.set_ylabel('Vcal_Coeff_0 [mV]')
            ax1.set_xlabel("Colpr_Addr")
            ax1.set_xlim(-0.5, 39.5)

            ax2 = fig.add_subplot(312)
            ax2.set_title('PlsrDAC Vcal_Coeff_1 vs. DC')
            ax2.errorbar(dc_data["colpr_addr"], dc_data['Vcal_Coeff_1'], yerr=dc_data['Vcal_Coeff_1_err'], fmt='o', label='Vcal_Coeff_1')
            ax2.set_ylabel('Vcal_Coeff_1 [mV/DAC]')
            ax2.set_xlabel("Colpr_Addr")
            ax2.set_xlim(-0.5, 39.5)

            ax2 = fig.add_subplot(313)
            ax2.set_title('PlsrDAC Plateau vs. DC')
            ax2.errorbar(dc_data["colpr_addr"], dc_data['Vcal_plateau'], yerr=dc_data['Vcal_plateau_err'], fmt='o', label='Plateau')
            ax2.set_ylabel('Plateau [mV]')
            ax2.set_xlabel("Colpr_Addr")
            ax2.set_xlim(-0.5, 39.5)

            fig.tight_layout()
            output_pdf.savefig(fig)

            output_pdf.close()

def plot_pulser_dac(x, y, y_err=None, output_pdf=None, title_suffix=""):
    # plot result
    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.errorbar(x, y, yerr=y_err, label='PlsrDAC', fmt='o')
    ax.set_title('PlsrDAC Measurement %s' % title_suffix)
    ax.set_xlabel("PlsrDAC")
    ax.set_ylabel('Voltage [V]')
    ax.grid(True)
    ax.set_xlim((0, max(x)))
    ax.legend(loc='upper left')
    if isinstance(output_pdf, PdfPages):
        output_pdf.savefig(fig)
    else:
        fig.show()

    # calculate 1st and 2nd deviation to estimate fit range
    tck = interpolate.splrep(x, y, k=3, s=0)
    xnew = np.linspace(min(x), max(x), num=100, endpoint=True)

    dev_1 = interpolate.splev(x, tck, der=1)
    dev_2 = interpolate.splev(x, tck, der=2)

    # calculate turning point
    turning_point_idx = np.where(np.logical_and(dev_1 > 0, dev_2 < 0))[0]

    # calculate slope
    slope_data_dev1_idx = np.where(dev_1 > 0)[0]
    slope_data_dev2_idx = np.where(np.isclose(dev_2, 0, atol=5.0 * 1e-05))[0]
    slope_data_idx = np.intersect1d(slope_data_dev1_idx, slope_data_dev2_idx, assume_unique=True)

    # index of slope fit values
    slope_idx = max(consecutive(slope_data_idx), key=len)

    # calculate plateau
    plateau_data_dev1_idx = np.where(np.isclose(dev_1, 0, atol=1e-04))[0]
    plateau_data_dev2_idx = np.where(np.isclose(dev_2, 0, atol=1e-05))[0]
    plateau_data_idx = np.intersect1d(plateau_data_dev1_idx, plateau_data_dev2_idx, assume_unique=True)
    if turning_point_idx.size:
        # take last index from array
        turning_point = turning_point_idx[-1]
    else:
        # select highest index
        turning_point = len(x) - 1
    plateau_data_idx = plateau_data_idx[plateau_data_idx > turning_point]

    # index of plateau fit values
    plateau_idx = max(consecutive(plateau_data_idx), key=len)

    fig = Figure()
    FigureCanvas(fig)
    ax1 = fig.add_subplot(311)
    ax1.set_title('PlsrDAC Fit Range %s' % title_suffix)
    ax1.plot(x, y, 'o', label='data')
    ax1.plot(x[slope_idx], y[slope_idx], 'ro', label='ramp')
    ax1.plot(x[plateau_idx], y[plateau_idx], 'go', label='plateau')
    ax1.plot(xnew, interpolate.splev(xnew, tck, der=0), label='B-spline')

    def slope_fit_fn(x, offset, slope):
        return offset + slope * x

    def plateau_fit_fn(x, offset):
        return offset

    try:
        slope_p_opt, slope_p_cov = optimize.curve_fit(slope_fit_fn, x[slope_idx], y[slope_idx], p0=[0.04, 0.0015], sigma=y_err[slope_idx] if y_err is not None else None, absolute_sigma=True)
    except (RuntimeError, TypeError):
        slope_p_opt = [np.nan, np.nan]
        slope_p_err = [np.nan, np.nan]
    else:
        slope_p_err = np.sqrt(np.diag(slope_p_cov))

    try:
        plateau_p_opt, plateau_p_cov = optimize.curve_fit(plateau_fit_fn, x[plateau_idx], y[plateau_idx], p0=[1.3], sigma=y_err[plateau_idx] if y_err is not None else None, absolute_sigma=True)
    # in case of failing fit or missing plateau
    except (RuntimeError, TypeError):
        plateau_p_opt = [np.nan]
        plateau_p_err = [np.nan]
    else:
        plateau_p_err = np.sqrt(np.diag(plateau_p_cov))

#     slope_p_opt = polyfit(x[slope_idx], y[slope_idx], 1)
#     slope_fit_fn = poly1d(slope_p_opt)
#     plateau_p_opt = polyfit(x[plateau_idx], y[plateau_idx], 0)
#     plateau_fit_fn = poly1d(plateau_p_opt)
    ax1.set_ylabel('Voltage [V]')
    ax1.set_xlabel("PlsrDAC")
    ax1.set_xlim((0, max(x)))
    ax1.set_ylim(bottom=0)
    ax1.legend(loc='best')

    ax2 = fig.add_subplot(312)
    ax2.plot(x, dev_1, label='1st dev')
    ax2.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
    ax2.set_xlabel("PlsrDAC")
    ax2.set_xlim((0, max(x)))
    ax2.legend(loc='best')

    ax3 = fig.add_subplot(313)
    ax3.plot(x, dev_2, label='2st dev')
    ax3.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
    ax3.plot(x[turning_point], dev_2[turning_point], 'rx', label='Turning point')
    ax3.set_xlabel("PlsrDAC")
    ax3.set_xlim((0, max(x)))
    ax3.legend(loc='best')
    fig.tight_layout()
    if isinstance(output_pdf, PdfPages):
        output_pdf.savefig(fig)
    else:
        fig.show()

    # plot and fit result
    fig = Figure()
    FigureCanvas(fig)
    ax = fig.add_subplot(111)
    ax.plot(x, np.vectorize(slope_fit_fn)(x, *slope_p_opt), '--k', label='%.5f+/-%.5f+\n%.5f+/-%.5f*x' % (slope_p_opt[0], slope_p_err[0], slope_p_opt[1], slope_p_err[1]))
    ax.plot(x, np.vectorize(plateau_fit_fn)(x, *plateau_p_opt), '-k', label='%.5f+/-%.5f' % (plateau_p_opt[0], plateau_p_err[0]))
    ax.errorbar(x, y, None, label='PlsrDAC', fmt='o')
#     ax.plot(x[slope_idx], y[slope_idx], 'ro', label='PlsrDAC ramp')
#     ax.plot(x[plateau_idx], y[plateau_idx], 'go', label='PlsrDAC plateau')
#     ax.plot(x, slope_fit_fn(x), '--k', label=str(slope_fit_fn))
#     ax.plot(x, plateau_fit_fn(x), '-k', label=str(plateau_fit_fn))

    ax.set_title('PlsrDAC Calibration %s' % title_suffix)
    ax.set_xlabel("PlsrDAC")
    ax.set_ylabel('Voltage [V]')
    ax.grid(True)
    ax.set_xlim((0, max(x)))
    ax.set_ylim(bottom=0)
    ax.legend(loc='upper left')
    # second plot with shared axis
    divider = make_axes_locatable(ax)
    ax_bottom_plot = divider.append_axes("bottom", 1.0, pad=0.1, sharex=ax)
    ax_bottom_plot.bar(x, (y - np.vectorize(slope_fit_fn)(x, *slope_p_opt)) * 1e3, align='center')
    ax_bottom_plot.grid(True)
    ax_bottom_plot.set_xlabel("PlsrDAC")
    ax_bottom_plot.set_ylabel("$\Delta$Voltage [mV]")

    if isinstance(output_pdf, PdfPages):
        output_pdf.savefig(fig)
    else:
        fig.show()

    return slope_p_opt, slope_p_err, plateau_p_opt, plateau_p_err


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(PlsrDacCalibration)
