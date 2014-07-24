import numpy as np
import struct
import logging

from scan.scan import ScanBase
from daq.readout import FEI4Record
from matplotlib.backends.backend_pdf import PdfPages
from analysis.plotting import plotting

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class RegisterTest(ScanBase):
    scan_id = "register_test"

    def scan(self, **kwargs):
        '''Testing of FE global and pixel registers and reading of chip S/N.

        Note
        ----
        Number of register errors is some arbitrary number.
        FEI4A has timing issues when reading pixel registers. The data from pixel registers is corrupted. It is a known bug of the FEI4A. Lowering the digital voltage (VDDD) to 1.0V can improve results.
        '''
        self.register.create_restore_point()

        read_chip_sn(self)

        self.register.restore(keep=True)
        self.register_utils.configure_global()
        test_global_register(self)

        self.register.restore(keep=True)
        self.register_utils.configure_global()
        test_pixel_register(self)

        self.register.restore()
        self.register_utils.configure_global()


def read_chip_sn(self):
    '''Reading Chip S/N

    Note
    ----
    Bits [MSB-LSB] | [15]       | [14-6]       | [5-0]
    Content        | reserved   | wafer number | chip number
    '''
    commands = []
    commands.extend(self.register.get_commands("confmode"))
    self.register_utils.send_commands(commands)
    self.readout.reset_sram_fifo()
    if self.register.fei4b:
        commands = []
        self.register.set_global_register_value('Efuse_Sense', 1)
        commands.extend(self.register.get_commands("wrregister", name=['Efuse_Sense']))
        commands.extend(self.register.get_commands("globalpulse", width=0))
        self.register.set_global_register_value('Efuse_Sense', 0)
        commands.extend(self.register.get_commands("wrregister", name=['Efuse_Sense']))
        self.register_utils.send_commands(commands)
    commands = []
    self.register.set_global_register_value('Conf_AddrEnable', 1)
    commands.extend(self.register.get_commands("wrregister", name=['Conf_AddrEnable']))
    chip_sn_address = self.register.get_global_register_attributes("addresses", name="Chip_SN")
    # print chip_sn_address
    commands.extend(self.register.get_commands("rdregister", addresses=chip_sn_address))
    self.register_utils.send_commands(commands)

    data = self.readout.read_data()
    if data.shape[0] == 0:
        logging.error('Chip S/N: No data')
        return
    read_values = []
    for index, word in enumerate(np.nditer(data)):
        fei4_data_word = FEI4Record(word, self.register.chip_flavor)
        if fei4_data_word == 'AR':
            fei4_next_data_word = FEI4Record(data[index + 1], self.register.chip_flavor)
            if fei4_next_data_word == 'VR':
                read_value = fei4_next_data_word['value']
                # print read_value
                read_values.append(read_value)

    commands = []
    commands.extend(self.register.get_commands("runmode"))
    self.register_utils.send_commands(commands)

    if len(read_values) == 0:
        logging.error('No Chip S/N was found')
    elif len(read_values) == 1:
        logging.info('Chip S/N: %d' % read_values[0])
    else:
        logging.warning('Ambiguous Chip S/N: %s' % read_values)


def test_global_register(self):
    '''Test Global Register
    '''
    logging.info('Running Global Register Test...')
    self.register_utils.configure_global()
    commands = []
    commands.extend(self.register.get_commands("confmode"))
    self.register_utils.send_commands(commands)
    commands = []
    self.register.set_global_register_value('Conf_AddrEnable', 1)
    commands.extend(self.register.get_commands("wrregister", name='Conf_AddrEnable'))
    read_from_address = range(1, 64)
    self.register_utils.send_commands(commands)
    self.readout.reset_sram_fifo()
    commands = []
    commands.extend(self.register.get_commands("rdregister", addresses=read_from_address))
    self.register_utils.send_commands(commands)

    data = self.readout.read_data()
    if data.shape[0] == 0:
        logging.error('Global Register Test: No data')
        return
    checked_address = []
    number_of_errors = 0
    for index, word in enumerate(np.nditer(data)):
        fei4_data_word = FEI4Record(word, self.register.chip_flavor)
        # print fei4_data_word
        if fei4_data_word == 'AR':
            fei4_next_data_word = FEI4Record(data[index + 1], self.register.chip_flavor)
            if fei4_next_data_word == 'VR':
                read_value = fei4_next_data_word['value']
                set_value_bitarray = self.register.get_global_register_bitsets([fei4_data_word['address']])[0]
                set_value_bitarray.reverse()
                set_value = struct.unpack('H', set_value_bitarray.tobytes())[0]
                checked_address.append(fei4_data_word['address'])
                # print int(self.register.get_global_register_bitsets([fei4_data_word['address']])[0])
                if read_value == set_value:
                    # print 'Register Test:', 'Address', fei4_data_word['address'], 'PASSED'
                    pass
                else:
                    number_of_errors += 1
                    logging.warning('Global Register Test: Wrong data for Global Register at address %d (read: %d, expected: %d)' % (fei4_data_word['address'], read_value, set_value))
            else:
                number_of_errors += 1
                logging.warning('Global Register Test: Expected Value Record but found %s' % fei4_next_data_word)

    commands = []
    commands.extend(self.register.get_commands("runmode"))
    self.register_utils.send_commands(commands)
    not_read_registers = set.difference(set(read_from_address), checked_address)
    not_read_registers = list(not_read_registers)
    not_read_registers.sort()
    for address in not_read_registers:
        logging.error('Global Register Test: Data for Global Register at address %d missing' % address)
        number_of_errors += 1
    logging.info('Global Register Test: Found %d error(s)' % number_of_errors)


def test_pixel_register(self, pix_regs=["EnableDigInj", "Imon", "Enable", "C_High", "C_Low", "TDAC", "FDAC"], dcs=range(40)):
    '''Test Pixel Register
    '''
    logging.info('Running Pixel Register Test for %s' % str(pix_regs))
    self.register_utils.configure_pixel()
    commands = []
    commands.extend(self.register.get_commands("confmode"))
    self.register_utils.send_commands(commands)
    self.readout.reset_sram_fifo()

    plots = PdfPages(self.scan_data_filename + ".pdf")

    for i, result in enumerate(self.register_utils.read_pixel_register(pix_regs=pix_regs, dcs=dcs)):
        result_array = np.ones_like(result)
        result_array.data[result == self.register.get_pixel_register_value(pix_regs[i])] = 0
        logging.info("Pixel register %s: %d pixel error" % (pix_regs[i], np.count_nonzero(result_array == 1)))
        plotting.plotThreeWay(result_array.T, title=str(pix_regs[i]) + " register test with " + str(np.count_nonzero(result_array == 1)) + '/' + str(26880 - np.ma.count_masked(result_array)) + " pixel failing", x_axis_title="0:OK, 1:FAIL", maximum=1, filename=plots)

    plots.close()

if __name__ == "__main__":
    import configuration
    scan = RegisterTest(**configuration.default_configuration)
    scan.start()
    scan.stop()
