"""A script that changes the voltage in a certain range and measures the current needed for IV curves. Maximum voltage and current limits
can be set for device protection.
"""
import logging
import time

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import numpy as np
import tables as tb

import progressbar

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager


class IVScan(Fei4RunBase):
    _default_run_conf = {
        "voltages": np.arange(-2, -101, -2).tolist(),  # voltage steps of the IV curve
        "max_leakage": 10e-6,  # scan aborts if current is higher
        "max_voltage": -20,  # for safety, scan aborts if voltage is higher
        "minimum_delay": 0.5,  # minimum delay between current measurements in seconds
        "bias_voltage": -10  # if defined ramp bias to bias voltage after scan is finished, has to be less than last scanned voltage
    }

    def configure(self):
        pass

    def scan(self):
        logging.info('Measure IV for V = %s' % self.voltages)
        description = [('voltage', np.float), ('current', np.float)]
        data = self.raw_data_file.h5_file.create_table(self.raw_data_file.h5_file.root, name='IV_data', description=np.zeros((1, ), dtype=description).dtype, title='Data from the IV scan')

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.voltages), term_width=80)
        progress_bar.start()
        actual_voltage = None
        try:
            raise Exception("bla")
            for index, voltage in enumerate(self.voltages):
                if self.stop_run.is_set():
                    break
                if voltage > 0:
                    RuntimeError('Voltage has to be negative! Abort to protect device.')
                if self.abort_run.is_set():
                    break
                if abs(voltage) <= abs(self.max_voltage):
                    self.dut['Sourcemeter'].set_voltage(voltage)
                    actual_voltage = voltage
                    time.sleep(self.minimum_delay)
                else:
                    logging.info('Maximum voltage with %f V reached, abort', voltage)
                    break
                current = float(self.dut['Sourcemeter'].get_current().split(',')[1])
                if abs(current) > abs(self.max_leakage):
                    logging.info('Maximum current with %e I reached, abort', current)
                    break
                logging.info('V = %f, I = %e', voltage, current)
                max_repeat = 50
                for i in range(max_repeat):  # repeat current measurement until stable (current does not increase)
                    time.sleep(self.minimum_delay)
                    actual_current = float(self.dut['Sourcemeter'].get_current().split(',')[1])
                    if abs(actual_current) > abs(self.max_leakage):
                        logging.info('Maximum current with %e I reached, abort', actual_current)
                        break
                    if (abs(actual_current) < abs(current)):  # stable criterion
                        break
                    current = actual_current
                if i == max_repeat - 1:  # true if the leakage always increased
                    raise RuntimeError('Leakage current is not stable')
                else:
                    a = np.array([(voltage, current)], dtype=description)
                    data.append(a)
                progress_bar.update(index)
            progress_bar.finish()
            data.flush()
        finally:
            # ramp down
            if self.bias_voltage and self.bias_voltage <= 0 and actual_voltage is not None:
                logging.info('Set bias voltage from %f V to %f V', actual_voltage, self.bias_voltage)
                progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(range(actual_voltage, self.bias_voltage + 1, 2)), term_width=80)
                progress_bar.start()
                for index, voltage in enumerate(range(actual_voltage, self.bias_voltage + 1, 2)):  # ramp until bias
                    time.sleep(self.minimum_delay)
                    self.dut['Sourcemeter'].set_voltage(voltage)
                    progress_bar.update(index)
                progress_bar.finish()

    def analyze(self):
        logging.info('Analyze and plot results')
        with tb.open_file(self.output_filename + '.h5', 'r+') as in_file_h5:
            data = in_file_h5.root.IV_data[:]
            # Plot and fit result
            x, y = data['voltage'], data['current'] * 1e6
            fig = Figure()
            FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.plot(x, y, '.-', label='data')
            ax.set_title('IV curve')
            ax.set_ylabel('Current [uA]')
            ax.set_xlabel('Voltage [V]')
            ax.grid(True)
            ax.legend(loc=0)
            fig.savefig(self.output_filename + '.pdf')


if __name__ == "__main__":
    RunManager('configuration.yaml').run_run(IVScan)
