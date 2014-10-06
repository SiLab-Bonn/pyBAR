import re
import os
import sys
from functools import wraps
from threading import Event, Thread
from Queue import Queue
from time import time
import tables as tb
from analysis.RawDataConverter.data_struct import NameValue
from basil.dut import Dut
from fei4.register import FEI4Register
from fei4.register_utils import FEI4RegisterUtils
from daq.readout import DataReadout, RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout, open_raw_data_file
from collections import namedtuple, Mapping
from contextlib import contextmanager
from run_manager import RunBase, RunAborted
import abc
import logging

punctuation = """!,.:;?"""


class ScanBase(RunBase):
    '''Implementation of the base scan.

    Base class for scan- / tune- / analyze-classes.
    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, working_dir, fe_configuration=None, dut_configuration=None, scan_configuration=None, **kwargs):
        self.fe_configuration = fe_configuration
        self.dut_configuration = dut_configuration
        sc = namedtuple('scan_configuration', field_names=self.default_scan_configuration.iterkeys())
        self.scan_configuration = sc(**self.default_scan_configuration)
        if scan_configuration:
            self.scan_configuration = self.scan_configuration._replace(**scan_configuration)._asdict()
        else:
            self.scan_configuration = self.scan_configuration._asdict()
        self.__dict__.update(self.scan_configuration)
        self.scan_parameters = {}
        if 'scan_parameters' in self.scan_configuration:
            sp = namedtuple('scan_parameters', field_names=self.scan_configuration['scan_parameters'].iterkeys())
            self.scan_parameters = sp(**self.scan_configuration['scan_parameters'])
        else:
            sp = namedtuple_with_defaults('scan_parameters', field_names=[])
            self.scan_parameters = sp()

        self.stop_run = Event()
        self.err_queue = Queue()

        self.data_readout = None
        self.register_utils = None
        if self.module_id:
            super(ScanBase, self).__init__(os.path.join(working_dir, self.module_id))
        else:
            super(ScanBase, self).__init__(working_dir)

        self.raw_data_file = None

    @abc.abstractproperty
    def _scan_id(self):
        '''Scan name
        '''
        pass

    @property
    def scan_id(self):
        '''Scan name
        '''
        if not self._scan_id:
            return type(self).__name__
        else:
            scan_id = self._scan_id
            scan_id = re.sub(r"[^\w\s+]", '', scan_id)
            return re.sub(r"\s+", '_', scan_id).lower()

    @abc.abstractproperty
    def _default_scan_configuration(self):
        '''Default scan configuration dictionary
        '''
        pass

    @property
    def default_scan_configuration(self):
        '''Default scan configuration dictionary
        '''
        return self._default_scan_configuration

    @property
    def dut(self):
        return self.dut_configuration['dut']

    @property
    def register(self):
        return self.fe_configuration['configuration']

    @property
    def output_filename(self):
        if self.module_id:
            return os.path.join(self.working_dir, str(self.run_number) + "_" + self.module_id + "_" + self.scan_id)
        else:
            return os.path.join(self.working_dir, str(self.run_number) + "_" + self.scan_id)

    @property
    def scan_data_filename(self):
        logging.warning('scan_data_filename is deprecated, use output_filename')
        return self.output_filename

    @property
    def module_id(self):
        if 'module_id' in self.fe_configuration and self.fe_configuration['module_id']:
            module_id = self.fe_configuration['module_id']
            module_id = re.sub(r"[^\w\s+]", '', module_id)
            return re.sub(r"\s+", '_', module_id).lower()
        else:
            return None

    def run(self):
        try:
            if 'configuration' in self.fe_configuration and self.fe_configuration['configuration']:
                if not isinstance(self.fe_configuration['configuration'], FEI4Register):
                    if isinstance(self.fe_configuration['configuration'], basestring):
                        self.fe_configuration['configuration'] = FEI4Register(configuration_file=self.fe_configuration['configuration'])
                    elif isinstance(self.fe_configuration['configuration'], (int, long)) and self.fe_configuration['configuration'] >= 0:
                        self.fe_configuration['configuration'] = FEI4Register(configuration_file=self._get_configuration(self.fe_configuration['configuration']))
                    else:
                        self.fe_configuration['configuration'] = FEI4Register(configuration_file=self._get_configuration())
                else:
                    pass  # do nothing, already initialized
            else:
                self.fe_configuration['configuration'] = FEI4Register(configuration_file=self._get_configuration())

            if not isinstance(self.dut_configuration['dut'], Dut):
                self.dut_configuration['dut'] = Dut(self.dut_configuration['dut'])
                if 'dut_configuration' in self.dut_configuration and self.dut_configuration['dut_configuration']:
                    self.dut.init(self.dut_configuration['dut_configuration'])
                elif self.dut.name == 'usbpix':
                    self.dut.init('dut_configuration_usbpix.yaml')
                elif self.dut.name == 'usbpix_gpac':
                    self.dut.init('dut_configuration_usbpix_gpac.yaml')
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

            if not self.data_readout:
                self.data_readout = DataReadout(self.dut)
            if not self.register_utils:
                self.register_utils = FEI4RegisterUtils(self.dut, self.data_readout, self.register)
            self._save_configuration_dict('dut_configuration', self.dut_configuration)
            self._save_configuration_dict('fe_configuration', self.fe_configuration)
            self._save_configuration_dict('scan_configuration', self.scan_configuration)
            self.register_utils.global_reset()
            self.register_utils.reset_bunch_counter()
            self.register_utils.reset_event_counter()
            self.register_utils.reset_service_records()
            self.register_utils.configure_all()
            self.register.create_restore_point(name=self.run_number)
            self.configure()
            self.register.save_configuration_to_hdf5(self.output_filename)
            self.data_readout.reset_rx()
            self.data_readout.reset_sram_fifo()
            self.data_readout.print_readout_status()
            logging.info('Found scan parameter(s): %s' % (', '.join(['%s:%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None'))
            self.stop_run.clear()
            with open_raw_data_file(filename=self.output_filename, title=self.scan_id, scan_parameters=self.scan_parameters._asdict()) as self.raw_data_file:
                self.scan()
            self.data_readout.print_readout_status()
            self.register.restore(name=self.run_number)
            self.raw_data_file = None
        except Exception as e:
            self.handle_err(sys.exc_info())
        else:
            try:
                self.analyze()
            except Exception as e:
                self.handle_err(sys.exc_info())
            else:
                self.register.save_configuration(self.output_filename)
        finally:
            try:
                if self.data_readout.is_running:
                    self.data_readout.stop(timeout=0.0)
            except AttributeError as e:
                pass
            try:
                self.dut['USB'].close()  # free USB resources
            except AttributeError as e:
                pass
        if not self.err_queue.empty():
            exc = self.err_queue.get()
            if isinstance(exc[1], (RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout)):
                raise RunAborted(exc[1])
            else:
                raise exc[0], exc[1], exc[2]

    def retry(self):
        self.run()

    def abort(self, msg=None):
        logging.error('%s. Stopping scan...' % msg)
        if msg:
            self.err_queue.put(Exception(msg))
        else:
            self.err_queue.put(Exception('Unknown exception'))
        self.stop_run.set()

    def stop(self, msg=None):
        self.stop_run.set()
        if msg:
            logging.info('%s%s Stopping scan...' % (msg, ('' if msg[-1] in punctuation else '.')))
        else:
            logging.info('Stopping scan...')

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), flush=False)

    def handle_err(self, exc):
        self.err_queue.put(exc)
        self.stop_run.set()
        if exc[1]:
            logging.error('%s%s%s' % (exc[1], ('' if str(exc[1])[-1] in punctuation else '.'), ('' if self.stop_run.is_set() else ' Stopping scan...')))
        else:
            logging.error('Error.%s' % ('' if self.stop_run.is_set() else ' Stopping scan...'))


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
        yield
        self.stop_readout()

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.data_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err)

    def stop_readout(self):
        self.data_readout.stop()

    def _save_configuration_dict(self, configuation_name, configuration, **kwargs):
        '''Stores any configuration dictionary to HDF5 file.

        Parameters
        ----------
        configuation_name : str
            Configuration name. Will be used for table name.
        configuration : dict
            Configuration dictionary.
        '''
        h5_file = self.output_filename
        if os.path.splitext(h5_file)[1].strip().lower() != ".h5":
            h5_file = os.path.splitext(h5_file)[0] + ".h5"

        # append to file if existing otherwise create new one
        with tb.open_file(h5_file, mode="a", title='put title', **kwargs) as raw_data_file_h5:
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

    @abc.abstractmethod
    def configure(self):
        '''Implementation of the scan configuration.

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
        '''Implementation of scan data processing.

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
