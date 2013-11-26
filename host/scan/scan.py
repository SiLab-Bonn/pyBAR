import time
import os
import logging
import re

from threading import Thread, Event, Lock, Timer

min_pysilibusb_version = '0.1.2'
from SiLibUSB import SiUSBDevice, __version__ as pysilibusb_version
from distutils.version import StrictVersion as v
if v(pysilibusb_version) < v(min_pysilibusb_version):
    raise ImportError('Wrong pySiLibUsb version (installed=%s, minimum expected=%s)' % (pysilibusb_version, min_pysilibusb_version))

from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from daq.readout_utils import ReadoutUtils
from daq.readout import Readout

import signal
import BitVector

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class ScanBase(object):
    # TODO: implement callback for stop() & analyze()
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="base_scan", scan_data_path=None):
        # fixing event handler: http://stackoverflow.com/questions/15457786/ctrl-c-crashes-python-after-importing-scipy-stats
        if os.name == 'nt':
            import thread

            def handler(signum, hook=thread.interrupt_main):
                hook()
                return True
            import win32api
            win32api.SetConsoleCtrlHandler(handler, 1)
        if device is not None:
            #if isinstance(device, usb.core.Device):
            if isinstance(device, SiUSBDevice):
                self.device = device
            else:
                raise TypeError('Device has wrong type')
        else:
            self.device = SiUSBDevice()
        logging.info('Found USB board with ID %s', self.device.board_id)
        if bit_file != None:
            logging.info('Programming FPGA: %s' % bit_file)
            self.device.DownloadXilinx(bit_file)
            time.sleep(1)

        self.readout = Readout(self.device)
        self.readout_utils = ReadoutUtils(self.device)

        self.register = FEI4Register(config_file, definition_file=definition_file)
        self.register_utils = FEI4RegisterUtils(self.device, self.readout, self.register)

        if scan_data_path == None:
            self.scan_data_path = os.getcwd()
        else:
            self.scan_data_path = scan_data_path
        self.scan_identifier = scan_identifier.lstrip('/\\')  # remove leading slashes, prevent problems with os.path.join
        self.scan_number = None
        self.scan_data_filename = None
        self.scan_completed = False

        self.lock = Lock()

        self.scan_thread = None
        self.stop_thread_event = Event()
        self.stop_thread_event.set()
        self.use_thread = None
        self.restore_configuration = None

    @property
    def is_running(self):
        return self.scan_thread.is_alive()

    def configure(self):
        logging.info('Sending configuration to FE')
        #scan.register.load_configuration_file(config_file)
        self.register_utils.configure_all(same_mask_for_all_dc=False, do_global_rest=True)

    def start(self, configure=True, restore_configuration=False, use_thread=False, **kwargs):  # TODO: in Python 3 use def func(a,b,*args,kw1=None,**kwargs)
        '''Starting scan.

        Parameters
        ----------
        configure : bool
            If true, configure FE before starting scan.scan().
        restore_configuration : bool
            Restore FE configuration after finishing scan.scan().
        use_thread : bool
            If true, scan.scan() is running in a separate thread. Only then Ctrl-C can be used to interrupt scan loop.
        **kwargs : any
            Any keyword argument passed to scan.start() will be forwarded to scan.scan().
        '''
        self.scan_completed = False
        self.use_thread = use_thread
        if self.scan_thread != None:
            raise RuntimeError('Scan thread is already running')

        self.write_scan_number()

        if configure:
            self.configure()
        self.restore_configuration = restore_configuration
        if self.restore_configuration:
            self.register.create_restore_point(name=self.scan_identifier)

        self.readout.reset_rx()
#        self.readout.reset_sram_fifo()

        if not any(self.readout.print_readout_status()):
            self.device.dispose()  # free USB resources
            raise NoSyncError('No data sync on any input channel. Power? Cables?')
#             logging.error('Stopping scan: no sync')
#             return

        self.stop_thread_event.clear()

        logging.info('Starting scan %s with ID %d (output path: %s)' % (self.scan_identifier, self.scan_number, self.scan_data_path))
        if use_thread:
            self.scan_thread = Thread(target=self.scan, name='%s with ID %d' % (self.scan_identifier, self.scan_number), kwargs=kwargs)  # , args=kwargs)
            self.scan_thread.daemon = True  # Abruptly close thread when closing main thread. Resources may not be released properly.
            self.scan_thread.start()
            logging.info('Press Ctrl-C to stop scan loop')
            signal.signal(signal.SIGINT, self.signal_handler)
        else:
            self.scan(**kwargs)

    def stop(self, timeout=None):
        '''Stopping scan. Cleaning up of variables and joining thread (if existing).

        '''
        self.scan_completed = True
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
                self.scan_completed = False

            timeout_timer = Timer(timeout, stop_thread)  # could also use shed.scheduler() here
            if timeout:
                timeout_timer.start()
            try:
                while self.scan_thread.is_alive() and not self.stop_thread_event.wait(1):
                    pass
            except IOError:  # catching "IOError: [Errno4] Interrupted function call" because of wait_timeout_event.wait()
                logging.exception('Event handler problem?')
                raise

            timeout_timer.cancel()
            signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler
            self.stop_thread_event.set()

            self.scan_thread.join()  # SIGINT will be suppressed here
            self.scan_thread = None
        self.use_thread = None
        if self.restore_configuration:
            logging.info('Restoring FE configuration')
            self.register.restore(name=self.scan_identifier)
            self.configure()
        logging.info('Stopped scan %s with ID %d' % (self.scan_identifier, self.scan_number))
        self.readout.print_readout_status()

        self.device.dispose()  # free USB resources
        self.write_scan_status(self.scan_completed)
        return self.scan_completed

    def write_scan_number(self):
        scan_numbers = {}
        self.lock.acquire()
        if not os.path.exists(self.scan_data_path):
            os.makedirs(self.scan_data_path)
        with open(os.path.join(self.scan_data_path, self.scan_identifier + ".cfg"), "a+") as f:
            for line in f.readlines():
                scan_number = int(re.findall(r'\d+\s', line)[0])
                scan_numbers[scan_number] = line
        if not scan_numbers:
            self.scan_number = 0
        else:
            self.scan_number = max(dict.iterkeys(scan_numbers)) + 1
        scan_numbers[self.scan_number] = str(self.scan_number) + '\n'
        with open(os.path.join(self.scan_data_path, self.scan_identifier + ".cfg"), "w") as f:
            for value in dict.itervalues(scan_numbers):
                f.write(value)
        self.lock.release()
        self.scan_data_filename = os.path.join(self.scan_data_path, self.scan_identifier + "_" + str(self.scan_number))

    def write_scan_status(self, finished=True):
        scan_numbers = {}
        self.lock.acquire()
        with open(os.path.join(self.scan_data_path, self.scan_identifier + ".cfg"), "r") as f:
            for line in f.readlines():
                scan_number = int(re.findall(r'\d+\s', line)[0])
                if scan_number != self.scan_number:
                    scan_numbers[scan_number] = line
                else:
                    scan_numbers[scan_number] = line.strip() + (' SUCCESS\n' if finished else ' ABORTED\n')
        with open(os.path.join(self.scan_data_path, self.scan_identifier + ".cfg"), "w") as f:
            for value in dict.itervalues(scan_numbers):
                f.write(value)
        self.lock.release()

    def scan_loop(self, command, repeat_command=100, hardware_repeat=True, mask_steps=3, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=False, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None):
        '''Implementation of the scan loops (mask shifting, loop over double columns, repeatedly sending any arbitrary command).

        Parameters
        ----------
        command : BitVector
            (FEI4) command that will be sent out serially.
        repeat_command : int
            The number of repetitions command will be sent out each mask step.
        hardware_repeat : bool
            If true, use FPGA to repeat commands. In general this is much faster than doing this in software.
        mask_steps : int
            Number of mask steps.
        enable_mask_steps : list, tuple
            List of mask steps which will be applied. Default is all mask steps. From 0 to (mask-1). A value equal None or empty list will select all mask steps.
        enable_double_columns : list, tuple
            List of double columns which will be enabled during scan. Default is all double columns. From 0 to 39 (double columns counted from zero). A value equal None or empty list will select all double columns.
        same_mask_for_all_dc : bool
            Use same mask for all double columns. Enabling this is in general not a good idea since all double columns will have the same configuration but the scan speed can increased by an order of magnitude.
        eol_function : function
            End of loop function that will be called each time the innermost loop ends.
        digital_injection : bool
            Enables digital injection.
        enable_c_high : bool
            Enables C_High pixel mask. No change if value is equal None. Note: will be overwritten during mask shifting if in shift_masks.
        enable_c_low : bool
            Enables C_Low pixel mask. No change if value is equal None. Note: will be overwritten during mask shifting if in shift_masks.
        shift_masks : list, tuple
            List of pixel masks that will be shifted.
        restore_shift_masks : bool
            Writing the initial (restored) FE pixel configuration into FE after finishing the scan loop.
        mask : array-like
            Additional mask. Must be convertible to an array of booleans with the same shape as mask array. True indicates a masked (i.e. invalid) data. Masked pixels will be selected (enabled) during mask shifting.
        '''
        if not isinstance(command, BitVector.BitVector):
            raise TypeError

        # create restore point
        restore_point_name = self.scan_identifier + '_scan'
        self.register.create_restore_point(name=restore_point_name)

        # pre-calculate often used commands
        conf_mode_command = self.register.get_commands("confmode")
        run_mode_command = self.register.get_commands("runmode")

        if enable_mask_steps == None or not enable_mask_steps:
            enable_mask_steps = range(mask_steps)

        if enable_double_columns == None or not enable_double_columns:
            enable_double_columns = range(40)

        # preparing for scan
        commands = []
        commands.extend(conf_mode_command)
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
        self.register_utils.send_commands(commands)

        for mask_step in enable_mask_steps:
            commands = []
            commands.extend(conf_mode_command)
            curr_mask = self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step, mask=mask)
            #plt.imshow(np.transpose(curr_mask), interpolation='nearest', aspect="auto")
            #plt.pcolor(np.transpose(curr_mask))
            #plt.colorbar()
            #plt.savefig('mask_step'+str(mask_step)+'.eps')
            map(lambda mask_name: self.register.set_pixel_register_value(mask_name, curr_mask), [shift_mask_name for shift_mask_name in shift_masks if (shift_mask_name.lower() != "EnableDigInj".lower())])
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=same_mask_for_all_dc, name=shift_masks))
            if digital_injection == True:  # TODO: write EnableDigInj to FE or do it manually?
                self.register.set_pixel_register_value("EnableDigInj", curr_mask)
                commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=same_mask_for_all_dc, name=["EnableDigInj"]))
                self.register.set_global_register_value("DIGHITIN_SEL", 1)
                commands.extend(self.register.get_commands("wrregister", name=["DIGHITIN_SEL"]))  # write DIGHITIN_SEL mask last
#             else:
#                 commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=["EnableDigInj"]))
            self.register_utils.send_commands(commands)
            logging.info('%d injection(s): mask step %d' % (repeat_command, mask_step))

            for dc in enable_double_columns:
                commands = []
                #commands.extend(conf_mode_command)
                self.register.set_global_register_value("Colpr_Addr", dc)
                # pack all commands into one bit vector, speeding up of inner loop
                #commands.append(conf_mode_command[0]+BitVector.BitVector(size = 10)+self.register.get_commands("wrregister", name = ["Colpr_Addr"])[0]+BitVector.BitVector(size = 10)+run_mode_command[0])
                commands.append(conf_mode_command[0] + self.register.get_commands("wrregister", name=["Colpr_Addr"])[0] + run_mode_command[0])
                #commands.extend(self.register.get_commands("wrregister", name=["Colpr_Addr"]))
                #commands.extend(run_mode_command)
                self.register_utils.wait_for_command(wait_for_cmd=True)
                self.register_utils.send_commands(commands)

                #print repeat_command, 'injections:', 'mask step', mask_step, 'dc', dc
                bit_length = self.register_utils.set_command(command)
                if hardware_repeat == True:
                    self.register_utils.send_command(repeat=repeat_command, wait_for_cmd=False, command_bit_length=bit_length)
                else:
                    for _ in range(repeat_command):
                        self.register_utils.send_command()
                try:
                    eol_function()
                except TypeError:
                    pass

            self.register_utils.wait_for_command(wait_for_cmd=True)

        # restoring default values
        self.register.restore(name=restore_point_name)
        self.register_utils.configure_global()  # always restore global configuration
        if restore_shift_masks:
            commands = []
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=shift_masks))
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name="EnableDigInj"))
            self.register_utils.send_commands(commands)

    def scan(self, **kwargs):
        raise NotImplementedError('scan.scan() not implemented')

    def analyze(self, **kwargs):
        raise NotImplementedError('scan.analyze() not implemented')

    def signal_handler(self, signum, frame):
        signal.signal(signal.SIGINT, signal.SIG_DFL)  # setting default handler... pressing Ctrl-C a second time will kill application
        logging.info('Pressed Ctrl-C. Stopping scan...')
        self.scan_completed = False
        self.stop_thread_event.set()


class NoSyncError(Exception):
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
