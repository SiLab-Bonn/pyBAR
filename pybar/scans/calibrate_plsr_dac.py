"""A script that changes the PlsrDAC in a certain range and measures the voltage. Then the data is analyzed and fitted.
The multimeter device can be any device supported by basil. Add a device in dut_mio.yaml where also an example is shown.
"""
import numpy as np
from pylab import polyfit, poly1d
import logging
import matplotlib.pyplot as plt

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager


class PlsrDacScan(Fei4RunBase):
    _default_run_conf = {
        "colpr_addr": 35,  # the double column to measure the PlsrDAC for
        "scan_parameter": 'PlsrDAC',
        "scan_parameter_steps": range(0, 1024, 33),
        "fit_range": [0, 700]
    }

    def set_scan_parameter(self, parameter, value):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value(parameter, value)
        commands.extend(self.register.get_commands("WrRegister", name=[parameter]))
        self.register_utils.send_commands(commands)

    def configure(self):
        self.dut['Multimeter'].init()
        logging.info('Initialized multimeter %s' % self.dut['Multimeter'].get_name())
        # Route Vcal to external pin
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value('Colpr_Addr', self.colpr_addr)
        self.register.set_global_register_value('Colpr_Mode', 0)
        self.register.set_global_register_value('ExtDigCalSW', 0)
        self.register.set_global_register_value('ExtAnaCalSW', 1)
        commands.extend(self.register.get_commands("WrRegister", name=['Colpr_Addr', 'Colpr_Mode', 'ExtDigCalSW', 'ExtAnaCalSW']))
        self.register_utils.send_commands(commands)

    def scan(self):
        self.data = np.zeros(shape=(len(self.scan_parameter_steps), 2))  # data array with the measured values

        for index, scan_parameter_step in enumerate(self.scan_parameter_steps):
            logging.info('Set ' + self.scan_parameter + ' to ' + str(scan_parameter_step))
            self.set_scan_parameter(self.scan_parameter, scan_parameter_step)
            voltage_string = self.dut['Multimeter'].get_voltage()
            voltage = float(voltage_string.split(',')[0])
            self.data[index] = (scan_parameter_step, voltage)
            logging.info('Measure %f V', voltage)

    def analyze(self):
        logging.info('Analyze and plot results')
        x = self.data[:, 0]
        y = self.data[:, 1]

        fit = polyfit(x[np.logical_and(x >= self.fit_range[0], x <= self.fit_range[1])], y[np.logical_and(x >= self.fit_range[0], x <= self.fit_range[1])], 1)
        fit_fn = poly1d(fit)
        plt.plot(x, y, 'o-', label='data')
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
