import logging
import time
import numpy as np
import tables as tb
import re
import ast
import struct
import os
from ast import literal_eval
from operator import itemgetter
import itertools

from bitarray import bitarray

from basil.utils.BitLogic import BitLogic

from pybar.utils.utils import bitarray_to_array
from pybar.daq.readout_utils import interpret_pixel_data
from pybar.daq.fei4_record import FEI4Record


class NameValue(tb.IsDescription):
    name = tb.StringCol(256, pos=0)
    value = tb.StringCol(1024, pos=0)


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
            delay = length * 25e-9 * repeat - 0.002  # subtract 2ms delay
            if delay < 0:
                delay = 0.0
        else:
            delay = None
        if use_timeout:
            if delay is None:
                timeout = 1
            else:
                timeout = 10 * delay
            try:
                msg = "Time out while waiting for sending command becoming ready in %s, module %s. Power cycle or reset readout board!" % (self.dut['CMD'].name, self.dut['CMD'].__class__.__module__)
                if not self.dut['CMD'].wait_for_ready(timeout=timeout, times=None, delay=delay, abort=self.abort) and not self.abort.is_set():
                    raise CmdTimeoutError(msg)
            except RuntimeError:
                raise CmdTimeoutError(msg)
        else:
            if delay:
                try:
                    time.sleep(delay)  # subtract 2ms delay
                except IOError:  # negative value
                    pass
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
        This should be only issues after power up, otherwise the timing (BCID counter) is worse.
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
            self.register.set_global_register_value("Vthin_AltCoarse", altc)  # take every second AltCoarse value
            self.register.set_global_register_value("Vthin_AltFine", altf)  # take low word
        else:
            altf = value & 0xff
            altc = (value >> 8)
            self.register.set_global_register_value("Vthin_AltCoarse", altc)  # take high word
            self.register.set_global_register_value("Vthin_AltFine", altf)  # take low word
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


# Helper functions
def parse_global_config(filename):  # parses the global config text file
    with open(filename, 'r') as f:
        f.seek(0)
        config_dict = {}
        for line in f.readlines():
            line = line.partition('#')[0].strip()
            if not line:
                continue
            parts = re.split(r'\s*[=]\s*|\s+', line)
            key = parts[0].strip()
            if key in config_dict:
                logging.warning('Item %s in configuration file exists more than once', parts[0])
            try:
                config_dict[key] = ast.literal_eval(parts[1].strip())
            except SyntaxError:  # for comma separated values, e.g. lists
                try:
                    config_dict[key] = ast.literal_eval(line[len(parts[0]):].strip())
                except SyntaxError:
                    config_dict[key] = line[len(parts[0]):].strip()
            except ValueError:
                config_dict[key] = parts[1].strip()
    return config_dict


def parse_pixel_mask_config(filename):
    mask = np.empty((80, 336), dtype=np.uint8)
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
    return mask


def write_pixel_mask_config(filename, value):
    with open(filename, 'w') as f:
        seq = []
        seq.append("###  1     6     11    16     21    26     31    36     41    46     51    56     61    66     71    76\n")
        seq.append("\n".join([(repr(row + 1).rjust(3) + "  ") + "  ".join(["-".join(["".join([repr(value[col, row]) for col in range(col_fine, col_fine + 5)]) for col_fine in range(col_coarse, col_coarse + 10, 5)]) for col_coarse in range(0, 80, 10)]) for row in range(336)]))
        seq.append("\n")
        f.writelines(seq)


def parse_pixel_dac_config(filename):
    mask = np.empty((80, 336), dtype=np.uint8)
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
    return mask


def bitarray_from_value(value, size=None, fmt='Q'):
    ba = bitarray(endian='little')
    ba.frombytes(struct.pack(fmt, value))
    if size is not None:
        if size > ba.length():
            ba.extend((size - ba.length()) * [0])
        else:
            ba = ba[:size]
    ba.reverse()
    return ba


def write_pixel_dac_config(filename, value):
    with open(filename, 'w') as f:
        seq = []
        seq.append("###    1  2  3  4  5  6  7  8  9 10   11 12 13 14 15 16 17 18 19 20   21 22 23 24 25 26 27 28 29 30   31 32 33 34 35 36 37 38 39 40\n")
        seq.append("###   41 42 43 44 45 46 47 48 49 50   51 52 53 54 55 56 57 58 59 60   61 62 63 64 65 66 67 68 69 70   71 72 73 74 75 76 77 78 79 80\n")
        seq.append("\n".join(["\n".join([((repr(row + 1).rjust(3) + ("a" if col_coarse == 0 else "b") + "  ") + "   ".join([" ".join([repr(value[col, row]).rjust(2) for col in range(col_fine, col_fine + 10)]) for col_fine in range(col_coarse, col_coarse + 40, 10)])) for col_coarse in range(0, 80, 40)]) for row in range(336)]))
        seq.append("\n")
        f.writelines(seq)


def load_configuration_from_text_file(register, configuration_file):
    '''Loading configuration from text files to register object

    Parameters
    ----------
    register : pybar.fei4.register object
    configuration_file : string
        Full path (directory and filename) of the configuration file. If name is not given, reload configuration from file.
    '''
    logging.info("Loading configuration: %s" % configuration_file)
    register.configuration_file = configuration_file

    config_dict = parse_global_config(register.configuration_file)

    if 'Flavor' in config_dict:
        flavor = config_dict.pop('Flavor').lower()
        if register.flavor:
            pass
        else:
            register.init_fe_type(flavor)
    else:
        if register.flavor:
            pass
        else:
            raise ValueError('Flavor not specified')
    if 'Chip_ID' in config_dict:
        chip_id = config_dict.pop('Chip_ID')
        if register.chip_address:
            pass
        else:
            register.broadcast = True if chip_id & 0x8 else False
            register.set_chip_address(chip_id & 0x7)
    elif 'Chip_Address' in config_dict:
        chip_address = config_dict.pop('Chip_Address')
        if register.chip_address:
            pass
        else:
            register.set_chip_address(chip_address)
    else:
        if register.chip_id_initialized:
            pass
        else:
            raise ValueError('Chip address not specified')
    global_registers_configured = []
    pixel_registers_configured = []
    for key in config_dict.keys():
        value = config_dict.pop(key)
        if key in register.global_registers:
            register.set_global_register_value(key, value)
            global_registers_configured.append(key)
        elif key in register.pixel_registers:
            register.set_pixel_register_value(key, value)
            pixel_registers_configured.append(key)
        elif key in register.calibration_parameters:
            register.calibration_parameters[key] = value
        else:
            register.miscellaneous[key] = value

    global_registers = register.get_global_register_attributes('name', readonly=False)
    pixel_registers = register.pixel_registers.keys()
    global_registers_not_configured = set(global_registers).difference(global_registers_configured)
    pixel_registers_not_configured = set(pixel_registers).difference(pixel_registers_configured)
    if global_registers_not_configured:
        logging.warning("Following global register(s) not configured: {}".format(', '.join('\'' + reg + '\'' for reg in global_registers_not_configured)))
    if pixel_registers_not_configured:
        logging.warning("Following pixel register(s) not configured: {}".format(', '.join('\'' + reg + '\'' for reg in pixel_registers_not_configured)))
    if register.miscellaneous:
        logging.warning("Found following unknown parameter(s): {}".format(', '.join('\'' + parameter + '\'' for parameter in register.miscellaneous.iterkeys())))


def load_configuration_from_hdf5(register, configuration_file, node=''):
    '''Loading configuration from HDF5 file to register object

    Parameters
    ----------
    register : pybar.fei4.register object
    configuration_file : string, file
        Filename of the HDF5 configuration file or file object.
    node : string
        Additional identifier (subgroup). Useful when more than one configuration is stored inside a HDF5 file.
    '''
    def load_conf():
        logging.info("Loading configuration: %s" % h5_file.filename)
        register.configuration_file = h5_file.filename
        if node:
            configuration_group = h5_file.root.configuration.node
        else:
            configuration_group = h5_file.root.configuration

        # miscellaneous
        for row in configuration_group.miscellaneous:
            name = row['name']
            try:
                value = ast.literal_eval(row['value'])
            except ValueError:
                value = row['value']
            if name == 'Flavor':
                if register.flavor:
                    pass
                else:
                    register.init_fe_type(value)
            elif name == 'Chip_ID':
                if register.chip_address:
                    pass
                else:
                    register.broadcast = True if value & 0x8 else False
                    register.set_chip_address(value & 0x7)
            elif name == 'Chip_Address':
                if register.chip_address:
                    pass
                else:
                    register.set_chip_address(value)
            else:
                register.miscellaneous[name] = value

        if register.flavor:
            pass
        else:
            raise ValueError('Flavor not specified')

        if register.chip_id_initialized:
            pass
        else:
            raise ValueError('Chip address not specified')

        # calibration parameters
        for row in configuration_group.calibration_parameters:
            name = row['name']
            value = row['value']
            register.calibration_parameters[name] = ast.literal_eval(value)

        # global
        for row in configuration_group.global_register:
            name = row['name']
            value = row['value']
            register.set_global_register_value(name, ast.literal_eval(value))

        # pixels
        for pixel_reg in h5_file.iter_nodes(configuration_group, 'CArray'):  # ['Enable', 'TDAC', 'C_High', 'C_Low', 'Imon', 'FDAC', 'EnableDigInj']:
            if pixel_reg.name in register.pixel_registers:
                register.set_pixel_register_value(pixel_reg.name, np.asarray(pixel_reg).T)  # np.asarray(h5_file.get_node(configuration_group, name=pixel_reg)).T

    if isinstance(configuration_file, tb.file.File):
        h5_file = configuration_file
        load_conf()
    else:
        with tb.open_file(configuration_file, mode="r", title='') as h5_file:
            load_conf()


def save_configuration_to_text_file(register, configuration_file):
    '''Saving configuration to text files from register object

    Parameters
    ----------
    register : pybar.fei4.register object
    configuration_file : string
        Filename of the configuration file.
    '''
    configuration_path, filename = os.path.split(configuration_file)
    if os.path.split(configuration_path)[1] == 'configs':
        configuration_path = os.path.split(configuration_path)[0]
    filename = os.path.splitext(filename)[0].strip()
    register.configuration_file = os.path.join(os.path.join(configuration_path, 'configs'), filename + ".cfg")
    if os.path.isfile(register.configuration_file):
        logging.warning("Overwriting configuration: %s", register.configuration_file)
    else:
        logging.info("Saving configuration: %s" % register.configuration_file)
    pixel_reg_dict = {}
    for path in ["tdacs", "fdacs", "masks", "configs"]:
        configuration_file_path = os.path.join(configuration_path, path)
        if not os.path.exists(configuration_file_path):
            os.makedirs(configuration_file_path)
        if path == "tdacs":
            dac = register.get_pixel_register_objects(name="TDAC")[0]
            dac_config_path = os.path.join(configuration_file_path, "_".join([dac['name'].lower(), filename]) + ".dat")
            write_pixel_dac_config(dac_config_path, dac['value'])
            pixel_reg_dict[dac['name']] = os.path.relpath(dac_config_path, os.path.dirname(register.configuration_file))
        elif path == "fdacs":
            dac = register.get_pixel_register_objects(name="FDAC")[0]
            dac_config_path = os.path.join(configuration_file_path, "_".join([dac['name'].lower(), filename]) + ".dat")
            write_pixel_dac_config(dac_config_path, dac['value'])
            pixel_reg_dict[dac['name']] = os.path.relpath(dac_config_path, os.path.dirname(register.configuration_file))
        elif path == "masks":
            masks = register.get_pixel_register_objects(bitlength=1)
            for mask in masks:
                dac_config_path = os.path.join(configuration_file_path, "_".join([mask['name'].lower(), filename]) + ".dat")
                write_pixel_mask_config(dac_config_path, mask['value'])
                pixel_reg_dict[mask['name']] = os.path.relpath(dac_config_path, os.path.dirname(register.configuration_file))
        elif path == "configs":
            with open(register.configuration_file, 'w') as f:
                lines = []
                lines.append("# FEI4 Flavor\n")
                lines.append('%s %s\n' % ('Flavor', register.flavor))
                lines.append("\n# FEI4 Chip ID\n")
                lines.append('%s %d\n' % ('Chip_ID', register.chip_id))
                lines.append("\n# FEI4 Global Registers\n")
                global_regs = register.get_global_register_objects(readonly=False)
                for global_reg in sorted(global_regs, key=itemgetter('name')):
                    lines.append('%s %d\n' % (global_reg['name'], global_reg['value']))
                lines.append("\n# FEI4 Pixel Registers\n")
                for key in sorted(pixel_reg_dict):
                    lines.append('%s %s\n' % (key, pixel_reg_dict[key]))
                lines.append("\n# FEI4 Calibration Parameters\n")
                for key in register.calibration_parameters:
                    if register.calibration_parameters[key] is None:
                        lines.append('%s %s\n' % (key, register.calibration_parameters[key]))
                    elif isinstance(register.calibration_parameters[key], (float, int, long)):
                        lines.append('%s %s\n' % (key, round(register.calibration_parameters[key], 4)))
                    elif isinstance(register.calibration_parameters[key], list):
                        lines.append('%s %s\n' % (key, [round(elem, 2) for elem in register.calibration_parameters[key]]))
                    else:
                        raise ValueError('type %s not supported' % type(register.calibration_parameters[key]))
                if register.miscellaneous:
                    lines.append("\n# Miscellaneous\n")
                    for key, value in register.miscellaneous.iteritems():
                        lines.append('%s %s\n' % (key, value))
                f.writelines(lines)


def save_configuration_to_hdf5(register, configuration_file, name=''):
    '''Saving configuration to HDF5 file from register object

    Parameters
    ----------
    register : pybar.fei4.register object
    configuration_file : string, file
        Filename of the HDF5 configuration file or file object.
    name : string
        Additional identifier (subgroup). Useful when storing more than one configuration inside a HDF5 file.
    '''
    def save_conf():
        logging.info("Saving configuration: %s" % h5_file.filename)
        register.configuration_file = h5_file.filename
        try:
            configuration_group = h5_file.create_group(h5_file.root, "configuration")
        except tb.NodeError:
            configuration_group = h5_file.root.configuration
        if name:
            try:
                configuration_group = h5_file.create_group(configuration_group, name)
            except tb.NodeError:
                configuration_group = h5_file.root.configuration.name

        # calibration_parameters
        try:
            h5_file.remove_node(configuration_group, name='calibration_parameters')
        except tb.NodeError:
            pass
        calibration_data_table = h5_file.create_table(configuration_group, name='calibration_parameters', description=NameValue, title='calibration_parameters')
        calibration_data_row = calibration_data_table.row
        for key, value in register.calibration_parameters.iteritems():
            calibration_data_row['name'] = key
            calibration_data_row['value'] = str(value)
            calibration_data_row.append()
        calibration_data_table.flush()

        # miscellaneous
        try:
            h5_file.remove_node(configuration_group, name='miscellaneous')
        except tb.NodeError:
            pass
        miscellaneous_data_table = h5_file.create_table(configuration_group, name='miscellaneous', description=NameValue, title='miscellaneous')
        miscellaneous_data_row = miscellaneous_data_table.row
        miscellaneous_data_row['name'] = 'Flavor'
        miscellaneous_data_row['value'] = register.flavor
        miscellaneous_data_row.append()
        miscellaneous_data_row['name'] = 'Chip_ID'
        miscellaneous_data_row['value'] = register.chip_id
        miscellaneous_data_row.append()
        for key, value in register.miscellaneous.iteritems():
            miscellaneous_data_row['name'] = key
            miscellaneous_data_row['value'] = value
            miscellaneous_data_row.append()
        miscellaneous_data_table.flush()

        # global
        try:
            h5_file.remove_node(configuration_group, name='global_register')
        except tb.NodeError:
            pass
        global_data_table = h5_file.create_table(configuration_group, name='global_register', description=NameValue, title='global_register')
        global_data_table_row = global_data_table.row
        global_regs = register.get_global_register_objects(readonly=False)
        for global_reg in sorted(global_regs, key=itemgetter('name')):
            global_data_table_row['name'] = global_reg['name']
            global_data_table_row['value'] = global_reg['value']  # TODO: some function that converts to bin, hex
            global_data_table_row.append()
        global_data_table.flush()

        # pixel
        for pixel_reg in register.pixel_registers.itervalues():
            try:
                h5_file.remove_node(configuration_group, name=pixel_reg['name'])
            except tb.NodeError:
                pass
            data = pixel_reg['value'].T
            atom = tb.Atom.from_dtype(data.dtype)
            ds = h5_file.createCArray(configuration_group, name=pixel_reg['name'], atom=atom, shape=data.shape, title=pixel_reg['name'])
            ds[:] = data

    if isinstance(configuration_file, tb.file.File):
        h5_file = configuration_file
        save_conf()
    else:
        with tb.open_file(configuration_file, mode="a", title='') as h5_file:
            save_conf()


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
    self.fifo_readout.reset_sram_fifo()
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

    data = self.fifo_readout.read_data()
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
    self.fifo_readout.reset_sram_fifo()
    commands = []
    read_from_address = self.register.get_global_register_attributes("addresses", readonly=False)
    commands.extend(self.register.get_commands("RdRegister", addresses=read_from_address))
    self.register_utils.send_commands(commands)
    time.sleep(1.0)  # wait for data
    data = self.fifo_readout.read_data()
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
    self.fifo_readout.reset_sram_fifo()

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
                data = self.fifo_readout.read_data()
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

    data = self.fifo_readout.read_data()

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
            data = self.fifo_readout.read_data()
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
    data = self.fifo_readout.read_data()
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
    if np.any(col_array >= 80) or np.any(col_array < 0) or np.any(row_array >= 336) or np.any(col_array < 0):
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
    if np.any(col_array >= 80) or np.any(col_array < 0) or np.any(row_array >= 336) or np.any(col_array < 0):
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
        Pixel mask

    Returns
    -------
    ndarray
        Xtalk mask

    Example
    -------
    Input:
    [[1 0 0 0 0 0 1 0 0 0 ..., 0 0 0 0 1 0 0 0 0 0]
     [0 0 0 1 0 0 0 0 0 1 ..., 0 1 0 0 0 0 0 1 0 0]
     ...,
     [1 0 0 0 0 0 1 0 0 0 ..., 0 0 0 0 1 0 0 0 0 0]
     [0 0 0 1 0 0 0 0 0 1 ..., 0 1 0 0 0 0 0 1 0 0]]

    Output:
    [[0 1 0 0 0 1 0 1 0 0 ..., 0 0 0 1 0 1 0 0 0 1]
     [0 0 1 0 1 0 0 0 1 0 ..., 1 0 1 0 0 0 1 0 1 0]
     ...,
     [0 1 0 0 0 1 0 1 0 0 ..., 0 0 0 1 0 1 0 0 0 1]
     [0 0 1 0 1 0 0 0 1 0 ..., 1 0 1 0 0 0 1 0 1 0]]
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


def scan_loop(self, command, repeat_command=100, use_delay=True, mask_steps=3, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, fast_dc_loop=True, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=None, disable_shift_masks=None, restore_shift_masks=True, mask=None, double_column_correction=False):
    '''Implementation of the scan loops (mask shifting, loop over double columns, repeatedly sending any arbitrary command).

    Parameters
    ----------
    command : BitVector
        (FEI4) command that will be sent out serially.
    repeat_command : int
        The number of repetitions command will be sent out each mask step.
    use_delay : bool
        Add additional delay to the command (append zeros). This helps to avoid FE data errors because of sending to many commands to the FE chip.
    mask_steps : int
        Number of mask steps.
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
        delay = self.register.get_commands("zeros", mask_steps=mask_steps)[0]
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
        if self.stop_run.is_set():
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
                    if self.stop_run.is_set():
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
                    if self.stop_run.is_set():
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
                    if self.stop_run.is_set():
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
                    if self.stop_run.is_set():
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
