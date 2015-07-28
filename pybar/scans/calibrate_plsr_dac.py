"""A script that changes the PlsrDAC in a certain range and measures the voltage. Then the data is analyzed and fitted.
The multimeter device can be any device supported by basil. Add a device in dut_mio.yaml where also an example is shown.
"""
import numpy as np
import tables as tb
from pylab import polyfit, poly1d
import logging
import progressbar
import matplotlib.pyplot as plt

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import make_pixel_mask


class PlsrDacScan(Fei4RunBase):
    _default_run_conf = {
        "colpr_address": range(25, 26),  # the double column range to measure the PlsrDAC output voltage for
        "scan_parameter": 'PlsrDAC',
        "scan_parameter_steps": range(0, 1024, 33),
        "fit_range": [0, 700],
        "mask_steps": 3,  # number of injections per PlsrDAC step
        "enable_shift_masks": ["Enable", "C_High", "C_Low"]
    }

    def set_scan_parameter(self, parameter, value):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value(parameter, value)
        commands.extend(self.register.get_commands("WrRegister", name=[parameter]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

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
        commands.extend(self.register.get_commands("WrRegister", name=['Colpr_Addr', 'Colpr_Mode', 'ExtDigCalSW', 'ExtAnaCalSW']))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def set_column(self, column_address):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value('Colpr_Addr', column_address)
        commands.extend(self.register.get_commands("WrRegister", name='Colpr_Addr'))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        description = [('column_address', np.uint32), (self.scan_parameter, np.int32), ('voltage', np.float)]  # output data table description
        data = self.raw_data_file.h5_file.create_table(self.raw_data_file.h5_file.root, name='plsr_dac_data', description=np.zeros((1, ), dtype=description).dtype, title='Data from PlsrDAC calibration scan')

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.scan_parameter_steps) * len(self.colpr_address), term_width=80)
        progress_bar.start()

        progress_bar_index = 0
        for column_address in self.colpr_address:
            self.set_column(column_address)
            actual_data = np.zeros(shape=(len(self.scan_parameter_steps), ), dtype=description)
            actual_data['column_address'] = column_address
            for index, scan_parameter_step in enumerate(self.scan_parameter_steps):
                if self.abort_run.is_set():
                    break
                logging.info('Set ' + self.scan_parameter + ' to ' + str(scan_parameter_step))
                self.set_scan_parameter(self.scan_parameter, scan_parameter_step)
                voltage_string = self.dut['Multimeter'].get_voltage()
                voltage = float(voltage_string.split(',')[0])
                actual_data[self.scan_parameter][index] = scan_parameter_step
                actual_data['voltage'][index] = voltage
                logging.info('Measure %f V', voltage)
                progress_bar_index += 1
                progress_bar.update(progress_bar_index)
            data.append(actual_data)
        progress_bar.finish()
        data.flush()

    def analyze(self):
        logging.info('Analyze and plot results')
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            data = in_file_h5.root.plsr_dac_data[:]
            # Calculate mean PlsrDAC transfer function
            mean_data = np.zeros(shape=(len(self.scan_parameter_steps), ), dtype=[(self.scan_parameter, np.int32), ('voltage_mean', np.float), ('voltage_rms', np.float)])
            for index, parameter in enumerate(self.scan_parameter_steps):
                mean_data[self.scan_parameter][index] = parameter
                mean_data['voltage_mean'][index] = data['voltage'][data[self.scan_parameter] == parameter].mean()
                mean_data['voltage_rms'][index] = data['voltage'][data[self.scan_parameter] == parameter].std()
            plt.errorbar(self.scan_parameter_steps, mean_data['voltage_mean'], mean_data['voltage_rms'])
            # Plot and fit result
            x, y, y_err = np.array(self.scan_parameter_steps), mean_data['voltage_mean'], mean_data['voltage_rms']
            fit = polyfit(x[np.logical_and(x >= self.fit_range[0], x <= self.fit_range[1])], y[np.logical_and(x >= self.fit_range[0], x <= self.fit_range[1])], 1)
            fit_fn = poly1d(fit)
            plt.clf()
            plt.errorbar(x, y, y_err, label='data')
            plt.plot(x, fit_fn(x), '--k', label=str(fit_fn))
            plt.title(self.scan_parameter + ' calibration')
            plt.xlabel(self.scan_parameter)
            plt.ylabel('Voltage [V]')
            plt.grid(True)
            plt.legend(loc=0)
            plt.savefig(self.output_filename + '.pdf')
            # Store result in file
            self.register.calibration_parameters['Vcal_Coeff_0'] = fit[1] * 1000.  # store in mV
            self.register.calibration_parameters['Vcal_Coeff_1'] = fit[0] * 1000.  # store in mV/DAC


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(PlsrDacScan)
