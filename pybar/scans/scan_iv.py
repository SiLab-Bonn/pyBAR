"""A script that changes the voltage in a certain range and measures the current needed for IV curves. Maximum voltage and current limits
can be set for device protection.
"""
import numpy as np
import tables as tb
import logging
import progressbar
import matplotlib.pyplot as plt
import time

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager


class IVScan(Fei4RunBase):
    _default_run_conf = {
        "voltages": np.arange(0, -100, 20),  # voltage steps of the IV curve
        "max_leakage": 1e-5,  # scan aborts if current is higher
        "max_voltage": -20  # for safety, scan aborts if voltage is higher
    }

    def configure(self):
        self.dut['Sourcemeter'].init()
        logging.info('Initialized sourcemeter: %s' % self.dut['Sourcemeter'].get_name())

    def scan(self):
        description = [('voltage', np.float), ('current', np.float)]
        data = self.raw_data_file.h5_file.create_table(self.raw_data_file.h5_file.root, name='IV_data', description=np.zeros((1, ), dtype=description).dtype, title='Data from the IV scan')

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.voltages), term_width=80)
        progress_bar.start()

        for index, voltage in enumerate(self.voltages):
            if voltage > 0:
                RuntimeError('Voltage has to be negative! Abort to protect device.')
            if voltage >= self.max_voltage:
                self.dut['Sourcemeter'].set_voltage(voltage)
            else:
                logging.info('Maximum voltage %f V reached, abort', self.max_voltage)
                break
            current_string = self.dut['Sourcemeter'].get_current()
            current = float(current_string.split(',')[1])
            if current < self.max_leakage:
                logging.info('Maximum current %e I reached, abort', self.max_leakage)
                break
            logging.info('V = %f, I = %f', (voltage, current))
            for i in range(100):  # repeat current measurement until stable (current does not increase)
                time.sleep(0.1)
                actual_current = float(self.dut['Sourcemeter'].get_current().split(',')[1])
                if actual_current < self.max_leakage:
                    logging.info('Maximum current %e I reached, abort', self.max_leakage)
                    break
                if (actual_current < current):
                    current = actual_current
            if i == 99:  # true if the leakage always increased
                raise RuntimeError('Leakage current is not stable')
            else:
                data.append(np.array([[voltage, current]], dtype=description))
            progress_bar.update(index)
        progress_bar.finish()
        data.flush()

    def analyze(self):
        logging.info('Analyze and plot results')
        with tb.open_file(self.output_filename + '.h5', 'r+') as in_file_h5:
            data = in_file_h5.root.IV_data[:]
            # Plot and fit result
            x, y = np.array(data['voltage'], data['current']) * 1e6
            plt.clf()
            plt.plot(x, y, label='data')
            plt.title('IV curve')
            plt.xlabel('Current [uA]')
            plt.ylabel('Voltage [V]')
            plt.grid(True)
            plt.legend(loc=0)
            plt.savefig(self.output_filename + '.pdf')


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(IVScan)
