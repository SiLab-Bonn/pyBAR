import logging
import time
import re
import os
import string
import struct
import smtplib
from socket import gethostname
import zmq
import numpy as np
from functools import wraps
from threading import Event, Thread
from Queue import Queue
from collections import namedtuple, Mapping
from contextlib import contextmanager
from operator import itemgetter
import abc
import ast
import inspect
import sys

from basil.dut import Dut

from pybar.run_manager import RunManager, RunBase, RunAborted, RunStopped
from pybar.utils.utils import find_file_dir_up
from pybar.fei4.register import FEI4Register
from pybar.fei4.register_utils import FEI4RegisterUtils, is_fe_ready, CmdTimeoutError
from pybar.daq.fifo_readout import FifoReadout, RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout
from pybar.daq.readout_utils import save_configuration_dict
from pybar.daq.fei4_raw_data import open_raw_data_file, send_meta_data
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
        if 'working_dir' not in conf:
            conf.update({'working_dir': ''})  # path string, if empty, path of configuration.yaml file will be used
        if 'zmq_context' not in conf:
            conf.update({'zmq_context': None})  # ZMQ context
        if 'send_data' not in conf:
            conf.update({'send_data': None})  # address string of PUB socket
        if 'send_error_msg' not in conf:
            conf.update({'send_error_msg': None})  # bool

        self.err_queue = Queue()
        self.fifo_readout = None
        self.raw_data_file = None

    @property
    def working_dir(self):
        if self.module_id:
            return os.path.join(self._conf['working_dir'], self.module_id)
        else:
            return os.path.join(self._conf['working_dir'], self.run_id)

    @property
    def dut(self):
        return self._conf['dut']

    @property
    def register(self):
        return self._conf['fe_configuration']

    @property
    def output_filename(self):
        if self.module_id:
            return os.path.join(self.working_dir, str(self.run_number) + "_" + self.module_id + "_" + self.run_id)
        else:
            return os.path.join(self.working_dir, str(self.run_number) + "_" + self.run_id)

    @property
    def module_id(self):
        if 'module_id' in self._conf and self._conf['module_id']:
            module_id = str(self._conf['module_id'])
            module_id = re.sub(r"[^\w\s+]", '', module_id)
            return re.sub(r"\s+", '_', module_id).lower()
        else:
            return None

    def init_dut(self):
        if self.dut.name == 'mio':  # MIO2 with Single Chip Adapter Card (SCAC) or QUAD Module Adapter Card
            if self.dut.get_modules('FEI4AdapterCard') and [adapter_card for adapter_card in self.dut.get_modules('FEI4AdapterCard') if adapter_card.name == 'ADAPTER_CARD']:
                try:
                    self.dut['ADAPTER_CARD'].set_voltage('VDDA1', 1.5)
                    self.dut['ADAPTER_CARD'].set_voltage('VDDA2', 1.5)
                    self.dut['ADAPTER_CARD'].set_voltage('VDDD1', 1.2)
                    self.dut['ADAPTER_CARD'].set_voltage('VDDD2', 1.2)
                except struct.error:
                    logging.warning('Cannot set adapter card voltages. Maybe card not calibrated?')
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
        elif self.dut.name == 'mio_gpac':  # MIO2 with Genaral Purpose Analog Card (GPAC)
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
        elif self.dut.name == 'lx9':  # Avnet LX9
            # enable LVDS RX/TX
            self.dut['I2C'].write(0xe8, [6, 0xf0, 0xff])
            self.dut['I2C'].write(0xe8, [2, 0x01, 0x00])  # select channels here
        elif self.dut.name == 'nexys4':  # Digilent Nexys 4
            # enable LVDS RX/TX
            self.dut['I2C'].write(0xe8, [6, 0xf0, 0xff])
            self.dut['I2C'].write(0xe8, [2, 0x0f, 0x00])  # select channels here
            self.dut['ENABLE_CHANNEL']['CH1'] = 1
            self.dut['ENABLE_CHANNEL']['CH2'] = 1
            self.dut['ENABLE_CHANNEL']['CH3'] = 1
            self.dut['ENABLE_CHANNEL']['CH4'] = 1
            self.dut['ENABLE_CHANNEL']['TLU'] = 1
            self.dut['ENABLE_CHANNEL']['TDC'] = 1
            self.dut['ENABLE_CHANNEL'].write()
        else:
            logging.warning('Omitting initialization of DUT %s', self.dut.name)
        # enabling all FEI4 Rx
        rx_names = [rx.name for rx in self.dut.get_modules('fei4_rx')]
        for rx_name in rx_names:
            self.dut[rx_name].ENABLE_RX = 1

    def init_fe(self):
        if 'fe_configuration' in self._conf:
            last_configuration = self._get_configuration()
            # init config, a number <=0 will also do the initialization (run 0 does not exists)
            if (not self._conf['fe_configuration'] and not last_configuration) or (isinstance(self._conf['fe_configuration'], (int, long)) and self._conf['fe_configuration'] <= 0):
                if 'chip_address' in self._conf and self._conf['chip_address']:
                    chip_address = self._conf['chip_address']
                    broadcast = False
                else:
                    chip_address = 0
                    broadcast = True
                if 'fe_flavor' in self._conf and self._conf['fe_flavor']:
                    self._conf['fe_configuration'] = FEI4Register(fe_type=self._conf['fe_flavor'], chip_address=chip_address, broadcast=broadcast)
                else:
                    raise ValueError('No fe_flavor given')
            # use existing config
            elif not self._conf['fe_configuration'] and last_configuration:
                self._conf['fe_configuration'] = FEI4Register(configuration_file=last_configuration)
            # path string
            elif isinstance(self._conf['fe_configuration'], basestring):
                if os.path.isabs(self._conf['fe_configuration']):  # absolute path
                    self._conf['fe_configuration'] = FEI4Register(configuration_file=self._conf['fe_configuration'])
                else:  # relative path
                    self._conf['fe_configuration'] = FEI4Register(configuration_file=os.path.join(self._conf['working_dir'], self._conf['fe_configuration']))
            # run number
            elif isinstance(self._conf['fe_configuration'], (int, long)) and self._conf['fe_configuration'] > 0:
                self._conf['fe_configuration'] = FEI4Register(configuration_file=self._get_configuration(self._conf['fe_configuration']))
            # assume fe_configuration already initialized
            elif not isinstance(self._conf['fe_configuration'], FEI4Register):
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
        # clear error queue in case run is executed a second time
        self.err_queue.queue.clear()
        # opening ZMQ context and binding socket
        if self._conf['send_data'] and not self._conf['zmq_context']:
            logging.info('Creating ZMQ context')
            self._conf['zmq_context'] = zmq.Context()  # contexts are thread safe unlike sockets
        else:
            logging.info('Using existing socket')
        # scan parameters
        if 'scan_parameters' in self._run_conf:
            if isinstance(self._run_conf['scan_parameters'], basestring):
                self._run_conf['scan_parameters'] = ast.literal_eval(self._run_conf['scan_parameters'])
            sp = namedtuple('scan_parameters', field_names=zip(*self._run_conf['scan_parameters'])[0])
            self.scan_parameters = sp(*zip(*self._run_conf['scan_parameters'])[1])
        else:
            sp = namedtuple_with_defaults('scan_parameters', field_names=[])
            self.scan_parameters = sp()
        logging.info('Scan parameter(s): %s', ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')

        # init DUT
        if not isinstance(self._conf['dut'], Dut):
            module_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
            if isinstance(self._conf['dut'], basestring):
                # dirty fix for Windows pathes
                self._conf['dut'] = os.path.normpath(self._conf['dut'].replace('\\', '/'))
                # abs path
                if os.path.isabs(self._conf['dut']):
                    dut = self._conf['dut']
                # working dir, and directorys upwards
                elif find_file_dir_up(filename=self._conf['dut'], path=self._conf['working_dir']):
                    dut = find_file_dir_up(filename=self._conf['dut'], path=self._conf['working_dir'])
                # path of this file
                elif os.path.isfile(os.path.join(module_path, self._conf['dut'])):
                    dut = os.path.join(module_path, self._conf['dut'])
                else:
                    raise ValueError('dut parameter not a valid path: %s' % self._conf['dut'])
                logging.info('Loading DUT configuration from file %s', os.path.abspath(dut))
            else:
                dut = self._conf['dut']
            dut = Dut(dut)

            # only initialize when DUT was not initialized before
            if 'dut_configuration' in self._conf and self._conf['dut_configuration']:
                if isinstance(self._conf['dut_configuration'], basestring):
                    # dirty fix for Windows pathes
                    self._conf['dut_configuration'] = os.path.normpath(self._conf['dut_configuration'].replace('\\', '/'))
                    # abs path
                    if os.path.isabs(self._conf['dut_configuration']):
                        dut_configuration = self._conf['dut_configuration']
                    # working dir, and directorys upwards
                    elif find_file_dir_up(filename=self._conf['dut_configuration'], path=self._conf['working_dir']):
                        dut_configuration = find_file_dir_up(filename=self._conf['dut_configuration'], path=self._conf['working_dir'])
                    # path of this file
                    elif os.path.isfile(os.path.join(module_path, self._conf['dut_configuration'])):
                        dut_configuration = os.path.join(module_path, self._conf['dut_configuration'])
                    else:
                        raise ValueError('dut_configuration parameter not a valid path: %s' % self._conf['dut_configuration'])
                    logging.info('Loading DUT initialization parameters from file %s', os.path.abspath(dut_configuration))
                    # convert to dict
                    dut_configuration = RunManager.open_conf(dut_configuration)
                    # change bit file path
                    for drv in dut_configuration.iterkeys():
                        if 'bit_file' in dut_configuration[drv] and dut_configuration[drv]['bit_file']:
                            dut_configuration[drv]['bit_file'] = os.path.normpath(dut_configuration[drv]['bit_file'].replace('\\', '/'))
                            # abs path
                            if os.path.isabs(dut_configuration[drv]['bit_file']):
                                pass
                            # working dir, and directorys upwards
                            elif find_file_dir_up(filename=dut_configuration[drv]['bit_file'], path=self._conf['working_dir']):
                                dut_configuration[drv]['bit_file'] = find_file_dir_up(filename=dut_configuration[drv]['bit_file'], path=self._conf['working_dir'])
                            # path of this file
                            elif os.path.isfile(os.path.join(module_path, dut_configuration[drv]['bit_file'])):
                                dut_configuration[drv]['bit_file'] = os.path.join(module_path, dut_configuration[drv]['bit_file'])
                            else:
                                raise ValueError("Parameter 'bit_file' is not a valid path: %s" % dut_configuration[drv]['bit_file'])
                else:
                    dut_configuration = self._conf['dut_configuration']
            else:
                dut_configuration = None
            logging.info('Initializing basil')
            dut.init(dut_configuration)
            # assign dut after init in case of exceptions during init
            self._conf['dut'] = dut
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
            self.fifo_readout.reset_fifo(fifos="FIFO")
            self.fifo_readout.print_readout_status()
            # open raw data file
            with open_raw_data_file(filename=self.output_filename, mode='w', title=self.run_id, scan_parameters=self.scan_parameters._asdict(), context=self._conf['zmq_context'], socket_address=self._conf['send_data']) as self.raw_data_file:
                # save configuration data to raw data file
                self.register.save_configuration(self.raw_data_file.h5_file)
                save_configuration_dict(self.raw_data_file.h5_file, 'conf', self._conf)
                save_configuration_dict(self.raw_data_file.h5_file, 'run_conf', self._run_conf)
                # send configuration data to online monitor
                if self.raw_data_file.socket:
                    send_meta_data(self.raw_data_file.socket, self.output_filename, name='Filename')
                    global_register_config = {}
                    for global_reg in sorted(self.register.get_global_register_objects(readonly=False), key=itemgetter('name')):
                        global_register_config[global_reg['name']] = global_reg['value']
                    send_meta_data(self.raw_data_file.socket, global_register_config, name='GlobalRegisterConf')
                    send_meta_data(self.raw_data_file.socket, self._run_conf, name='RunConf')
                # scan
                self.scan()

    def post_run(self):
        # printing FIFO status
        try:
            self.fifo_readout.print_readout_status()
        except Exception:  # no device?
            pass

        # analyzing data
        try:
            self.analyze()
        except Exception:  # analysis errors
            self.handle_err(sys.exc_info())
        else:  # analyzed data, save config
            self.register.save_configuration(self.output_filename)

        if not self.err_queue.empty():
            exc = self.err_queue.get()
            # well known errors, do not print traceback
            if isinstance(exc[1], (RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout, AnalysisError)):
                raise RunAborted(exc[1])
            # some other error via handle_err(), print traceback
            else:
                raise exc[0], exc[1], exc[2]
        elif self.abort_run.is_set():
            raise RunAborted()
        elif self.stop_run.is_set():
            raise RunStopped()
        # if ending up here, succcess!

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
        '''Handling of the data.

        Parameters
        ----------
        data : list, tuple
            Data tuple of the format (data (np.array), last_time (float), curr_time (float), status (int))
        '''
        self.raw_data_file.append(data[0], scan_parameters=self.scan_parameters._asdict(), flush=True)

    def handle_err(self, exc):
        '''Handling of Exceptions.

        Parameters
        ----------
        exc : list, tuple
            Information of the exception of the format (type, value, traceback).
            Uses the return value of sys.exc_info().
        '''
        if self.reset_rx_on_error and isinstance(exc[1], (RxSyncError, EightbTenbError)):
            self.fifo_readout.print_readout_status()
            self.fifo_readout.reset_rx()
        else:
            # print just the first error massage
            if not self.abort_run.is_set():
                self.abort(msg=exc[1].__class__.__name__ + ": " + str(exc[1]))
            self.err_queue.put(exc)

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
        errback = kwargs.pop('errback', self.handle_err)
        reset_fifo = kwargs.pop('reset_fifo', False)
        fill_buffer = kwargs.pop('fill_buffer', False)
        no_data_timeout = kwargs.pop('no_data_timeout', None)
        if args or kwargs:
            self.set_scan_parameters(*args, **kwargs)
        self.fifo_readout.start(fifos="FIFO", callback=callback, errback=errback, reset_fifo=reset_fifo, fill_buffer=fill_buffer, no_data_timeout=no_data_timeout, enabled_fe_channels=None)

    def stop_readout(self, timeout=10.0):
        self.fifo_readout.stop(timeout=timeout)

    def _cleanup(self):  # called in run base after exception handling
        super(Fei4RunBase, self)._cleanup()
        if 'send_message' in self._conf and self._run_status in self._conf['send_message']['status']:
            subject = '{}{} ({})'.format(self._conf['send_message']['subject_prefix'], self._run_status, gethostname())
            last_status_message = '{} run {} ({}) in {} (total time: {})'.format(self.run_status, self.run_number, self.__class__.__name__, self.working_dir, str(self._total_run_time))
            body = '\n'.join(item for item in [self._last_traceback, last_status_message] if item)
            try:
                send_mail(subject=subject, body=body, smtp_server=self._conf['send_message']['smtp_server'], user=self._conf['send_message']['user'], password=self._conf['send_message']['password'], from_addr=self._conf['send_message']['from_addr'], to_addrs=self._conf['send_message']['to_addrs'])
            except Exception:
                logging.warning("Failed sending pyBAR status report")

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


def send_mail(subject, body, smtp_server, user, password, from_addr, to_addrs):
    ''' Sends a run status mail with the traceback to a specified E-Mail address if a run crashes.
    '''
    logging.info('Send status E-Mail (' + subject + ')')
    content = string.join((
        "From: %s" % from_addr,
        "To: %s" % ','.join(to_addrs),  # comma separated according to RFC822
        "Subject: %s" % subject,
        "",
        body),
        "\r\n")
    server = smtplib.SMTP_SSL(smtp_server)
    server.login(user, password)
    server.sendmail(from_addr, to_addrs, content)
    server.quit()
