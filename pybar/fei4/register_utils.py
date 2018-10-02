import logging
import time
import re
import struct
from ast import literal_eval
import itertools

from bitarray import bitarray
import numpy as np

from basil.utils.BitLogic import BitLogic

from pybar.utils.utils import bitarray_to_array
from pybar.daq.readout_utils import interpret_pixel_data
from pybar.daq.fei4_record import FEI4Record


class CmdTimeoutError(Exception):
    pass


class FEI4RegisterUtils(object):

    def __init__(self, dut, register, abort=None):
        self.dut = dut
        self.register = register
        self.command_memory_byte_size = 2048 - 16  # 16 bytes of register data
        self.zero_cmd_length = 1
        self.zero_cmd = self.register.get_commands("zeros", length=self.zero_cmd_length)[0]
        self.zero_cmd_padded = self.zero_cmd.copy()
        self.zero_cmd_padded.fill()
        self.abort = abort

    def add_commands(self, x, y):
        return x + self.zero_cmd + y  # FE needs a zero bits between commands

    def add_byte_padded_commands(self, x, y):
        x_fill = x.copy()
        x_fill.fill()
        y_fill = y.copy()
        y_fill.fill()
        return x_fill + self.zero_cmd_padded + y_fill  # FE needs a zero between commands

    def concatenate_commands(self, commands, byte_padding=False):
        if byte_padding:
            return reduce(self.add_byte_padded_commands, commands)
        else:
            return reduce(self.add_commands, commands)

    def send_commands(self, commands, repeat=1, wait_for_finish=True, concatenate=True, byte_padding=False, clear_memory=False, use_timeout=True):
        if concatenate:
            commands_iter = iter(commands)
            try:
                concatenated_cmd = commands_iter.next()
            except StopIteration:
                logging.warning('No commands to be sent')
            else:
                for command in commands_iter:
                    concatenated_cmd_tmp = self.concatenate_commands((concatenated_cmd, command), byte_padding=byte_padding)
                    if concatenated_cmd_tmp.length() > self.command_memory_byte_size * 8:
                        self.send_command(command=concatenated_cmd, repeat=repeat, wait_for_finish=wait_for_finish, set_length=True, clear_memory=clear_memory, use_timeout=use_timeout)
                        concatenated_cmd = command
                    else:
                        concatenated_cmd = concatenated_cmd_tmp
                # send remaining commands
                self.send_command(command=concatenated_cmd, repeat=repeat, wait_for_finish=wait_for_finish, set_length=True, clear_memory=clear_memory, use_timeout=use_timeout)
        else:
            max_length = 0
            if repeat is not None:
                self.dut['CMD']['CMD_REPEAT'] = repeat
            for command in commands:
                max_length = max(command.length(), max_length)
                self.send_command(command=command, repeat=None, wait_for_finish=wait_for_finish, set_length=True, clear_memory=False, use_timeout=use_timeout)
            if clear_memory:
                self.clear_command_memory(length=max_length)

    def send_command(self, command, repeat=1, wait_for_finish=True, set_length=True, clear_memory=False, use_timeout=True):
        if repeat is not None:
            self.dut['CMD']['CMD_REPEAT'] = repeat
        # write command into memory
        command_length = self.set_command(command, set_length=set_length)
        # sending command
        self.dut['CMD']['START']
        # wait for command to be finished
        if wait_for_finish:
            self.wait_for_command(length=command_length, repeat=repeat, use_timeout=use_timeout)
        # clear command memory
        if clear_memory:
            self.clear_command_memory(length=command_length)

    def clear_command_memory(self, length=None):
        self.set_command(self.register.get_commands("zeros", length=(self.command_memory_byte_size * 8) if length is None else length)[0], set_length=False)

    def set_command(self, command, set_length=True, byte_offset=0):
        command_length = command.length()
        # set command bit length
        if set_length:
            self.dut['CMD']['CMD_SIZE'] = command_length
        # set command
        data = bitarray_to_array(command)
        self.dut['CMD'].set_data(data=data, addr=byte_offset)
        return command_length

    def wait_for_command(self, length=None, repeat=None, use_timeout=True):
        # for scans using the scan loop, reading length and repeat will decrease processor load by 30 to 50%, but has a marginal influence on scan time
        if length is None:
            length = self.dut['CMD']['CMD_SIZE'] - self.dut['CMD']['START_SEQUENCE_LENGTH'] - self.dut['CMD']['STOP_SEQUENCE_LENGTH']
        if repeat is None:
            repeat = self.dut['CMD']['CMD_REPEAT']
        if length and repeat > 1:
            delay = length * 25e-9 * repeat
            if delay <= 0.0:
                delay = None  # no additional delay
        else:
            delay = None
        if use_timeout:
            timeout = 1.0  # minimum timeout threshold
            if delay is not None and delay > 0.0:
                timeout += delay  # adding command delay to timeout
            try:
                msg = "Time out while waiting for sending command becoming ready in %s, module %s. Power cycle or reset readout board!" % (self.dut['CMD'].name, self.dut['CMD'].__class__.__module__)
                if not self.dut['CMD'].wait_for_ready(timeout=timeout, times=None, delay=delay, abort=self.abort) and not self.abort.is_set():
                    raise CmdTimeoutError(msg)
            except RuntimeError:
                raise CmdTimeoutError(msg)
        else:
            if delay is not None and delay > 0.0:
                time.sleep(delay)
            while not self.is_ready:
                pass

    @property
    def is_ready(self):
        return True if self.dut['CMD']['READY'] else False

    def global_reset(self):
        '''FEI4 Global Reset

        Special function to do a global reset on FEI4. Sequence of commands has to be like this, otherwise FEI4B will be left in weird state.
        '''
        logging.info('Sending Global Reset')
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("GlobalReset"))
        self.send_commands(commands)
        time.sleep(0.1)
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("RunMode"))
        self.send_commands(commands)

    def reset_service_records(self):
        '''Resetting Service Records

        This will reset Service Record counters. This will also bring back alive some FE where the output FIFO is stuck (no data is coming out in run mode).
        This should be only issued after power up and in the case of a stuck FIFO, otherwise the BCID counter starts jumping.
        '''
        logging.info('Resetting Service Records')
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value('ReadErrorReq', 1)
        commands.extend(self.register.get_commands("WrRegister", name=['ReadErrorReq']))
        commands.extend(self.register.get_commands("GlobalPulse", Width=0))
        self.register.set_global_register_value('ReadErrorReq', 0)
        commands.extend(self.register.get_commands("WrRegister", name=['ReadErrorReq']))
        commands.extend(self.register.get_commands("RunMode"))
        self.send_commands(commands)

    def reset_bunch_counter(self):
        '''Resetting Bunch Counter
        '''
        logging.info('Resetting Bunch Counter')
        commands = []
        commands.extend(self.register.get_commands("RunMode"))
        commands.extend(self.register.get_commands("BCR"))
        self.send_commands(commands)
        time.sleep(0.1)
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("RunMode"))
        self.send_commands(commands)

    def reset_event_counter(self):
        '''Resetting Event Counter
        '''
        logging.info('Resetting Event Counter')
        commands = []
        commands.extend(self.register.get_commands("RunMode"))
        commands.extend(self.register.get_commands("ECR"))  # wait some time after ECR
        self.send_commands(commands)
        time.sleep(0.1)
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("RunMode"))
        self.send_commands(commands)

    def configure_all(self, same_mask_for_all_dc=False):
        self.configure_global()
        self.configure_pixel(same_mask_for_all_dc=same_mask_for_all_dc)

    def configure_global(self):
        logging.info('Sending global configuration to FE')
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("WrRegister", readonly=False))
        commands.extend(self.register.get_commands("RunMode"))
        self.send_commands(commands, concatenate=True)

    def configure_pixel(self, same_mask_for_all_dc=False):
        logging.info('Sending pixel configuration to FE')
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=same_mask_for_all_dc, name=["TDAC", "FDAC", "Imon", "Enable", "C_High", "C_Low", "EnableDigInj"]))
        commands.extend(self.register.get_commands("RunMode"))
        self.send_commands(commands)

    def set_gdac(self, value, send_command=True):
        if self.register.fei4b:
            altf = value & 0xff
            altc = (value >> 7)
            altc &= ~0x01
        else:
            altf = value & 0xff
            altc = (value >> 8)
        self.register.set_global_register_value("Vthin_AltCoarse", altc)  # write high word
        self.register.set_global_register_value("Vthin_AltFine", altf)  # write low word
        if send_command:
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            commands.extend(self.register.get_commands("WrRegister", name=["Vthin_AltFine", "Vthin_AltCoarse"]))
            commands.extend(self.register.get_commands("RunMode"))
            self.send_commands(commands)
            logging.info("Writing GDAC %d (VthinAltCoarse / VthinAltFine = %d / %d)", value, altc, altf)
        else:
            logging.info("Setting GDAC to %d (VthinAltCoarse / VthinAltFine = %d / %d)", value, altc, altf)

    def get_gdac(self, altc=None, altf=None):
        if altc is None:
            altc = self.register.get_global_register_value("Vthin_AltCoarse")
        if altf is None:
            altf = self.register.get_global_register_value("Vthin_AltFine")
        if self.register.fei4b:
            value = altf & 0xff
            altc &= ~0x01
            value += (altc << 7)
            return value
        else:
            value = altf & 0xff
            value += (altc << 8)
            return value


def read_chip_sn(self):
    '''Reading Chip S/N

    Note
    ----
    Bits [MSB-LSB] | [15]       | [14-6]       | [5-0]
    Content        | reserved   | wafer number | chip number
    '''
    commands = []
    commands.extend(self.register.get_commands("ConfMode"))
    self.register_utils.send_commands(commands)
    self.fifo_readout.reset_fifo(fifos="FIFO")
    if self.register.fei4b:
        commands = []
        self.register.set_global_register_value('Efuse_Sense', 1)
        commands.extend(self.register.get_commands("WrRegister", name=['Efuse_Sense']))
        commands.extend(self.register.get_commands("GlobalPulse", Width=0))
        self.register.set_global_register_value('Efuse_Sense', 0)
        commands.extend(self.register.get_commands("WrRegister", name=['Efuse_Sense']))
        self.register_utils.send_commands(commands)
    commands = []
    self.register.set_global_register_value('Conf_AddrEnable', 1)
    commands.extend(self.register.get_commands("WrRegister", name=['Conf_AddrEnable']))
    chip_sn_address = self.register.get_global_register_attributes("addresses", name="Chip_SN")
    commands.extend(self.register.get_commands("RdRegister", addresses=chip_sn_address))
    self.register_utils.send_commands(commands)

    data = self.fifo_readout.read_raw_data_from_fifo(fifo="FIFO")
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
                read_values.append(read_value)

    commands = []
    commands.extend(self.register.get_commands("RunMode"))
    self.register_utils.send_commands(commands)

    if len(read_values) == 0:
        logging.error('No Chip S/N was found')
    elif len(read_values) == 1:
        logging.info('Chip S/N: %d', read_values[0])
    else:
        logging.warning('Ambiguous Chip S/N: %s', read_values)


def test_global_register(self):
    '''Test Global Register
    '''
    logging.info('Running Global Register Test...')
    self.register_utils.configure_global()
    commands = []
    commands.extend(self.register.get_commands("ConfMode"))
    self.register_utils.send_commands(commands)
    commands = []
    self.register.set_global_register_value('Conf_AddrEnable', 1)
    commands.extend(self.register.get_commands("WrRegister", name='Conf_AddrEnable'))
    self.register_utils.send_commands(commands)
    self.fifo_readout.reset_fifo(fifos="FIFO")
    commands = []
    read_from_address = self.register.get_global_register_attributes("addresses", readonly=False)
    commands.extend(self.register.get_commands("RdRegister", addresses=read_from_address))
    self.register_utils.send_commands(commands)
    time.sleep(1.0)  # wait for data
    data = self.fifo_readout.read_raw_data_from_fifo(fifo="FIFO")
    if data.shape[0] == 0:
        logging.error('Global Register Test: No data')
        return 1
    checked_address = []
    number_of_errors = 0
    for index, word in enumerate(np.nditer(data)):
        fei4_data_word = FEI4Record(word, self.register.chip_flavor)
        if fei4_data_word == 'AR':
            fei4_next_data_word = FEI4Record(data[index + 1], self.register.chip_flavor)
            if fei4_next_data_word == 'VR':
                read_value = fei4_next_data_word['value']
                set_value_bitarray = self.register.get_global_register_bitsets([fei4_data_word['address']])[0]
                set_value_bitarray.reverse()
                set_value = struct.unpack('H', set_value_bitarray.tobytes())[0]
                checked_address.append(fei4_data_word['address'])
                if read_value == set_value:
                    pass
                else:
                    number_of_errors += 1
                    logging.warning('Global Register Test: Wrong data for Global Register at address %d (read: %d, expected: %d)', fei4_data_word['address'], read_value, set_value)
            else:
                number_of_errors += 1
                logging.warning('Global Register Test: Expected Value Record but found %s', fei4_next_data_word)

    commands = []
    commands.extend(self.register.get_commands("RunMode"))
    self.register_utils.send_commands(commands)
    not_read_registers = set.difference(set(read_from_address), checked_address)
    not_read_registers = list(not_read_registers)
    not_read_registers.sort()
    for address in not_read_registers:
        logging.error('Global Register Test: Data for Global Register at address %d missing', address)
        number_of_errors += 1
    logging.info('Global Register Test: Found %d error(s)' % number_of_errors)
    return number_of_errors


def test_pixel_register(self):
    '''Test Pixel Register
    '''
    logging.info('Running Pixel Register Test...')
    self.register_utils.configure_pixel()
    commands = []
    commands.extend(self.register.get_commands("ConfMode"))
    self.register_utils.send_commands(commands)
    self.fifo_readout.reset_fifo(fifos="FIFO")

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

    commands.extend(self.register.get_commands("WrRegister", name=["Conf_AddrEnable", "S0", "S1", "SR_Clr", "CalEn", "DIGHITIN_SEL", "GateHitOr", "ReadSkipped", "ReadErrorReq", "StopClkPulse", "SR_Clock", "Efuse_Sense", "HITLD_IN", "Colpr_Mode", "Colpr_Addr", "Pixel_Strobes", "Latch_En"]))
    self.register_utils.send_commands(commands)
    time.sleep(1)
    register_objects = self.register.get_pixel_register_objects(do_sort=['pxstrobe'], reverse=True, name=["EnableDigInj", "Imon", "Enable", "C_High", "C_Low", "TDAC", "FDAC"])  # check EnableDigInj first, because it is not latched
    number_of_errors = 0
    for register_object in register_objects:
        pxstrobe = register_object['pxstrobe']
        bitlength = register_object['bitlength']
        for pxstrobe_bit_no in range(bitlength):
            logging.info('Testing Pixel Register %s Bit %d', register_object['name'], pxstrobe_bit_no)
            do_latch = True
            commands = []
            try:
                self.register.set_global_register_value("Pixel_Strobes", 2 ** (pxstrobe + pxstrobe_bit_no))
            except TypeError:
                self.register.set_global_register_value("Pixel_Strobes", 0)  # do not latch
                do_latch = False
            commands.extend(self.register.get_commands("WrRegister", name=["Pixel_Strobes"]))
            self.register_utils.send_commands(commands)
            for dc_no in range(40):
                commands = []
                self.register.set_global_register_value("Colpr_Addr", dc_no)
                commands.extend(self.register.get_commands("WrRegister", name=["Colpr_Addr"]))
                self.register_utils.send_commands(commands)

                if do_latch is True:
                    commands = []
                    self.register.set_global_register_value("S0", 1)
                    self.register.set_global_register_value("S1", 1)
                    self.register.set_global_register_value("SR_Clock", 1)
                    commands.extend(self.register.get_commands("WrRegister", name=["S0", "S1", "SR_Clock"]))
                    commands.extend(self.register.get_commands("GlobalPulse", Width=0))
                    self.register_utils.send_commands(commands)
                commands = []
                self.register.set_global_register_value("S0", 0)
                self.register.set_global_register_value("S1", 0)
                self.register.set_global_register_value("SR_Clock", 0)
                commands.extend(self.register.get_commands("WrRegister", name=["S0", "S1", "SR_Clock"]))
                self.register_utils.send_commands(commands)

                register_bitset = self.register.get_pixel_register_bitset(register_object, pxstrobe_bit_no if (register_object['littleendian'] is False) else register_object['bitlength'] - pxstrobe_bit_no - 1, dc_no)

                commands = []
                if self.register.fei4b:
                    self.register.set_global_register_value("SR_Read", 1)
                    commands.extend(self.register.get_commands("WrRegister", name=["SR_Read"]))
                commands.extend([self.register.build_command("WrFrontEnd", pixeldata=register_bitset, chipid=self.register.chip_id)])
                if self.register.fei4b:
                    self.register.set_global_register_value("SR_Read", 0)
                    commands.extend(self.register.get_commands("WrRegister", name=["SR_Read"]))
                self.register_utils.send_commands(commands)
                data = self.fifo_readout.read_raw_data_from_fifo(fifo="FIFO")
                if data.shape[0] == 0:  # no data
                    if do_latch:
                        logging.error('Pixel Register Test: No data from PxStrobes Bit %d at DC %d', pxstrobe + pxstrobe_bit_no, dc_no)
                    else:
                        logging.error('Pixel Register Test: No data from PxStrobes Bit SR at DC %d', dc_no)
                    number_of_errors += 1
                else:
                    expected_addresses = range(15, 672, 16)
                    seen_addresses = {}
                    for index, word in enumerate(np.nditer(data)):
                        fei4_data = FEI4Record(word, self.register.chip_flavor)
                        if fei4_data == 'AR':
                            read_value = bitarray()
                            fei4_next_data_word = FEI4Record(data[index + 1], self.register.chip_flavor)
                            if fei4_next_data_word == 'VR':
                                read_value.frombytes(struct.pack('H', fei4_next_data_word['value']))
                                if do_latch is True:
                                    read_value.invert()
                                read_value = struct.unpack('H', read_value.tobytes())[0]
                                read_address = fei4_data['address']
                                if read_address not in expected_addresses:
                                    if do_latch:
                                        logging.warning('Pixel Register Test: Wrong address for PxStrobes Bit %d at DC %d at address %d', pxstrobe + pxstrobe_bit_no, dc_no, read_address)
                                    else:
                                        logging.warning('Pixel Register Test: Wrong address for PxStrobes Bit SR at DC %d at address %d', dc_no, read_address)
                                    number_of_errors += 1
                                else:
                                    if read_address not in seen_addresses:
                                        seen_addresses[read_address] = 1
                                        set_value = register_bitset[read_address - 15:read_address + 1]
                                        set_value = struct.unpack('H', set_value.tobytes())[0]
                                        if read_value == set_value:
                                            pass
#                                             if do_latch:
#                                                 print 'Register Test:', 'PxStrobes Bit', pxstrobe+pxstrobe_bit_no, 'DC', dc_no, 'Address', read_address, 'PASSED'
#                                             else:
#                                                 print 'Register Test:', 'PxStrobes Bit', 'SR', 'DC', dc_no, 'Address', read_address, 'PASSED'
                                        else:
                                            number_of_errors += 1
                                            if do_latch:
                                                logging.warning('Pixel Register Test: Wrong value at PxStrobes Bit %d at DC %d at address %d (read: %d, expected: %d)', pxstrobe + pxstrobe_bit_no, dc_no, read_address, read_value, set_value)
                                            else:
                                                logging.warning('Pixel Register Test: Wrong value at PxStrobes Bit SR at DC %d at address %d (read: %d, expected: %d)', dc_no, read_address, read_value, set_value)
                                    else:
                                        seen_addresses[read_address] = seen_addresses[read_address] + 1
                                        number_of_errors += 1
                                        if do_latch:
                                            logging.warning('Pixel Register Test: Multiple occurrence of data for PxStrobes Bit %d at DC %d at address %d', pxstrobe + pxstrobe_bit_no, dc_no, read_address)
                                        else:
                                            logging.warning('Pixel Register Test: Multiple occurrence of data for PxStrobes Bit SR at DC %d at address %d', dc_no, read_address)
                            else:
                                # number_of_errors += 1  # will be increased later
                                logging.warning('Pixel Register Test: Expected Value Record but found %s', fei4_next_data_word)

                    not_read_addresses = set.difference(set(expected_addresses), seen_addresses.iterkeys())
                    not_read_addresses = list(not_read_addresses)
                    not_read_addresses.sort()
                    for address in not_read_addresses:
                        number_of_errors += 1
                        if do_latch:
                            logging.warning('Pixel Register Test: Missing data from PxStrobes Bit %d at DC %d at address %d', pxstrobe + pxstrobe_bit_no, dc_no, address)
                        else:
                            logging.warning('Pixel Register Test: Missing data at PxStrobes Bit SR at DC %d at address %d', dc_no, address)

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
        commands.extend(self.register.get_commands("WrRegister", name=["Colpr_Addr", "Pixel_Strobes", "S0", "S1", "SR_Clock", "SR_Read"]))
    else:
        commands.extend(self.register.get_commands("WrRegister", name=["Colpr_Addr", "Pixel_Strobes", "S0", "S1", "SR_Clock"]))
    # fixes bug in FEI4 (B only?): reading GR doesn't work after latching pixel register
    commands.extend(self.register.get_commands("WrFrontEnd", name=["EnableDigInj"]))
    commands.extend(self.register.get_commands("RunMode"))
    self.register_utils.send_commands(commands)

    logging.info('Pixel Register Test: Found %d error(s)', number_of_errors)


def read_global_register(self, name, overwrite_config=False):
    '''The function reads the global register, interprets the data and returns the register value.

    Parameters
    ----------
    name : register name
    overwrite_config : bool
        The read values overwrite the config in RAM if true.

    Returns
    -------
    register value
    '''
    self.register_utils.send_commands(self.register.get_commands("ConfMode"))

    commands = []
    commands.extend(self.register.get_commands("RdRegister", name=name))
    self.register_utils.send_commands(commands)

    data = self.fifo_readout.read_raw_data_from_fifo(fifo="FIFO")

    register_object = self.register.get_global_register_objects(name=[name])[0]
    value = BitLogic(register_object['addresses'] * 16)
    index = 0
    for word in np.nditer(data):
        fei4_data_word = FEI4Record(word, self.register.chip_flavor)
        if fei4_data_word == 'AR':
            address_value = fei4_data_word['address']
            if address_value != register_object['address'] + index:
                raise Exception('Unexpected address from Address Record: read: %d, expected: %d' % (address_value, register_object['address'] + index))
        elif fei4_data_word == 'VR':
            read_value = BitLogic.from_value(fei4_data_word['value'], size=16)
            if register_object['register_littleendian']:
                read_value.reverse()
            value[index * 16 + 15:index * 16] = read_value
            index += 1
    value = value[register_object['bitlength'] + register_object['offset'] - 1:register_object['offset']]
    if register_object['littleendian']:
        value.reverse()
    value = value.tovalue()
    if overwrite_config:
        self.register.set_global_register(name, value)
    return value


def read_pixel_register(self, pix_regs=None, dcs=range(40), overwrite_config=False):
    '''The function reads the pixel register, interprets the data and returns a masked numpy arrays with the data for the chosen pixel register.
    Pixels without any data are masked.

    Parameters
    ----------
    pix_regs : iterable, string
        List of pixel register to read (e.g. Enable, C_High, ...).
        If None all are read: "EnableDigInj", "Imon", "Enable", "C_High", "C_Low", "TDAC", "FDAC"
    dcs : iterable, int
        List of double columns to read.
    overwrite_config : bool
        The read values overwrite the config in RAM if true.

    Returns
    -------
    list of masked numpy.ndarrays
    '''
    if pix_regs is None:
        pix_regs = ["EnableDigInj", "Imon", "Enable", "C_High", "C_Low", "TDAC", "FDAC"]

    self.register_utils.send_commands(self.register.get_commands("ConfMode"))

    result = []
    for pix_reg in pix_regs:
        pixel_data = np.ma.masked_array(np.zeros(shape=(80, 336), dtype=np.uint32), mask=True)  # the result pixel array, only pixel with data are not masked
        for dc in dcs:
            self.register_utils.send_commands(self.register.get_commands("RdFrontEnd", name=[pix_reg], dcs=[dc]))
            data = self.fifo_readout.read_raw_data_from_fifo(fifo="FIFO")
            interpret_pixel_data(data, dc, pixel_data, invert=False if pix_reg == "EnableDigInj" else True)
        if overwrite_config:
            self.register.set_pixel_register(pix_reg, pixel_data.data)
        result.append(pixel_data)
    return result


def is_fe_ready(self):
    '''Get FEI4 status.

    If FEI4 is not ready, resetting service records is necessary to bring the FEI4 to a defined state.

    Returns
    -------
    value : bool
        True if FEI4 is ready, False if the FEI4 was powered up recently and is not ready.
    '''
    commands = []
    commands.extend(self.register.get_commands("ConfMode"))
    commands.extend(self.register.get_commands("RdRegister", address=[1]))
    commands.extend(self.register.get_commands("RunMode"))
    self.register_utils.send_commands(commands)
    data = self.fifo_readout.read_raw_data_from_fifo(fifo="FIFO")
    if len(data):
        return True if FEI4Record(data[-1], self.register.chip_flavor) == 'VR' else False
    else:
        return False


def invert_pixel_mask(mask):
    '''Invert pixel mask (0->1, 1(and greater)->0).

    Parameters
    ----------
    mask : array-like
        Mask.

    Returns
    -------
    inverted_mask : array-like
        Inverted Mask.
    '''
    inverted_mask = np.ones(shape=(80, 336), dtype=np.dtype('>u1'))
    inverted_mask[mask >= 1] = 0
    return inverted_mask


def make_pixel_mask(steps, shift, default=0, value=1, enable_columns=None, mask=None):
    '''Generate pixel mask.

    Parameters
    ----------
    steps : int
        Number of mask steps, e.g. steps=3 (every third pixel is enabled), steps=336 (one pixel per column), steps=672 (one pixel per double column).
    shift : int
        Shift mask by given value to the bottom (towards higher row numbers). From 0 to (steps - 1).
    default : int
        Value of pixels that are not selected by the mask.
    value : int
        Value of pixels that are selected by the mask.
    enable_columns : list
        List of columns where the shift mask will be applied. List elements can range from 1 to 80.
    mask : array_like
        Additional mask. Must be convertible to an array of booleans with the same shape as mask array. True indicates a masked (i.e. invalid) data. Masked pixels will be set to default value.

    Returns
    -------
    mask_array : numpy.ndarray
        Mask array.

    Usage
    -----
    shift_mask = 'enable'
    steps = 3 # three step mask
    for mask_step in range(steps):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        mask_array = make_pixel_mask(steps=steps, step=mask_step)
        self.register.set_pixel_register_value(shift_mask, mask_array)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=shift_mask))
        self.register_utils.send_commands(commands)
        # do something here
    '''
    shape = (80, 336)
    # value = np.zeros(dimension, dtype = np.uint8)
    mask_array = np.full(shape, default, dtype=np.uint8)
    # FE columns and rows are starting from 1
    if enable_columns:
        odd_columns = [odd - 1 for odd in enable_columns if odd % 2 != 0]
        even_columns = [even - 1 for even in enable_columns if even % 2 == 0]
    else:
        odd_columns = range(0, 80, 2)
        even_columns = range(1, 80, 2)
    odd_rows = np.arange(shift % steps, 336, steps)
    even_row_offset = ((steps // 2) + shift) % steps  # // integer devision
    even_rows = np.arange(even_row_offset, 336, steps)
    if odd_columns:
        odd_col_rows = itertools.product(odd_columns, odd_rows)  # get any combination of column and row, no for loop needed
        for odd_col_row in odd_col_rows:
            mask_array[odd_col_row[0], odd_col_row[1]] = value  # advanced indexing
    if even_columns:
        even_col_rows = itertools.product(even_columns, even_rows)
        for even_col_row in even_col_rows:
            mask_array[even_col_row[0], even_col_row[1]] = value
    if mask is not None:
        mask_array = np.ma.array(mask_array, mask=mask, fill_value=default)
        mask_array = mask_array.filled()
    return mask_array


def make_pixel_mask_from_col_row(column, row, default=0, value=1):
    '''Generate mask from column and row lists

    Parameters
    ----------
    column : iterable, int
        List of colums values.
    row : iterable, int
        List of row values.
    default : int
        Value of pixels that are not selected by the mask.
    value : int
        Value of pixels that are selected by the mask.

    Returns
    -------
    mask : numpy.ndarray
    '''
    # FE columns and rows start from 1
    col_array = np.array(column) - 1
    row_array = np.array(row) - 1
    if np.any(col_array >= 80) or np.any(col_array < 0) or np.any(row_array >= 336) or np.any(row_array < 0):
        raise ValueError('Column and/or row out of range')
    shape = (80, 336)
    mask = np.full(shape, default, dtype=np.uint8)
    mask[col_array, row_array] = value  # advanced indexing
    return mask


def make_box_pixel_mask_from_col_row(column, row, default=0, value=1):
    '''Generate box shaped mask from column and row lists. Takes the minimum and maximum value from each list.

    Parameters
    ----------
    column : iterable, int
        List of colums values.
    row : iterable, int
        List of row values.
    default : int
        Value of pixels that are not selected by the mask.
    value : int
        Value of pixels that are selected by the mask.

    Returns
    -------
    numpy.ndarray
    '''
    # FE columns and rows start from 1
    col_array = np.array(column) - 1
    row_array = np.array(row) - 1
    if np.any(col_array >= 80) or np.any(col_array < 0) or np.any(row_array >= 336) or np.any(row_array < 0):
        raise ValueError('Column and/or row out of range')
    shape = (80, 336)
    mask = np.full(shape, default, dtype=np.uint8)
    if column and row:
        mask[col_array.min():col_array.max() + 1, row_array.min():row_array.max() + 1] = value  # advanced indexing
    return mask


def make_xtalk_mask(mask):
    """
    Generate xtalk mask (row - 1, row + 1) from pixel mask.

    Parameters
    ----------
    mask : ndarray
        Pixel mask.

    Returns
    -------
    ndarray
        Xtalk mask.

    Example
    -------
    Input:
    [[1 0 0 0 0 0 1 0 0 0 ... 0 0 0 0 1 0 0 0 0 0]
     [0 0 0 1 0 0 0 0 0 1 ... 0 1 0 0 0 0 0 1 0 0]
     ...
     [1 0 0 0 0 0 1 0 0 0 ... 0 0 0 0 1 0 0 0 0 0]
     [0 0 0 1 0 0 0 0 0 1 ... 0 1 0 0 0 0 0 1 0 0]]

    Output:
    [[0 1 0 0 0 1 0 1 0 0 ... 0 0 0 1 0 1 0 0 0 1]
     [0 0 1 0 1 0 0 0 1 0 ... 1 0 1 0 0 0 1 0 1 0]
     ...
     [0 1 0 0 0 1 0 1 0 0 ... 0 0 0 1 0 1 0 0 0 1]
     [0 0 1 0 1 0 0 0 1 0 ... 1 0 1 0 0 0 1 0 1 0]]
    """
    col, row = mask.nonzero()
    row_plus_one = row + 1
    del_index = np.where(row_plus_one > 335)
    row_plus_one = np.delete(row_plus_one, del_index)
    col_plus_one = np.delete(col.copy(), del_index)
    row_minus_one = row - 1
    del_index = np.where(row_minus_one > 335)
    row_minus_one = np.delete(row_minus_one, del_index)
    col_minus_one = np.delete(col.copy(), del_index)
    col = np.concatenate((col_plus_one, col_minus_one))
    row = np.concatenate((row_plus_one, row_minus_one))
    return make_pixel_mask_from_col_row(col + 1, row + 1)


def make_checkerboard_mask(column_distance, row_distance, column_offset=0, row_offset=0, default=0, value=1):
    """
    Generate chessboard/checkerboard mask.

    Parameters
    ----------
    column_distance : int
        Column distance of the enabled pixels.
    row_distance : int
        Row distance of the enabled pixels.
    column_offset : int
        Additional column offset which shifts the columns by the given amount.
    column_offset : int
        Additional row offset which shifts the rows by the given amount.

    Returns
    -------
    ndarray
        Chessboard mask.

    Example
    -------
    Input:
    column_distance : 6
    row_distance : 2

    Output:
    [[1 0 0 0 0 0 1 0 0 0 ... 0 0 0 0 1 0 0 0 0 0]
     [0 0 0 0 0 0 0 0 0 0 ... 0 0 0 0 0 0 0 0 0 0]
     [0 0 0 1 0 0 0 0 0 1 ... 0 1 0 0 0 0 0 1 0 0]
     ...
     [0 0 0 0 0 0 0 0 0 0 ... 0 0 0 0 0 0 0 0 0 0]
     [0 0 0 1 0 0 0 0 0 1 ... 0 1 0 0 0 0 0 1 0 0]
     [0 0 0 0 0 0 0 0 0 0 ... 0 0 0 0 0 0 0 0 0 0]]
    """
    col_shape = (336,)
    col = np.full(col_shape, fill_value=default, dtype=np.uint8)
    col[::row_distance] = value
    shape = (80, 336)
    chessboard_mask = np.full(shape, fill_value=default, dtype=np.uint8)
    chessboard_mask[column_offset::column_distance * 2] = np.roll(col, row_offset)
    chessboard_mask[column_distance + column_offset::column_distance * 2] = np.roll(col, row_distance / 2 + row_offset)
    return chessboard_mask


def parse_key_value(filename, key, deletechars=''):
    with open(filename, 'r') as f:
        return parse_key_value_from_file(f, key, deletechars)


def parse_key_value_from_file(f, key, deletechars=''):
    for line in f.readlines():
        key_value = re.split("\s+|[\s]*=[\s]*", line)
        if (key_value[0].translate(None, deletechars).lower() == key.translate(None, deletechars).lower()):
            if len(key_value) > 1:
                return key_value[0].translate(None, deletechars).lower(), key_value[1].translate(None, deletechars).lower()
            else:
                raise ValueError('Value not found')
        else:
            return None


def calculate_wait_cycles(mask_steps):
    # This delay is a delicate part. A wrong (too short) delay can lead to an effectively smaller injection charge.
    # The delay is good practice, see also bug report #59.
    # The delay was verified with different PlsrDAC settings.
    return int(336.0 / mask_steps * 25.0 + 600)


def scan_loop(self, command, repeat_command=100, use_delay=True, additional_delay=0, mask_steps=3, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, fast_dc_loop=True, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=None, disable_shift_masks=None, restore_shift_masks=True, mask=None, double_column_correction=False):
    '''Implementation of the scan loops (mask shifting, loop over double columns, repeatedly sending any arbitrary command).

    Parameters
    ----------
    command : BitVector
        (FEI4) command that will be sent out serially.
    repeat_command : int
        The number of repetitions command will be sent out each mask step.
    use_delay : bool
        Add additional delay to the command (append zeros). This helps to avoid FE data errors because of sending to many commands to the FE chip.
    additional_delay: int
        Additional delay to increase the command-to-command delay (in number of clock cycles / 25ns).
    mask_steps : int
        Number of mask steps (from 1 to 672).
    enable_mask_steps : list, tuple
        List of mask steps which will be applied. Default is all mask steps. From 0 to (mask-1). A value equal None or empty list will select all mask steps.
    enable_double_columns : list, tuple
        List of double columns which will be enabled during scan. Default is all double columns. From 0 to 39 (double columns counted from zero). A value equal None or empty list will select all double columns.
    same_mask_for_all_dc : bool
        Use same mask for all double columns. This will only affect all shift masks (see enable_shift_masks). Enabling this is in general a good idea since all double columns will have the same configuration and the scan speed can increased by an order of magnitude.
    fast_dc_loop : bool
        If True, optimize double column (DC) loop to save time. Note that bol_function and eol_function cannot do register operations, if True.
    bol_function : function
        Begin of loop function that will be called each time before sending command. Argument is a function pointer (without braces) or functor.
    eol_function : function
        End of loop function that will be called each time after sending command. Argument is a function pointer (without braces) or functor.
    digital_injection : bool
        Enables digital injection. C_High and C_Low will be disabled.
    enable_shift_masks : list, tuple
        List of enable pixel masks which will be shifted during scan. Mask set to 1 for selected pixels else 0. None will select "Enable", "C_High", "C_Low".
    disable_shift_masks : list, tuple
        List of disable pixel masks which will be shifted during scan. Mask set to 0 for selected pixels else 1. None will disable no mask.
    restore_shift_masks : bool
        Writing the initial (restored) FE pixel configuration into FE after finishing the scan loop.
    mask : array-like
        Additional mask. Must be convertible to an array of booleans with the same shape as mask array. True indicates a masked pixel. Masked pixels will be disabled during shifting of the enable shift masks, and enabled during shifting disable shift mask.
    double_column_correction : str, bool, list, tuple
        Enables double column PlsrDAC correction. If value is a filename (string) or list/tuple, the default PlsrDAC correction will be overwritten. First line of the file must be a Python list ([0, 0, ...])
    '''
    if not isinstance(command, bitarray):
        raise TypeError

    if enable_shift_masks is None:
        enable_shift_masks = ["Enable", "C_High", "C_Low"]

    if disable_shift_masks is None:
        disable_shift_masks = []

    # get PlsrDAC correction
    if isinstance(double_column_correction, basestring):  # from file
        with open(double_column_correction) as fp:
            plsr_dac_correction = list(literal_eval(fp.readline().strip()))
    elif isinstance(double_column_correction, (list, tuple)):  # from list/tuple
        plsr_dac_correction = list(double_column_correction)
    else:  # default
        if "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks) and "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks):
            plsr_dac_correction = self.register.calibration_parameters['Pulser_Corr_C_Inj_High']
        elif "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks):
            plsr_dac_correction = self.register.calibration_parameters['Pulser_Corr_C_Inj_Med']
        elif "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks):
            plsr_dac_correction = self.register.calibration_parameters['Pulser_Corr_C_Inj_Low']
    # initial PlsrDAC value for PlsrDAC correction
    initial_plsr_dac = self.register.get_global_register_value("PlsrDAC")
    # create restore point
    restore_point_name = str(self.run_number) + self.run_id + '_scan_loop'
    self.register.create_restore_point(name=restore_point_name)

    # pre-calculate often used commands
    conf_mode_command = self.register.get_commands("ConfMode")[0]
    run_mode_command = self.register.get_commands("RunMode")[0]
    if use_delay:
        delay = self.register.get_commands("zeros", length=additional_delay + calculate_wait_cycles(mask_steps))[0]
        scan_loop_command = command + delay
    else:
        scan_loop_command = command

    def enable_columns(dc):
        if digital_injection:
            return [dc * 2 + 1, dc * 2 + 2]
        else:  # analog injection
            if dc == 0:
                return [1]
            elif dc == 39:
                return [78, 79, 80]
            else:
                return [dc * 2, dc * 2 + 1]

    def write_double_columns(dc):
        if digital_injection:
            return [dc]
        else:  # analog injection
            if dc == 0:
                return [0]
            elif dc == 39:
                return [38, 39]
            else:
                return [dc - 1, dc]

    def get_dc_address_command(dc):
        commands = []
        commands.append(conf_mode_command)
        self.register.set_global_register_value("Colpr_Addr", dc)
        commands.append(self.register.get_commands("WrRegister", name=["Colpr_Addr"])[0])
        if double_column_correction:
            self.register.set_global_register_value("PlsrDAC", initial_plsr_dac + int(round(plsr_dac_correction[dc])))
            commands.append(self.register.get_commands("WrRegister", name=["PlsrDAC"])[0])
        commands.append(run_mode_command)
        return self.register_utils.concatenate_commands(commands, byte_padding=True)

    if not enable_mask_steps:
        enable_mask_steps = range(mask_steps)

    if not enable_double_columns:
        enable_double_columns = range(40)

    # preparing for scan
    commands = []
    commands.append(conf_mode_command)
    if digital_injection is True:
        # check if C_High and/or C_Low is in enable_shift_mask and/or disable_shift_mask
        if "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks) or "C_High".lower() in map(lambda x: x.lower(), disable_shift_masks):
            raise ValueError('C_High must not be shift mask when using digital injection')
        if "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks) or "C_Low".lower() in map(lambda x: x.lower(), disable_shift_masks):
            raise ValueError('C_Low must not be shift mask when using digital injection')
        # turn off all injection capacitors by default
        self.register.set_pixel_register_value("C_High", 0)
        self.register.set_pixel_register_value("C_Low", 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=["C_Low", "C_High"], joint_write=True))
        self.register.set_global_register_value("DIGHITIN_SEL", 1)
# self.register.set_global_register_value("CalEn", 1)  # for GlobalPulse instead Cal-Command
    else:
        self.register.set_global_register_value("DIGHITIN_SEL", 0)
        # setting EnableDigInj to 0 not necessary since DIGHITIN_SEL is turned off
#             self.register.set_pixel_register_value("EnableDigInj", 0)

# plotting registers
#     plt.clf()
#     plt.imshow(curr_en_mask.T, interpolation='nearest', aspect="auto")
#     plt.pcolor(curr_en_mask.T)
#     plt.colorbar()
#     plt.savefig('mask_step' + str(mask_step) + '.pdf')

    commands.extend(self.register.get_commands("WrRegister", name=["DIGHITIN_SEL"]))
    self.register_utils.send_commands(commands, concatenate=True)

    for mask_step in enable_mask_steps:
        if self.abort_run.is_set():
            break
        commands = []
        commands.append(conf_mode_command)
        if same_mask_for_all_dc:  # generate and write first mask step
            if disable_shift_masks:
                curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False if mask is not None else True, name=disable_shift_masks, joint_write=True))
            if enable_shift_masks:
                curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), enable_shift_masks)
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False if mask is not None else True, name=enable_shift_masks, joint_write=True))
            if digital_injection is True:  # write EnableDigInj last
                # write DIGHITIN_SEL since after mask writing it is disabled
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("WrRegister", name=["DIGHITIN_SEL"]))
        else:  # set masks to default values
            if disable_shift_masks:
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, 1), disable_shift_masks)
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=disable_shift_masks, joint_write=True))
            if enable_shift_masks:
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, 0), enable_shift_masks)
                commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=enable_shift_masks, joint_write=True))
            if digital_injection is True:  # write EnableDigInj last
                # write DIGHITIN_SEL since after mask writing it is disabled
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("WrRegister", name=["DIGHITIN_SEL"]))
        self.register_utils.send_commands(commands, concatenate=True)
        logging.info('%d injection(s): mask step %d %s', repeat_command, mask_step, ('[%d - %d]' % (enable_mask_steps[0], enable_mask_steps[-1])) if len(enable_mask_steps) > 1 else ('[%d]' % enable_mask_steps[0]))

        if same_mask_for_all_dc:
            if fast_dc_loop:  # fast DC loop with optimized pixel register writing
                # set repeat, should be 1 by default when arriving here
                self.dut['CMD']['CMD_REPEAT'] = repeat_command

                # get DC command for the first DC in the list, DC command is byte padded
                # fill CMD memory with DC command and scan loop command, inside the loop only overwrite DC command
                dc_address_command = get_dc_address_command(enable_double_columns[0])
                self.dut['CMD']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                for index, dc in enumerate(enable_double_columns):
                    if self.abort_run.is_set():
                        break
                    if index != 0:  # full command is already set before loop
                        # get DC command before wait to save some time
                        dc_address_command = get_dc_address_command(dc)
                        self.register_utils.wait_for_command()
                        if eol_function:
                            eol_function()  # do this after command has finished
                        # only set command after FPGA is ready
                        # overwrite only the DC command in CMD memory
                        self.register_utils.set_command(dc_address_command, set_length=False)  # do not set length here, because it was already set up before the loop

                    if bol_function:
                        bol_function()

                    self.dut['CMD']['START']

                # wait here before we go on because we just jumped out of the loop
                self.register_utils.wait_for_command()
                if eol_function:
                    eol_function()
                self.dut['CMD']['START_SEQUENCE_LENGTH'] = 0

            else:  # the slow DC loop allows writing commands inside bol and eol functions
                for index, dc in enumerate(enable_double_columns):
                    if self.abort_run.is_set():
                        break
                    dc_address_command = get_dc_address_command(dc)
                    self.register_utils.send_command(dc_address_command)

                    if bol_function:
                        bol_function()

                    self.register_utils.send_command(scan_loop_command, repeat=repeat_command)

                    if eol_function:
                        eol_function()

        else:
            if fast_dc_loop:  # fast DC loop with optimized pixel register writing
                dc = enable_double_columns[0]
                ec = enable_columns(dc)
                dcs = write_double_columns(dc)
                commands = []
                commands.append(conf_mode_command)
                if disable_shift_masks:
                    curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                    commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks, joint_write=True))
                if enable_shift_masks:
                    curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), enable_shift_masks)
                    commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks, joint_write=True))
                if digital_injection is True:
                    self.register.set_global_register_value("DIGHITIN_SEL", 1)
                    commands.extend(self.register.get_commands("WrRegister", name=["DIGHITIN_SEL"]))
                self.register_utils.send_commands(commands, concatenate=True)

                dc_address_command = get_dc_address_command(dc)
                self.dut['CMD']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                self.dut['CMD']['CMD_REPEAT'] = repeat_command
                self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                for index, dc in enumerate(enable_double_columns):
                    if self.abort_run.is_set():
                        break
                    if index != 0:  # full command is already set before loop
                        ec = enable_columns(dc)
                        dcs = write_double_columns(dc)
                        dcs.extend(write_double_columns(enable_double_columns[index - 1]))
                        commands = []
                        commands.append(conf_mode_command)
                        if disable_shift_masks:
                            curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks, joint_write=True))
                        if enable_shift_masks:
                            curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), enable_shift_masks)
                            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks, joint_write=True))
                        if digital_injection is True:
                            self.register.set_global_register_value("DIGHITIN_SEL", 1)
                            commands.extend(self.register.get_commands("WrRegister", name=["DIGHITIN_SEL"]))
                        dc_address_command = get_dc_address_command(dc)

                        self.register_utils.wait_for_command()
                        if eol_function:
                            eol_function()  # do this after command has finished
                        self.register_utils.send_commands(commands, concatenate=True)

                        self.dut['CMD']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                        self.dut['CMD']['CMD_REPEAT'] = repeat_command
                        self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                    if bol_function:
                        bol_function()

                    self.dut['CMD']['START']

                self.register_utils.wait_for_command()
                if eol_function:
                    eol_function()
                self.dut['CMD']['START_SEQUENCE_LENGTH'] = 0

            else:
                for index, dc in enumerate(enable_double_columns):
                    if self.abort_run.is_set():
                        break
                    ec = enable_columns(dc)
                    dcs = write_double_columns(dc)
                    if index != 0:
                        dcs.extend(write_double_columns(enable_double_columns[index - 1]))
                    commands = []
                    commands.append(conf_mode_command)
                    if disable_shift_masks:
                        curr_dis_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                        map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks, joint_write=True))
                    if enable_shift_masks:
                        curr_en_mask = make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                        map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), enable_shift_masks)
                        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks, joint_write=True))
                    if digital_injection is True:
                        self.register.set_global_register_value("DIGHITIN_SEL", 1)
                        commands.extend(self.register.get_commands("WrRegister", name=["DIGHITIN_SEL"]))
                    self.register_utils.send_commands(commands, concatenate=True)

                    dc_address_command = get_dc_address_command(dc)
                    self.register_utils.send_command(dc_address_command)

                    if bol_function:
                        bol_function()

                    self.register_utils.send_command(scan_loop_command, repeat=repeat_command)

                    if eol_function:
                        eol_function()

    # restoring default values
    self.register.restore(name=restore_point_name)
    self.register_utils.configure_global()  # always restore global configuration
    if restore_shift_masks:
        commands = []
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=disable_shift_masks))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name=enable_shift_masks))
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name="EnableDigInj"))
        self.register_utils.send_commands(commands)
