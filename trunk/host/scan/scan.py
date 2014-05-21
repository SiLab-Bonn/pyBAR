import time
import os
import logging
import re
import tables as tb
import platform
import inspect
from analysis.RawDataConverter.data_struct import generate_scan_configuration_description

from threading import Thread, Event, Lock, Timer

min_pysilibusb_version = '0.1.3'
from usb.core import USBError
from SiLibUSB import SiUSBDevice, __version__ as pysilibusb_version
from distutils.version import StrictVersion as v
if v(pysilibusb_version) < v(min_pysilibusb_version):
    raise ImportError('Wrong pySiLibUsb version (installed=%s, expected>=%s)' % (pysilibusb_version, min_pysilibusb_version))

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from daq.readout_utils import ReadoutUtils
from daq.readout import Readout

import signal
from bitarray import bitarray

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class ScanBase(object):
    scan_id = "base_scan"

    def __init__(self, configuration_file=None, register=None, definition_file=None, bit_file=None, force_download=False, device_id=None, device=None, scan_data_path=None, module_id="", **kwargs):
        '''
        configuration_file : str, FEI4Register
            Filename of FE configuration file or FEI4Register object.
        definition_file : str
            Filename of FE definition file (XML file). Usually not needed.
        bit_file : str
            Filename of FPGA bitstream file (bit file).
        force_download : bool
            Force download of bitstream file, even if FPGA is configured.
        device : SiUSBDevice, int
            SiUSBDevice object or device ID. If None, any available USB device will be taken.
        scan_id : str
            Scan identifier string.
        scan_data_path : str
            Pathname of data output path.
        '''
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name == 'nt':
            import thread

            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True

            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)

        self.device_id = device_id
        self.device = device

        if not self.device and not self.device_id:
            # search for any available device
            try:
                self.device = SiUSBDevice()
            except USBError:
                raise NoDeviceError('Can\'t find USB board. Connect or reset USB board!')
            try:
                # avoid reading board ID and FW version a second time because this will crash the uC
                if not self.device.XilinxAlreadyLoaded():
                    logging.info('Found %s with ID %s (FW %s)', self.device.board_name, filter(type(self.device.board_id).isdigit, self.device.board_id), filter(type(self.device.fw_version).isdigit, self.device.fw_version))
            except USBError:
                raise DeviceError('Can\'t communicate with USB board. Reset USB board!')
        else:
            if not self.device:
                self.device = SiUSBDevice.from_board_id(device_id)
            try:
                # avoid reading board ID and FW version a second time because this will crash the uC
                if not self.device.XilinxAlreadyLoaded():
                    logging.info('Using %s with ID %s (FW %s)', self.device.board_name, filter(type(self.device.board_id).isdigit, self.device.board_id), filter(type(self.device.fw_version).isdigit, self.device.fw_version))
                else:
                    logging.info('Using %s with ID %s', 'USBpix', str(device))
            except USBError:
                raise DeviceError('Can\'t communicate with USB board. Reset USB board!')

        if bit_file:
            if self.device.XilinxAlreadyLoaded() and not force_download:
                logging.info('FPGA already configured, skipping download of bitstream')
            else:
                logging.info('Downloading bitstream to FPGA: %s' % bit_file)
                try:
                    if not self.device.DownloadXilinx(bit_file):
                        raise IOError('Can\'t program FPGA firmware. Reset USB board!')
                except USBError:
                    raise DeviceError('Can\'t program FPGA firmware. Reset USB board!')
                time.sleep(1)

        self.readout = Readout(self.device)
        self.readout_utils = ReadoutUtils(self.device)

        self.configuration_file = configuration_file
        self.register = register

        if not self.register:
            self.register = FEI4Register(configuration_file=self.configuration_file, definition_file=definition_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout, self.register)

        # remove all non_word characters and whitespace characters to prevent problems with os.path.join
        self.module_id = re.sub(r"[^\w\s+]", '', module_id)
        self.module_id = re.sub(r"\s+", '_', self.module_id)
        self.scan_id = re.sub(r"[^\w\s+]", '', self.scan_id)
        self.scan_id = re.sub(r"\s+", '_', self.scan_id)
        if scan_data_path == None:
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
        args, _, _, locals = inspect.getargvalues(frame)
        self._device_configuration = {key: locals[key] for key in args if key != 'self' and key != 'args' and key != 'kwargs'}
        self._device_configuration["register"] = self.register
        self._device_configuration["device"] = self.device
        if kwargs:
            self._device_configuration.update(kwargs)

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
        args, _, _, locals = inspect.getargvalues(frame)
        self._scan_configuration = {key: locals[key] for key in args if key is not 'self'}
        self._scan_configuration.update(kwargs)

        all_parameters = {}
        all_parameters.update(self.scan_configuration)
        all_parameters.update(self.device_configuration)

        self.write_scan_number()

        if self.device_configuration:
            self.save_configuration('device_configuration', self.device_configuration)

        if self.scan_configuration:
            self.save_configuration('scan_configuration', self.scan_configuration)

        self.use_thread = use_thread
        if self.scan_thread != None:
            raise RuntimeError('Scan thread is already running')

        # setting FPGA register to default state
        self.readout_utils.configure_rx_fsm(**self.device_configuration)
        self.readout_utils.configure_command_fsm(**self.device_configuration)
        self.readout_utils.configure_trigger_fsm(**self.device_configuration)
        self.readout_utils.configure_tdc_fsm(**self.device_configuration)

        if do_global_reset:
            self.register_utils.global_reset()
        self.register_utils.reset_service_records()
        if configure:
            self.register_utils.configure_all()
        self.restore_configuration = restore_configuration
        if self.restore_configuration:
            self.register.create_restore_point(name=self.scan_id)

        self.readout.reset_rx()
#        self.readout.reset_sram_fifo()

        self.readout.print_readout_status()
        if not any(self.readout.get_rx_sync_status()):
            self.device.dispose()  # free USB resources
            raise NoSyncError('No RX sync on any input channel. Power? Cables?')
#             logging.error('Stopping scan: no sync')
#             return

        self.stop_thread_event.clear()

        logging.info('Starting scan %s with ID %d (output path: %s)' % (self.scan_id, self.scan_number, self.scan_data_output_path))
        if use_thread:
            self.scan_thread = Thread(target=self.scan, name='%s with ID %d' % (self.scan_id, self.scan_number), kwargs=all_parameters)  # , args=kwargs)
            self.scan_thread.daemon = True  # Abruptly close thread when closing main thread. Resources may not be released properly.
            self.scan_thread.start()
            logging.info('Press Ctrl-C to stop scan loop')
            signal.signal(signal.SIGINT, self.signal_handler)
        else:
            self.scan(**all_parameters)

    def stop(self, timeout=None):
        '''Stopping scan. Cleaning up of variables and joining thread (if existing).

        '''
        if (self.scan_thread is not None) ^ self.use_thread:
            if self.scan_thread is None:
                pass
                #logging.warning('Scan thread has already stopped')
                #raise RuntimeError('Scan thread has already stopped')
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
        if self.restore_configuration:
            logging.info('Restoring FE configuration')
            self.register.restore(name=self.scan_id)
            self.register_utils.configure_all()
        logging.info('Stopped scan %s with ID %d' % (self.scan_id, self.scan_number))
        self.readout.print_readout_status()

        self.device.dispose()  # free USB resources
        self.write_scan_status(self.scan_aborted)
        self.scan_is_running = False

    def write_scan_number(self):
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

    def write_scan_status(self, aborted=False):
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

    def scan_loop(self, command, repeat_command=100, use_delay=True, hardware_repeat=True, mask_steps=3, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, bol_function=None, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, enable_shift_masks=["Enable", "C_High", "C_Low"], disable_shift_masks=[], restore_shift_masks=True, mask=None):
        '''Implementation of the scan loops (mask shifting, loop over double columns, repeatedly sending any arbitrary command).

        Parameters
        ----------
        command : BitVector
            (FEI4) command that will be sent out serially.
        repeat_command : int
            The number of repetitions command will be sent out each mask step.
        use_delay : bool
            Add additional delay to the command (append zeros). This helps to avoid FE data errors because of sending to many commands to the FE chip.
        hardware_repeat : bool
            If true, use FPGA to repeat commands. In general this is much faster than doing this in software.
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
            Enables digital injection.
        enable_c_high : bool
            Enables C_High pixel mask. No change if value is equal None. Note: will be overwritten during mask shifting if in enable_shift_masks.
        enable_c_low : bool
            Enables C_Low pixel mask. No change if value is equal None. Note: will be overwritten during mask shifting if in enable_shift_masks.
        enable_shift_masks : list, tuple
            List of enable pixel masks which will be shifted during scan. Mask set to 1 for selected pixels else 0.
        disable_shift_masks : list, tuple
            List of disable pixel masks which will be shifted during scan. Mask set to 0 for selected pixels else 1.
        restore_shift_masks : bool
            Writing the initial (restored) FE pixel configuration into FE after finishing the scan loop.
        mask : array-like
            Additional mask. Must be convertible to an array of booleans with the same shape as mask array. True indicates a masked (i.e. invalid) data. Masked pixels will be selected (enabled) during mask shifting.
        '''
        if not isinstance(command, bitarray):
            raise TypeError

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

        def get_dc_address_command(dc):
            self.register.set_global_register_value("Colpr_Addr", dc)
            return self.register_utils.concatenate_commands((conf_mode_command, self.register.get_commands("wrregister", name=["Colpr_Addr"])[0], run_mode_command), byte_padding=True)

        if enable_mask_steps == None or not enable_mask_steps:
            enable_mask_steps = range(mask_steps)

        if enable_double_columns == None or not enable_double_columns:
            enable_double_columns = range(40)

        # preparing for scan
        commands = []
        commands.append(conf_mode_command)
        if digital_injection == True:
            #self.register.set_global_register_value("CalEn", 1) # for GlobalPulse instead Cal-Command
            self.register.set_global_register_value("DIGHITIN_SEL", 1)
        else:
            self.register.set_global_register_value("DIGHITIN_SEL", 0)
            self.register.set_pixel_register_value("EnableDigInj", 0)
        commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
        if enable_c_high is not None:
            self.register.set_pixel_register_value("C_High", 1 if enable_c_high else 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["C_High"]))
        if enable_c_low is not None:
            self.register.set_pixel_register_value("C_Low", 1 if enable_c_low else 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["C_Low"]))
        self.register_utils.send_commands(commands, concatenate=True)

        for mask_step in enable_mask_steps:
            commands = []
            commands.append(conf_mode_command)
            if disable_shift_masks:
                curr_dis_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, default=1, value=0, mask=mask)
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_dis_mask), disable_shift_masks)
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=same_mask_for_all_dc, name=disable_shift_masks))
            if enable_shift_masks or digital_injection:
                curr_en_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, mask=mask)
#                 plt.imshow(np.transpose(curr_en_mask), interpolation='nearest', aspect="auto")
#                 plt.pcolor(np.transpose(curr_en_mask))
#                 plt.colorbar()
#                 plt.savefig('mask_step'+str(mask_step)+'.eps')
                map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_en_mask), [shift_mask_name for shift_mask_name in enable_shift_masks if (shift_mask_name.lower() != "EnableDigInj".lower())])
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=same_mask_for_all_dc, name=enable_shift_masks))
                if digital_injection == True:  # TODO: write EnableDigInj to FE or do it manually?
                    self.register.set_pixel_register_value("EnableDigInj", curr_en_mask)
                    commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=same_mask_for_all_dc, name=["EnableDigInj"]))  # write EnableDigInj mask last
                    self.register.set_global_register_value("DIGHITIN_SEL", 1)
                    commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))
#                 else:
#                     commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["EnableDigInj"]))
            self.register_utils.send_commands(commands, concatenate=True)
            logging.info('%d injection(s): mask step %d %s' % (repeat_command, mask_step, ('[%d - %d]' % (enable_mask_steps[0], enable_mask_steps[-1])) if len(enable_mask_steps) > 1 else ('[%d]' % enable_mask_steps[0])))

            # set repeat, should be 1 by default when arriving here
            if hardware_repeat == True:
                self.register_utils.set_hardware_repeat(repeat_command)

            # get DC command for the first DC in the list, DC command is byte padded
            # fill CMD memory with DC command and scan loop command, inside the loop only overwrite DC command
            self.register_utils.set_command(command=self.register_utils.concatenate_commands((get_dc_address_command(enable_double_columns[0]), scan_loop_command), byte_padding=False))

            for index, dc in enumerate(enable_double_columns):
                if index != 0:  # full command is already set before loop
                    # get DC command before wait to save some time
                    dc_address_command = get_dc_address_command(dc)
                    self.register_utils.wait_for_command()
                    # only set command after FPGA is ready
                    # overwrite only the DC command in CMD memory
                    self.register_utils.set_command(dc_address_command, set_length=False)  # do not set length here, because it was already set up before the loop

                try:
                    bol_function()
                except TypeError:
                    pass

                if hardware_repeat == True:
                    self.register_utils.start_command()
                else:  # do this in software, much slower
                    for _ in range(repeat_command):
                        self.register_utils.start_command()

                try:
                    eol_function()
                except TypeError:
                    pass

            # wait here before we go on because we just jumped out of the loop
            self.register_utils.wait_for_command()

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

    def signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        logging.info('Pressed Ctrl-C. Stopping scan...')
        self.scan_aborted = False
        self.stop_thread_event.set()

    def save_configuration(self, configuation_name, configuration, **kwargs):
        if os.path.splitext(self.scan_data_filename)[1].strip().lower() != ".h5":
            h5_file = os.path.splitext(self.scan_data_filename)[0] + ".h5"

        # append to file if existing otherwise create new one
        #raw_data_file_h5 = tb.openFile(h5_file, mode="a", title=((self.module_id + "_" + self.scan_id) if self.module_id else self.scan_id) + "_" + str(self.scan_number), **kwargs)
        with tb.openFile(h5_file, mode="a", title=((self.module_id + "_" + self.scan_id) if self.module_id else self.scan_id) + "_" + str(self.scan_number), **kwargs) as raw_data_file_h5:
            try:
                scan_param_descr = generate_scan_configuration_description(dict.iterkeys(configuration))
                filter_tables = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
                self.scan_param_table = raw_data_file_h5.createTable(raw_data_file_h5.root, name=configuation_name, description=scan_param_descr, title='device_configuration', filters=filter_tables)
            except tb.exceptions.NodeError:
                self.scan_param_table = raw_data_file_h5.getNode(raw_data_file_h5.root, name=configuation_name)

            row_scan_param = self.scan_param_table.row

            for key, value in dict.iteritems(configuration):
                row_scan_param[key] = str(value)

            row_scan_param.append()

            self.scan_param_table.flush()

        #raw_data_file_h5.close()


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
                #logging.info('Keyboard interrupt: setting %s' % _lambda(self).__name__)
                _lambda(self).set()
        return wrapped_f
    return wrapper
