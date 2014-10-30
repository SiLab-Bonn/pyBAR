''' Script to test the FPGA TDC
'''

from scan.scan import ScanBase
import visa
import time
from daq.readout import is_tdc_data

import numpy as np
from analysis.plotting import plotting

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")

local_configuration = {
    "GPIB_prim_address": 1,
    "n_pulses": 10000
}


class TdcTest(ScanBase):
    scan_id = "tdc_test"

    def init_pulser(self, GPIB_prim_address):
        try:
            self.pulser = visa.instrument("GPIB::" + str(GPIB_prim_address))
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
        self.init_pulser(self.GPIB_prim_address)

        self.dut['tdc_rx2']['ENABLE'] = True
        self.dut['tdc_rx2']['EN_ARMING'] = False

        x = []
        y = []
        y_err = []
        tdc_hist = None

        self.readout.read_data()  # clear data
        for pulse_width in [i for j in (range(10, 100, 5), range(100, 400, 10)) for i in j]:
            logging.info('Test TDC for a pulse with of %d' % pulse_width)
            self.start_pulser(pulse_width, self.n_pulses)
            time.sleep(1)
            data = self.readout.read_data()
            if len(is_tdc_data(data)) != 0:
                if len(is_tdc_data(data)) != self.n_pulses:
                    logging.warning('Too less TDC words %d instead of %d ' % (len(is_tdc_data(data)), self.n_pulses))
                tdc_values = np.bitwise_and(data[is_tdc_data(data)], 0x00000FFF)
                tdc_counter = np.bitwise_and(data[is_tdc_data(data)], 0x0FFFF000)
                tdc_counter = np.right_shift(tdc_counter, 12)
                if np.any(np.logical_and(tdc_counter[np.gradient(tdc_counter) != 1] != 0, tdc_counter[np.gradient(tdc_counter) != 1] != 65535)):
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

if __name__ == "__main__":
    import configuration
    scan = TdcTest(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=False, **local_configuration)
    scan.stop()
