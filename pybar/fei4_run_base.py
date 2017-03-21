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
                                     is_tdc_word, is_tdc_from_channel, convert_tdc_to_channel)


class Fei4RawDataHandle(object):
    ''' Access to single or multiple raw data files with filter functions.

    Needed to encapsulate raw data write from hardware setup.
    '''
    def __init__(self, raw_data_files, module_cfgs, module_id=None):
        ''' If module_id is not set use multiple files otherwise only the file of module_id '''
        if module_id:  # One file only
            self._raw_data_files = {module_id: raw_data_files[module_id]}
            self._module_cfgs = {module_id: module_cfgs[module_id]}
        else:  # Acces to multiple files
            self._raw_data_files = raw_data_files
            self._module_cfgs = module_cfgs

        # Module filter functions dict for quick lookup
        self._filter_funcs = {}
        self._converter_funcs = {}
        for module_id, setting in self._module_cfgs.iteritems():
            self._filter_funcs[module_id] = logical_or(
                is_trigger_word,
                logical_or(
                    logical_and(is_tdc_word, is_tdc_from_channel(setting['channel'])),
                    logical_and(is_fe_word, is_data_from_channel(setting['channel']))))
            self._converter_funcs[module_id] = convert_tdc_to_channel(channel=setting['channel'])

    def append_item(self, data_tuple, scan_parameters=None, new_file=False, flush=True):
        ''' Append raw data for each module after filtering the raw data for this module
        '''
        for module_id, filter_func in self._filter_funcs.iteritems():
            mod_data = convert_data_iterable((data_tuple,), filter_func=filter_func, converter_func=self._converter_funcs[module_id])
            self._raw_data_files[module_id].append_item(mod_data[0], scan_parameters=scan_parameters, new_file=new_file, flush=flush)


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

    def __init__(self, conf, run_conf=None):
        # default run conf parameters added for all scans
        if 'comment' not in self._default_run_conf:
            self._default_run_conf.update({'comment': ''})
        if 'reset_rx_on_error' not in self._default_run_conf:
            self._default_run_conf.update({'reset_rx_on_error': False})

        # Sets self._conf = conf
        super(Fei4RunBase, self).__init__(conf=conf, run_conf=run_conf)

        self.err_queue = Queue()
        self.fifo_readout = None

        self._module_cfgs = {}
        self._module_register_utils = {}
        self._raw_data_files = {}

        self._parse_module_cfgs(conf)
        self._n_modules = len(self._module_cfgs)
        self._set_default_cfg(conf)

        self.tdc = None  # Handle for TDC modules
        self._unset_module_handles()

        # Data structures to store scan related data
        self._attr = None  # Stores class attr before scan start to be able to restore
        self._scan_attr = {}  # Store specific scan attributes per module to make available after scan
        self._scan_pars = {}  # Store specific scan parameters per module to make available after scan
        self.scan_parameters = None

        self.set_scan_mode()

    def set_scan_mode(self):
        ''' Called during init to set scan in serial or paralle mode.

            Overwrite this function in the scan to change the mode.
            Std. setting is parallel.
        '''
        self.parallel = True

    def _parse_module_cfgs(self, conf):
        ''' Extracts the configuration of the modules '''

        if 'fe_configuration' in conf:
            raise NotImplementedError('You are using the old module configuration format. This is not supported anymore!')
        if 'send_data' in conf:
            raise NotImplementedError('Specifiy the send_data in the module cfg!')

        if 'modules' in conf:
            for module_id in conf['modules']:
                self._module_cfgs[module_id] = conf['modules'][module_id]

    def _set_default_cfg(self, conf):
        ''' Sets the default  parameters if they are not specified '''

        # Default module parameters
        for module_id, m_settings in self._module_cfgs.iteritems():
            if 'send_data' not in m_settings:
                m_settings.update({'send_data': None})  # address string of PUB socket
            if 'send_error_msg' not in m_settings:
                m_settings.update({'send_error_msg': None})  # bool
            if 'fe_configuration' not in m_settings:
                logging.warning('No fe_configuration for %s defined, fallback to std. config', module_id)
            if 'channel' not in m_settings:
                if self._n_modules > 1:
                    raise RuntimeError('No channel defined for %d in multi module configuration')
                else:  # Single module config, std channel is 4
                    self._module_cfgs[module_id]['channel'] = 4

        # Default config parameters
        if 'working_dir' not in conf:
            conf.update({'working_dir': ''})  # path string, if empty, path of configuration.yaml file will be used

    @property
    def dut(self):
        return self._conf['dut']

    def get_register(self, module_id):
        ''' Returns the register configuration of the module with given id '''
        return self._module_cfgs[module_id]['fe_configuration']

    def get_register_utils(self, module_id):
        ''' Returns the register utils of the module with given id '''
        return self._module_register_utils[module_id]

    def get_output_filename(self, module_id):
        module_path = os.path.join(self.working_dir, module_id)
        return os.path.join(module_path, str(self.run_number) + "_" + module_id + "_" + self.run_id)

    def init_dut(self):
        if self.dut.name == 'mio':
            if self.dut.get_modules('FEI4AdapterCard') and [adapter_card for adapter_card in self.dut.get_modules('FEI4AdapterCard') if adapter_card.name == 'ADAPTER_CARD']:
                if self._n_modules > 1:
                    raise RuntimeError('More than one module is not supported by your hardware!')
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
                if len(channel_names) < self._n_modules:
                    raise RuntimeError('Less hardware channels activated than modules defined.')
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
            self.tdc = TdcHandle(self.dut, tdc_modules=['TDC', 'TDC1', 'TDC2', 'TDC3', 'TDC4'])
        else:
            logging.warning('Omitting initialization of DUT %s', self.dut.name)

    def init_modules(self):
        ''' Initialize all modules consecutevly'''
        for module_id, m_config in self._module_cfgs.iteritems():
            last_configuration = self._get_configuration(module_id=module_id)
            # init config, a number <=0 will also do the initialization (run 0 does not exists)
            if (not m_config['fe_configuration'] and not last_configuration) or (isinstance(m_config['fe_configuration'], (int, long)) and m_config['fe_configuration'] <= 0):
                if 'chip_address' in m_config and m_config['chip_address'] is not None:
                    chip_address = m_config['chip_address']
                else:
                    # In single chip setups the std. address is usually 0
                    if self._n_modules == 1:
                        chip_address = 0
                    else:
                        raise RuntimeError('You have to specify a chip address in multi module setups')
                if 'fe_flavor' in m_config and m_config['fe_flavor']:
                    m_config['fe_configuration'] = FEI4Register(fe_type=m_config['fe_flavor'], chip_address=chip_address, broadcast=False)
                else:
                    raise ValueError('No fe_flavor given')
            # use existing config
            elif not m_config['fe_configuration'] and last_configuration:
                m_config['fe_configuration'] = FEI4Register(configuration_file=last_configuration)
            # path string
            elif isinstance(m_config['fe_configuration'], basestring):
                if os.path.isabs(m_config['fe_configuration']):  # absolute path
                    m_config['fe_configuration'] = FEI4Register(configuration_file=m_config['fe_configuration'])
                else:  # relative path
                    m_config['fe_configuration'] = FEI4Register(configuration_file=os.path.join(m_config['working_dir'], m_config['fe_configuration']))
            # run number
            elif isinstance(m_config['fe_configuration'], (int, long)) and m_config['fe_configuration'] > 0:
                m_config['fe_configuration'] = FEI4Register(configuration_file=self._get_configuration(module_id=module_id,
                                                                                                       run_number=m_config['fe_configuration']))
            # assume fe_configuration already initialized
            elif not isinstance(m_config['fe_configuration'], FEI4Register):
                raise ValueError('No valid fe_configuration given')

            # Init FE

            # init register utils
            self._module_register_utils[module_id] = FEI4RegisterUtils(self.dut, self.get_register(module_id))
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

    def _set_single_handles(self, module_id):
        ''' Sets handles to access one module
        '''
        self.register = self.get_register(module_id)
        self.output_filename = self.get_output_filename(module_id)
        self.register_utils = self.get_register_utils(module_id)

    def _check_fe_type(self):
        ''' Warns if all FE do not have the same flavor
        '''
        flavor = []
        for setting in self._module_cfgs.values():
            flavor.append(setting['fe_flavor'])
        if len(set(flavor)) > 1:
            logging.warning('Mixed FE flavor in broadcast mode.')
        return flavor[0]

    def _set_broadcast_handles(self):
        ''' Sets handles to access multiple module with broadcast
        '''
        fe_type = self._check_fe_type()  # Broadcast can fail if FE flavors differ
        self.register = FEI4Register(configuration_file=None,
                                     fe_type=fe_type,
                                     chip_address=None,
                                     broadcast=True)
        self.output_filename = None
        self.register_utils = FEI4RegisterUtils(self.dut, self.register)

    def _set_multi_handles(self):
        ''' Sets handles to access multiple module at different channels
        '''
        raise NotImplemented('This feature is not implemented yet')

    def _unset_module_handles(self):
        ''' Unset actual module handles
        '''
        self.register = None
        self.output_filename = None
        self.register_utils = None
        self.raw_data_file = None

    def _set_scan_par_from_run_cfg(self, module_id=None):
        ''' Sets the scan parameters defined in the run configuration

        If scan parameters are defined already (from a previous module scan) they are stored
        for later usage
        '''

        if 'scan_parameters' in self._run_conf:
            if isinstance(self._run_conf['scan_parameters'], basestring):
                self._run_conf['scan_parameters'] = ast.literal_eval(self._run_conf['scan_parameters'])
            sp = namedtuple('scan_parameters', field_names=zip(*self._run_conf['scan_parameters'])[0])
            self.scan_parameters = sp(*zip(*self._run_conf['scan_parameters'])[1])
        else:
            sp = namedtuple_with_defaults('scan_parameters', field_names=[])
            self.scan_parameters = sp()

    def pre_run(self):
        # clear error queue in case run is executed a second time
        self.err_queue.queue.clear()

        self._set_scan_par_from_run_cfg()
        logging.info('Scan parameter(s): %s', ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')

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
                        raise ValueError('dut_configuration parameter not a valid path: %s' % self._conf['dut_configuration'])
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
                            raise ValueError('bit_file parameter not a valid path: %s' % bit_file)
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

    def _store_attributes(self):
        ''' Store actual class attributes for later restore '''

        # Complete dict copy is not possible since objects do not always
        # support deepcopy
        self._attr = self.__dict__.keys()

    def _restore_attributes(self, module_id=None, store=False):
        ''' Restore stored class attributes

        Deletes all attributes that are not stored to keep class constant.
        These attributes were added in the scan and can be saved in an additional dict for
        later use. Als sets the run config to the default run config since it might
        be changed in the scan.

        Warnning: all classe attributes that are not given by run config parameters but existed before
        the scan are not restored. This is not possible with the actual design.
        '''

        scan_attr = {}
        for attr in self.__dict__.keys():
            # attr is added in scan
            if attr not in self._attr:
                scan_attr[attr] = self.__dict__[attr]
                del self.__dict__[attr]
            # attr is a default run config that was maybe changed
            if attr in self._default_run_conf.keys():
                scan_attr[attr] = self.__dict__[attr]

        if store:
            self._scan_attr[module_id] = scan_attr

        # Set default run conf (e.g. self.plots_filename was changed)
        self._init_run_conf(run_conf=False, update=False)

        # Reset scan pars (e.g. scan par PlsrDAC was changed)
        self._set_scan_par_from_run_cfg()

    def _load_scan_attr(self, module_id):
        ''' Load the scan attributes for module with module_id that where added during scan
        '''
        try:  # serial scan
            self.__dict__.update(self._scan_attr[module_id])
        except KeyError:  # parallel scan, there is only one scan attr dict
            self.__dict__.update(self._scan_attr[None])

    def _store_scan_pars(self, module_id=None):
        ''' Store the scan parameters for module with module_id.

        These where maybe changed during scan and are maybe needed in post run data analysis
        '''
        if self.scan_parameters:
            self._scan_pars[module_id] = self.scan_parameters

    def _load_scan_par(self, module_id):
        ''' Load the scan parameters for module with module_id that where maybe changed during scan
        '''
        try:  # There are module specific scan parameters (serial scan)
            self.scan_parameters = self._scan_pars[module_id]
        except KeyError:  # No module specific scan pars (parallel scan)
            try:
                self.scan_parameters = self._scan_pars[None]
            except KeyError:  # No scan parameters at all
                self.scan_parameters = None
                pass

    def do_run(self):
        ''' Start runs on all modules sequentially.

        Sets properties to access current module properties.
        '''

        if not self.parallel:  # Use each FE one by one
            for module_id in self._module_cfgs:
                # Gives access for scan to actual module
                self._set_single_handles(module_id)

                with self.register.restored(name=self.run_number):
                    # configure for scan
                    self.configure()
                    self.fifo_readout.reset_rx()
                    self.fifo_readout.reset_sram_fifo()
                    self.fifo_readout.print_readout_status()

                    with open_raw_data_file(filename=self.get_output_filename(module_id), mode='w', title=self.run_id, register=self.register,
                                            conf=self._conf, run_conf=self._run_conf,
                                            scan_parameters=self.scan_parameters._asdict(),
                                            socket_address=self._module_cfgs[module_id]['send_data']) as self._raw_data_files[module_id]:
                        self.raw_data_file = Fei4RawDataHandle(self._raw_data_files, self._module_cfgs, module_id=module_id)

                        # Run the scan but restore class attributes that might have been set
                        self._store_attributes()
                        self.scan()
                        self._store_scan_pars(module_id)
                        self._restore_attributes(module_id=module_id, store=True)

                # For safety to prevent no crash if handles is not set correclty
                self._unset_module_handles()
        else:  # Use all FE at once with command broadcast
            # Gives access for scan to all modules
            self._set_broadcast_handles()
            self.configure()
            self.fifo_readout.reset_rx()
            self.fifo_readout.reset_sram_fifo()
            self.fifo_readout.print_readout_status()

            with contextlib.ExitStack() as stack:
                for module_id in self._module_cfgs:
                    self._raw_data_files[module_id] = stack.enter_context(open_raw_data_file(filename=self.get_output_filename(module_id), mode='w', title=self.run_id, register=self.register,
                                                                                             conf=self._conf, run_conf=self._run_conf,
                                                                                             scan_parameters=self.scan_parameters._asdict(),
                                                                                             socket_address=self._module_cfgs[module_id]['send_data']))
                self.raw_data_file = Fei4RawDataHandle(self._raw_data_files, self._module_cfgs)

                self._store_attributes()
                self.scan()
                self._store_scan_pars(module_id)
                self._restore_attributes(store=True)

            # For safety to prevent NO crash if handles is not set correclty
            self._unset_module_handles()

    def post_run(self):
        try:
            self.fifo_readout.print_readout_status()
        except Exception:  # no device?
            pass

        # analyzing data and store register cfg per front end one by one
        for module_id in self._module_cfgs:
            # Set module specific handles and data structures
            self._set_single_handles(module_id)
            self._load_scan_attr(module_id)
            self._load_scan_par(module_id)

            try:
                self.analyze()
            except Exception:  # analysis errors
                self.handle_err(sys.exc_info())
            else:  # analyzed data, save config
                self.register.save_configuration(self.output_filename)

            # Reset module specific handles and data structures
            # To prevent silent bugs
            self._unset_module_handles()
            self._restore_attributes(module_id)
            self.scan_parameters = None

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

    def _get_configuration(self, module_id, run_number=None):
        ''' Returns the configuration for a given module_id

        The working directory is searched for a file matching the module_id with the
        given run number. If no run number is defined the last successfull run defines
        the run number.
        '''
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
                        logging.warning('Module %s has no configuration for run %d, use config of run %d', module_id, last_fin_run, run_number)
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
        filter = kwargs.pop('filter', None)
        converter = kwargs.pop('converter', None)
        # this is the implementation for a filter and converter for a individual module
#         if self.current_single_handle is not None:
#             module_cfg = self._module_cfgs[self.current_single_handle]
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
        self.fifo_readout.start(reset_sram_fifo=reset_sram_fifo, fill_buffer=fill_buffer, clear_buffer=clear_buffer, callback=callback, errback=errback, no_data_timeout=no_data_timeout, filter=filter, converter=converter)

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
