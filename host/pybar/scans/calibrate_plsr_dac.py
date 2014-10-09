"""A script that changes the PlsrDAC in a certain range and measures the voltage. Then the data is analyzed and fitted. The multimeter device is a Keithley 2XXX connected via com port.
"""
import numpy as np
import yaml
from pylab import polyfit, poly1d
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

from utils import Keithley24xx
from scan.scan import ScanBase
import matplotlib.pyplot as plt

local_configuration = {
    "multimeter_device_config": 'keithley.yaml',
    "colpr_addr": 20,
    "scan_parameter": 'PlsrDAC',
    "plsr_dac_steps": range(0, 1024, 33),
    "fit_range": [0, 700]
}


class PlsrDacScan(ScanBase):
    scan_id = "pulser_dac_calibration"

    def init_multimeter_device(self, multimeter_device_config):
        with open(multimeter_device_config, 'r') as config_file:
            return Keithley24xx.Keithley24xx(yaml.load(config_file))

    def set_scan_parameter(self, parameter, value):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value(parameter, value)
        commands.extend(self.register.get_commands("wrregister", name=[parameter]))
        self.register_utils.send_commands(commands)

    def route_vcal_to_pin(self, colpr_addr):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value('colpr_addr', colpr_addr)
        self.register.set_global_register_value('colpr_mode', 0)
        self.register.set_global_register_value('ExtAnaCalSW', 1)
        commands.extend(self.register.get_commands("wrregister", name=['colpr_addr', 'colpr_mode', 'ExtAnaCalSW']))
        self.register_utils.send_commands(commands)

    def scan(self):
        self.fit_range = self.fit_range
        multimeter_device = self.init_multimeter_device(self.multimeter_device_config)

        self.register.create_restore_point()
        self.register_utils.configure_all()
        self.route_vcal_to_pin(self.colpr_addr)

        self.data = np.zeros(shape=(len(self.plsr_dac_steps), 3))  # data array with the measured values

        multimeter_device.set_voltage(0, 'mV')  # better save than sorry
        multimeter_device.enable_output(True)

        for index, plsr_dac in enumerate(self.plsr_dac_steps):
            logging.info('Set Plsr DAC to ' + str(plsr_dac))
            self.set_scan_parameter(self.scan_parameter, plsr_dac)
            voltage, voltage_error = multimeter_device.get_voltage(unit='mV', with_error=True)
            self.data[index] = (plsr_dac, voltage, voltage_error)
            logging.info('Measure (%f +- %f) mV ' % (voltage, voltage_error))

        multimeter_device.enable_output(False)

        self.register.restore()
        self.register_utils.configure_all()

    def analyze(self, show=False):
        logging.info('Analyze and plot results')
        x = self.data[:, 0]
        y = self.data[:, 1]
        yerr = self.data[:, 2]

        fit = polyfit(x[np.logical_and(x >= self.fit_range[0], x <= self.fit_range[1])], y[np.logical_and(x >= self.fit_range[0], x <= self.fit_range[1])], 1)
        fit_fn = poly1d(fit)
        data_plt = plt.errorbar(x, y, yerr)
        fit_plt, = plt.plot(x, fit_fn(x), '--k')
        plt.title('PlsrDAC calibration')
        plt.xlabel('PlsrDAC')
        plt.ylabel('voltage [mV]')
        plt.grid(True)
        plt.legend([data_plt, fit_plt], ["data", str(fit_fn)], loc=0)
        if show:
            plt.show()
        else:
            plt.savefig(self.scan_data_filename + '.pdf')
        plt.close()


if __name__ == "__main__":
    import configuration
    scan = PlsrDacScan(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=False, **local_configuration)
    scan.stop()
