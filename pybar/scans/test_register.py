import logging

from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.fei4.register_utils import read_chip_sn, test_global_register, read_pixel_register
from pybar.analysis.plotting import plotting


class RegisterTest(Fei4RunBase):

    '''Testing of FEI4(A/B) global and pixel register and reading of chip S/N.

    Note
    ----
    Number of register errors is some arbitrary number.

    FEI4A specific features:
    Register at address 41 will always fail (EOCHLskipped).
    FEI4A has timing issues when reading pixel registers. The data from pixel registers is corrupted. It is a known bug of the FEI4A. Lowering the digital voltage (VDDD) to 1.0V may improve the result.

    FEI4B specific features:
    Register at address 40 will always fail (ADC output value).
    '''
    _default_run_conf = {
        "read_sn": True,
        "test_global": True,
        "test_pixel": True
    }

    def configure(self):
        pass

    def scan(self):
        if self.read_sn:
            read_chip_sn(self)

        if self.test_global:
            global_register_errors = test_global_register(self)
            if global_register_errors:
                raise Exception('Global register test finished with %d errors' % global_register_errors)

        if self.test_pixel:
            pixel_register_errors = self.test_pixel_register()
            if pixel_register_errors:
                raise Exception('Pixel register test finished with %d errors' % pixel_register_errors)

    def analyze(self):
        pass

    def test_pixel_register(self, pix_regs=["EnableDigInj", "Imon", "Enable", "C_High", "C_Low", "TDAC", "FDAC"], dcs=range(40)):
        '''Test Pixel Register
        '''
        logging.info('Running Pixel Register Test for %s', str(pix_regs))
        self.register_utils.configure_pixel()
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register_utils.send_commands(commands)
        self.fifo_readout.reset_sram_fifo()

        pixel_register_errors = 0

        plots = PdfPages(self.output_filename + ".pdf")

        for i, result in enumerate(read_pixel_register(self, pix_regs=pix_regs, dcs=dcs)):
            result_array = np.ones_like(result)
            result_array.data[result == self.register.get_pixel_register_value(pix_regs[i])] = 0
            pixel_register_errors += np.count_nonzero(result_array == 1)
            logging.info("Pixel register %s: %d pixel error", pix_regs[i], np.count_nonzero(result_array == 1))
            plotting.plot_three_way(result_array.T, title=str(pix_regs[i]) + " register test with " + str(np.count_nonzero(result_array == 1)) + '/' + str(26880 - np.ma.count_masked(result_array)) + " pixel failing", x_axis_title="0:OK, 1:FAIL", maximum=1, filename=plots)

        plots.close()
        return pixel_register_errors

if __name__ == "__main__":
    RunManager('configuration.yaml').run_run(RegisterTest)
