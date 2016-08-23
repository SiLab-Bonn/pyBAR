import logging
from bitarray import bitarray
import re
import os
import numpy as np
from collections import OrderedDict
import copy
import tables as tb
import datetime
from contextlib import contextmanager
from importlib import import_module
from operator import itemgetter

from pybar.fei4 import register_utils
from pybar.utils.utils import string_is_binary, flatten_iterable, iterable


flavors = ('fei4a', 'fei4b')


class FEI4Register(object):

    def __init__(self, configuration_file=None, fe_type=None, chip_address=None, broadcast=False):
        '''

        Note:
        Chip ID: This 4-bit field consists of broadcast bit and chip address. The broadcast bit, the most significant one, if set, means that the command is broadcasted to all FE chips receiving the data stream.
        Chip address: The three least significant bits of the chip ID define the chip address and are compared with the geographical address of the chip (selected via wire bonding/jumpers).
        '''
        self.flavor = None
        if fe_type:
            self.init_fe_type(fe_type)

        self.broadcast = broadcast
        self.chip_address = None
        if chip_address is not None:
            self.set_chip_address(chip_address)

        self.configuration_file = fe_type
        if configuration_file:
            self.load_configuration(configuration_file)

        self.config_state = OrderedDict()

    def __repr__(self):
        return self.configuration_file

    def set_chip_address(self, chip_address):
        if 7 < chip_address < 0:
            raise ValueError('Chip address out of range: %i' % chip_address)
        self.chip_id_initialized = True
        self.chip_address = chip_address
        self.chip_id = chip_address
        if self.broadcast:
            self.chip_id += 0x8
        self.chip_id_bitarray = register_utils.bitarray_from_value(value=self.chip_id, size=4, fmt='I')
        logging.info('Setting chip address to %d (broadcast bit %s)', self.chip_address, 'set' if self.broadcast else 'not set')

    def init_fe_type(self, fe_type):
        self.flavor = None
        self.global_registers = {}
        self.pixel_registers = {}
        self.calibration_parameters = OrderedDict()
        self.miscellaneous = OrderedDict()
        self.commands = {}
        fei4_defines = import_module('pybar.fei4.fei4_defines')
        fe_type = getattr(fei4_defines, fe_type)
        if 'flavor' not in fe_type:
            raise ValueError('FEI4 flavor not defined')
        elif fe_type['flavor'] not in flavors:
            raise ValueError('Unknown FEI4 flavor: %s' % fe_type['flavor'])
        else:
            self.flavor = fe_type['flavor']
            logging.info('Initializing FEI4 registers (flavor: %s)', self.flavor)
        for name, reg in fe_type['global_registers'].iteritems():
            address = reg.get('address')
            offset = reg.get('offset', 0)
            bitlength = reg.get('bitlength')
            addresses = range(address, address + (offset + bitlength + 16 - 1) / 16)
            littleendian = reg.get('littleendian', False)
            register_littleendian = reg.get('register_littleendian', False)
            value = reg.get('value', 0)
            if not 0 <= value < 2 ** bitlength:
                raise ValueError("Global register %s: value exceeds limits" % (name,))
            readonly = reg.get('readonly', False)
            description = reg.get('description', '')
            self.global_registers[name] = dict(name=name, address=address, offset=offset, bitlength=bitlength, addresses=addresses, littleendian=littleendian, register_littleendian=register_littleendian, value=value, readonly=readonly, description=description)
        for name, reg in fe_type['pixel_registers'].iteritems():
            pxstrobe = reg.get('pxstrobe')
            bitlength = reg.get('bitlength')
            if bitlength > 8:
                raise Exception('Pixel register %s: up to 8 bits supported' % (name,))  # numpy array dtype is uint8
            littleendian = reg.get('littleendian', False)
            if not 0 <= reg.get('value', 0) < 2 ** bitlength:
                raise ValueError("Global register %s: value exceeds limits" % (name,))
            value = np.full((80, 336), reg.get('value', 0), dtype=np.uint8)
            description = reg.get('description', '')
            self.pixel_registers[name] = dict(name=name, pxstrobe=pxstrobe, bitlength=bitlength, littleendian=littleendian, value=value, description=description)
        for name, command in fe_type['commands'].iteritems():
            bitlength = command.get('bitlength')
            description = command.get('description', '')
            if 'bitstream' in command:
                bitstream = command.get('bitstream')
                self.commands[name] = dict(name=name, bitstream=bitstream, bitlength=bitlength, description=description)
            else:
                self.commands[name] = dict(name=name, bitlength=bitlength, description=description)
        self.calibration_parameters = fe_type['calibration_parameters'].copy()

    def is_chip_flavor(self, chip_flavor):
        if chip_flavor in flavors:
            if chip_flavor == self.flavor:
                return True
            else:
                return False
        else:
            raise ValueError('Unknown FEI4 flavor: %s' % chip_flavor)

    @property
    def chip_flavor(self):
        return self.flavor

    @property
    def fei4a(self):
        return True if self.flavor == 'fei4a' else False

    @property
    def fei4b(self):
        return True if self.flavor == 'fei4b' else False

    def load_configuration(self, configuration_file):
        '''Loading configuration

        Parameters
        ----------
        configuration_file : string
            Path to the configuration file (text or HDF5 file).
        '''
        if os.path.isfile(configuration_file):
            if not isinstance(configuration_file, tb.file.File) and os.path.splitext(configuration_file)[1].strip().lower() != ".h5":
                register_utils.load_configuration_from_text_file(self, configuration_file)
            else:
                register_utils.load_configuration_from_hdf5(self, configuration_file)
        else:
            raise ValueError('Cannot find configuration file specified: %s' % configuration_file)

    def save_configuration(self, configuration_file):
        '''Saving configuration

        Parameters
        ----------
        configuration_file : string
            Filename of the configuration file.
        '''
        if not isinstance(configuration_file, tb.file.File) and os.path.splitext(configuration_file)[1].strip().lower() != ".h5":
            return register_utils.save_configuration_to_text_file(self, configuration_file)
        else:
            return register_utils.save_configuration_to_hdf5(self, configuration_file)

    '''
    TODO:
    for the following functions use
    filter(function, iterable).

    Make new generic function that uses filter.

    Use next(iterator[, default]).
    '''

    def set_global_register_value(self, name, value):
        if self.global_registers[name]['readonly']:
            raise ValueError('Global register %s: register is read-only' % name)
        value = long(str(value), 0)  # value is decimal string or number or BitVector
        if not 0 <= value < 2 ** self.global_registers[name]['bitlength']:
            raise ValueError('Global register %s: value exceeds limits' % name)
        self.global_registers[name]['value'] = value

    def get_global_register_value(self, name):
        return self.global_registers[name]['value']

    def set_pixel_register_value(self, name, value):
        try:  # value is decimal string or number or array
            self.pixel_registers[name]['value'][:, :] = value
        except ValueError:  # value is path to pixel config
            if self.pixel_registers[name]['bitlength'] == 1:  # pixel mask
                if value[0] == "~" or value[0] == "!":
                    reg_value = register_utils.parse_pixel_mask_config(os.path.join(os.path.dirname(self.configuration_file), os.path.normpath(value[1:].replace('\\', '/'))))
                    inverted_mask = np.ones(shape=(80, 336), dtype=np.dtype('>u1'))
                    inverted_mask[reg_value >= 1] = 0
                    self.pixel_registers[name]['value'][:, :] = inverted_mask
                else:
                    self.pixel_registers[name]['value'][:, :] = register_utils.parse_pixel_mask_config(os.path.join(os.path.dirname(self.configuration_file), os.path.normpath(value).replace('\\', '/')))
            else:  # pixel dac
                self.pixel_registers[name]['value'][:, :] = register_utils.parse_pixel_dac_config(os.path.join(os.path.dirname(self.configuration_file), os.path.normpath(value).replace('\\', '/')))
        if (self.pixel_registers[name]['value'] >= 2 ** self.pixel_registers[name]['bitlength']).any() or (self.pixel_registers[name]['value'] < 0).any():
            raise ValueError("Pixel register %s: value exceeds limits" % name)

    def get_pixel_register_value(self, name):
        return self.pixel_registers[name]['value'].copy()

    def get_commands(self, command_name, **kwargs):
        """get fe_command from command name and keyword arguments

        wrapper for build_commands()
        implements FEI4 specific behavior

        """
        chip_id = kwargs.pop("ChipID", self.chip_id_bitarray)
        commands = []
        if command_name == "zeros":
            bv = bitarray(endian='little')
            if "length" in kwargs:
                bv += bitarray(kwargs["length"], endian='little')  # initialized from int, bits may be random
            elif kwargs:
                raise ValueError("Unknown parameter(s): %s" % ", ".join(kwargs.iterkeys()))
            bv.setall(0)  # all bits to zero
            commands.append(bv)
        elif command_name == "ones":
            bv = bitarray(endian='little')
            if "length" in kwargs:
                bv += bitarray(kwargs["length"], endian='little')  # initialized from int, bits may be random
            elif kwargs:
                raise ValueError("Unknown parameter(s): %s" % ", ".join(kwargs.iterkeys()))
            bv.setall(1)  # all bits to one
            commands.append(bv)
        elif command_name == "WrRegister":
            register_addresses = self.get_global_register_attributes("addresses", **kwargs)
            register_bitsets = self.get_global_register_bitsets(register_addresses)
            commands.extend([self.build_command(command_name, Address=register_address, GlobalData=register_bitset, ChipID=chip_id, **kwargs) for register_address, register_bitset in zip(register_addresses, register_bitsets)])
        elif command_name == "RdRegister":
            register_addresses = self.get_global_register_attributes('addresses', **kwargs)
            commands.extend([self.build_command(command_name, Address=register_address, ChipID=chip_id) for register_address in register_addresses])
        elif command_name == "WrFrontEnd":
            registers = ["S0", "S1", "SR_Clr", "CalEn", "DIGHITIN_SEL", "GateHitOr", "ReadErrorReq", "StopClkPulse", "SR_Clock", "Efuse_Sense", "HITLD_IN", "Colpr_Mode", "Colpr_Addr"]
            if self.fei4a:
                registers.append("ReadSkipped")
            elif self.fei4b:
                registers.append("SR_Read")
            self.create_restore_point()
            dcs = kwargs.pop("dcs", range(40))  # set the double columns to latch
            # in case of empty list
            if not dcs:
                dcs = range(40)
            joint_write = kwargs.pop("joint_write", False)
            same_mask_for_all_dc = kwargs.pop("same_mask_for_all_dc", False)
            register_objects = self.get_pixel_register_objects(do_sort=['pxstrobe'], **kwargs)
            self.set_global_register_value("S0", 0)
            self.set_global_register_value("S1", 0)
            self.set_global_register_value("SR_Clr", 0)
            self.set_global_register_value("CalEn", 0)
            self.set_global_register_value("DIGHITIN_SEL", 0)
            self.set_global_register_value("GateHitOr", 0)
            self.set_global_register_value("ReadErrorReq", 0)
            self.set_global_register_value("StopClkPulse", 0)
            self.set_global_register_value("SR_Clock", 0)
            self.set_global_register_value("Efuse_Sense", 0)
            self.set_global_register_value("HITLD_IN", 0)
            self.set_global_register_value("Colpr_Mode", 3 if same_mask_for_all_dc else 0)  # write only the addressed double-column
            self.set_global_register_value("Colpr_Addr", 0)
            if self.fei4a:
                self.set_global_register_value("ReadSkipped", 0)
            elif self.fei4b:
                self.set_global_register_value("SR_Read", 0)
            commands.extend(self.get_commands("WrRegister", name=registers))
            if joint_write:
                pxstrobes = 0
                first_read = True
                do_latch = False
                for register_object in register_objects:
                    if register_object['bitlength'] != 1:
                        raise ValueError('Pixel register %s: joint write not supported for pixel DACs' % register_object['name'])
                    pxstrobe = register_object['pxstrobe']
                    if not isinstance(pxstrobe, basestring):
                        do_latch = True
                        pxstrobes += 2 ** register_object['pxstrobe']
                    if first_read:
                        pixel_reg_value = register_object['value']
                        first_read = False
                    else:
                        if np.array_equal(pixel_reg_value, register_object['value']):
                            pixel_reg_value = register_object['value']
                        else:
                            raise ValueError('Pixel register %s: joint write not supported, pixel register values must be equal' % register_object['name'])
                if do_latch:
                    self.set_global_register_value("Latch_En", 1)
                else:
                    self.set_global_register_value("Latch_En", 0)
                self.set_global_register_value("Pixel_Strobes", pxstrobes)
                commands.extend(self.get_commands("WrRegister", name=["Pixel_Strobes", "Latch_En"]))
                for dc_no in (dcs[:1] if same_mask_for_all_dc else dcs):
                    self.set_global_register_value("Colpr_Addr", dc_no)
                    commands.extend(self.get_commands("WrRegister", name=["Colpr_Addr"]))
                    register_bitset = self.get_pixel_register_bitset(register_objects[0], 0, dc_no)
                    commands.extend([self.build_command(command_name, PixelData=register_bitset, ChipID=chip_id, **kwargs)])
                    if do_latch:
                        commands.extend(self.get_commands("GlobalPulse", Width=0))
            else:
                for register_object in register_objects:
                    pxstrobe = register_object['pxstrobe']
                    if isinstance(pxstrobe, basestring):
                        do_latch = False
                        self.set_global_register_value("Pixel_Strobes", 0)  # no latch
                        self.set_global_register_value("Latch_En", 0)
                        commands.extend(self.get_commands("WrRegister", name=["Pixel_Strobes", "Latch_En"]))
                    else:
                        do_latch = True
                        self.set_global_register_value("Latch_En", 1)
                        commands.extend(self.get_commands("WrRegister", name=["Latch_En"]))
                    bitlength = register_object['bitlength']
                    for bit_no, pxstrobe_bit_no in (enumerate(range(bitlength)) if (register_object['littleendian'] is False) else enumerate(reversed(range(bitlength)))):
                        if do_latch:
                            self.set_global_register_value("Pixel_Strobes", 2 ** (pxstrobe + bit_no))
                            commands.extend(self.get_commands("WrRegister", name=["Pixel_Strobes"]))
                        for dc_no in (dcs[:1] if same_mask_for_all_dc else dcs):
                            self.set_global_register_value("Colpr_Addr", dc_no)
                            commands.extend(self.get_commands("WrRegister", name=["Colpr_Addr"]))
                            register_bitset = self.get_pixel_register_bitset(register_object, pxstrobe_bit_no, dc_no)
                            commands.extend([self.build_command(command_name, PixelData=register_bitset, ChipID=chip_id, **kwargs)])
                            if do_latch:
                                commands.extend(self.get_commands("GlobalPulse", Width=0))
            self.restore(pixel_register=False)
            commands.extend(self.get_commands("WrRegister", name=registers))
        elif command_name == "RdFrontEnd":
            registers = ["Conf_AddrEnable", "S0", "S1", "SR_Clr", "CalEn", "DIGHITIN_SEL", "GateHitOr", "ReadErrorReq", "StopClkPulse", "SR_Clock", "Efuse_Sense", "HITLD_IN", "Colpr_Mode", "Colpr_Addr", "Pixel_Strobes", "Latch_En"]
            if self.fei4a:
                registers.append("ReadSkipped")
            elif self.fei4b:
                registers.append("SR_Read")
            self.create_restore_point()
            dcs = kwargs.pop("dcs", range(40))  # set the double columns to latch
            # in case of empty list
            if not dcs:
                dcs = range(40)
            register_objects = self.get_pixel_register_objects(**kwargs)
            self.set_global_register_value('Conf_AddrEnable', 1)
            self.set_global_register_value("S0", 0)
            self.set_global_register_value("S1", 0)
            self.set_global_register_value("SR_Clr", 0)
            if self.fei4b:
                self.set_global_register_value("SR_Read", 0)
            self.set_global_register_value("CalEn", 0)
            self.set_global_register_value("DIGHITIN_SEL", 0)
            self.set_global_register_value("GateHitOr", 0)
            if self.fei4a:
                self.set_global_register_value("ReadSkipped", 0)
            self.set_global_register_value("ReadErrorReq", 0)
            self.set_global_register_value("StopClkPulse", 0)
            self.set_global_register_value("SR_Clock", 0)
            self.set_global_register_value("Efuse_Sense", 0)
            self.set_global_register_value("HITLD_IN", 0)
            self.set_global_register_value("Colpr_Mode", 0)  # write only the addressed double-column
            self.set_global_register_value("Colpr_Addr", 0)
            self.set_global_register_value("Latch_En", 0)
            self.set_global_register_value("Pixel_Strobes", 0)
            commands.extend(self.get_commands("WrRegister", name=registers))
            for index, register_object in enumerate(register_objects):  # make sure that EnableDigInj is first read back, because it is not latched
                if register_object['name'] == 'EnableDigInj':
                    register_objects[0], register_objects[index] = register_objects[index], register_objects[0]
                    break
            for register_object in register_objects:
                pxstrobe = register_object['pxstrobe']
                bitlength = register_object['bitlength']
                for pxstrobe_bit_no in range(bitlength):
                    logging.debug('Pixel Register %s Bit %d', register_object['name'], pxstrobe_bit_no)
                    do_latch = True
                    try:
                        self.set_global_register_value("Pixel_Strobes", 2 ** (pxstrobe + pxstrobe_bit_no))
                    except TypeError:  # thrown for not latched digInjection
                        self.set_global_register_value("Pixel_Strobes", 0)  # do not latch
                        do_latch = False
                    commands.extend(self.get_commands("WrRegister", name=["Pixel_Strobes"]))
                    for dc_no in dcs:
                        self.set_global_register_value("Colpr_Addr", dc_no)
                        commands.extend(self.get_commands("WrRegister", name=["Colpr_Addr"]))
                        if do_latch is True:
                            self.set_global_register_value("S0", 1)
                            self.set_global_register_value("S1", 1)
                            self.set_global_register_value("SR_Clock", 1)
                            commands.extend(self.get_commands("WrRegister", name=["S0", "S1", "SR_Clock"]))
                            commands.extend(self.get_commands("GlobalPulse", Width=0))
                        self.set_global_register_value("S0", 0)
                        self.set_global_register_value("S1", 0)
                        self.set_global_register_value("SR_Clock", 0)
                        commands.extend(self.get_commands("WrRegister", name=["S0", "S1", "SR_Clock"]))
                        register_bitset = self.get_pixel_register_bitset(register_object, pxstrobe_bit_no if (register_object['littleendian'] is False) else register_object['bitlength'] - pxstrobe_bit_no - 1, dc_no)
                        if self.fei4b:
                            self.set_global_register_value("SR_Read", 1)
                            commands.extend(self.get_commands("WrRegister", name=["SR_Read"]))
                        commands.extend([self.build_command("WrFrontEnd", PixelData=register_bitset, ChipID=chip_id)])
                        if self.fei4b:
                            self.set_global_register_value("SR_Read", 0)
                            commands.extend(self.get_commands("WrRegister", name=["SR_Read"]))
            self.restore(pixel_register=False)
            commands.extend(self.get_commands("WrRegister", name=registers))
        else:
            commands.append(self.build_command(command_name, ChipID=chip_id, **kwargs))
        return commands

    def build_command(self, command_name, **kwargs):
        """build command from command_name and keyword values

        Returns
        -------
        command_bitvector : list
            List of bitarrays.

        Usage
        -----
        Receives: command name as defined inside xml file, key-value-pairs as defined inside bit stream filed for each command
        """
#         command_name = command_name.lower()
        command_bitvector = bitarray(0, endian='little')
        if command_name not in self.commands:
            raise ValueError('Unknown command %s' % command_name)
        command_object = self.commands[command_name]
        command_parts = re.split(r'\s*[+]\s*', command_object['bitstream'])
        # for index, part in enumerate(command_parts, start = 1): # loop over command parts
        for part in command_parts:  # loop over command parts
            try:
                command_part_object = self.commands[part]
            except KeyError:
                command_part_object = None
            if command_part_object and 'bitstream'in command_part_object:  # command parts of defined content and length, e.g. Slow, ...
                if string_is_binary(command_part_object['bitstream']):
                    command_bitvector += bitarray(command_part_object['bitstream'], endian='little')
                else:
                    command_bitvector += self.build_command(part, **kwargs)
            elif command_part_object:  # Command parts with any content of defined length, e.g. ChipID, Address, ...
                if part in kwargs:
                    value = kwargs[part]
                else:
                    raise ValueError('Value of command part %s not given' % part)
                try:
                    command_bitvector += value
                except TypeError:  # value is no bitarray
                    if string_is_binary(value):
                        value = int(value, 2)
                    try:
                        command_bitvector += register_utils.bitarray_from_value(value=int(value), size=command_part_object['bitlength'], fmt='I')
                    except:
                        raise TypeError("Type of value not supported")
            elif string_is_binary(part):
                command_bitvector += bitarray(part, endian='little')
            # elif part in kwargs.keys():
            #    command_bitvector += kwargs[command_name]
            else:
                raise ValueError("Cannot process command part %s" % part)
        if command_bitvector.length() != command_object['bitlength']:
            raise ValueError("Command has unexpected length")
        if command_bitvector.length() == 0:
            raise ValueError("Command has length 0")
        return command_bitvector

    def get_global_register_attributes(self, register_attribute, do_sort=True, **kwargs):
        """Calculating register numbers from register names.

        Usage: get_global_register_attributes("attribute_name", name = [regname_1, regname_2, ...], addresses = 2)
        Receives: attribute name to be returned, dictionaries (kwargs) of register attributes and values for making cuts
        Returns: list of attribute values that matches dictionaries of attributes

        """
        # speed up of the most often used keyword name
        try:
            names = iterable(kwargs.pop('name'))
        except KeyError:
            register_attribute_list = []
        else:
            register_attribute_list = [self.global_registers[reg][register_attribute] for reg in names]
        for keyword in kwargs.keys():
            allowed_values = iterable(kwargs[keyword])
            try:
                register_attribute_list.extend(map(itemgetter(register_attribute), filter(lambda global_register: set(iterable(global_register[keyword])).intersection(allowed_values), self.global_registers.itervalues())))
            except AttributeError:
                pass
        if not register_attribute_list and filter(None, kwargs.itervalues()):
            raise ValueError('Global register attribute %s empty' % register_attribute)
        if do_sort:
            return sorted(set(flatten_iterable(register_attribute_list)))
        else:
            return flatten_iterable(register_attribute_list)

    def get_global_register_objects(self, do_sort=None, reverse=False, **kwargs):
        """Generate register objects (list) from register name list

        Usage: get_global_register_objects(name = ["Amp2Vbn", "GateHitOr", "DisableColumnCnfg"], address = [2, 3])
        Receives: keyword lists of register names, addresses,... for making cuts
        Returns: list of register objects

        """
        # speed up of the most often used keyword name
        try:
            names = iterable(kwargs.pop('name'))
        except KeyError:
            register_objects = []
        else:
            register_objects = [self.global_registers[reg] for reg in names]
        for keyword in kwargs.iterkeys():
            allowed_values = iterable(kwargs[keyword])
            register_objects.extend(filter(lambda global_register: set(iterable(global_register[keyword])).intersection(allowed_values), self.global_registers.itervalues()))
        if not register_objects and filter(None, kwargs.itervalues()):
            raise ValueError('Global register objects empty')
        if do_sort:
            return sorted(register_objects, key=itemgetter(*do_sort), reverse=reverse)
        else:
            return register_objects

    def get_global_register_bitsets(self, register_addresses):  # TOTO: add sorting
        """Calculating register bitsets from register addresses.

        Usage: get_global_register_bitsets([regaddress_1, regaddress_2, ...])
        Receives: list of register addresses
        Returns: list of register bitsets

        """
        register_bitsets = []
        for register_address in register_addresses:
            register_objects = self.get_global_register_objects(addresses=register_address)
            register_bitset = bitarray(16, endian='little')  # TODO remove hardcoded register size, see also below
            register_bitset.setall(0)
            register_littleendian = False
            for register_object in register_objects:
                if register_object['register_littleendian']:  # check for register endianness
                    register_littleendian = True
                if (16 * register_object['address'] + register_object['offset'] < 16 * (register_address + 1) and 16 * register_object['address'] + register_object['offset'] + register_object['bitlength'] > 16 * register_address):
                    reg = register_utils.bitarray_from_value(value=register_object['value'], size=register_object['bitlength'])
                    if register_object['littleendian']:
                        reg.reverse()
# register_bitset[max(0, 16 * (register_object['address'] - register_address) + register_object['offset']):min(16, 16 * (register_object['address'] - register_address) + register_object['offset'] + register_object['bitlength'])] |= reg[max(0, 16 * (register_address - register_object['address']) - register_object['offset']):min(register_object['bitlength'], 16 * (register_address - register_object['address'] + 1) - register_object['offset'])]  # [ bit(n) bit(n-1)... bit(0) ]
                    register_bitset[max(0, 16 - 16 * (register_object['address'] - register_address) - register_object['offset'] - register_object['bitlength']):min(16, 16 - 16 * (register_object['address'] - register_address) - register_object['offset'])] |= reg[max(0, register_object['bitlength'] - 16 - 16 * (register_address - register_object['address']) + register_object['offset']):min(register_object['bitlength'], register_object['bitlength'] + 16 - 16 * (register_address - register_object['address'] + 1) + register_object['offset'])]  # [ bit(0)... bit(n-1) bit(n) ]
                else:
                    raise Exception("wrong register object")
            if register_littleendian:
                register_bitset.reverse()
            register_bitsets.append(register_bitset)
        return register_bitsets

    def get_pixel_register_objects(self, do_sort=None, reverse=False, **kwargs):
        """Generate register objects (list) from register name list

        Usage: get_pixel_register_objects(name = ["TDAC", "FDAC"])
        Receives: keyword lists of register names, addresses,...
        Returns: list of register objects

        """
        # speed up of the most often used keyword name
        try:
            names = iterable(kwargs.pop('name'))
        except KeyError:
            register_objects = []
        else:
            register_objects = [self.pixel_registers[reg] for reg in names]
        for keyword in kwargs.iterkeys():
            allowed_values = iterable(kwargs[keyword])
            register_objects.extend(filter(lambda pixel_register: pixel_register[keyword] in allowed_values, self.pixel_registers.itervalues()))
        if not register_objects and filter(None, kwargs.itervalues()):
            raise ValueError('Pixel register objects empty')
        if do_sort:
            return sorted(register_objects, key=itemgetter(*do_sort), reverse=reverse)
        else:
            return register_objects

    def get_pixel_register_bitset(self, register_object, bit_no, dc_no):
        """Calculating pixel register bitsets from pixel register addresses.

        Usage: get_pixel_register_bitset(object, bit_number, double_column_number)
        Receives: register object, bit number, double column number
        Returns: double column bitset

        """
        if not 0 <= dc_no < 40:
            raise ValueError("Pixel register %s: DC out of range" % register_object['name'])
        if not 0 <= bit_no < register_object['bitlength']:
            raise ValueError("Pixel register %s: bit number out of range" % register_object['name'])
        col0 = register_object['value'][dc_no * 2, :]
        sel0 = (2 ** bit_no == (col0 & 2 ** bit_no))
        bv0 = bitarray(sel0.tolist(), endian='little')
        col1 = register_object['value'][dc_no * 2 + 1, :]
        sel1 = (2 ** bit_no == (col1 & 2 ** bit_no))
        # sel1 = sel1.astype(numpy.uint8) # copy of array
        # sel1 = sel1.view(dtype=np.uint8) # in-place type conversion
        bv1 = bitarray(sel1.tolist(), endian='little')
        bv1.reverse()  # shifted first
        # bv = bv1+bv0
        return bv1 + bv0

    @contextmanager
    def restored(self, name=None):
        self.create_restore_point(name)
        try:
            yield
        finally:
            self.restore()

    def create_restore_point(self, name=None):
        '''Creating a configuration restore point.

        Parameters
        ----------
        name : str
            Name of the restore point. If not given, a md5 hash will be generated.
        '''
        if name is None:
            for i in iter(int, 1):
                name = datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f') + '_' + str(i)
                try:
                    self.config_state[name]
                except KeyError:
                    break
                else:
                    pass
        if name in self.config_state:
            raise ValueError('Restore point %s already exists' % name)
        self.config_state[name] = (copy.deepcopy(self.global_registers), copy.deepcopy(self.pixel_registers))

    def restore(self, name=None, keep=False, last=True, global_register=True, pixel_register=True):
        '''Restoring a configuration restore point.

        Parameters
        ----------
        name : str
            Name of the restore point. If not given, a md5 hash will be generated.
        keep : bool
            Keeping restore point for later use.
        last : bool
            If name is not given, the latest restore point will be taken.
        global_register : bool
            Restore global register.
        pixel_register : bool
            Restore pixel register.
        '''
        if name is None:
            if keep:
                name = next(reversed(self.config_state)) if last else next(iter(self.config_state))
                value = self.config_state[name]
            else:
                name, value = self.config_state.popitem(last=last)
        else:
            value = self.config_state[name]
            if not keep:
                value = copy.deepcopy(value)  # make a copy before deleting object
                del self.config_state[name]

        if global_register:
            self.global_registers = copy.deepcopy(value[0])
        if pixel_register:
            self.pixel_registers = copy.deepcopy(value[1])

    def clear_restore_points(self, name=None):
        '''Deleting all/a configuration restore points/point.

        Parameters
        ----------
        name : str
            Name of the restore point to be deleted. If not given, all restore points will be deleted.
        '''
        if name is None:
            self.config_state.clear()
        else:
            del self.config_state[name]

    @property
    def can_restore(self):
        '''Any restore point existing?

        Parameters
        ----------
        none

        Returns
        -------
        True if restore points are existing, else false.
        '''
        if self.config_state:
            return True
        else:
            return False

#     def has_changed(self, name=None, last=True):
#         '''Compare existing restore point to current configuration.
#
#         Parameters
#         ----------
#         name : str
#             Name of the restore point. If name is not given, the first/last restore point will be taken depending on last.
#         last : bool
#             If name is not given, the latest restore point will be taken.
#
#         Returns
#         -------
#         True if configuration is identical, else false.
#         '''
#         if name is None:
#             key = next(reversed(self.config_state) if last else iter(self.config_state))
#             global_registers, pixel_registers = self.config_state[key]
#         else:
#             global_registers, pixel_registers = self.config_state[name]
#         md5_state = hashlib.md5()
#         md5_state.update(global_registers)
#         md5_state.update(pixel_registers)
#         md5_curr = hashlib.md5()
#         md5_curr.update(self.global_registers)
#         md5_curr.update(self.pixel_registers)
#         if md5_state.digest() != md5_curr.digest():
#             return False
#         else:
#             return True
