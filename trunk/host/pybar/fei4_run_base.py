import logging
from time import time
import re
import os
import sys
from functools import wraps
from threading import Event, Thread
from Queue import Queue
import tables as tb
from collections import namedtuple, Mapping
from contextlib import contextmanager
import abc
import inspect
from basil.dut import Dut

from pybar.run_manager import RunBase, RunAborted
from pybar.fei4.register import FEI4Register
from pybar.fei4.register_utils import FEI4RegisterUtils
from pybar.daq.fifo_readout import FifoReadout, RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout
from pybar.daq.fei4_raw_data import open_raw_data_file
from pybar.analysis.analyze_raw_data import AnalysisError, IncompleteInputError, NotSupportedError
from pybar.analysis.RawDataConverter.data_struct import NameValue


class Fei4RunBase(RunBase):
    '''Basic FEI4 run meta class.

    Base class for scan- / tune- / analyze-class.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, conf, run_conf=None):
        super(Fei4RunBase, self).__init__(conf=conf, run_conf=run_conf)

        self.err_queue = Queue()

        self.fifo_readout = None
        self.register_utils = None

        self.raw_data_file = None

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
            module_id = self.conf['module_id']
            module_id = re.sub(r"[^\w\s+]", '', module_id)
            return re.sub(r"\s+", '_', module_id).lower()
        else:
            return None

    def _run(self):
        if 'scan_parameters' in self.run_conf:
            sp = namedtuple('scan_parameters', field_names=self.run_conf['scan_parameters'].iterkeys())
            self.scan_parameters = sp(**self.run_conf['scan_parameters'])
        else:
            sp = namedtuple_with_defaults('scan_parameters', field_names=[])
            self.scan_parameters = sp()
        logging.info('Scan parameter(s): %s' % (', '.join(['%s:%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None'))

        try:
            if 'fe_configuration' in self.conf and self.conf['fe_configuration']:
                if not isinstance(self.conf['fe_configuration'], FEI4Register):
                    if isinstance(self.conf['fe_configuration'], basestring):
                        if os.path.isabs(self.conf['fe_configuration']):
                            fe_configuration = self.conf['fe_configuration']
                        else:
                            fe_configuration = os.path.join(self.conf['working_dir'], self.conf['fe_configuration'])
                        self._conf['fe_configuration'] = FEI4Register(configuration_file=fe_configuration)
                    elif isinstance(self.conf['fe_configuration'], (int, long)) and self.conf['fe_configuration'] >= 0:
                        self._conf['fe_configuration'] = FEI4Register(configuration_file=self._get_configuration(self.conf['fe_configuration']))
                    else:
                        self._conf['fe_configuration'] = FEI4Register(configuration_file=self._get_configuration())
                else:
                    pass  # do nothing, already initialized
            else:
                self._conf['fe_configuration'] = FEI4Register(configuration_file=self._get_configuration())

            if not isinstance(self.conf['dut'], Dut):
                if isinstance(self.conf['dut'], basestring):
                    if os.path.isabs(self.conf['dut']):
                        dut = self.conf['dut']
                    else:
                        dut = os.path.join(self.conf['working_dir'], self.conf['dut'])
                    self._conf['dut'] = Dut(dut)
                else:
                    self._conf['dut'] = Dut(self.conf['dut'])
                module_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
                if 'dut_configuration' in self.conf and self.conf['dut_configuration']:
                    if isinstance(self.conf['dut_configuration'], basestring):
                        if os.path.isabs(self.conf['dut_configuration']):
                            dut_configuration = self.conf['dut_configuration']
                        else:
                            dut_configuration = os.path.join(self.conf['working_dir'], self.conf['dut_configuration'])
                        self.dut.init(dut_configuration)
                    else:
                        self.dut.init(self.conf['dut_configuration'])
                elif self.dut.name == 'usbpix':
                    self.dut.init(os.path.join(module_path, 'dut_configuration_usbpix.yaml'))
                elif self.dut.name == 'usbpix_gpac':
                    self.dut.init(os.path.join(module_path, 'dut_configuration_usbpix_gpac.yaml'))
                else:
                    logging.warning('Omit initialization of DUT')
                if self.dut.name == 'usbpix':
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
                elif self.dut.name == 'usbpix_gpac':
                    # enabling LVDS transceivers
                    self.dut['CCPD_Vdd'].set_enable(False)
                    self.dut['CCPD_Vdd'].set_current_limit(1000, unit='mA')
                    self.dut['CCPD_Vdd'].set_voltage(0.0, unit='V')
                    self.dut['CCPD_Vdd'].set_enable(True)
                    # enabling V_in
                    self.dut['V_in'].set_enable(False)
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
                    logging.warning('Unknown DUT name: %s. DUT may not be set up properly' % self.dut.name)

            else:
                pass  # do nothing, already initialized

            if not self.fifo_readout:
                self.fifo_readout = FifoReadout(self.dut)
            if not self.register_utils:
                self.register_utils = FEI4RegisterUtils(self.dut, self.register)
            with open_raw_data_file(filename=self.output_filename, mode='w', title=self.run_id, scan_parameters=self.scan_parameters._asdict()) as self.raw_data_file:
                self.save_configuration_dict(self.raw_data_file.h5_file, 'conf', self.conf)
                self.save_configuration_dict(self.raw_data_file.h5_file, 'run_conf', self.run_conf)
                self.register_utils.global_reset()
                self.register_utils.configure_all()
                self.register_utils.reset_bunch_counter()
                self.register_utils.reset_event_counter()
                self.register_utils.reset_service_records()
                with self.register.restored(name=self.run_number):
                    self.configure()
                    self.register.save_configuration_to_hdf5(self.raw_data_file.h5_file)
                    self.fifo_readout.reset_rx()
                    self.fifo_readout.reset_sram_fifo()
                    self.fifo_readout.print_readout_status()
                    self.scan()
        except Exception:
            self.handle_err(sys.exc_info())
        else:
            try:
                if self.abort_run.is_set():
                    raise RunAborted('Do not analyze data.')
                self.analyze()
            except (AnalysisError, IncompleteInputError, NotSupportedError) as e:
                logging.error('Analysis of raw data failed: %s' % e)
            except Exception:
                self.handle_err(sys.exc_info())
            else:
                self.register.save_configuration(self.output_filename)
        finally:
            self.raw_data_file = None
            try:
                self.fifo_readout.print_readout_status()
            except Exception:
                pass
            try:
                self.dut['USB'].close()  # free USB resources
            except Exception:
                logging.error('Cannot close USB device')
        if not self.err_queue.empty():
            exc = self.err_queue.get()
            if isinstance(exc[1], (RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout)):
                raise RunAborted(exc[1])
            else:
                raise exc[0], exc[1], exc[2]

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), flush=False)

    def handle_err(self, exc):
        self.err_queue.put(exc)
        self.abort(msg='%s' % exc[1])

    def _get_configuration(self, run_number=None):
        if not run_number:
            run_numbers = self._get_run_numbers(status='FINISHED')
            if run_numbers:
                run_number = max(dict.iterkeys(run_numbers))
            else:
                raise ValueError('Found no valid configuration')
        for root, dirs, files in os.walk(self.working_dir):
            for cfgfile in files:
                cfg_root, cfg_ext = os.path.splitext(cfgfile)
                if cfg_root.startswith(''.join([str(run_number), '_', self.module_id])) and cfg_ext.endswith(".cfg"):
                    return os.path.join(root, cfgfile)
        raise ValueError('Found no configuration with run number %s' % run_number)

    def set_scan_parameters(self, **kwargs):
        self.scan_parameters = self.scan_parameters._replace(**kwargs)

    @contextmanager
    def readout(self, **kwargs):
        self.start_readout(**kwargs)
        try:
            yield
            self.stop_readout()
        finally:
            # in case something fails, call this on last resort
            if self.fifo_readout.is_running:
                self.fifo_readout.stop(timeout=0.0)

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err)

    def stop_readout(self):
        self.fifo_readout.stop()

    def save_configuration_dict(self, h5_file, configuation_name, configuration, **kwargs):
        '''Stores any configuration dictionary to HDF5 file.

        Parameters
        ----------
        h5_file : string, file
            Filename of the HDF5 configuration file or file object.
        configuation_name : str
            Configuration name. Will be used for table name.
        configuration : dict
            Configuration dictionary.
        '''
        def save_conf():
            try:
                h5_file.removeNode(h5_file.root.configuration, name=configuation_name)
            except tb.NodeError:
                pass
            try:
                configuration_group = h5_file.create_group(h5_file.root, "configuration")
            except tb.NodeError:
                configuration_group = h5_file.root.configuration
            self.scan_param_table = h5_file.createTable(configuration_group, name=configuation_name, description=NameValue, title=configuation_name)

            row_scan_param = self.scan_param_table.row

            for key, value in dict.iteritems(configuration):
                row_scan_param['name'] = key
                row_scan_param['value'] = str(value)
                row_scan_param.append()

            self.scan_param_table.flush()

        if isinstance(h5_file, tb.file.File):
            save_conf()
        else:
            if os.path.splitext(h5_file)[1].strip().lower() != ".h5":
                h5_file = os.path.splitext(h5_file)[0] + ".h5"
            with tb.open_file(h5_file, mode="a", title='', **kwargs) as h5_file:
                save_conf()

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


def namedtuple_with_defaults(typename, field_names, default_values=[]):
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
    T = namedtuple(typename, field_names)
    T.__new__.__defaults__ = (None,) * len(T._fields)
    if isinstance(default_values, Mapping):
        prototype = T(**default_values)
    else:
        prototype = T(*default_values)
    T.__new__.__defaults__ = tuple(prototype)
    return T
