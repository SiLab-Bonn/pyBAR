import logging
import time
import os
import string
import struct
import smtplib
from socket import gethostname
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
import contextlib2 as contextlib

from basil.dut import Dut

from pybar.run_manager import RunManager, RunBase, RunAborted, RunStopped
from pybar.fei4.register import FEI4Register
from pybar.fei4.register_utils import FEI4RegisterUtils, is_fe_ready
from pybar.daq.fifo_readout import FifoReadout, RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout
from pybar.daq.readout_utils import save_configuration_dict
from pybar.daq.fei4_raw_data import open_raw_data_file, send_meta_data
from pybar.analysis.analysis_utils import AnalysisError
from pybar.daq.readout_utils import (convert_data_iterable, logical_or, logical_and, is_trigger_word, is_fe_word, is_data_from_channel,
                                     is_tdc_word, is_tdc_from_channel, convert_tdc_to_channel, false)


class Fei4RawDataHandle(object):
    ''' Handle for multiple raw data files with filter and converter functions.
    '''
    def __init__(self, raw_data_files, module_cfgs, selected_modules=None):
        self._raw_data_files = raw_data_files
        self._module_cfgs = module_cfgs

        # Module filter functions dict for quick lookup
        self._filter_funcs = {}
        self._converter_funcs = {}
        if selected_modules is None:
            selected_modules = [item for item in sorted(self._module_cfgs.keys(), key=lambda x: (x is not None, x)) if item is not None]
        if len(raw_data_files) != len(selected_modules):
            raise ValueError("Selected modules do not match number of raw data files.")
        for module_id in selected_modules:
            module_cfg = module_cfgs[module_id]
            if module_id is None:
                continue
            if 'rx_channel' in module_cfg and module_cfg['rx_channel'] is not None:
                rx_filter = logical_and(is_fe_word, is_data_from_channel(module_cfg['rx_channel']))
            else:
                rx_filter = is_fe_word
            if 'tdc_channel' in module_cfg and module_cfg['tdc_channel'] is not None:
                tdc_filter = logical_and(is_tdc_word, is_tdc_from_channel(module_cfg['tdc_channel']))
                self._converter_funcs[module_id] = convert_tdc_to_channel(channel=module_cfg['tdc_channel'])
            else:
                tdc_filter = false
                self._converter_funcs[module_id] = None
            self._filter_funcs[module_id] = logical_or(is_trigger_word, logical_or(rx_filter, tdc_filter))

    def append_item(self, data_tuple, scan_parameters=None, new_file=False, flush=True):
        ''' Append raw data for each module after filtering and converting the raw data individually.
        '''
        for module_id, filter_func in self._filter_funcs.iteritems():
            converted_data_tuple = convert_data_iterable((data_tuple,), filter_func=filter_func, converter_func=self._converter_funcs[module_id])[0]
            self._raw_data_files[module_id].append_item(converted_data_tuple, scan_parameters=scan_parameters, new_file=new_file, flush=flush)


class TdcHandle(object):
    ''' Access to single or multiple tdc modules.

    Needed to encapsulate tdc configuration in scan from hardware setup.
    '''
    def __init__(self, dut, tdc_modules):
        self._dut = dut
        self._tdc_modules = tdc_modules
        self._conf = {}  # Common conf for all TDCs

    def __getitem__(self, key):
        ''' Return configurations that are common to all TDC modules
        '''
        return self._conf[key]

    def __setitem__(self, key, value):
        ''' Set TDC setting to all TDC modules
        '''
        self._conf[key] = value
        for module in self._tdc_modules:
            tdc = self._dut[module]
            tdc[key] = value


class Fei4RunBase(RunBase):
    '''Basic FEI4 run meta class.

    Base class for scan- / tune- / analyze-class.

    A fei4 run consist of 3 major steps:
      1. pre_run
        - dut initialization (readout system init)
        - init readout fifo (data taking buffer)
        - load scan parameters from run config
        - init each front-end one by one (configure registers, serial)
      2. do_run
        The following steps are either run for all front-ends
        at once (parallel scan) or one by one (serial scan):
        - scan specific configuration
        - store run attributes
        - run scan
        - restore run attributes (some scans change run conf attributes or add new attributes, this restores to before)
        - restore scan parameters from default run config (they mighte have been changed in scan)
      3. post_run
        - call analysis on raw data files one by one (serial)

    Several handles are provided to encapsulate the underlying hardware
    and scan type to be able to use generic scan definitions:

    - serial scan mode:
      - register: one FE register data
      - register_utils: access to one FE registers
      - output_filename: output file name of a selected module
      - raw_data_file: one output data file

    - parallel scan mode:
      - register: broadcast register or multiple front-end registers
      - register_utils: access all FE registers via broadcast or each front-end registers
        at different channels
      - output_filename: output file name of a selected module
      - raw_data_file: all output data files with channel data filters

    '''
    __metaclass__ = abc.ABCMeta

    def __init__(self, conf):
        # Sets self._conf = conf
        super(Fei4RunBase, self).__init__(conf=conf)
        # settting up scan
        self.set_scan_mode()

        self.err_queue = Queue()

        self._module_cfgs = {}
        self._module_register_utils = {}
        self._raw_data_files = {}
        self._module_attr = {}
        self._scan_parameters = {}  # Store specific scan parameters per module to make available after scan
        self._parse_module_cfgs(conf)
        self._set_default_cfg(conf)
        self.fifo_readout = None  # FIFO readout
        self.tdc = None  # Handle for TDC modules
        self.raw_data_file = None
        self.deselect_module()  # Initialize handles
        self._initialized = True

    def _init_run_conf(self, run_conf):
        # set up default run conf parameters
        self._default_run_conf.setdefault('comment', '{}'.format(self.__class__.__name__))
        self._default_run_conf.setdefault('reset_rx_on_error', False)

        super(Fei4RunBase, self)._init_run_conf(run_conf=run_conf)

    @property
    def is_initialized(self):
        if "_initialized" in self.__dict__ and self._initialized:
            return True
        else:
            return False

    def set_scan_mode(self):
        ''' Called during init to set scan in serial or paralle mode.

        Overwrite this function in the scan to change the mode.
        Std. setting is parallel.
        '''
        self.parallel = True

    def _parse_module_cfgs(self, conf):
        ''' Extracts the configuration of the modules.
        '''
        if 'modules' in conf and conf['modules']:
            for module_id, module_cfg in conf['modules'].iteritems():
                # Check here for missing module config items.
                if 'rx_channel' not in module_cfg:
                    raise ValueError("No parameter 'rx_channel' defined for module '%s'" % module_id)
                if 'fe_flavor' not in module_cfg:
                    raise ValueError("No parameter 'fe_flavor' defined for module '%s'" % module_id)
                if 'chip_address' not in module_cfg:
                    raise ValueError("No parameter 'chip_address' defined for module '%s'" % module_id)
                # Save config to dict.
                self._module_cfgs[module_id] = module_cfg

        else:
            raise ValueError("No module configuration specified")

    def _set_default_cfg(self, conf):
        ''' Sets the default parameters if they are not specified.
        '''
        # Adding here default run config parameters.
        conf.setdefault('working_dir', '')  # path string, if empty, path of configuration.yaml file will be used

        fe_flavors = set([module_cfg['fe_flavor'] for module_cfg in self._module_cfgs.values()])
        if len(fe_flavors) != 1 and self.parallel:
            raise ValueError("Parameter 'fe_flavor' must be the same for module group")
        elif self.parallel:
            # Adding broadcast config for parallel mode.
            self._module_cfgs[None] = {
                'channel': None,
                'fe_flavor': fe_flavors.pop(),
                'chip_address': None}

        # Adding here default module config items.
        for module_cfg in self._module_cfgs.values():
            module_cfg.setdefault('send_data', None)  # address string of PUB socket
            module_cfg.setdefault('send_error_msg', None)  # bool, None
            module_cfg.setdefault('fe_configuration', None)  # value, None
            module_cfg.setdefault('rx', None)  # value, None
            # TODO: message missing

    @property
    def dut(self):
        return self._conf['dut']

    def get_module_cfg(self, module_id):
        ''' Returns the configuration of the module with given ID.
        '''
        return self._module_cfgs[module_id]

    def get_scan_parameters(self, module_id):
        ''' Returns the scan parameters of the module with given ID.
        '''
        return self._scan_parameters[module_id]

    def get_register(self, module_id):
        ''' Returns the register configuration of the module with given ID.
        '''
        return self._module_cfgs[module_id]['fe_configuration']

    def get_register_utils(self, module_id):
        ''' Returns the register utils of the module with given ID.
        '''
        return self._module_register_utils[module_id]

    def get_output_filename(self, module_id):
        if module_id is None:
            return None
        module_path = os.path.join(self.working_dir, module_id)
        return os.path.join(module_path, str(self.run_number) + "_" + module_id + "_" + self.run_id)

    def init_dut(self):
        if self.dut.name == 'mio':
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
                self.tdc = TdcHandle(self.dut, tdc_modules=['TDC'])
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
                self.tdc = TdcHandle(self.dut, tdc_modules=['TDC'])
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
                self.tdc = TdcHandle(self.dut, tdc_modules=['TDC'])

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
            self.tdc = TdcHandle(self.dut, tdc_modules=['TDC', 'CCPD_TDC'])
        elif self.dut.name == 'lx9':
            # enable LVDS RX/TX
            self.dut['I2C'].write(0xe8, [6, 0xf0, 0xff])
            self.dut['I2C'].write(0xe8, [2, 0x01, 0x00])  # select channels here
        elif self.dut.name == 'nexys4':
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
            self.tdc = TdcHandle(self.dut, tdc_modules=['TDC'])
        elif self.dut.name == 'beast':
            logging.info('BEAST initialization')
            self.dut['DLY_CONFIG']['CLK_DLY'] = 0
            self.dut['DLY_CONFIG'].write()
            self.tdc = TdcHandle(self.dut, tdc_modules=['TDC0', 'TDC1', 'TDC2', 'TDC3', 'TDC4'])
        elif self.dut.name == 'MMC3_8_chip':
            channel_names = [channel.name for channel in self.dut.get_modules('fei4_rx')]
            active_channel_names = [module_cfg["rx"] for module_cfg in self._module_cfgs.values()]
            for channel_name in channel_names:
                # enabling readout
                if channel_name in active_channel_names:
                    self.dut[channel_name].ENABLE_RX = 1
                else:
                    self.dut[channel_name].ENABLE_RX = 0
        else:
            logging.warning('Omitting initialization of DUT %s', self.dut.name)

    def init_modules(self):
        ''' Initialize all modules consecutevly'''
        for module_id in sorted(self._module_cfgs.keys(), key=lambda x: (x is not None, x)):
            module_cfg = self._module_cfgs[module_id]
            logging.info("Initializing %s..." % "broadcast module" if module_id is None else module_id)
            # adding scan parameters for each module
            if 'scan_parameters' in self._run_conf:
                if isinstance(self._run_conf['scan_parameters'], basestring):
                    self._run_conf['scan_parameters'] = ast.literal_eval(self._run_conf['scan_parameters'])
                sp = namedtuple('scan_parameters', field_names=zip(*self._run_conf['scan_parameters'])[0])
                self._scan_parameters[module_id] = sp(*zip(*self._run_conf['scan_parameters'])[1])
            else:
                sp = namedtuple_with_defaults('scan_parameters', field_names=[])
                self._scan_parameters[module_id] = sp()
            # init FE config
            # a config number <=0 will create a new config (run 0 does not exists)
            last_configuration = self.get_configuration(module_id=module_id)
            if (not module_cfg['fe_configuration'] and not last_configuration) or (isinstance(module_cfg['fe_configuration'], (int, long)) and module_cfg['fe_configuration'] <= 0):
                broadcast = False
                if 'chip_address' in module_cfg and module_cfg['chip_address'] is not None:
                    chip_address = module_cfg['chip_address']
                else:
                    # In single chip setups the std. address is usually 0
                    if len(filter(None, self._module_cfgs.keys())) == 1 or module_id is None:
                        chip_address = 0
                        broadcast = True
                    else:
                        raise ValueError("Parameter 'chip_address' not specified for module '%s'" % module_id)
                if 'fe_flavor' in module_cfg and module_cfg['fe_flavor']:
                    module_cfg['fe_configuration'] = FEI4Register(fe_type=module_cfg['fe_flavor'], chip_address=chip_address, broadcast=broadcast)
                else:
                    raise ValueError("Parameter 'fe_flavor' not specified for module '%s'" % module_id)
            # use existing config
            elif not module_cfg['fe_configuration'] and last_configuration:
                module_cfg['fe_configuration'] = FEI4Register(configuration_file=last_configuration)
            # path string
            elif isinstance(module_cfg['fe_configuration'], basestring):
                if os.path.isabs(module_cfg['fe_configuration']):  # absolute path
                    module_cfg['fe_configuration'] = FEI4Register(configuration_file=module_cfg['fe_configuration'])
                else:  # relative path
                    module_cfg['fe_configuration'] = FEI4Register(configuration_file=os.path.join(module_cfg['working_dir'], module_cfg['fe_configuration']))
            # run number
            elif isinstance(module_cfg['fe_configuration'], (int, long)) and module_cfg['fe_configuration'] > 0:
                module_cfg['fe_configuration'] = FEI4Register(configuration_file=self.get_configuration(module_id=module_id,
                                                                                                        run_number=module_cfg['fe_configuration']))
            # assume fe_configuration already initialized
            elif not isinstance(module_cfg['fe_configuration'], FEI4Register):
                raise ValueError("Found no valid value for parameter 'fe_configuration' for module '%s'" % module_id)

            # init register utils
            self._module_register_utils[module_id] = FEI4RegisterUtils(self.dut, self.get_register(module_id=module_id))

            if module_id is not None:
                # reset and configuration
                self._module_register_utils[module_id].global_reset()
                self._module_register_utils[module_id].configure_all()
                if is_fe_ready(self, module_id):
                    reset_service_records = False
                else:
                    reset_service_records = True
                self._module_register_utils[module_id].reset_bunch_counter()
                self._module_register_utils[module_id].reset_event_counter()
                if reset_service_records:
                    # resetting service records must be done once after power up
                    self._module_register_utils[module_id].reset_service_records()

                # Create module data path if it does not exist
                module_path = self.get_module_path(module_id)
                if not os.path.exists(module_path):
                    os.makedirs(module_path)

    def pre_run(self):
        # clear error queue in case run is executed a second time
        self.err_queue.queue.clear()

        # init DUT
        if not isinstance(self._conf['dut'], Dut):  # Check if already initialized
            module_path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
            if isinstance(self._conf['dut'], basestring):
                # dirty fix for Windows pathes
                self._conf['dut'] = os.path.normpath(self._conf['dut'].replace('\\', '/'))
                # abs path
                if os.path.isabs(self._conf['dut']):
                    dut = self._conf['dut']
                # working dir
                elif os.path.exists(os.path.join(self._conf['working_dir'], self._conf['dut'])):
                    dut = os.path.join(self._conf['working_dir'], self._conf['dut'])
                # path of this file
                elif os.path.exists(os.path.join(module_path, self._conf['dut'])):
                    dut = os.path.join(module_path, self._conf['dut'])
                else:
                    raise ValueError("Parameter 'dut' is not a valid path: %s" % self._conf['dut'])
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
                    # working dir
                    elif os.path.exists(os.path.join(self._conf['working_dir'], self._conf['dut_configuration'])):
                        dut_configuration = os.path.join(self._conf['working_dir'], self._conf['dut_configuration'])
                    # path of dut file
                    elif os.path.exists(os.path.join(os.path.dirname(dut.conf_path), self._conf['dut_configuration'])):
                        dut_configuration = os.path.join(os.path.dirname(dut.conf_path), self._conf['dut_configuration'])
                    # path of this file
                    elif os.path.exists(os.path.join(module_path, self._conf['dut_configuration'])):
                        dut_configuration = os.path.join(module_path, self._conf['dut_configuration'])
                    else:
                        raise ValueError("Parameter 'dut_configuration' is not a valid path: %s" % self._conf['dut_configuration'])
                    logging.info('Loading DUT initialization parameters from file %s', os.path.abspath(dut_configuration))
                    # convert to dict
                    dut_configuration = RunManager.open_conf(dut_configuration)
                    # change bit file path
                    if 'USB' in dut_configuration and 'bit_file' in dut_configuration['USB'] and dut_configuration['USB']['bit_file']:
                        bit_file = os.path.normpath(dut_configuration['USB']['bit_file'].replace('\\', '/'))
                        # abs path
                        if os.path.isabs(bit_file):
                            pass
                        # working dir
                        elif os.path.exists(os.path.join(self._conf['working_dir'], bit_file)):
                            bit_file = os.path.join(self._conf['working_dir'], bit_file)
                        # path of dut file
                        elif os.path.exists(os.path.join(os.path.dirname(dut.conf_path), bit_file)):
                            bit_file = os.path.join(os.path.dirname(dut.conf_path), bit_file)
                        # path of this file
                        elif os.path.exists(os.path.join(module_path, bit_file)):
                            bit_file = os.path.join(module_path, bit_file)
                        else:
                            raise ValueError("Parameter 'bit_file' is not a valid path: %s" % bit_file)
                        dut_configuration['USB']['bit_file'] = bit_file
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
        # initialize the modules
        self.init_modules()

    def do_run(self):
        ''' Start runs on all modules sequentially.

        Sets properties to access current module properties.
        '''
        if self.parallel:  # Broadcast FE commands
            with contextlib.ExitStack() as stack:
                # Configure each FE individually
                # Sort module config keys, configure broadcast module (key is None) first
                for module_id in sorted(self._module_cfgs.keys(), key=lambda x: (x is not None, x)):
                    if self.abort_run.is_set():
                        break
                    with self.access_module(module_id=module_id):
                        logging.info('Scan parameter(s): %s', ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')
                        stack.enter_context(self.register.restored(name=self.run_number))
                        self.configure()

                self.fifo_readout.reset_rx()
                self.fifo_readout.reset_sram_fifo()
                self.fifo_readout.print_readout_status()

                with self.access_module(module_id=None):
                    with self.open_file(module_id=None):
                        self.scan()

            self.fifo_readout.print_readout_status()

        else:  # Scan each FE individually
            for module_id in sorted(self._module_cfgs.keys(), key=lambda x: (x is not None, x)):
                if self.abort_run.is_set():
                    break
                self.stop_run.clear()  # some scans use this event to stop scan loop, clear event here to make another scan possible
                if module_id is None:
                    continue
                with self.access_module(module_id=module_id):
                    logging.info('Scan parameter(s): %s', ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')
                    with self.register.restored(name=self.run_number):
                        self.configure()

                        self.fifo_readout.reset_rx()
                        self.fifo_readout.reset_sram_fifo()
                        self.fifo_readout.print_readout_status()

                        with self.open_file(module_id=module_id):
                            self.scan()

                self.fifo_readout.print_readout_status()

    def post_run(self):
        # analyzing data and store register cfg per front end one by one
        for module_id in sorted(self._module_cfgs.keys(), key=lambda x: (x is not None, x)):
            if self.abort_run.is_set():
                    break
            if module_id is None:
                continue
            with self.access_module(module_id=module_id):
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
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), flush=True)

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

    def get_module_path(self, module_id):
        return os.path.join(self.working_dir, module_id)

    def get_configuration(self, module_id, run_number=None):
        ''' Returns the configuration for a given module ID.

        The working directory is searched for a file matching the module_id with the
        given run number. If no run number is defined the last successfull run defines
        the run number.
        '''
        if module_id is None:
            return None

        def find_file(run_number):
            module_path = self.get_module_path(module_id)
            for root, _, files in os.walk(module_path):
                for cfgfile in files:
                    cfg_root, cfg_ext = os.path.splitext(cfgfile)
                    if cfg_root.startswith(''.join([str(run_number), '_', module_id])) and cfg_ext.endswith(".cfg"):
                        return os.path.join(root, cfgfile)

        if not run_number:
            run_numbers = sorted(self._get_run_numbers(status='FINISHED').iterkeys(), reverse=True)
            found_fin_run_cfg = True
            if not run_numbers:
                return None
            last_fin_run = run_numbers[0]
            for run_number in run_numbers:
                cfg_file = find_file(run_number)
                if cfg_file:
                    if not found_fin_run_cfg:
                        logging.warning("Module '%s' has no configuration for run %d, use config of run %d", module_id, last_fin_run, run_number)
                    return cfg_file
                else:
                    found_fin_run_cfg = False
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
        self._scan_parameters[self.current_module_handle] = self.scan_parameters._replace(**fields)
        self.scan_parameters = self._scan_parameters[self.current_module_handle]
        scan_parameters_new = self.scan_parameters._asdict()
        diff = [name for name in scan_parameters_old.keys() if np.any(scan_parameters_old[name] != scan_parameters_new[name])]
        if diff:
            logging.info('Changing scan parameter(s): %s', ', '.join([('%s=%s' % (name, fields[name])) for name in diff]))

    def __setattr__(self, name, value):
        ''' Always called to retrun the value for an attribute.
        '''
        if self.is_initialized and name not in self.__dict__:
            if self.current_module_handle not in self._module_attr:
                self._module_attr[self.current_module_handle] = {}
            self._module_attr[self.current_module_handle][name] = value
        else:
            super(Fei4RunBase, self).__setattr__(name, value)

    def __getattr__(self, name):
        ''' This is called in a last attempt to receive the value for an attribute that was not found in the usual places.
        '''
        try:
            return self._module_attr[self.current_module_handle][name]  # this has to come first
        except KeyError:
            try:
                return super(Fei4RunBase, self).__getattr__(name=name)
            except AttributeError:
                try:
                    return self._module_attr[None][name]
                except KeyError:
                    raise AttributeError("'%s' (current handle '%s') has no attribute '%s'" % (self.__class__.__name__, self.current_module_handle, name))

    @contextmanager
    def access_module(self, module_id):
        self.select_module(module_id=module_id)
        try:
            yield
        finally:
            # in case something fails, call this on last resort
            self.deselect_module()

    def select_module(self, module_id):
        ''' Select module and give access to the module.
        '''
        self.current_module_handle = module_id
        self.scan_parameters = self.get_scan_parameters(module_id=module_id)
        self.register = self.get_register(module_id=module_id)
        self.register_utils = self.get_register_utils(module_id=module_id)
        self.output_filename = self.get_output_filename(module_id=module_id)

    def deselect_module(self):
        ''' Deselect module and cleanup.
        '''
        self.current_module_handle = None
        self.scan_parameters = None
        self.register = None
        self.register_utils = None
        self.output_filename = None

    @contextmanager
    def open_file(self, module_id):
        self.create_file(module_id=module_id)
        try:
            yield
        finally:
            # in case something fails, call this on last resort
            self.close_file()

    def create_file(self, module_id):
        if module_id is None:
            selected_modules = [item for item in sorted(self._module_cfgs.keys(), key=lambda x: (x is not None, x)) if item is not None]
        else:
            selected_modules = [module_id]
        for selected_module_id in selected_modules:
            self._raw_data_files[selected_module_id] = open_raw_data_file(filename=self.get_output_filename(selected_module_id),
                                                                          mode='w',
                                                                          title=self.run_id,
                                                                          register=self.register,
                                                                          conf=self._conf,
                                                                          run_conf=self._run_conf,
                                                                          scan_parameters=self.scan_parameters._asdict(),
                                                                          socket_address=self._module_cfgs[selected_module_id]['send_data'])
        self.raw_data_file = Fei4RawDataHandle(raw_data_files=self._raw_data_files, module_cfgs=self._module_cfgs, selected_modules=selected_modules)

    def close_file(self):
        for module_id in sorted(self._raw_data_files.keys()):
            self._raw_data_files[module_id].close()
        # delete all file objects
        self._raw_data_files.clear()
        self.raw_data_file = None

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
        filter_f = kwargs.pop('filter', None)
        converter_f = kwargs.pop('converter', None)
        enabled_fe_channels = kwargs.pop('enabled_channels', filter(None, [item['rx'] for item in self._module_cfgs.itervalues()]))
        # this is the implementation for a filter and converter for a individual module
#         if self.current_module_handle is not None:
#             module_cfg = self._module_cfgs[self.current_module_handle]
#             if 'rx_channel' in module_cfg and module_cfg['rx_channel']:
#                 rx_filter = logical_and(is_fe_word, is_data_from_channel(module_cfg['rx_channel']))
#             else:
#                 rx_filter = false
#             if 'tdc_channel' in module_cfg and module_cfg['tdc_channel']:
#                 tdc_filter = logical_and(is_tdc_word, is_tdc_from_channel(module_cfg['tdc_channel']))
#                 converter = convert_tdc_to_channel(channel=module_cfg['tdc_channel'])
#             else:
#                 tdc_filter = false
#                 converter = None
#             filter = logical_or(is_trigger_word, logical_or(rx_filter, tdc_filter))
        if args or kwargs:
            self.set_scan_parameters(*args, **kwargs)
        self.fifo_readout.start(reset_sram_fifo=reset_sram_fifo, fill_buffer=fill_buffer, clear_buffer=clear_buffer, callback=callback, errback=errback, no_data_timeout=no_data_timeout, filter=filter_f, converter=converter_f, enabled_fe_channels=enabled_fe_channels)

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
            except:
                logging.warning("Failed sending pyBAR status report")

    def configure(self):
        '''The module configuration happens here.

        Will be executed before calling the scan method.
        Any changes of the module configuration will be reverted after after finishing the scan method.
        '''
        pass

    def scan(self):
        '''Implementation of the scan.
        '''
        pass

    def analyze(self):
        '''Implementation of the data analysis.

        Will be executed after finishing the scan method.
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
