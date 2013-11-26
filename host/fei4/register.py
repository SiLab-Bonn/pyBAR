#import BitVector  # note: bitarray, bitstring, BitVector are packages with similar functionality
from bitarray import bitarray
import xml.sax
import re
import os
import numpy as np
import itertools
from collections import OrderedDict
import hashlib
import copy
import struct

from utils.utils import string_is_binary, flatten_iterable, iterable, str2bool


def bitarray_from_value(value, size=None, fmt='Q'):
    ba = bitarray(endian='little')
    ba.frombytes(struct.pack(fmt, value))
    if size is not None:
        ba = ba[:size]
    ba.reverse()
    return ba


class FEI4GlobalRegister(object):
    '''Object with named attributes

    '''
    def __init__(self, name, address=0, offset=0, bitlength=0, littleendian=False, register_littleendian=False, value=0, readonly=False, description=""):
        self.name = str(name).lower()
        self.full_name = str(name)
        self.address = int(address)  # int() defaults to base 10 when base is not set
        self.offset = int(offset)
        self.bitlength = int(bitlength)
        self.addresses = range(self.address, self.address + (self.offset + self.bitlength + 16 - 1) / 16)
        self.littleendian = str2bool(littleendian)
        self.register_littleendian = str2bool(register_littleendian)
        self.value = long(str(value), 0)  # value is decimal string or number or BitVector
        if self.value >= 2 ** self.bitlength or self.value < 0:
            raise Exception("Value exceeds limits")
        self.readonly = str2bool(readonly)
        self.description = str(description)
        self.not_set = True

    def __repr__(self):
        return repr((self.name,
                     self.full_name,
                     self.address,
                     self.offset,
                     self.bitlength,
                     self.addresses,
                     self.littleendian,
                     self.register_littleendian,
                     self.value,
                     self.readonly,
                     self.description,
                     self.not_set))

    def __add__(self, other):
        """add: self + other

        """
        # other is FEI4GlobalRegister
        try:
            return bitarray_from_value(value=self.value, size=self.bitlength) + bitarray_from_value(value=other.value, size=other.bitlength)
        except TypeError:
            # other is bitarray.bitarray
            try:
                return bitarray_from_value(value=self.value, size=self.bitlength) + other
            except TypeError:
                # other is bit string
                try:
                    return bitarray_from_value(value=self.value, size=self.bitlength) + bitarray(other, endian='little')
                except:
                    raise Exception('Do not know how to add')

    def __radd__(self, other):
        """Reverse add: other + self

        """
        # other is FEI4GlobalRegister
        try:
            return bitarray_from_value(value=other.value, size=other.bitlength) + bitarray_from_value(value=self.value, size=self.bitlength)
        except TypeError:
            # other is bitarray.bitarray
            try:
                return other + bitarray_from_value(value=self.value, size=self.bitlength)
            except TypeError:
                # other is bit string
                try:
                    return bitarray(other, endian='little') + bitarray_from_value(value=self.value, size=self.bitlength)
                except:
                    raise Exception('Do not know how to radd')

    # rich comparison:
    def __eq__(self, other):
        if (self.address * 16 + self.offset == other.address * 16 + other.offset):
            return True
        else:
            return False

    def __ne__(self, other):
        if (self.address * 16 + self.offset != other.address * 16 + other.offset):
            return True
        else:
            return False

    def __cmp__(self, other):
        if (other.address * 16 + other.offset < self.address * 16 + self.offset):
            return (self.address * 16 + self.offset) - (other.address * 16 + other.offset)
        elif (self.address * 16 + self.offset < other.address * 16 + other.offset):
            return (self.address * 16 + self.offset) - (other.address * 16 + other.offset)
        else:
            return 0


class FEI4PixelRegister(object):
    def __init__(self, name, pxstrobe=0, bitlength=0, littleendian=False, value=0, description=""):
        self.name = str(name).lower()
        self.full_name = str(name)
        try:
            self.pxstrobe = int(pxstrobe)
        except ValueError:
            self.pxstrobe = str(pxstrobe)  # writing into SR, no latch
            # raise
        self.bitlength = int(bitlength)
        if self.bitlength > 8:
            raise Exception(name + "max. uint8 supported")  # numpy array dtype is uint8
        self.littleendian = str2bool(littleendian)
        dimension = (80, 336)
        self.value = np.zeros(dimension, dtype=np.uint8)
        try:  # value is decimal string or number or array
            self.value[:, :] = value
            # reg.value.fill(value)
        except ValueError:  # value is path to pixel config
            raise
        finally:
            if (self.value >= 2 ** self.bitlength).any() or (self.value < 0).any():
                raise ValueError('Value exceeds limits')

        self.description = str(description)
        self.not_set = True

    def __repr__(self):
        return repr((self.name,
                     self.full_name,
                     self.pxstrobe,
                     self.bitlength,
                     self.littleendian,
                     self.value,
                     self.description,
                     self.not_set))


class FEI4Command(object):
    def __init__(self, name, bitlength=0, bitstream="", description=""):
        self.name = str(name).lower()
        self.full_name = str(name)
        self.bitlength = int(bitlength)
        self.bitstream = str(bitstream)
        self.description = str(description)

    def __repr__(self):
        return repr((self.name,
                     self.full_name,
                     self.bitlength,
                     self.bitstream,
                     self.description))


class FEI4Handler(xml.sax.ContentHandler):  # TODO separate handlers
    # contains some basic logic need to use within my program such as whether or not this module has been imported or not
    def __init__(self):
        # constructor to call sax constructor
        xml.sax.ContentHandler.__init__(self)
        # reset and assign all temp variables
        self.global_registers = []
        self.pixel_registers = []
        self.fe_command = []

    # this is executed after each element is terminated. elem is the tag element being read
    def startElement(self, name, attrs):
        # process the collected entry
        # import models based on saved values
        if (name == "register"):
            self.global_registers.append(FEI4GlobalRegister(**attrs))
        elif (name == "pixel_register"):
            self.pixel_registers.append(FEI4PixelRegister(**attrs))
        elif (name == "command"):
            self.fe_command.append(FEI4Command(**attrs))


class FEI4Register(object):
    def __init__(self, configuration_file=None, definition_file=None):
        self.global_registers = {}
        self.pixel_registers = {}
        self.fe_command = {}

        self.configuration_file = configuration_file
        self.definition_file = definition_file
        self.chip_id = 8  # This 4-bit field always exists and is the chip ID. The three least significant bits define the chip address and are compared with the geographical address of the chip (selected via wire bonding), while the most significant one, if set, means that the command is broadcasted to all FE chips receiving the data stream.
        self.chip_flavor = None
        self.chip_flavors = ['fei4a', 'fei4b']
        self.config_state = OrderedDict()

        self.load_configuration_file(self.configuration_file)

    def is_chip_flavor(self, chip_flavor):
        chip_flavor = chip_flavor.translate(None, '_-').lower()
        if chip_flavor in self.chip_flavors:
            if chip_flavor == self.chip_flavor:
                return True
            else:
                return False
        else:
            raise ValueError("Can't detect chip flavor")

    @property
    def fei4a(self):
        return True if self.chip_flavor == 'fei4a' else False

    @fei4a.setter
    def fei4a(self, value):
        if value:
            self.chip_flavor = 'fei4a'
        else:
            raise ValueError('unknown flavor')

    @property
    def fei4b(self):
        return True if self.chip_flavor == 'fei4b' else False

    @fei4b.setter
    def fei4b(self, value):
        if value:
            self.chip_flavor = 'fei4b'
        else:
            raise ValueError('unknown flavor')

    def load_configuration_file(self, configuration_file=None):
        if configuration_file is not None:
            self.configuration_file = configuration_file
        if self.configuration_file is not None:
            print "Loading configuration file:", self.configuration_file
            self.parse_chip_parameters()  # get flavor, chip ID
            self.parse_register_config()
            self.parse_chip_config()
        else:
            print "No configuration file specified."

    def save_configuration(self, name):
        '''Saving configuration files to specific location

        Parameters
        ----------
        name : string
            Filename of the configuration file (any file name extension will be ignored).
            Any path can be omitted. If path is not given, path will be taken from loaded configuration file.

        Returns
        -------
        self.configuration_file : string
            Path to the main configuration file.
        '''

        configuration_path, filename = os.path.split(name)
        filename = os.path.splitext(filename)[0].strip()
        if filename == '':
            print "Unknown filename: nothing saved"
            return
        if configuration_path == '':
            if self.configuration_file is not None:
                configuration_path, _ = os.path.split(self.configuration_file)
                configuration_path = os.path.dirname(configuration_path)
                # filename, extension = os.path.splitext(config_file_name)
            else:
                print "Unknown path: nothing saved"
                return
        if os.path.split(configuration_path)[1] == 'configs':
            configuration_path = os.path.split(configuration_path)[0]

        pixel_reg_dict = {}
        for path in ["configs", "tdacs", "fdacs", "masks"]:
            configuration_file_path = os.path.join(configuration_path, path)
            if not os.path.exists(configuration_file_path):
                os.makedirs(configuration_file_path)
            if  path == "configs":
                self.configuration_file = os.path.join(configuration_file_path, filename + ".cfg")
                if os.path.isfile(self.configuration_file):
                    print "Overwriting configuration file:", self.configuration_file
                    os.remove(self.configuration_file)
                else:
                    print "Saving configuration file:", self.configuration_file
                self.write_chip_paramters()
                self.write_chip_config()
            elif path == "tdacs":
                dac = self.get_pixel_register_objects(name="TDAC")[0]
                dac_config_path = os.path.join(configuration_file_path, "_".join([dac.name, filename]) + ".dat")
                self.write_pixel_dac_config(dac_config_path, dac.value)
                pixel_reg_dict[dac.full_name] = dac_config_path
            elif path == "fdacs":
                dac = self.get_pixel_register_objects(name="FDAC")[0]
                dac_config_path = os.path.join(configuration_file_path, "_".join([dac.name, filename]) + ".dat")
                self.write_pixel_dac_config(dac_config_path, dac.value)
                pixel_reg_dict[dac.full_name] = dac_config_path
            elif path == "masks":
                masks = self.get_pixel_register_objects(bitlength=1)
                for mask in masks:
                    dac_config_path = os.path.join(configuration_file_path, "_".join([mask.name, filename]) + ".dat")
                    self.write_pixel_mask_config(dac_config_path, mask.value)
                    pixel_reg_dict[mask.full_name] = dac_config_path

        with open(self.configuration_file, 'a') as f:
            lines = []
            lines.append("# Pixel Registers\n")
            for key in sorted(pixel_reg_dict):
                lines.append('%s %s\n' % (key, pixel_reg_dict[key]))
            lines.append("\n")
            f.writelines(lines)

            lines = []
            lines.append("# Calibration Parameters\n")
            lines.append('C_Inj_Low %f\n' % 0.0)  # TODO:
            lines.append('C_Inj_High %f\n' % 0.0)  # TODO:
            lines.append('Vcal_Coeff_0 %f\n' % 0.0)  # TODO:
            lines.append('Vcal_Coeff_1 %f\n' % 0.0)  # TODO:
            lines.append("\n")
            f.writelines(lines)

        return self.configuration_file

    def parse_register_config(self):
        # print "parse xml"
        parser = xml.sax.make_parser()
        handler = FEI4Handler()
        parser.setContentHandler(handler)

        if self.definition_file is None:
            if self.is_chip_flavor("fei4a"):
                parser.parse("register_fei4a.xml")
            elif self.is_chip_flavor("fei4b"):
                parser.parse("register_fei4b.xml")
            else:
                raise ValueError("No chip flavor assigned")
        else:
            parser.parse(self.definition_file)

        self.global_registers = handler.global_registers
        self.pixel_registers = handler.pixel_registers
        self.fe_command = handler.fe_command
        # pprint.pprint(self.fe_command)
        # pprint.pprint(self.global_registers)
        # pprint.pprint(self.pixel_registers)

    def parse_chip_parameters(self):
        # print "load cfg"
        with open(self.configuration_file, 'r') as f:
            for line in f.readlines():
                key_value = re.split("\s+|[\s]*=[\s]*", line)
                if (key_value[0].lower() == "flavour" or key_value[0].lower() == "flavor" or key_value[0].translate(None, '_-').lower() == "chipflavour" or key_value[0].translate(None, '_-').lower() == "chipflavor"):
                    if key_value[1].translate(None, '_-').lower() == "fei4a":
                        self.chip_flavor = "fei4a"
                    elif key_value[1].translate(None, '_-').lower() == "fei4b":
                        self.chip_flavor = "fei4b"
                    else:
                        raise ValueError("Can't detect chip flavor")

                if key_value[0].translate(None, '_-').lower() == "chipid":
                    if (int(key_value[1]) >= 0 and int(key_value[1]) < 16):
                        self.chip_id = int(key_value[1])
                    else:
                        raise ValueError('Value exceeds limits')
                        self.chip_id = 8  # TODO default to 8

                # if (key_value[0].lower() == "moduleid" or key_value[0].lower() == "module_id"):
                #    pass

            print "Flavor:", self.chip_flavor
            print "Chip ID:", self.chip_id

    def write_chip_paramters(self):
#         lines = []
#         search = ["flavour", "chip-flavour", "chip_flavour", "flavor", "chip-flavor", "chip_flavor", "chipid", "chip-id", "chip_id", "Parameters"]
#         with open(self.configuration_file, 'r') as f:
#             for line in f.readlines():
#                 line_split = line.split()
#                 if not any(x.lower() in line_split.lower() for x in search):
#                     lines.append(line)
        with open(self.configuration_file, 'a') as f:
            lines = []
            lines.append("# Chip Parameters" + "\n")
            lines.append('Flavor %s\n' % self.chip_flavor.upper())
            lines.append('Chip_ID %d\n' % self.chip_id)
            lines.append("\n")
            f.writelines(lines)

    def parse_chip_config(self):
        # print "load cfg"
        all_config_keys = []
        all_config_keys_lower = []
        with open(self.configuration_file, 'r') as f:
            for line in f.readlines():
                key_value = re.split("\s+|[\s]*=[\s]*", line)
                if len(key_value) > 0 and ((len(key_value[0]) > 0 and key_value[0][0] == '#') or key_value[0] == '' or key_value[1] == ''):  # ignore line if empty line or starts with '#'
                    # print key_value
                    continue
                elif (key_value[0].lower() == "flavour" or key_value[0].lower() == "flavor" or key_value[0].translate(None, '_-').lower() == "chipflavour" or key_value[0].translate(None, '_-').lower() == "chipflavor"):
                    continue
                elif key_value[0].translate(None, '_-').lower() == "chipid":
                    continue
                else:
                    self.set_global_register_value(key_value[0], key_value[1], ignore_no_match=True)
                    self.set_pixel_register_value(key_value[0], key_value[1], ignore_no_match=True)

                    all_config_keys.append(key_value[0])
                    all_config_keys_lower.append(key_value[0].lower())

        all_config_keys_dict = dict(zip(all_config_keys_lower, all_config_keys))
        pixel_not_configured = []
        pixel_not_configured.extend([x for x in self.pixel_registers if (x.not_set == True and x.readonly == False)])
        global_not_configured = []
        global_not_configured.extend([x for x in self.global_registers if (x.not_set == True and x.readonly == False)])
        if len(global_not_configured) != 0:
            raise ValueError("Following global register(s) not configured: {}".format(', '.join('\'' + reg.full_name + '\'' for reg in global_not_configured)))
        if len(pixel_not_configured) != 0:
            raise ValueError("Following pixel register(s) not configured: {}".format(', '.join('\'' + reg.full_name + '\'' for reg in pixel_not_configured)))
        all_known_regs = []
        all_known_regs.extend([x.name for x in self.pixel_registers])
        all_known_regs.extend([x.name for x in self.global_registers if x.readonly == False])
        print "Found following unknown register(s): {}".format(', '.join('\'' + all_config_keys_dict[reg] + '\'' for reg in set.difference(set(all_config_keys_dict.iterkeys()), all_known_regs)))

    def write_chip_config(self):
        with open(self.configuration_file, 'a') as f:
            lines = []
            lines.append("# Global Registers\n")
            reg_dict = {register.full_name: register.value for register in self.get_global_register_objects(readonly=False)}
            for key in sorted(reg_dict):
                lines.append('%s %d\n' % (key, reg_dict[key]))
            lines.append("\n")
            f.writelines(lines)

    def parse_pixel_mask_config(self, filename):
        dimension = (80, 336)
        mask = np.empty(dimension, dtype=np.uint8)

        with open(filename, 'r') as f:
            row = 0
            for line in f.readlines():
                line = line.split()
                if len(line) == 0 or line[0][0] == '#':
                    continue
                try:
                    int(line[0])
                except ValueError:
                    line = ''.join(line).translate(None, '_-')
                else:
                    line = ''.join(line[1:]).translate(None, '_-')
                if len(line) != 80:
                    raise ValueError('Dimension of column')
                # for col, value in enumerate(line):
                #    mask[col][row] = value
                mask[:, row] = list(line)
                row += 1
            if row != 336:
                raise ValueError('Dimension of row')
        # print filename, mask
        return mask

    def write_pixel_mask_config(self, filename, value):
        if os.path.isfile(filename):
            print "Overwriting configuration file:", filename
        with open(filename, 'w') as f:
            seq = []
            seq.append("###  1     6     11    16     21    26     31    36     41    46     51    56     61    66     71    76\n")
            seq.append("\n".join([(repr(row + 1).rjust(3) + "  ") + "  ".join(["-".join(["".join([repr(value[col, row]) for col in range(col_fine, col_fine + 5)]) for col_fine in range(col_coarse, col_coarse + 10, 5)]) for col_coarse in range(0, 80, 10)]) for row in range(336)]))
            seq.append("\n")
            f.writelines(seq)

    def parse_pixel_dac_config(self, filename):
        dimension = (80, 336)
        mask = np.empty(dimension, dtype=np.uint8)

        with open(filename, 'r') as f:
            row = 0
            read_line = 0
            for line in f.readlines():
                line = line.split()
                if len(line) == 0 or line[0][0] == '#':
                    continue
                try:
                    int(line[0])
                except ValueError:
                    line = line[1:]
                else:
                    pass  # nothing to do
                if len(line) != 40:
                    raise ValueError('Dimension of column')
                if read_line % 2 == 0:
                    mask[:40, row] = line
                else:
                    mask[40:, row] = line
                    row += 1
                read_line += 1
            if row != 336:
                raise ValueError('Dimension of row')
        # print mask
        return mask

    def write_pixel_dac_config(self, filename, value):
        if os.path.isfile(filename):
            print "Overwriting configuration file:", filename
        with open(filename, 'w') as f:
            seq = []
            seq.append("###    1  2  3  4  5  6  7  8  9 10   11 12 13 14 15 16 17 18 19 20   21 22 23 24 25 26 27 28 29 30   31 32 33 34 35 36 37 38 39 40\n")
            seq.append("###   41 42 43 44 45 46 47 48 49 50   51 52 53 54 55 56 57 58 59 60   61 62 63 64 65 66 67 68 69 70   71 72 73 74 75 76 77 78 79 80\n")
            seq.append("\n".join(["\n".join([((repr(row + 1).rjust(3) + ("a" if col_coarse == 0 else "b") + "  ") + "   ".join([" ".join([repr(value[col, row]).rjust(2) for col in range(col_fine, col_fine + 10)]) for col_fine in range(col_coarse, col_coarse + 40, 10)])) for col_coarse in range(0, 80, 40)]) for row in range(336)]))
            seq.append("\n")
            f.writelines(seq)

    '''
    TODO:
    for the following functions use
    filter(function, iterable).

    Make new generic function that uses filter.

    Use next(iterator[, default]).
    '''

    def set_global_register_value(self, name, value, ignore_no_match=False):
        regs = [x for x in self.global_registers if x.name.lower() == name.lower()]
        if ignore_no_match == False and len(regs) == 0:
            raise ValueError('No matching register found')
        if len(regs) > 1:
            raise ValueError('Found more than one matching register')
        for reg in regs:
            old_value = reg.value
            value = long(str(value), 0)  # value is decimal string or number or BitVector
            if value >= 2 ** reg.bitlength or value < 0:
                raise ValueError('Value exceeds limits')
            reg.value = value
            reg.not_set = False
            return old_value

    def get_global_register_value(self, name):
        regs = [x for x in self.global_registers if x.name.lower() == name.lower()]
        if len(regs) == 0:
            raise ValueError('No matching register found')
        if len(regs) > 1:
            raise ValueError('Found more than one matching register')
        for reg in regs:
            return reg.value

    def set_pixel_register_value(self, name, value, ignore_no_match=False):
        regs = [x for x in self.pixel_registers if x.name.lower() == name.lower()]
        if ignore_no_match == False and len(regs) == 0:
            raise ValueError('No matching register found')
        if len(regs) > 1:
            raise ValueError('Found more than one matching register')
        for reg in regs:
            old_value = reg.value.copy()
            try:  # value is decimal string or number or array
                reg.value[:, :] = value
                # reg.value.fill(value)
            except ValueError:  # value is path to pixel config
                if reg.bitlength == 1:
                    reg.value = self.parse_pixel_mask_config(value)
                else:
                    reg.value = self.parse_pixel_dac_config(value)
            finally:
                if (reg.value >= 2 ** reg.bitlength).any() or (reg.value < 0).any():
                    reg.value = old_value.copy()
                    raise ValueError("Value exceeds limits: " + reg.full_name)
            reg.not_set = False
            return old_value

    def get_pixel_register_value(self, name):
        regs = [x for x in self.pixel_registers if x.name.lower() == name.lower()]
        if len(regs) == 0:
            raise ValueError('No matching register found')
        if len(regs) > 1:
            raise ValueError('Found more than one matching register')
        for reg in regs:
            return reg.value.copy()

    def get_commands(self, command_name, same_mask_for_all_dc=False, **kwargs):
        """get fe_command from command name and keyword arguments

        wrapper for build_commands()
        implements FEI4 specific behavior

        """
        # TODO: fix behavior when register name does not exist
        commands = []

        if command_name.lower() == "zeros":
            if "length" in kwargs:
                bv = bitarray(kwargs["length"], endian='little')  # all bits to zero
            elif "mask_steps" in kwargs:
                def calculate_wait_cycles(mask_steps):
                    return int(336 * 2 / mask_steps ** (1 / 2) * 24 / 4 * 3)  # good practice
                bv = bitarray(calculate_wait_cycles(kwargs["mask_steps"]), endian='little')
            else:
                raise ValueError('Cannot calculate length')
            bv.setall(0)
            commands.append(bv)
        elif command_name.lower() == "ones":
            if "length" in kwargs:
                bv = bitarray(kwargs["length"], endian='little')  # all bits to zero
            elif "mask_steps" in kwargs:
                bv = bitarray(calculate_wait_cycles(kwargs["mask_steps"]), endian='little')
            else:
                raise ValueError('cannot calculate length')
            bv.setall(1)  # all bits to one
            commands.append(bv)
        elif command_name.lower() == "wrregister":
            # print "wrregister"
            register_addresses = self.get_global_register_attributes("addresses", **kwargs)
            register_bitsets = self.get_global_register_bitsets(register_addresses)
            # print register_addresses
            commands.extend([self.build_command(command_name, address=register_address, globaldata=register_bitset, chipid=self.chip_id, **kwargs) for register_address, register_bitset in zip(register_addresses, register_bitsets)])

        elif command_name.lower() == "rdregister":
            # print "rdregister"
            register_addresses = self.get_global_register_attributes('addresses', **kwargs)
            commands.extend([self.build_command(command_name, address=register_address, chipid=self.chip_id) for register_address in register_addresses])

        elif command_name.lower() == "wrfrontend":
            # print "wrfrontend"
            register_objects = self.get_pixel_register_objects(False, **kwargs)
            # pprint.pprint(register_objects)
            self.set_global_register_value("S0", 0)
            self.set_global_register_value("S1", 0)
            self.set_global_register_value("SR_Clr", 0)
            self.set_global_register_value("CalEn", 0)
            self.set_global_register_value("DIGHITIN_SEL", 0)
            self.set_global_register_value("GateHitOr", 0)
            if self.is_chip_flavor('fei4a'):
                self.set_global_register_value("ReadSkipped", 0)
            self.set_global_register_value("ReadErrorReq", 0)
            self.set_global_register_value("StopClkPulse", 0)
            self.set_global_register_value("SR_Clock", 0)
            self.set_global_register_value("Efuse_Sense", 0)

            self.set_global_register_value("HITLD_IN", 0)
            self.set_global_register_value("Colpr_Mode", 3 if same_mask_for_all_dc else 0)  # write only the addressed double-column
            self.set_global_register_value("Colpr_Addr", 0)

            commands.extend(self.get_commands("wrregister", name=["S0", "S1", "SR_Clr", "CalEn", "DIGHITIN_SEL", "GateHitOr", "ReadSkipped", "ReadErrorReq", "StopClkPulse", "SR_Clock", "Efuse_Sense", "HITLD_IN", "Colpr_Mode", "Colpr_Addr"]))
            for register_object in register_objects:
                pxstrobe = register_object.pxstrobe
                bitlength = register_object.bitlength
                for bit_no, pxstrobe_bit_no in (enumerate(range(bitlength)) if (register_object.littleendian == False) else enumerate(reversed(range(bitlength)))):
                    do_latch = True
                    try:
                        self.set_global_register_value("Pixel_Strobes", 2 ** (pxstrobe + bit_no))
#                         print register_object.name
#                         print "reg bit no", pxstrobe_bit_no
#                         print "pxstrobes reg", 2**(pxstrobe+bit_no)

                    except TypeError:
                        self.set_global_register_value("Pixel_Strobes", 0)  # no latch
                        do_latch = False
#                         print register_object.name
#                         print "bit_no", bit_no
#                         print "pxstrobes", 0

                    if do_latch == True:
                        self.set_global_register_value("Latch_En", 1)
                    else:
                        self.set_global_register_value("Latch_En", 0)
                    commands.extend(self.get_commands("wrregister", name=["Pixel_Strobes", "Latch_En"]))
                    for dc_no in range(1 if same_mask_for_all_dc else 40):
                        self.set_global_register_value("Colpr_Addr", dc_no)
                        commands.extend(self.get_commands("wrregister", name=["Colpr_Addr"]))
                        register_bitset = self.get_pixel_register_bitset(register_object, pxstrobe_bit_no, dc_no)
                        # if dc_no == 0: print dc_no, register_bitset
                        # print "dc_no", dc_no
                        # print register_bitset
                        commands.extend([self.build_command(command_name, pixeldata=register_bitset, chipid=self.chip_id, **kwargs)])
                        if do_latch == True:
                            # self.set_global_register_value("Latch_En", 1)
                            # fe_command.extend(self.get_commands("wrregister", name = ["Latch_En"]))
                            commands.extend(self.get_commands("globalpulse", width=0))
                            # self.set_global_register_value("Latch_En", 0)
                            # fe_command.extend(self.get_commands("wrregister", name = ["Latch_En"]))
            self.set_global_register_value("Pixel_Strobes", 0)  # for SEU hardness set to zero
            self.set_global_register_value("Latch_En", 0)
            self.set_global_register_value("Colpr_Mode", 0)
            self.set_global_register_value("Colpr_Addr", 0)
            commands.extend(self.get_commands("wrregister", name=["Pixel_Strobes", "Latch_En", "Colpr_Mode", "Colpr_Addr"]))

        else:
            # print command_name.lower()
            commands.append(self.build_command(command_name, chipid=self.chip_id, **kwargs))
        # pprint.pprint(fe_command)
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
        command_name = command_name.lower()
        command_bitvector = bitarray(0, endian='little')
        try:
            command_object = self.get_command_objects(name=command_name)[0]
        except IndexError:
            command_object = None
        if command_object:
            command_parts = re.split("[\s]*\+[\s]*", command_object.bitstream.lower())
            # for index, part in enumerate(command_parts, start = 1): # loop over command parts
            for part in command_parts:  # loop over command parts
                try:
                    command_part_object = self.get_command_objects(name=part)[0]
                except IndexError:
                    command_part_object = None
                if command_part_object and len(command_part_object.bitstream) != 0:  # command parts of defined content and length, e.g. Slow, ...
                    if string_is_binary(command_part_object.bitstream):
                        command_bitvector += bitarray(command_part_object.bitstream, endian='little')
                    else:
                        command_bitvector += self.build_command(part, **kwargs)
                elif command_part_object and len(command_part_object.bitstream) == 0:  # Command parts with any content of defined length, e.g. ChipID, Address, ...
                    value = None
                    if part in kwargs.keys():
                        value = kwargs[part]
                    try:
                        command_bitvector += value
                    except TypeError:  # value is no bitarray
                        if string_is_binary(value):
                            value = int(value, 2)
                        try:
                            command_bitvector += bitarray_from_value(value=int(value), size=command_part_object.bitlength, fmt='I')
                        except:
                            raise Exception("unknown type")
                elif string_is_binary(part):
                    command_bitvector += bitarray(part, endian='little')
                # elif part in kwargs.keys():
                #    command_bitvector += kwargs[command_name]
            if command_bitvector.length() != command_object.bitlength:
                raise Exception("command has wrong length")
        if command_bitvector.length() == 0:
            raise Exception("unknown command name")
        return command_bitvector

    def add_global_registers(self, x, y):
        """Adding up bitvectors.

        Usage: reduce(self.add_global_registers, [bitvector_1, bitvector_2, ...])
        Receives: list of bitvectors, FEI4GlobalRegister objects
        Returns: single bitvector

        """
        try:
            return x + y
        except AttributeError:
            pass

        try:
            return x + bitarray_from_value(value=y.value, size=y.bitlength, fmt='I')
        except AttributeError:
            pass

    def get_global_register_attributes(self, register_attribute, do_sort=True, **kwargs):
        """Calculating register numbers from register names.

        Usage: get_global_register_attributes("attribute_name", name = [regname_1, regname_2, ...], addresses = 2)
        Receives: attribute name to be returned, dictionaries (kwargs) of register attributes and values for making cuts
        Returns: list of attribute values that matches dictionaries of attributes

        """
        register_attribute_list = []
        for keyword in kwargs.keys():
            # make keyword value list
            import collections

            # make keyword values iterable
            if not isinstance(kwargs[keyword], collections.Iterable):
                kwargs[keyword] = iterable(kwargs[keyword])

            # lowercase letters for string keyword values
            try:
                keyword_values = [x.lower() for x in iterable(kwargs[keyword])]
            except AttributeError:
                keyword_values = kwargs[keyword]
            try:
                register_attribute_list.extend([getattr(x, register_attribute) for x in self.global_registers if set(iterable(getattr(x, keyword))).intersection(keyword_values)])
            except AttributeError:
                pass
        if do_sort:
            return sorted(set(flatten_iterable(register_attribute_list)))
        else:
            return flatten_iterable(register_attribute_list)

    def get_global_register_objects(self, do_sort=True, **kwargs):
        """Generate register objects (list) from register name list

        Usage: get_global_register_objects(name = ["Amp2Vbn", "GateHitOr", "DisableColumnCnfg"], address = [2, 3])
        Receives: keyword lists of register names, addresses,... for making cuts
        Returns: list of register objects

        """
        register_objects = []
        for keyword in kwargs.keys():
            # make keyword value list
            import collections

            # make keyword values iterable
            if not isinstance(kwargs[keyword], collections.Iterable):
                kwargs[keyword] = iterable(kwargs[keyword])

            # lowercase letters for string keyword values
            try:
                keyword_values = [x.lower() for x in iterable(kwargs[keyword])]
            except AttributeError:
                keyword_values = kwargs[keyword]
            try:
                register_objects.extend([x for x in self.global_registers if set(iterable(getattr(x, keyword))).intersection(keyword_values)])  # any(set([False]).intersection([False])) returns False
            except AttributeError:
                pass
        if do_sort:
            return sorted(register_objects)
        else:
            return register_objects

    def get_global_register_bitsets(self, register_addresses, do_sort=True):  # TODO instead of register_names use
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
                if register_object.register_littleendian:  # check for register endianness
                    register_littleendian = True
                if (16 * register_object.address + register_object.offset < 16 * (register_address + 1) and
                    16 * register_object.address + register_object.offset + register_object.bitlength > 16 * register_address):
                    reg = bitarray_from_value(value=register_object.value, size=register_object.bitlength)
                    if register_object.littleendian:
                        reg.reverse()
                    # register_bitset[max(0, 16*(register_object.address-register_address)+register_object.offset):min(16, 16*(register_object.address-register_address)+register_object.offset+register_object.bitlength)] |= reg[max(0, 16*(register_address-register_object.address)-register_object.offset):min(register_object.bitlength,16*(register_address-register_object.address+1)-register_object.offset)] # [ bit(n) bit(n-1)... bit(0) ]
                    register_bitset[max(0, 16 - 16 * (register_object.address - register_address) - register_object.offset - register_object.bitlength):min(16, 16 - 16 * (register_object.address - register_address) - register_object.offset)] |= reg[max(0, register_object.bitlength - 16 - 16 * (register_address - register_object.address) + register_object.offset):min(register_object.bitlength, register_object.bitlength + 16 - 16 * (register_address - register_object.address + 1) + register_object.offset)]  # [ bit(0)... bit(n-1) bit(n) ]
                else:
                    raise Exception("wrong register object")
            if register_littleendian:
                register_bitset.reverse()
            register_bitsets.append(register_bitset)
        return register_bitsets

    def get_command_objects(self, **kwargs):
        """Generate register objects (list) from register name list

        Usage: get_global_register_objects(name = ["Amp2Vbn", "GateHitOr", "DisableColumnCnfg"], address = [2, 3])
        Receives: keyword lists of register names, adresses, ...
        Returns: list of register objects

        """
        command_objects = []
        for keyword in kwargs.keys():
            # make keyword value list
            import collections

            # make keyword values iterable
            if not isinstance(kwargs[keyword], collections.Iterable):
                kwargs[keyword] = iterable(kwargs[keyword])

            # lowercase letters for string keyword values
            try:
                keyword_values = [x.lower() for x in iterable(kwargs[keyword])]
            except AttributeError:
                keyword_values = kwargs[keyword]
            try:
                command_objects.extend([x for x in self.fe_command if set(iterable(getattr(x, keyword))).intersection(keyword_values)])
            except AttributeError:
                pass
        return command_objects

    def get_pixel_register_attributes(self, register_attribute, do_sort=True, **kwargs):
        """Calculating register numbers from register names.

        Usage: get_pixel_register_attributes("attribute_name", name = [regname_1, regname_2, ...], addresses = 2)
        Receives: attribute name to be returned, dictionaries (kwargs) of register attributes and values for making cuts
        Returns: list of attribute values that matches dictionaries of attributes

        """
        register_attribute_list = []
        for keyword in kwargs.keys():
            # make keyword value list
            import collections

            # make keyword values iterable
            if not isinstance(kwargs[keyword], collections.Iterable):
                kwargs[keyword] = iterable(kwargs[keyword])

            # lowercase letters for string keyword values
            try:
                keyword_values = [x.lower() for x in iterable(kwargs[keyword])]
            except AttributeError:
                keyword_values = kwargs[keyword]
            try:
                register_attribute_list.extend([getattr(x, register_attribute) for x in self.pixel_registers if set(iterable(getattr(x, keyword))).intersection(keyword_values)])
            except AttributeError:
                pass
        if do_sort:
            return sorted(set(flatten_iterable(register_attribute_list)))
        else:
            return flatten_iterable(register_attribute_list)

    def get_pixel_register_objects(self, do_sort=True, **kwargs):
        """Generate register objects (list) from register name list

        Usage: get_pixel_register_objects(name = ["TDAC"], address = [2, 3])
        Receives: keyword lists of register names, addresses,... for making cuts
        Returns: list of register objects

        """
        register_objects = []
        for keyword in kwargs.keys():
            keyword_values = iterable(kwargs[keyword])
            try:
                keyword_values = [x.lower() for x in keyword_values]
            except AttributeError:
                pass
            register_objects.extend(itertools.ifilter(lambda pixel_register: set.intersection(set(iterable(getattr(pixel_register, keyword))), keyword_values), self.pixel_registers))
        if do_sort:
            return sorted(register_objects)
        else:
            return register_objects

#        register_objects = []
#        for keyword in kwargs.keys():
#            # make keyword value list
#            import collections
#
#            # make keyword values iterable
#            if not isinstance(kwargs[keyword], collections.Iterable):
#                kwargs[keyword] = iterable(kwargs[keyword])
#
#            # lowercase letters for string keyword values
#            try:
#                keyword_values = [x.lower() for x in iterable(kwargs[keyword])]
#            except AttributeError:
#                keyword_values = kwargs[keyword]
#            try:
#                register_objects.extend([x for x in self.pixel_registers if set(iterable(getattr(x, keyword))).intersection(keyword_values)]) # any(set([False]).intersection([False])) returns False
#            except AttributeError:
#                pass
#        if do_sort:
#            return sorted(register_objects)
#        else:
#            return register_objects

    def get_pixel_register_bitset(self, register_object, bit_no, dc_no):
        """Calculating pixel register bitsets from pixel register addresses.

        Usage: get_pixel_register_bitset(object, bit_number, double_column_number)
        Receives: register object, bit number, double column number
        Returns: double column bitset

        """
        # pprint.pprint(register_object)
        if not (dc_no >= 0 and dc_no < 40):
            raise Exception("wrong DC number")
        if not (bit_no >= 0 and bit_no < register_object.bitlength):
            raise Exception("wrong bit number")
        col0 = register_object.value[dc_no * 2, :]
        sel0 = (2 ** bit_no == (col0 & 2 ** bit_no))
        bv0 = bitarray(sel0.tolist(), endian='little')
        col1 = register_object.value[dc_no * 2 + 1, :]
        sel1 = (2 ** bit_no == (col1 & 2 ** bit_no))
        # sel1 = sel1.astype(numpy.uint8) # copy of array
        # sel1 = sel1.view(dtype=np.uint8) # in-place type conversion
        bv1 = bitarray(sel1.tolist(), endian='little')
        bv1.reverse()  # shifted first
        # bv = bv1+bv0
        # print bv
        # print bv.length()
        return bv1 + bv0

    def create_restore_point(self, name=None):
        '''Creating a configuration restore point.

        Parameters
        ----------
        name : str
            Name of the restore point. If not given, a md5 hash will be generated.
        '''
        md5 = hashlib.md5()
        if name is None:
            md5.update(self.global_registers)
            md5.update(self.pixel_registers)
            name = md5.digest()
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
                key = next(reversed(self.config_state) if last else iter(self.config_state))
                value = self.config_state[key]
            else:
                value = self.config_state.popitem(last=last)
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

    def has_changed(self, name=None, last=True):
        '''Compare existing restore point to current configuration.

        Parameters
        ----------
        name : str
            Name of the restore point. If name is not given, the first/last restore point will be taken depending on last.
        last : bool
            If name is not given, the latest restore point will be taken.

        Returns
        -------
        True if configuration is identical, else false.
        '''
        if name is None:
            key = next(reversed(self.config_state) if last else iter(self.config_state))
            global_registers, pixel_registers = self.config_state[key]
        else:
            global_registers, pixel_registers = self.config_state[name]
        md5_state = hashlib.md5()
        md5_state.update(global_registers)
        md5_state.update(pixel_registers)
        md5_curr = hashlib.md5()
        md5_curr.update(self.global_registers)
        md5_curr.update(self.pixel_registers)
        if md5_state.digest() != md5_curr.digest():
            return False
        else:
            return True
