from basil.dut import Dut

# import time
import os
import logging
import re
import tables as tb
# import platform
import inspect
import ast
# import matplotlib.pyplot as plt
# import numpy as np
from analysis.RawDataConverter.data_struct import NameValue  # , generate_scan_configuration_description


from threading import Thread, Event, Lock, Timer

min_pysilibusb_version = '0.2.1'
# from usb.core import USBError
from SiLibUSB import __version__ as pysilibusb_version
from distutils.version import StrictVersion as v
if v(pysilibusb_version) < v(min_pysilibusb_version):
    raise ImportError('Wrong pySiLibUsb version (installed=%s, expected>=%s)' % (pysilibusb_version, min_pysilibusb_version))

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from daq.readout import Readout

import signal
from bitarray import bitarray

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class ScanBase(object):
    scan_id = "base_scan"

    def __init__(self, dut, configuration_file=None, register=None, definition_file=None, scan_data_path=None, module_id=""):
        '''
        dut : str, file, dict, object
            Device configuration or Dut object. See Basil wiki (https://silab-redmine.physik.uni-bonn.de/projects/basil/wiki) for more information.
        configuration_file : str, FEI4Register
            Filename of FE configuration file or FEI4Register object.
        register : object
            FEI4 register object. Will be preferred over configuration_file if given.
        definition_file : str
            Filename of FE definition file (XML file). Usually not needed.
        scan_data_path : str
            Pathname of data output path.
        module_id : str
            Additional module identifier. An additional folder with the module ID will be created below scan_data_path.
        '''
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name == 'nt':
            import thread

            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True

            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)

        if isinstance(dut, Dut):
            self.dut = dut
            # assuming it is initialized
        else:
            self.dut = Dut(dut)
            self.dut.init('configuration.yaml')

        if self.dut.name == 'pyBAR':
            self.dut['POWER'].set_voltage('VDDA1', 1.500)
            self.dut['POWER'].set_voltage('VDDA2', 1.500)
            self.dut['POWER'].set_voltage('VDDD1', 1.200)
            self.dut['POWER'].set_voltage('VDDD2', 1.200)
            self.dut['POWER_SCC']['EN_VD1'] = 1
            self.dut['POWER_SCC']['EN_VD2'] = 1
            self.dut['POWER_SCC']['EN_VA1'] = 1
            self.dut['POWER_SCC']['EN_VA2'] = 1
            self.dut['POWER_SCC'].write()
            # enabling readout
            self.dut['rx']['CH1'] = 0
            self.dut['rx']['CH2'] = 0
            self.dut['rx']['CH3'] = 0
            self.dut['rx']['CH4'] = 1
            self.dut['rx']['TLU'] = 1
            self.dut['rx']['TDC'] = 1
            self.dut['rx'].write()
        elif self.dut.name == 'pyBAR_GPAC':
            self.dut.init('configuration_gpac.yaml')
            # enabling LVDS transceivers
            self.dut['CCPD_Vdd'].set_current_limit(1000, unit='mA')
            self.dut['CCPD_Vdd'].set_voltage(0.0, unit='V')
            self.dut['CCPD_Vdd'].set_enable(True)
            # enabling V_in
            self.dut['V_in'].set_current_limit(2000, unit='mA')
            self.dut['V_in'].set_voltage(2.1, unit='V')
            self.dut['V_in'].set_enable(True)
            # enabling readout
            self.dut['rx']['FE'] = 1
            self.dut['rx']['TLU'] = 1
            self.dut['rx']['TDC'] = 1
            self.dut['rx']['CCPD_TDC'] = 0
            self.dut['rx'].write()
        else:
            raise ValueError('Unknown DUT')

        self.readout = Readout(self.dut)

        if not register and configuration_file:
            self.register = FEI4Register(configuration_file=configuration_file, definition_file=definition_file)
        elif register:  # prefer register object
            self.register = register
        else:
            raise ValueError('Unknown configuration')

        self.register_utils = FEI4RegisterUtils(self.dut, self.readout, self.register)

        # remove all non_word characters and whitespace characters to prevent problems with os.path.join
        self.module_id = re.sub(r"[^\w\s+]", '', module_id)
        self.module_id = re.sub(r"\s+", '_', self.module_id)
        self.scan_id = re.sub(r"[^\w\s+]", '', self.scan_id)
        self.scan_id = re.sub(r"\s+", '_', self.scan_id)
        if scan_data_path is None:
            self.scan_data_path = os.getcwd()
        else:
            self.scan_data_path = scan_data_path
        if self.module_id:
            self.scan_data_output_path = os.path.join(self.scan_data_path, self.module_id)
        else:
            self.scan_data_output_path = self.scan_data_path

        self.scan_number = None
        self.scan_data_filename = None
        self.scan_aborted = False
        self.scan_is_running = False

        self.lock = Lock()

        self.scan_thread = None
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        self.use_thread = None
        self.restore_configuration = None

        # get scan args
        frame = inspect.currentframe()
        args, _, _, local = inspect.getargvalues(frame)
        self._device_configuration = {key: local[key] for key in args if key != 'self' and key != 'args' and key != 'kwargs'}
        self._device_configuration["register"] = self.register
        self._device_configuration["dut"] = self.dut

        self._scan_configuration = {}

    @property
    def is_running(self):
        return self.scan_thread.is_alive()

    @property
    def device_configuration(self):
        return self._device_configuration.copy()

    @property
    def scan_configuration(self):
        return self._scan_configuration.copy()

    def start(self, configure=True, restore_configuration=False, use_thread=False, do_global_reset=True, **kwargs):  # TODO: in Python 3 use def func(a,b,*args,kw1=None,**kwargs)
        '''Starting scan.

        Parameters
        ----------
        configure : bool
            If true, configure FE before starting scan.scan().
        restore_configuration : bool
            Restore FE configuration after finishing scan.scan().
        use_thread : bool
            If true, scan.scan() is running in a separate thread. Only then Ctrl-C can be used to interrupt scan loop.
        do_global_reset : bool
            Do a FE Global Reset before sending FE configuration.
        kwargs : any
            Any keyword argument passed to scan.start() will be forwarded to scan.scan(). Please note: scan.start() keyword arguments will merged with class keyword arguments
        '''
        self.scan_is_running = True
        self.scan_aborted = False

        # get scan loop args
        frame = inspect.currentframe()
        args, _, _, local = inspect.getargvalues(frame)
        self._scan_configuration = {key: local[key] for key in args if key is not 'self'}
        self._scan_configuration.update(kwargs)

        self._write_scan_number()

        if self.device_configuration:
            self._save_configuration_dict('device_configuration', self.device_configuration)

        if self.scan_configuration:
            self._save_configuration_dict('scan_configuration', self.scan_configuration)

        self.register.save_configuration_to_hdf5(self.scan_data_filename)  # save scan config at the beginning, will be overwritten after successfull stop of scan loop

        self.use_thread = use_thread
        if self.scan_thread is not None:
            raise RuntimeError('Scan thread is already running')

        if do_global_reset:
            self.register_utils.global_reset()
            self.register_utils.reset_bunch_counter()
            self.register_utils.reset_event_counter()
        self.register_utils.reset_service_records()
        if configure:
            self.register_utils.configure_all()
        self.restore_configuration = restore_configuration
        if self.restore_configuration:
            self.register.create_restore_point(name=self.scan_id)

        logging.info('Resetting RX')
        if self.dut.name == 'pyBAR':
            self.dut['rx_1']['SOFT_RESET']
            self.dut['rx_2']['SOFT_RESET']
            self.dut['rx_3']['SOFT_RESET']
            self.dut['rx_4']['SOFT_RESET']
        elif self.dut.name == 'pyBAR_GPAC':
            self.dut['rx_fe']['SOFT_RESET']

        self.readout.print_readout_status()
        if not any(self.readout.get_rx_sync_status()):
            self.dut['USB'].close()  # free USB resources
            raise NoSyncError('No RX sync on any input channel. Power? Cables?')
#             logging.error('Stopping scan: no sync')
#             return

        self.stop_thread_event.clear()

        logging.info('Starting scan %s with ID %d (output path: %s)' % (self.scan_id, self.scan_number, self.scan_data_output_path))
        if use_thread:
            self.scan_thread = Thread(target=self.scan, name='%s with ID %d' % (self.scan_id, self.scan_number), kwargs=self._scan_configuration)  # , args=kwargs)
            self.scan_thread.daemon = True  # Abruptly close thread when closing main thread. Resources may not be released properly.
            self.scan_thread.start()
            logging.info('Press Ctrl-C to stop scan loop')
            signal.signal(signal.SIGINT, self._signal_handler)
        else:
            self.scan(**self._scan_configuration)

    def stop(self, timeout=None):
        '''Stopping scan. Cleaning up of variables and joining thread (if existing).

        '''
        if (self.scan_thread is not None) ^ self.use_thread:
            if self.scan_thread is None:
                pass
#                 logging.warning('Scan thread has already stopped')
#                 raise RuntimeError('Scan thread has already stopped')
            else:
                raise RuntimeError('Thread is running where no thread was expected')
        if self.scan_thread is not None:

            def stop_thread():
                logging.warning('Scan timeout after %.1f second(s)' % timeout)
                self.stop_thread_event.set()
                self.scan_aborted = True

            timeout_timer = Timer(timeout, stop_thread)  # could also use shed.scheduler() here
            if timeout:
                timeout_timer.start()
            try:
                while self.scan_thread.is_alive() and not self.stop_thread_event.wait(1):
                    pass
            except IOError:  # catching "IOError: [Errno4] Interrupted function call" because of wait_timeout_event.wait()
                logging.exception('Event handler problems?')
                raise

            timeout_timer.cancel()
            signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler
            self.stop_thread_event.set()

            self.scan_thread.join()  # SIGINT will be suppressed here
            self.scan_thread = None
        self.use_thread = None
        # do the following a second time
        args, _, _, defaults = inspect.getargspec(self.scan)
        if defaults:
            args = args[-len(defaults):]
            diff = set(args).difference(self.scan_configuration)
            args_dict = dict(zip(args, defaults))
            for item in diff:
                self._scan_configuration[item] = args_dict[item]
        if self.device_configuration:
            self._save_configuration_dict('device_configuration', self.device_configuration)
        if self.scan_configuration:
            self._save_configuration_dict('scan_configuration', self.scan_configuration)
        self.register.save_configuration_to_hdf5(self.scan_data_filename)  # save the config used last in the scan loop

        if self.restore_configuration:
            logging.info('Restoring FE configuration')
            self.register.restore(name=self.scan_id)
            self.register_utils.configure_all()
        logging.info('Stopped scan %s with ID %d' % (self.scan_id, self.scan_number))
        self.readout.print_readout_status()

        self.dut['USB'].close()  # free USB resources
        self._write_scan_status(self.scan_aborted)
        self.scan_is_running = False

    def _write_scan_number(self):
        scan_numbers = {}
        self.lock.acquire()
        if not os.path.exists(self.scan_data_output_path):
            os.makedirs(self.scan_data_output_path)
        # In Python 2.x, open on all POSIX systems ultimately just depends on fopen.
        with open(os.path.join(self.scan_data_output_path, (self.module_id if self.module_id else self.scan_id) + ".cfg"), 'a+') as f:
            f.seek(0)
            for line in f.readlines():
                scan_number = int(re.findall(r'\d+\s*', line)[0])
                if line[-1] != '\n':
                    line = line + '\n'
                scan_numbers[scan_number] = line
        if not scan_numbers:
            self.scan_number = 0
        else:
            self.scan_number = max(dict.iterkeys(scan_numbers)) + 1
        scan_numbers[self.scan_number] = str(self.scan_number) + ' ' + self.scan_id + ' ' + 'NOT_FINISHED' + '\n'
        with open(os.path.join(self.scan_data_output_path, (self.module_id if self.module_id else self.scan_id) + ".cfg"), "w") as f:
            for value in dict.itervalues(scan_numbers):
                f.write(value)
        self.lock.release()
        self.scan_data_filename = os.path.join(self.scan_data_output_path, ((self.module_id + "_" + self.scan_id) if self.module_id else self.scan_id) + "_" + str(self.scan_number))

    def _write_scan_status(self, aborted=False):
        scan_numbers = {}
        self.lock.acquire()
        with open(os.path.join(self.scan_data_output_path, (self.module_id if self.module_id else self.scan_id) + ".cfg"), 'a+') as f:
            f.seek(0)
            for line in f.readlines():
                scan_number = int(re.findall(r'\d+\s*', line)[0])
                if line[-1] != '\n':
                    line = line + '\n'
                if scan_number != self.scan_number:
                    scan_numbers[scan_number] = line
                else:
                    scan_numbers[scan_number] = str(self.scan_number) + ' ' + self.scan_id + ' ' + ('ABORTED' if aborted else 'FINISHED') + '\n'
        if not scan_numbers:
            scan_numbers[self.scan_number] = str(self.scan_number) + ' ' + self.scan_id + ' ' + ('ABORTED' if aborted else 'FINISHED') + '\n'
            logging.warning('Configuration file was deleted: Restoring %s', os.path.join(self.scan_data_output_path, (self.module_id if self.module_id else self.scan_id) + ".cfg"))
        with open(os.path.join(self.scan_data_output_path, (self.module_id if self.module_id else self.scan_id) + ".cfg"), "w") as f:
            for value in dict.itervalues(scan_numbers):
                f.write(value)
        self.lock.release()

    def scan_loop(self, command, repeat_command=100, use_delay=True, mask_steps=3, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, bol_function=None, eol_function=None, digital_injection=False, enable_shift_masks=["Enable", "C_High", "C_Low"], disable_shift_masks=[], restore_shift_masks=True, mask=None, double_column_correction=False):
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
        bol_function : function
            Begin of loop function that will be called each time before sending command. Argument is a function pointer (without braces) or functor.
        eol_function : function
            End of loop function that will be called each time after sending command. Argument is a function pointer (without braces) or functor.
        digital_injection : bool
            Enables digital injection. C_High and C_Low will be disabled.
        enable_shift_masks : list, tuple
            List of enable pixel masks which will be shifted during scan. Mask set to 1 for selected pixels else 0.
        disable_shift_masks : list, tuple
            List of disable pixel masks which will be shifted during scan. Mask set to 0 for selected pixels else 1.
        restore_shift_masks : bool
            Writing the initial (restored) FE pixel configuration into FE after finishing the scan loop.
        mask : array-like
            Additional mask. Must be convertible to an array of booleans with the same shape as mask array. True indicates a masked pixel. Masked pixels will be disabled during shifting of the enable shift masks, and enabled during shifting disable shift mask.
        double_column_correction : str, bool, list, tuple
            Enables double column PlsrDAC correction. If value is a filename (string) or list/tuple, the default PlsrDAC correction will be overwritten. First line of the file must be a Python list ([0, 0, ...])
        '''
        if not isinstance(command, bitarray):
            raise TypeError

        # get PlsrDAC correction
        if isinstance(double_column_correction, basestring):  # from file
            with open(double_column_correction) as fp:
                plsr_dac_correction = list(ast.literal_eval(fp.readline().strip()))
        elif isinstance(double_column_correction, (list, tuple)):  # from list/tuple
            plsr_dac_correction = list(double_column_correction)
        else:  # default
            if "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks) and "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks):
                plsr_dac_correction = self.register.calibration_config['Pulser_Corr_C_Inj_High']
            elif "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks):
                plsr_dac_correction = self.register.calibration_config['Pulser_Corr_C_Inj_Med']
            elif "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks):
                plsr_dac_correction = self.register.calibration_config['Pulser_Corr_C_Inj_Low']
        # initial PlsrDAC value for PlsrDAC correction
        initial_plsr_dac = self.register.get_global_register_value("PlsrDAC")
        # create restore point
        restore_point_name = self.scan_id + '_scan_loop'
        self.register.create_restore_point(name=restore_point_name)

        # pre-calculate often used commands
        conf_mode_command = self.register.get_commands("confmode")[0]
        run_mode_command = self.register.get_commands("runmode")[0]
        delay = self.register.get_commands("zeros", mask_steps=mask_steps)[0]
        if use_delay:
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
                return dc
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
            commands.append(self.register.get_commands("wrregister", name=["Colpr_Addr"])[0])
            if double_column_correction:
                self.register.set_global_register_value("PlsrDAC", initial_plsr_dac + plsr_dac_correction[dc])
                commands.append(self.register.get_commands("wrregister", name=["PlsrDAC"])[0])
            commands.append(run_mode_command)
            return self.register_utils.concatenate_commands(commands, byte_padding=True)

        if enable_mask_steps is None or not enable_mask_steps:
            enable_mask_steps = range(mask_steps)

        if enable_double_columns is None or not enable_double_columns:
            enable_double_columns = range(40)

        # preparing for scan
        commands = []
        commands.append(conf_mode_command)
        if digital_injection is True:
            self.register.set_global_register_value("DIGHITIN_SEL", 1)
#             self.register.set_global_register_value("CalEn", 1)  # for GlobalPulse instead Cal-Command
            # check if C_High and/or C_Low is in enable_shift_mask and/or disable_shift_mask
            if "C_High".lower() in map(lambda x: x.lower(), enable_shift_masks) or "C_High".lower() in map(lambda x: x.lower(), disable_shift_masks):
                raise ValueError('C_High must not be shift mask when using digital injection')
            if "C_Low".lower() in map(lambda x: x.lower(), enable_shift_masks) or "C_Low".lower() in map(lambda x: x.lower(), disable_shift_masks):
                raise ValueError('C_Low must not be shift mask when using digital injection')
        else:
            self.register.set_global_register_value("DIGHITIN_SEL", 0)
            # setting EnableDigInj to 0 not necessary since DIGHITIN_SEL is turned off
#             self.register.set_pixel_register_value("EnableDigInj", 0)
        # turn off all capacitors by default
        self.register.set_pixel_register_value("C_High", 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["C_High"]))
        self.register.set_pixel_register_value("C_Low", 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["C_Low"]))
        commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
        self.register_utils.send_commands(commands, concatenate=True)

        for mask_step in enable_mask_steps:
            commands = []
            commands.append(conf_mode_command)
            if same_mask_for_all_dc:  # generate and write first mask step
                if disable_shift_masks:
                    curr_dis_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, mask=mask)
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False if mask else True, name=disable_shift_masks))
                if enable_shift_masks:
                    curr_en_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, mask=mask)
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks])
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False if mask else True, name=enable_shift_masks))
    #                 plt.clf()
    #                 plt.imshow(curr_en_mask.T, interpolation='nearest', aspect="auto")
    #                 plt.pcolor(curr_en_mask.T)
    #                 plt.colorbar()
    #                 plt.savefig('mask_step' + str(mask_step) + '.pdf')
                if digital_injection is True:  # write EnableDigInj last
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False if mask else True, name=['EnableDigInj']))
                    # write DIGHITIN_SEL since after mask writing it is disabled
                    self.register.set_global_register_value("DIGHITIN_SEL", 1)
                    commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
            else:  # set masks to default values
                if disable_shift_masks:
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, 1), disable_shift_masks)
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=disable_shift_masks))
                if enable_shift_masks:
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, 0), [shift_mask_name for shift_mask_name in enable_shift_masks])
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=enable_shift_masks))
                if digital_injection is True:  # write EnableDigInj last
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=['EnableDigInj']))
                    # write DIGHITIN_SEL since after mask writing it is disabled
                    self.register.set_global_register_value("DIGHITIN_SEL", 1)
                    commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
            self.register_utils.send_commands(commands, concatenate=True)
            logging.info('%d injection(s): mask step %d %s' % (repeat_command, mask_step, ('[%d - %d]' % (enable_mask_steps[0], enable_mask_steps[-1])) if len(enable_mask_steps) > 1 else ('[%d]' % enable_mask_steps[0])))

            if same_mask_for_all_dc:  # fast loop
                # set repeat, should be 1 by default when arriving here
                self.dut['cmd']['CMD_REPEAT'] = repeat_command

                # get DC command for the first DC in the list, DC command is byte padded
                # fill CMD memory with DC command and scan loop command, inside the loop only overwrite DC command
                dc_address_command = get_dc_address_command(enable_double_columns[0])
                self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                for index, dc in enumerate(enable_double_columns):
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

                    self.dut['cmd']['START']

                # wait here before we go on because we just jumped out of the loop
                self.register_utils.wait_for_command()
                if eol_function:
                    eol_function()
                self.dut['cmd']['START_SEQUENCE_LENGTH'] = 0
            else:  # slow loop
                dc = enable_double_columns[0]
                ec = enable_columns(dc)
                dcs = write_double_columns(dc)
                commands = []
                commands.append(conf_mode_command)
                if disable_shift_masks:
                    curr_dis_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks))
                if enable_shift_masks:
                    curr_en_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                    map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks])
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks))
                if digital_injection is True:
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=['EnableDigInj']))
                    self.register.set_global_register_value("DIGHITIN_SEL", 1)
                    commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
                self.register_utils.send_commands(commands, concatenate=True)

                dc_address_command = get_dc_address_command(dc)
                self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                self.dut['cmd']['CMD_REPEAT'] = repeat_command
                self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                for index, dc in enumerate(enable_double_columns):
                    if index != 0:  # full command is already set before loop
                        ec = enable_columns(dc)
                        dcs = write_double_columns(dc)
                        dcs.extend(write_double_columns(enable_double_columns[index - 1]))
                        commands = []
                        commands.append(conf_mode_command)
                        if disable_shift_masks:
                            curr_dis_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, enable_columns=ec, mask=mask)
                            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=disable_shift_masks))
                        if enable_shift_masks:
                            curr_en_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, enable_columns=ec, mask=mask)
                            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks])
                            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=enable_shift_masks))
                        if digital_injection is True:
                            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, dcs=dcs, name=['EnableDigInj']))
                            self.register.set_global_register_value("DIGHITIN_SEL", 1)
                            commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
                        dc_address_command = get_dc_address_command(dc)

                        self.register_utils.wait_for_command()
                        if eol_function:
                            eol_function()  # do this after command has finished
                        self.register_utils.send_commands(commands, concatenate=True)

                        self.dut['cmd']['START_SEQUENCE_LENGTH'] = len(dc_address_command)
                        self.dut['cmd']['CMD_REPEAT'] = repeat_command
                        self.register_utils.set_command(command=self.register_utils.concatenate_commands((dc_address_command, scan_loop_command), byte_padding=False))

                    if bol_function:
                        bol_function()

                    self.dut['cmd']['START']

                self.register_utils.wait_for_command()
                if eol_function:
                    eol_function()
                self.dut['cmd']['START_SEQUENCE_LENGTH'] = 0


        # restoring default values
        self.register.restore(name=restore_point_name)
        self.register_utils.configure_global()  # always restore global configuration
        if restore_shift_masks:
            commands = []
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=disable_shift_masks))
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=enable_shift_masks))
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name="EnableDigInj"))
            self.register_utils.send_commands(commands)

    def scan(self, **kwargs):
        raise NotImplementedError('scan.scan() not implemented')

    def analyze(self, **kwargs):
        raise NotImplementedError('scan.analyze() not implemented')

    def _signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        logging.info('Pressed Ctrl-C. Stopping scan...')
        self.scan_aborted = False
        self.stop_thread_event.set()

    def _save_configuration_dict(self, configuation_name, configuration, **kwargs):
        '''Stores any configuration dictionary to HDF5 file.

        Parameters
        ----------
        configuation_name : str
            Configuration name. Will be used for table name.
        configuration : dict
            Configuration dictionary.
        '''
        h5_file = self.scan_data_filename
        if os.path.splitext(h5_file)[1].strip().lower() != ".h5":
            h5_file = os.path.splitext(h5_file)[0] + ".h5"

        # append to file if existing otherwise create new one
#         raw_data_file_h5 = tb.openFile(h5_file, mode="a", title=((self.module_id + "_" + self.scan_id) if self.module_id else self.scan_id) + "_" + str(self.scan_number), **kwargs)
        with tb.openFile(h5_file, mode="a", title=((self.module_id + "_" + self.scan_id) if self.module_id else self.scan_id) + "_" + str(self.scan_number), **kwargs) as raw_data_file_h5:
#             scan_param_descr = generate_scan_configuration_description(dict.iterkeys(configuration))
            filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
            try:
                raw_data_file_h5.removeNode(raw_data_file_h5.root.configuration, name=configuation_name)
            except tb.NodeError:
                pass
            try:
                configuration_group = raw_data_file_h5.create_group(raw_data_file_h5.root, "configuration")
            except tb.NodeError:
                configuration_group = raw_data_file_h5.root.configuration
            self.scan_param_table = raw_data_file_h5.createTable(configuration_group, name=configuation_name, description=NameValue, title=configuation_name, filters=filter_tables)

            row_scan_param = self.scan_param_table.row

            for key, value in dict.iteritems(configuration):
                row_scan_param['name'] = key
                row_scan_param['value'] = str(value)
                row_scan_param.append()

            self.scan_param_table.flush()

#         raw_data_file_h5.close()

    def save_configuration(self, name):
        '''Stores FE configuration to text files.

        Parameters
        ----------
        name : str
            Name of the configuration file. None will overwrite existing configuration, empty string will use default configuration name composited from scan name and number.
        '''
        if name is None:
            self.register.save_configuration()
        elif name:
            self.register.save_configuration(name)
        else:
            self.register.save_configuration(self.scan_data_filename)

    def __getattr__(self, name):
        '''called only on last resort if there are no attributes in the instance that match the name
        '''
        if name in self._device_configuration:
            return self._device_configuration[name]
        elif name in self._scan_configuration:
            return self._scan_configuration[name]
        else:
            args, _, _, defaults = inspect.getargspec(self.scan)
            if defaults:
                args = args[-len(defaults):]
            if name in args:
                pos = args.index(name)
                return defaults[pos]
            else:
                raise AttributeError("%r object has no attribute %r" % (self.__class__, name))


class NoSyncError(Exception):
    pass


class NoDeviceError(Exception):
    pass


class DeviceError(Exception):
    pass


from functools import wraps


def set_event_when_keyboard_interrupt(_lambda):
    '''Decorator function that sets Threading.Event() when keyboard interrupt (Ctrl+C) was raised

    Parameters
    ----------
    _lambda : function
        Lambda function that points to Threading.Event() object

    Returns
    -------
    wrapper : function

    Examples
    --------
    @set_event_when_keyboard_interrupt(lambda x: x.stop_thread_event)
    def scan(self, **kwargs):
        # some code

    Note
    ----
    Decorated functions cannot be derived.
    '''
    def wrapper(f):
        @wraps(f)
        def wrapped_f(self, *f_args, **f_kwargs):
            try:
                f(self, *f_args, **f_kwargs)
            except KeyboardInterrupt:
#                 logging.info('Keyboard interrupt: setting %s' % _lambda(self).__name__)
                _lambda(self).set()
        return wrapped_f
    return wrapper
