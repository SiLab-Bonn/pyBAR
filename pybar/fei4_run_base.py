import logging
import time
import re
import os
import string
import smtplib
import socket
import zmq
import numpy as np
from functools import wraps
from threading import Event, Thread
from Queue import Queue
from collections import namedtuple, Mapping
from contextlib import contextmanager
import abc
import ast
import inspect
from basil.dut import Dut

from pybar.run_manager import RunManager, RunBase, RunAborted, RunStopped, run_status
from pybar.fei4.register import FEI4Register
from pybar.fei4.register_utils import FEI4RegisterUtils, is_fe_ready
from pybar.daq.fifo_readout import FifoReadout, RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout
from pybar.daq.fei4_raw_data import open_raw_data_file
from pybar.analysis.analysis_utils import AnalysisError


class Fei4RunBase(RunBase):
    '''Basic FEI4 run meta class.

    Base class for scan- / tune- / analyze-class.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, conf, run_conf=None):
        # default run conf parameters added for all scans
        if 'comment' not in self._default_run_conf:
            self._default_run_conf.update({'comment': ''})
        if 'reset_rx_on_error' not in self._default_run_conf:
            self._default_run_conf.update({'reset_rx_on_error': False})

        super(Fei4RunBase, self).__init__(conf=conf, run_conf=run_conf)

        # default conf parameters
        if 'send_data' not in conf:
            conf.update({'send_data': None})
        if 'send_error_msg' not in conf:
            conf.update({'send_error_msg': None})

        self.err_queue = Queue()
        self.fifo_readout = None
        self.raw_data_file = None
        self.zmq_context = None
        self.socket = None

    @property
    def working_dir(self):
        if self.module_id:
            return os.path.join(self.conf['working_dir'], self.module_id)
        else:
            return os.path.join(self.conf['working_dir'], self.run_id)

    @property
    def dut(self):
        return self.conf['dut']

    @property
    def register(self):
        return self.conf['fe_configuration']

    @property
    def output_filename(self):
        if self.module_id:
            return os.path.join(self.working_dir, str(self.run_number) + "_" + self.module_id + "_" + self.run_id)
        else:
            return os.path.join(self.working_dir, str(self.run_number) + "_" + self.run_id)

    @property
    def module_id(self):
        if 'module_id' in self.conf and self.conf['module_id']:
            module_id = str(self.conf['module_id'])
            module_id = re.sub(r"[^\w\s+]", '', module_id)
            return re.sub(r"\s+", '_', module_id).lower()
        else:
            return None

    def init_dut(self):
        if self.dut.name == 'mio':
            if self.dut.get_modules('FEI4AdapterCard') and [adapter_card for adapter_card in self.dut.get_modules('FEI4AdapterCard') if adapter_card.name == 'ADAPTER_CARD']:
                self.dut['ADAPTER_CARD'].set_voltage('VDDA1', 1.5)
                self.dut['ADAPTER_CARD'].set_voltage('VDDA2', 1.5)
                self.dut['ADAPTER_CARD'].set_voltage('VDDD1', 1.2)
                self.dut['ADAPTER_CARD'].set_voltage('VDDD2', 1.2)
                self.dut['POWER_SCC']['EN_VD1'] = 1
                self.dut['POWER_SCC']['EN_VD2'] = 1  # also EN_VPLL on old SCAC
                self.dut['POWER_SCC']['EN_VA1'] = 1
                self.dut['POWER_SCC']['EN_VA2'] = 1
                self.dut['POWER_SCC'].write()
                # enabling readout
                self.dut['ENABLE_CHANNEL']['CH1'] = 0  # RD2Bar on SCAC
                self.dut['ENABLE_CHANNEL']['CH2'] = 0  # RD1Bar on SCAC
                self.dut['ENABLE_CHANNEL']['CH3'] = 0  # RABar on SCAC
                self.dut['ENABLE_CHANNEL']['CH4'] = 1
                self.dut['ENABLE_CHANNEL']['TLU'] = 1
                self.dut['ENABLE_CHANNEL']['TDC'] = 1
                self.dut['ENABLE_CHANNEL'].write()
            elif self.dut.get_modules('FEI4QuadModuleAdapterCard') and [adapter_card for adapter_card in self.dut.get_modules('FEI4QuadModuleAdapterCard') if adapter_card.name == 'ADAPTER_CARD']:
                # resetting over current status
                self.dut['POWER_QUAD']['EN_CH1'] = 0
                self.dut['POWER_QUAD']['EN_CH2'] = 0
                self.dut['POWER_QUAD']['EN_CH3'] = 0
                self.dut['POWER_QUAD']['EN_CH4'] = 0
                self.dut['POWER_QUAD'].write()
                self.dut['ADAPTER_CARD'].set_voltage('CH1', 2.1)
                self.dut['ADAPTER_CARD'].set_voltage('CH2', 2.1)
                self.dut['ADAPTER_CARD'].set_voltage('CH3', 2.1)
                self.dut['ADAPTER_CARD'].set_voltage('CH4', 2.1)
                self.dut['POWER_QUAD'].write()
                channel_names = [channel.name for channel in self.dut.get_modules('fei4_rx')]
                for channel in channel_names:
                    # enabling readout
                    self.dut['ENABLE_CHANNEL'][channel] = 1
                    self.dut['POWER_QUAD']['EN_' + channel] = 1
                self.dut['ENABLE_CHANNEL']['TLU'] = 1
                self.dut['ENABLE_CHANNEL']['TDC'] = 1
                self.dut['ENABLE_CHANNEL'].write()
                self.dut['POWER_QUAD'].write()
            else:
                logging.warning('Unknown adapter card')
                # do the minimal configuration here
                self.dut['ENABLE_CHANNEL']['CH1'] = 0  # RD2Bar on SCAC
                self.dut['ENABLE_CHANNEL']['CH2'] = 0  # RD1Bar on SCAC
                self.dut['ENABLE_CHANNEL']['CH3'] = 0  # RABar on SCAC
                self.dut['ENABLE_CHANNEL']['CH4'] = 1
                self.dut['ENABLE_CHANNEL']['TLU'] = 1
                self.dut['ENABLE_CHANNEL']['TDC'] = 1
                self.dut['ENABLE_CHANNEL'].write()

        elif self.dut.name == 'mio_gpac':
            # PWR
            self.dut['V_in'].set_current_limit(0.1, unit='A')  # one for all, max. 1A
            # V_in
            self.dut['V_in'].set_voltage(2.1, unit='V')
            self.dut['V_in'].set_enable(True)
            if self.dut["V_in"].get_over_current():
                self.power_off()
                raise Exception('V_in overcurrent detected')
            # Vdd, also enabling LVDS transceivers
            self.dut['CCPD_Vdd'].set_voltage(1.80, unit='V')
            self.dut['CCPD_Vdd'].set_enable(True)
            if self.dut["CCPD_Vdd"].get_over_current():
                self.power_off()
                raise Exception('Vdd overcurrent detected')
            # Vssa
            self.dut['CCPD_Vssa'].set_voltage(1.50, unit='V')
            self.dut['CCPD_Vssa'].set_enable(True)
            if self.dut["CCPD_Vssa"].get_over_current():
                self.power_off()
                raise Exception('Vssa overcurrent detected')
            # VGate
            self.dut['CCPD_VGate'].set_voltage(2.10, unit='V')
            self.dut['CCPD_VGate'].set_enable(True)
            if self.dut["CCPD_VGate"].get_over_current():
                self.power_off()
                raise Exception('VGate overcurrent detected')
            # enabling readout
            self.dut['ENABLE_CHANNEL']['FE'] = 1
            self.dut['ENABLE_CHANNEL']['TLU'] = 1
            self.dut['ENABLE_CHANNEL']['TDC'] = 1
            self.dut['ENABLE_CHANNEL']['CCPD_TDC'] = 1
            self.dut['ENABLE_CHANNEL'].write()
        elif self.dut.name == 'seabas2':
            channel_names = [channel.name for channel in self.dut.get_modules('fei4_rx')]
            for channel in channel_names:
                # enabling readout
                self.dut['ENABLE_CHANNEL'][channel] = 1
            self.dut['ENABLE_CHANNEL']['TLU'] = 1
            self.dut['ENABLE_CHANNEL'].write()
        elif self.dut.name == 'lx9':
            # enable LVDS RX/TX
            self.dut['I2C'].write(0xe8, [6, 0xf0, 0xff])
            self.dut['I2C'].write(0xe8, [2, 0x01, 0x00])  # select channels here
        elif self.dut.name == 'nexys4':
            # enable LVDS RX/TX
            self.dut['I2C'].write(0xe8, [6, 0xf0, 0xff])
            self.dut['I2C'].write(0xe8, [2, 0x0f, 0x00])  # select channels here

            self.dut['ENABLE_CHANNEL']['CH1'] = 0
            self.dut['ENABLE_CHANNEL']['CH2'] = 0
            self.dut['ENABLE_CHANNEL']['CH3'] = 0
            self.dut['ENABLE_CHANNEL']['CH4'] = 1
            self.dut['ENABLE_CHANNEL']['TLU'] = 1
            self.dut['ENABLE_CHANNEL']['TDC'] = 1
            self.dut['ENABLE_CHANNEL'].write()
        else:
            logging.warning('Omit initialization of DUT %s', self.dut.name)

    def init_fe(self):
        if 'fe_configuration' in self.conf:
            last_configuration = self._get_configuration()
            # init config, a number <=0 will also do the initialization (run 0 does not exists)
            if (not self.conf['fe_configuration'] and not last_configuration) or (isinstance(self.conf['fe_configuration'], (int, long)) and self.conf['fe_configuration'] <= 0):
                if 'chip_address' in self.conf and self.conf['chip_address']:
                    chip_address = self.conf['chip_address']
                    broadcast = False
                else:
                    chip_address = 0
                    broadcast = True
                if 'fe_flavor' in self.conf and self.conf['fe_flavor']:
                    self._conf['fe_configuration'] = FEI4Register(fe_type=self.conf['fe_flavor'], chip_address=chip_address, broadcast=broadcast)
                else:
                    raise ValueError('No fe_flavor given')
            # use existing config
            elif not self.conf['fe_configuration'] and last_configuration:
                self._conf['fe_configuration'] = FEI4Register(configuration_file=last_configuration)
            # path
            elif isinstance(self.conf['fe_configuration'], basestring):
                if os.path.isabs(self.conf['fe_configuration']):
                    fe_configuration = self.conf['fe_configuration']
                else:
                    fe_configuration = os.path.join(self.conf['working_dir'], self.conf['fe_configuration'])
                self._conf['fe_configuration'] = FEI4Register(configuration_file=fe_configuration)
            # run number
            elif isinstance(self.conf['fe_configuration'], (int, long)) and self.conf['fe_configuration'] > 0:
                self._conf['fe_configuration'] = FEI4Register(configuration_file=self._get_configuration(self.conf['fe_configuration']))
            # assume fe_configuration already initialized
            elif not isinstance(self.conf['fe_configuration'], FEI4Register):
                raise ValueError('No valid fe_configuration given')
            # init register utils
            self.register_utils = FEI4RegisterUtils(self.dut, self.register)
            # reset and configuration
            self.register_utils.global_reset()
            self.register_utils.configure_all()
            if is_fe_ready(self):
                reset_service_records = False
            else:
                reset_service_records = True
            self.register_utils.reset_bunch_counter()
            self.register_utils.reset_event_counter()
            if reset_service_records:
                # resetting service records must be done once after power up
                self.register_utils.reset_service_records()
        else:
            pass  # no fe_configuration

    def pre_run(self):
        # opening ZMQ context
        if isinstance(self.conf['send_data'], basestring):
            self.zmq_context = zmq.Context()
            self.socket = self.zmq_context.socket(zmq.PUB)  # publisher
            self.socket.bind(self.conf['send_data'])
            logging.info('Creating socket connection to server %s', self.conf['send_data'])
        # scan parameters
        if 'scan_parameters' in self.run_conf:
            if isinstance(self.run_conf['scan_parameters'], basestring):
                self.run_conf['scan_parameters'] = ast.literal_eval(self.run_conf['scan_parameters'])
            sp = namedtuple('scan_parameters', field_names=zip(*self.run_conf['scan_parameters'])[0])
            self.scan_parameters = sp(*zip(*self.run_conf['scan_parameters'])[1])
        else:
            sp = namedtuple_with_defaults('scan_parameters', field_names=[])
            self.scan_parameters = sp()
        logging.info('Scan parameter(s): %s', ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')

        # init DUT
        if not isinstance(self.conf['dut'], Dut):
            module_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
            if isinstance(self.conf['dut'], basestring):
                # dirty fix for Windows pathes
                self.conf['dut'] = os.path.normpath(self.conf['dut'].replace('\\', '/'))
                # abs path
                if os.path.isabs(self.conf['dut']):
                    dut = self.conf['dut']
                # working dir
                elif os.path.exists(os.path.join(self.conf['working_dir'], self.conf['dut'])):
                    dut = os.path.join(self.conf['working_dir'], self.conf['dut'])
                # path of this file
                elif os.path.exists(os.path.join(module_path, self.conf['dut'])):
                    dut = os.path.join(module_path, self.conf['dut'])
                else:
                    raise ValueError('dut file not found: %s' % self.conf['dut'])
                self._conf['dut'] = Dut(dut)
            else:
                self._conf['dut'] = Dut(self.conf['dut'])

            # only initialize when DUT was not initialized before
            if 'dut_configuration' in self.conf and self.conf['dut_configuration']:
                if isinstance(self.conf['dut_configuration'], basestring):
                    # dirty fix for Windows pathes
                    self.conf['dut_configuration'] = os.path.normpath(self.conf['dut_configuration'].replace('\\', '/'))
                    # abs path
                    if os.path.isabs(self.conf['dut_configuration']):
                        dut_configuration = self.conf['dut_configuration']
                    # working dir
                    elif os.path.exists(os.path.join(self.conf['working_dir'], self.conf['dut_configuration'])):
                        dut_configuration = os.path.join(self.conf['working_dir'], self.conf['dut_configuration'])
                    # path of dut file
                    elif os.path.exists(os.path.join(os.path.dirname(self.dut.conf_path), self.conf['dut_configuration'])):
                        dut_configuration = os.path.join(os.path.dirname(self.dut.conf_path), self.conf['dut_configuration'])
                    # path of this file
                    elif os.path.exists(os.path.join(module_path, self.conf['dut_configuration'])):
                        dut_configuration = os.path.join(module_path, self.conf['dut_configuration'])
                    else:
                        raise ValueError('dut_configuration file not found: %s' % self.conf['dut_configuration'])
                    # make dict
                    dut_configuration = RunManager.open_conf(dut_configuration)
                    # change bit file path
                    if 'USB' in dut_configuration and 'bit_file' in dut_configuration['USB'] and dut_configuration['USB']['bit_file']:
                        bit_file = os.path.normpath(dut_configuration['USB']['bit_file'].replace('\\', '/'))
                        # abs path
                        if os.path.isabs(bit_file):
                            pass
                        # working dir
                        elif os.path.exists(os.path.join(self.conf['working_dir'], bit_file)):
                            bit_file = os.path.join(self.conf['working_dir'], bit_file)
                        # path of dut file
                        elif os.path.exists(os.path.join(os.path.dirname(self.dut.conf_path), bit_file)):
                            bit_file = os.path.join(os.path.dirname(self.dut.conf_path), bit_file)
                        # path of this file
                        elif os.path.exists(os.path.join(module_path, bit_file)):
                            bit_file = os.path.join(module_path, bit_file)
                        else:
                            raise ValueError('bit_file not found: %s' % bit_file)
                        dut_configuration['USB']['bit_file'] = bit_file
                    self.dut.init(dut_configuration)
                else:
                    self.dut.init(self.conf['dut_configuration'])
            else:
                self.dut.init()
            # additional init of the DUT
            self.init_dut()
        else:
            pass  # do nothing, already initialized
        # FIFO readout
        self.fifo_readout = FifoReadout(self.dut)
        # initialize the FE
        self.init_fe()

    def do_run(self):
        with self.register.restored(name=self.run_number):
            # configure for scan
            self.configure()
            self.fifo_readout.reset_rx()
            self.fifo_readout.reset_sram_fifo()
            self.fifo_readout.print_readout_status()
            with open_raw_data_file(filename=self.output_filename, mode='w', title=self.run_id, register=self.register, conf=self.conf, run_conf=self.run_conf, scan_parameters=self.scan_parameters._asdict(), socket=self.socket) as self.raw_data_file:
                # scan
                self.scan()

    def post_run(self):
        try:
            self.fifo_readout.print_readout_status()
        # no device?
        except Exception:
            pass

        if not self.err_queue.empty():
            exc = self.err_queue.get()
            # well known errors
            if isinstance(exc[1], (RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout)):
                raise RunAborted(exc[1])
            # some other error via handle_err(), print to crash.log
            else:
                raise exc[0], exc[1], exc[2]
        elif self.abort_run.is_set():
            raise RunAborted('Read the log')

        # analyzing data
        try:
            self.analyze()
        # known errors
        except AnalysisError as e:
            logging.error('Analysis of data failed: %s', e)
            raise RunAborted('Read the log')
        # analyzed data, save config
        else:
            self.register.save_configuration(self.output_filename)

        # other reasons
        if self.stop_run.is_set():
            raise RunStopped('Read the log')

    def cleanup_run(self):
        # no execption should be thrown here
        self.raw_data_file = None
        # USB interface needs to be closed here, otherwise an USBError may occur
        # USB interface can be reused at any time after close without another init
        try:
            usb_intf = self.dut.get_modules('SiUsb')
        except AttributeError:
            pass  # not yet initialized
        else:
            if usb_intf:
                import usb.core
                for board in usb_intf:
                    try:
                        board.close()  # free resources of USB
                    except usb.core.USBError:
                        logging.error('Cannot close USB device')
                    except ValueError:
                        pass  # no USB interface, Basil <= 2.1.1
                    except KeyError:
                        pass  # no USB interface, Basil > 2.1.1
                    except TypeError:
                        pass  # DUT not yet initialized
                    except AttributeError:
                        pass  # USB interface not yet initialized
                    else:
                        pass
#                         logging.error('Closed USB device')

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), flush=False)

    def handle_err(self, exc):
        if self.reset_rx_on_error and isinstance(exc[1], (RxSyncError, EightbTenbError)):
            self.fifo_readout.print_readout_status()
            self.fifo_readout.reset_rx()
        else:
            self.err_queue.put(exc)
            self.abort(msg='%s' % exc[1])

    def _get_configuration(self, run_number=None):
        def find_file(run_number):
            for root, _, files in os.walk(self.working_dir):
                for cfgfile in files:
                    cfg_root, cfg_ext = os.path.splitext(cfgfile)
                    if cfg_root.startswith(''.join([str(run_number), '_', self.module_id])) and cfg_ext.endswith(".cfg"):
                        return os.path.join(root, cfgfile)

        if not run_number:
            run_numbers = sorted(self._get_run_numbers(status='FINISHED').iterkeys(), reverse=True)
            for run_number in run_numbers:
                cfg_file = find_file(run_number)
                if cfg_file:
                    return cfg_file
        else:
            cfg_file = find_file(run_number)
            if cfg_file:
                return cfg_file
            else:
                raise ValueError('Found no configuration with run number %s' % run_number)

    def set_scan_parameters(self, *args, **kwargs):
        fields = dict(kwargs)
        for index, field in enumerate(self.scan_parameters._fields):
            try:
                value = args[index]
            except IndexError:
                break
            else:
                if field in fields:
                    raise TypeError('Got multiple values for keyword argument %s' % field)
                fields[field] = value
        scan_parameters_old = self.scan_parameters._asdict()
        self.scan_parameters = self.scan_parameters._replace(**fields)
        scan_parameters_new = self.scan_parameters._asdict()
        diff = [name for name in scan_parameters_old.keys() if np.any(scan_parameters_old[name] != scan_parameters_new[name])]
        if diff:
            logging.info('Changing scan parameter(s): %s', ', '.join([('%s=%s' % (name, fields[name])) for name in diff]))

    @contextmanager
    def readout(self, *args, **kwargs):
        timeout = kwargs.pop('timeout', 10.0)
        self.start_readout(*args, **kwargs)
        try:
            yield
            self.stop_readout(timeout=timeout)
        finally:
            # in case something fails, call this on last resort
            if self.fifo_readout.is_running:
                self.fifo_readout.stop(timeout=0.0)

    def start_readout(self, *args, **kwargs):
        # Pop parameters for fifo_readout.start
        callback = kwargs.pop('callback', self.handle_data)
        clear_buffer = kwargs.pop('clear_buffer', False)
        fill_buffer = kwargs.pop('fill_buffer', False)
        reset_sram_fifo = kwargs.pop('reset_sram_fifo', False)
        errback = kwargs.pop('errback', self.handle_err)
        no_data_timeout = kwargs.pop('no_data_timeout', None)
        if args or kwargs:
            self.set_scan_parameters(*args, **kwargs)
        self.fifo_readout.start(reset_sram_fifo=reset_sram_fifo, fill_buffer=fill_buffer, clear_buffer=clear_buffer, callback=callback, errback=errback, no_data_timeout=no_data_timeout)

    def stop_readout(self, timeout=10.0):
        self.fifo_readout.stop(timeout=timeout)

    def _cleanup(self):  # called in run base after exception handling
        if self.conf['send_error_msg'] and self._run_status == run_status.crashed:
            try:
                import requests
                ip = requests.request('GET', 'http://myip.dnsomatic.com').text
            except ImportError:
                ip = 'Unknown IP'
            try:
                text = 'Run %i at %s\n%s' % (self.run_number, time.strftime('%X %x %Z'), self.last_traceback)
                send_mail(text=text, configuration=self._run_conf['send_error'], subject='PyBAR run %i report from %s %s' % (self.run_number, ip, socket.gethostname()))
            except:
                logging.info("Failed sending pyBAR report")
                pass
        super(Fei4RunBase, self)._cleanup()

    @abc.abstractmethod
    def configure(self):
        '''Implementation of the run configuration.

        Will be executed before starting the scan routine.
        '''
        pass

    @abc.abstractmethod
    def scan(self):
        '''Implementation of the scan routine.

        Do you want to write your own scan? Here is the place to begin.
        '''
        pass

    @abc.abstractmethod
    def analyze(self):
        '''Implementation of run data processing.

        Will be executed after finishing the scan routine.
        '''
        pass


def timed(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time()
        result = f(*args, **kwargs)
        elapsed = time() - start
        print "%s took %fs to finish" % (f.__name__, elapsed)
        return result
    return wrapper


def interval_timed(interval):
    '''Interval timer decorator.

    Taken from: http://stackoverflow.com/questions/12435211/python-threading-timer-repeat-function-every-n-seconds/12435256
    '''
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            stopped = Event()

            def loop():  # executed in another thread
                while not stopped.wait(interval):  # until stopped
                    f(*args, **kwargs)

            t = Thread(name='IntervalTimerThread', target=loop)
            t.daemon = True  # stop if the program exits
            t.start()
            return stopped.set
        return wrapper
    return decorator


def interval_timer(interval, func, *args, **kwargs):
    '''Interval timer function.

    Taken from: http://stackoverflow.com/questions/22498038/improvement-on-interval-python/22498708
    '''
    stopped = Event()

    def loop():
        while not stopped.wait(interval):  # the first call is after interval
            func(*args, **kwargs)

    Thread(name='IntervalTimerThread', target=loop).start()
    return stopped.set


def namedtuple_with_defaults(typename, field_names, default_values=None):
    '''
    Namedtuple with defaults

    From: http://stackoverflow.com/questions/11351032/named-tuple-and-optional-keyword-arguments

    Usage:
    >>> Node = namedtuple_with_defaults('Node', ['val', 'left' 'right'])
    >>> Node()
    >>> Node = namedtuple_with_defaults('Node', 'val left right')
    >>> Node()
    Node(val=None, left=None, right=None)
    >>> Node = namedtuple_with_defaults('Node', 'val left right', [1, 2, 3])
    >>> Node()
    Node(val=1, left=2, right=3)
    >>> Node = namedtuple_with_defaults('Node', 'val left right', {'right':7})
    >>> Node()
    Node(val=None, left=None, right=7)
    >>> Node(4)
    Node(val=4, left=None, right=7)
    '''
    if default_values is None:
        default_values = []
    T = namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T


def send_mail(text, configuration, subject=''):
    ''' Sends a run status mail with the traceback to a specified E-Mail address if a run crashes.
    '''
    logging.info('Send status E-Mail (' + subject + ')')
    body = string.join((
        "From: %s" % configuration['email_account'][0],
        "To: %s" % str(configuration['email_to']).strip('[]'),
        "Subject: %s" % subject,
        "",
        text),
        "\r\n")
    server = smtplib.SMTP_SSL(configuration['email_host'])
    server.login(configuration['email_account'][0], configuration['email_account'][1])
    server.sendmail(configuration['email_account'][0], configuration['email_to'], body)
    server.quit()
