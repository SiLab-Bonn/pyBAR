''' Script to test the FPGA TDC with pulser. SCPI commands are send via RS232.
To measure the TDC values connect a pulser with 3 V amplitude to the RX2 plug
of the Multi IO board (without TDC modification).
To test the additional timing feature connect an additional
pulser to RX0. Synchronize the clocks and trigger the additional pulser with the
first pulser with about 10 ns delay.
'''

import serial
import time
import logging
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from pybar.fei4_run_base import Fei4RunBase
from pybar.daq.readout_utils import is_tdc_word
from pybar.analysis.plotting import plotting
from pybar.run_manager import RunManager


# Subclass pyserial to make it more usable, define termination characters (eol) here
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
        "COM_port": '/dev/ttyUSB0',  # in Windows 'COM?' where ? is the COM port
        "n_pulses": 10000,
        "test_tdc_values": True,
        "test_trigger_delay": True
    }

    def configure(self):  # init pulser
        try:
            self.pulser = my_serial(self.COM_port, 19200, timeout=1)
        except:
            logging.error('No device found ?!')
            raise
        identifier = self.pulser.ask("*IDN?")
        if 'Agilent Technologies,33250A' not in identifier and 'new_pulser_add_here' not in identifier:  # check if the correct pulser is connected
            raise NotImplementedError('Pulser ' + str(identifier) + ' is not supported. If SCPI commands are understood, just add its name here.')
        logging.info('Initialized pulser')
        self.pulser.write('PULS:PER 1E-6')  # set fast acquisition
        self.pulser.write('PULS:WIDT 10E-9')

    def start_pulser(self, pulse_width=100, n_pulses=100, pulse_delay=0):
        self.pulser.write('PULS:WIDT ' + str(pulse_width) + 'E-9')
        self.pulser.write('TRIG:DELAY ' + str(pulse_delay) + 'E-9')
        self.pulser.write('BURS:NCYC ' + str(n_pulses))
        self.pulser.write('*TRG')

    def scan(self):
        self.dut['tdc_rx2']['ENABLE'] = True
        self.dut['tdc_rx2']['EN_ARMING'] = False
        self.dut['tdc_rx2']['EN_TRIGGER_COUNT'] = True

        with PdfPages(self.output_filename + '.pdf') as output_pdf:
            if self.test_tdc_values:
                x, y, y_err = [], [], []
                tdc_hist = None

                self.fifo_readout.reset_sram_fifo()  # clear fifo data
                for pulse_width in [i for j in (range(10, 100, 5), range(100, 400, 10)) for i in j]:
                    logging.info('Test TDC for a pulse with of %d' % pulse_width)
                    self.start_pulser(pulse_width, self.n_pulses)
                    time.sleep(self.n_pulses * pulse_width * 1e-9 + 0.1)
                    data = self.fifo_readout.read_data()
                    if data[is_tdc_word(data)].shape[0] != 0:
                        if len(is_tdc_word(data)) != self.n_pulses:
                            logging.warning('%d TDC words instead of %d ' % (len(is_tdc_word(data)), self.n_pulses))
                        tdc_values = np.bitwise_and(data[is_tdc_word(data)], 0x00000FFF)
                        tdc_counter = np.bitwise_and(data[is_tdc_word(data)], 0x000FF000)
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

                plotting.plot_scatter(x, y, y_err, title='FPGA TDC linearity, ' + str(self.n_pulses) + ' each', x_label='Pulse width [ns]', y_label='TDC value', filename=output_pdf)
                plotting.plot_scatter(x, y_err, title='FPGA TDC RMS, ' + str(self.n_pulses) + ' each', x_label='Pulse width [ns]', y_label='TDC RMS', filename=output_pdf)
                plotting.plot_tdc_counter(tdc_hist, title='All TDC values', filename=output_pdf)

            if self.test_trigger_delay:
                x, y, y_err = [], [], []
                self.fifo_readout.reset_sram_fifo()  # clear fifo data
                for pulse_delay in [i for j in (range(0, 100, 5), range(100, 500, 20)) for i in j]:
                    logging.info('Test TDC for a pulse delay of %d' % pulse_delay)
                    for _ in range(10):
                        self.start_pulser(pulse_width=100, n_pulses=1, pulse_delay=pulse_delay)
                        time.sleep(0.1)
                    data = self.fifo_readout.read_data()
                    if data[is_tdc_word(data)].shape[0] != 0:
                        if len(is_tdc_word(data)) != 10:
                            logging.warning('%d TDC words instead of %d ' % (len(is_tdc_word(data)), 10))
                        tdc_delay = np.bitwise_and(data[is_tdc_word(data)], 0x0FF00000)
                        tdc_delay = np.right_shift(tdc_delay, 20)

                        x.append(pulse_delay)
                        y.append(np.mean(tdc_delay))
                        y_err.append(np.std(tdc_delay))
                    else:
                        logging.warning('No TDC words, check connection!')

                plotting.plot_scatter(x, y, y_err, title='FPGA TDC trigger delay, ' + str(10) + ' each', x_label='Pulse delay [ns]', y_label='TDC trigger delay', filename=output_pdf)
                plotting.plot_scatter(x, y_err, title='FPGA TDC trigger delay RMS, ' + str(10) + ' each', x_label='Pulse delay [ns]', y_label='TDC trigger delay RMS', filename=output_pdf)

    def analyze(self):
        pass

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(TdcTest)
