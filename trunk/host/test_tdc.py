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

scan_configuration = {
    "GPIB_prim_address": 1,
    "n_pulses": 10000
}


class TdcTest(ScanBase):
    scan_identifier = "tdc_test"

    def init_pulser(self, GPIB_prim_address):
        try:
            self.pulser = visa.instrument("GPIB::" + str(GPIB_prim_address))
        except:
            logging.error('No device found ?!')
            raise
        if not 'Agilent Technologies,33250A' in self.pulser.ask("*IDN?"):  # check if the correct pulserlloscope was found
            raise RuntimeError('Reading of histogram data from ' + self.pulser.ask("*IDN?") + ' is not supported')
        logging.info('Initialized pulser')
        self.pulser.write('PULS:PER 1E-6')  # set fast aquisition
        self.pulser.write('PULS:WIDT 10E-9')

    def start_pulser(self, pulse_width=100, n_pulses=100):
        self.pulser.write('PULS:WIDT ' + str(pulse_width) + 'E-9')
        self.pulser.write('BURS:NCYC ' + str(n_pulses))
        self.pulser.write('*TRG')

    def scan(self, GPIB_prim_address=1, n_pulses=100, **kwargs):
        self.init_pulser(GPIB_prim_address)

        self.readout_utils.configure_tdc_fsm(enable_tdc=True, enable_tdc_arming=False)

        x = []
        y = []
        y_err = []

        self.readout.read_data()  # clear data
        for pulse_width in [i for j in (range(10, 100, 5), range(100, 400, 10)) for i in j]:
            logging.info('Test TDC for a pulse with of %d' % pulse_width)
            self.start_pulser(pulse_width, n_pulses)
            time.sleep(1)
            data = self.readout.read_data()
            if len(is_tdc_data(data)) != n_pulses:
                logging.warning('Too less TDC words %d instead of %d ' % (len(is_tdc_data(data)), n_pulses))
            tdc_values = np.bitwise_and(data[is_tdc_data(data)], 0x00000FFF)
            tdc_counter = np.bitwise_and(data[is_tdc_data(data)], 0x0FFFF000)
            tdc_counter = np.right_shift(tdc_counter, 12)
            if np.any(np.logical_and(tdc_counter[np.gradient(tdc_counter) != 1] != 0, tdc_counter[np.gradient(tdc_counter) != 1] != 65535)):
                logging.warning('The counter did not count correctly')
            x.append(pulse_width)
            y.append(np.mean(tdc_values))
            y_err.append(np.std(tdc_values))

        plotting.plot_scatter(x, y, y_err, title='FPGA TDC linearity, ' + str(n_pulses) + ' each', x_label='pulse width [ns]', y_label='TDC value', filename=None)


if __name__ == "__main__":
    import configuration
    scan = TdcTest(**configuration.device_configuration)
    scan.start(**scan_configuration)
    scan.stop()
