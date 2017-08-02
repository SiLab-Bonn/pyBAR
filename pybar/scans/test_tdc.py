''' Script to test the FPGA TDC with a pulser. Pulser has to be defined in mio.yaml.
To measure the TDC values connect a pulser with 3 V amplitude to the RX2 plug
of the Multi IO board (without TDC modification).
To test the additional timing feature connect an additional
pulser to RX0. Synchronize the clocks and trigger the additional pulser with the
first pulser.

255: tdc without trigger or tdc with ambigous trigger, trigger is ambigous if:
    - the trigger rising edge is happens while a TDC signal is high
    - a trigger signal follows a trigger signal without another TDC signal
254: trigger rising edge is > 2^8 / (640 MHz) = 400 ns before TDC edge
'''
import logging
import time

from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.daq.readout_utils import is_tdc_word
from pybar.analysis.plotting import plotting
from pybar.run_manager import RunManager


class TdcTest(Fei4RunBase):

    '''Test TDC scan
    '''
    _default_run_conf = {
        "n_pulses": 10000,
        "pulse_period": '1E-6',  # s
        "test_tdc_values": False,
        "test_trigger_delay": True
    }

    def configure(self):  # init pulser
        self.dut['Pulser'].set_pulse_period(self.pulse_period)
        self.dut['TDC']['EN_TRIGGER_DIST'] = True
        self.dut['TDC']['EN_NO_WRITE_TRIG_ERR'] = False
        self.dut['TDC']['ENABLE'] = True

    def start_pulser(self, pulse_width=100, n_pulses=100, pulse_delay=0):  # in ns
        self.dut['Pulser'].set_pulse_width(str(pulse_width) + 'E-9')
        self.dut['Pulser'].set_trigger_delay(str(pulse_delay) + 'E-9')
        self.dut['Pulser'].set_n_bursts(str(n_pulses))
        self.dut['Pulser'].trigger()

    def scan(self):
        with PdfPages(self.output_filename + '.pdf') as output_pdf:
            if self.test_tdc_values:
                x, y, y_err = [], [], []
                tdc_hist = None

                self.fifo_readout.reset_fifo()  # clear fifo data
                for pulse_width in [i for j in (range(10, 100, 5), range(100, 400, 10)) for i in j]:
                    logging.info('Test TDC for a pulse with of %d', pulse_width)
                    self.start_pulser(pulse_width, self.n_pulses)
                    time.sleep(self.n_pulses * pulse_width * 1e-9 + 0.1)
                    data = self.fifo_readout.read_data()
                    if data[is_tdc_word(data)].shape[0] != 0:
                        tdc_values = np.bitwise_and(data[is_tdc_word(data)], 0x00000FFF)
                        tdc_counter = np.bitwise_and(data[is_tdc_word(data)], 0x000FF000)
                        tdc_counter = np.right_shift(tdc_counter, 12)
                        if len(is_tdc_word(data)) != self.n_pulses:
                            logging.warning('%d TDC words instead of %d ', len(is_tdc_word(data)), self.n_pulses)
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
                if tdc_hist is not None:
                    plotting.plot_tdc_counter(tdc_hist, title='All TDC values', filename=output_pdf)

            if self.test_trigger_delay:
                x, y, y_err, y2, y2_err = [], [], [], [], []
                self.fifo_readout.reset_fifo()  # clear fifo data
                for pulse_delay in [i for j in (range(0, 100, 5), range(100, 500, 500)) for i in j]:
                    logging.info('Test TDC for a pulse delay of %d', pulse_delay)
                    for _ in range(10):
                        self.start_pulser(pulse_width=100, n_pulses=1, pulse_delay=pulse_delay)
                        time.sleep(0.1)
                    data = self.fifo_readout.read_data()
                    if data[is_tdc_word(data)].shape[0] != 0:
                        if len(is_tdc_word(data)) != 10:
                            logging.warning('%d TDC words instead of %d ', len(is_tdc_word(data)), 10)
                        tdc_values = np.bitwise_and(data[is_tdc_word(data)], 0x00000FFF)
                        tdc_delay = np.bitwise_and(data[is_tdc_word(data)], 0x0FF00000)
                        tdc_delay = np.right_shift(tdc_delay, 20)

                        x.append(pulse_delay)
                        y.append(np.mean(tdc_delay))
                        y_err.append(np.std(tdc_delay))
                        y2.append(np.mean(tdc_values))
                        y2_err.append(np.std(tdc_values))
                    else:
                        logging.warning('No TDC words, check connection!')

                plotting.plot_scatter(x, y2, y2_err, title='FPGA TDC for different delays, ' + str(self.n_pulses) + ' each', x_label='Pulse delay [ns]', y_label='TDC value', filename=output_pdf)
                plotting.plot_scatter(x, y, y_err, title='FPGA TDC trigger delay, ' + str(10) + ' each', x_label='Pulse delay [ns]', y_label='TDC trigger delay', filename=output_pdf)
                plotting.plot_scatter(x, y_err, title='FPGA TDC trigger delay RMS, ' + str(10) + ' each', x_label='Pulse delay [ns]', y_label='TDC trigger delay RMS', filename=output_pdf)

    def analyze(self):
        pass


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(TdcTest)
