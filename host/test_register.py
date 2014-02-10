from scan.scan import ScanBase
from daq.readout import FEI4Record

import numpy as np
from bitarray import bitarray
import struct

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class RegisterTest(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(RegisterTest, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="register_test")

    def scan(self):
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
        logging.warning('Global Register Test: Data for Global Register at address %d missing' % address)
        number_of_errors += 1
    logging.info('Global Register Test: Found %d error(s)' % number_of_errors)


def test_pixel_register(self):
    '''Test Pixel Register
    '''
    logging.info('Running Pixel Register Test...')
    self.register_utils.configure_pixel()
    commands = []
    commands.extend(self.register.get_commands("confmode"))
    self.register_utils.send_commands(commands)
    self.readout.reset_sram_fifo()

    commands = []
    self.register.set_global_register_value('Conf_AddrEnable', 1)
    self.register.set_global_register_value("S0", 0)
    self.register.set_global_register_value("S1", 0)
    self.register.set_global_register_value("SR_Clr", 0)
    self.register.set_global_register_value("CalEn", 0)
    self.register.set_global_register_value("DIGHITIN_SEL", 0)
    self.register.set_global_register_value("GateHitOr", 0)
    if self.register.is_chip_flavor('fei4a'):
        self.register.set_global_register_value("ReadSkipped", 0)
    self.register.set_global_register_value("ReadErrorReq", 0)
    self.register.set_global_register_value("StopClkPulse", 0)
    self.register.set_global_register_value("SR_Clock", 0)
    self.register.set_global_register_value("Efuse_Sense", 0)

    self.register.set_global_register_value("HITLD_IN", 0)
    self.register.set_global_register_value("Colpr_Mode", 0)  # write only the addressed double-column
    self.register.set_global_register_value("Colpr_Addr", 0)

    self.register.set_global_register_value("Latch_En", 0)
    self.register.set_global_register_value("Pixel_Strobes", 0)

    commands.extend(self.register.get_commands("wrregister", name=["Conf_AddrEnable", "S0", "S1", "SR_Clr", "CalEn", "DIGHITIN_SEL", "GateHitOr", "ReadSkipped", "ReadErrorReq", "StopClkPulse", "SR_Clock", "Efuse_Sense", "HITLD_IN", "Colpr_Mode", "Colpr_Addr", "Pixel_Strobes", "Latch_En"]))
    self.register_utils.send_commands(commands)

    register_objects = self.register.get_pixel_register_objects(True, name=["EnableDigInj"])  # check EnableDigInj first, because it is not latched
    register_objects.extend(self.register.get_pixel_register_objects(True, name=["Imon", "Enable", "C_High", "C_Low", "TDAC", "FDAC"]))
    # pprint.pprint(register_objects)
    # print "register_objects", register_objects
    number_of_errors = 0
    for register_object in register_objects:
        # pprint.pprint(register_object)
        pxstrobe = register_object.pxstrobe
        bitlength = register_object.bitlength
        for pxstrobe_bit_no in range(bitlength):
            logging.info('Testing Pixel Register %s Bit %d', register_object.full_name, pxstrobe_bit_no)
            do_latch = True
            commands = []
            try:
                self.register.set_global_register_value("Pixel_Strobes", 2 ** (pxstrobe + pxstrobe_bit_no))
                # print register_object.name
                # print "bit_no", bit_no
                # print "pxstrobes", 2**(pxstrobe+pxstrobe_bit_no)

            except TypeError:
                self.register.set_global_register_value("Pixel_Strobes", 0)  # do not latch
                do_latch = False
                # print register_object.name
                # print "bit_no", bit_no
                # print "pxstrobes", 0
            commands.extend(self.register.get_commands("wrregister", name=["Pixel_Strobes"]))
            self.register_utils.send_commands(commands)

            for dc_no in range(40):
                commands = []
                self.register.set_global_register_value("Colpr_Addr", dc_no)
                commands.extend(self.register.get_commands("wrregister", name=["Colpr_Addr"]))
                self.register_utils.send_commands(commands)

                if do_latch == True:
                    commands = []
                    self.register.set_global_register_value("S0", 1)
                    self.register.set_global_register_value("S1", 1)
                    self.register.set_global_register_value("SR_Clock", 1)
                    commands.extend(self.register.get_commands("wrregister", name=["S0", "S1", "SR_Clock"]))
                    commands.extend(self.register.get_commands("globalpulse", width=0))
                    self.register_utils.send_commands(commands)
                commands = []
                self.register.set_global_register_value("S0", 0)
                self.register.set_global_register_value("S1", 0)
                self.register.set_global_register_value("SR_Clock", 0)
                commands.extend(self.register.get_commands("wrregister", name=["S0", "S1", "SR_Clock"]))
                self.register_utils.send_commands(commands)

                register_bitset = self.register.get_pixel_register_bitset(register_object, pxstrobe_bit_no if (register_object.littleendian == False) else register_object.bitlength - pxstrobe_bit_no - 1, dc_no)

                commands = []
                if self.register.fei4b:
                    self.register.set_global_register_value("SR_Read", 1)
                    commands.extend(self.register.get_commands("wrregister", name=["SR_Read"]))
                commands.extend([self.register.build_command("wrfrontend", pixeldata=register_bitset, chipid=self.register.chip_id)])
                if self.register.fei4b:
                    self.register.set_global_register_value("SR_Read", 0)
                    commands.extend(self.register.get_commands("wrregister", name=["SR_Read"]))
                # print commands[0]
                self.register_utils.send_commands(commands)
                # time.sleep( 0.2 )

                data = self.readout.read_data()
                if data.shape[0] == 0:  # no data
                    if do_latch:
                        logging.error('Pixel Register Test: No data from PxStrobes Bit %d at DC %d' % (pxstrobe + pxstrobe_bit_no, dc_no))
                    else:
                        logging.error('Pixel Register Test: No data from PxStrobes Bit SR at DC %d' % dc_no)
                    number_of_errors += 1
                else:
                    expected_addresses = range(15, 672, 16)
                    seen_addresses = {}
                    for index, word in enumerate(np.nditer(data)):
                        fei4_data = FEI4Record(word, self.register.chip_flavor)
                        # print fei4_data
                        if fei4_data == 'AR':
                            # print int(self.register.get_global_register_bitsets([fei4_data['address']])[0])
                            #read_value = BitArray(uint=FEI4Record(data[index + 1], self.register.chip_flavor)['value'], length=16)
                            read_value = bitarray()
                            fei4_next_data_word = FEI4Record(data[index + 1], self.register.chip_flavor)
                            if fei4_next_data_word == 'VR':
                                read_value.frombytes(struct.pack('H', fei4_next_data_word['value']))
                                if do_latch == True:
                                    read_value.invert()
                                read_value = struct.unpack('H', read_value.tobytes())[0]
                                read_address = fei4_data['address']
                                if read_address not in expected_addresses:
                                    if do_latch:
                                        logging.warning('Pixel Register Test: Wrong address for PxStrobes Bit %d at DC %d at address %d' % (pxstrobe + pxstrobe_bit_no, dc_no, read_address))
                                    else:
                                        logging.warning('Pixel Register Test: Wrong address for PxStrobes Bit SR at DC %d at address %d' % (dc_no, read_address))
                                    number_of_errors += 1
                                else:
                                    if read_address not in seen_addresses:
                                        seen_addresses[read_address] = 1
                                        set_value = register_bitset[read_address - 15:read_address + 1]
                                        set_value = struct.unpack('H', set_value.tobytes())[0]
                                        if read_value == set_value:
    #                                        if do_latch:
    #                                            print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', read_address, 'PASSED'
    #                                        else:
    #                                            print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', read_address, 'PASSED'
                                            pass
                                        else:
                                            number_of_errors += 1
                                            if do_latch:
                                                logging.warning('Pixel Register Test: Wrong value at PxStrobes Bit %d at DC %d at address %d (read: %d, expected: %d)' % (pxstrobe + pxstrobe_bit_no, dc_no, read_address, read_value, set_value))
                                            else:
                                                logging.warning('Pixel Register Test: Wrong value at PxStrobes Bit SR at DC %d at address %d (read: %d, expected: %d)' % (dc_no, read_address, read_value, set_value))
                                    else:
                                        seen_addresses[read_address] = seen_addresses[read_address] + 1
                                        number_of_errors += 1
                                        if do_latch:
                                            logging.warning('Pixel Register Test: Multiple occurrence of data for PxStrobes Bit %d at DC %d at address %d' % (pxstrobe + pxstrobe_bit_no, dc_no, read_address))
                                        else:
                                            logging.warning('Pixel Register Test: Multiple occurrence of data for PxStrobes Bit SR at DC %d at address %d' % (dc_no, read_address))
                            else:
                                # number_of_errors += 1  # will be increased later
                                logging.warning('Pixel Register Test: Expected Value Record but found %s' % fei4_next_data_word)

                    not_read_addresses = set.difference(set(expected_addresses), seen_addresses.iterkeys())
                    not_read_addresses = list(not_read_addresses)
                    not_read_addresses.sort()
                    for address in not_read_addresses:
                        number_of_errors += 1
                        if do_latch:
                            logging.warning('Pixel Register Test: Missing data from PxStrobes Bit %d at DC %d at address %d' % (pxstrobe + pxstrobe_bit_no, dc_no, address))
                        else:
                            logging.warning('Pixel Register Test: Missing data at PxStrobes Bit SR at DC %d at address %d' % (dc_no, address))

#                        for word in data:
#                            print FEI4Record(word, self.register.chip_flavor)
    commands = []
    self.register.set_global_register_value("Pixel_Strobes", 0)
    self.register.set_global_register_value("Colpr_Addr", 0)
    self.register.set_global_register_value("S0", 0)
    self.register.set_global_register_value("S1", 0)
    self.register.set_global_register_value("SR_Clock", 0)
    if self.register.fei4b:
        self.register.set_global_register_value("SR_Read", 0)
        commands.extend(self.register.get_commands("wrregister", name=["Colpr_Addr", "Pixel_Strobes", "S0", "S1", "SR_Clock", "SR_Read"]))
    else:
        commands.extend(self.register.get_commands("wrregister", name=["Colpr_Addr", "Pixel_Strobes", "S0", "S1", "SR_Clock"]))
    # fixes bug in FEI4 (B only?): reading GR doesn't work after latching pixel register
    commands.extend(self.register.get_commands("wrfrontend", name=["EnableDigInj"]))
    commands.extend(self.register.get_commands("runmode"))
    self.register_utils.send_commands(commands)

    logging.info('Pixel Register Test: Found %d error(s)' % number_of_errors)

if __name__ == "__main__":
    import configuration
    scan = RegisterTest(**configuration.device_configuration)
    scan.start()
    scan.stop()
