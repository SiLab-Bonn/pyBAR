''' Script to test the FPGA TDC with a Agilent Technologies,33250A pulser.
'''

import serial
import time
import logging
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.daq.readout_utils import is_tdc_word, data_array_from_data_iterable
from pybar.analysis.plotting import plotting
from pybar.run_manager import RunManager


# Subclass pyserial to make it more usable, define termination characters here
class my_serial(serial.Serial):
    def __init__(self, *args, **kwargs):
        super(my_serial, self).__init__(*args, **kwargs)
        self.eol = '\r\n'
 
    def write(self, data):
        super(my_serial, self).write(data + self.eol)

    def ask(self, data):
        self.write(data)
        return self.readline()


class TdcTest(Fei4RunBase):
    '''Test TDC scan
    '''
    _default_run_conf = {
        "COM_port": 3,
        "n_pulses": 10000
    }

    def configure(self):  # init pulser
        try:
            self.pulser = my_serial('COM%d' % self.COM_port, 19200, timeout=1)
        except:
            logging.error('No device found ?!')
            raise
        if 'Agilent Technologies,33250A' not in self.pulser.ask("*IDN?"):  # check if the correct pulser is connected
            raise RuntimeError('Reading of histogram data from ' + self.pulser.ask("*IDN?") + ' is not supported')
        logging.info('Initialized pulser')
        self.pulser.write('PULS:PER 1E-6')  # set fast acquisition
        self.pulser.write('PULS:WIDT 10E-9')

    def start_pulser(self, pulse_width=100, n_pulses=100):
        self.pulser.write('PULS:WIDT ' + str(pulse_width) + 'E-9')
        self.pulser.write('BURS:NCYC ' + str(n_pulses))
        self.pulser.write('*TRG')

    def scan(self):
        self.dut['tdc_rx2']['ENABLE'] = True
        self.dut['tdc_rx2']['EN_ARMING'] = False

        x = []
        y = []
        y_err = []
        tdc_hist = None

        self.fifo_readout.reset_sram_fifo()  # clear fifo data
        for pulse_width in [i for j in (range(10, 100, 5), range(100, 400, 10)) for i in j]:
            logging.info('Test TDC for a pulse with of %d' % pulse_width)
            self.start_pulser(pulse_width, self.n_pulses)
            time.sleep(1)
            data = self.fifo_readout.read_data()
            if data[is_tdc_word(data)].shape[0] != 0:
                if len(is_tdc_word(data)) != self.n_pulses:
                    logging.warning('Too less TDC words %d instead of %d ' % (len(is_tdc_word(data)), self.n_pulses))
                tdc_values = np.bitwise_and(data[is_tdc_word(data)], 0x00000FFF)
                tdc_counter = np.bitwise_and(data[is_tdc_word(data)], 0x000FF000)
                tdc_trig_delay = np.bitwise_and(data[is_tdc_word(data)], 0x0FF00000)
                tdc_counter = np.right_shift(tdc_counter, 12)
                try:
                    if np.any(np.logical_and(tdc_counter[np.gradient(tdc_counter) != 1] != 0, tdc_counter[np.gradient(tdc_counter) != 1] != 255)):
                        logging.warning('The counter did not count correctly')
                except ValueError:
                    logging.warning('The counter did not count correctly')

                x.append(pulse_width)
                y.append(np.mean(tdc_values))
                y_err.append(np.std(tdc_values))
                if tdc_hist is None:
                    tdc_hist = np.histogram(tdc_values, range=(0, 1023), bins=1024)[0]
                else:
                    tdc_hist += np.histogram(tdc_values, range=(0, 1023), bins=1024)[0]
            else:
                logging.warning('No TDC words, check connection!')

        plotting.plot_scatter(x, y, y_err, title='FPGA TDC linearity, ' + str(self.n_pulses) + ' each', x_label='pulse width [ns]', y_label='TDC value', filename=None)
        plotting.plot_scatter(x, y_err, title='FPGA TDC RMS, ' + str(self.n_pulses) + ' each', x_label='pulse width [ns]', y_label='TDC RMS', filename=None)
        plotting.plot_tdc_counter(tdc_hist, title='All TDC values', filename=None)

    def analyze(self):
        pass

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(TdcTest)
