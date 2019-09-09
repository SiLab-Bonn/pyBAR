import logging
import time
import os
import itertools
import string
import struct
import smtplib
from socket import gethostname
from functools import wraps
from threading import Event, Thread, current_thread, Lock, RLock, _MainThread
from Queue import Queue
from collections import namedtuple, Mapping, Iterable
from contextlib import contextmanager
from operator import itemgetter
import abc
import ast
import inspect
import sys

from contextlib2 import ExitStack
import numpy as np

import basil
from basil.dut import Dut

from pybar.utils.utils import groupby_dict, dict_compare, zip_nofill, find_file_dir_up
from pybar.run_manager import RunManager, RunBase, RunAborted
from pybar.fei4.register import FEI4Register
from pybar.fei4.register import flavors as fe_flavors
from pybar.fei4.register_utils import FEI4RegisterUtils, is_fe_ready
from pybar.daq.fifo_readout import FifoReadout, RxSyncError, EightbTenbError, FifoError, NoDataTimeout, StopTimeout
from pybar.daq.readout_utils import save_configuration_dict
from pybar.daq.fei4_raw_data import open_raw_data_file, send_meta_data
from pybar.analysis.analysis_utils import AnalysisError
from pybar.daq.readout_utils import logical_or, logical_and, is_trigger_word, is_fe_word, is_data_from_channel, is_tdc_word, is_tdc_from_channel, convert_tdc_to_channel, false


_reserved_driver_names = ["FIFO", "TX", "RX", "TLU", "TDC"]


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
        self.err_queue = Queue()
        self.global_lock = RLock()

        self._module_run_conf = {}  # Store module specific run conf
        self._module_cfgs = {}  # Store module specific configurations
        self._modules = {}  # Module IDs of real modules
        self._tx_module_groups = {}  # Module IDs of TX module groups (virtual modules) that share the same command output (TX)
        self._registers = {}  # Store module specific FEI4 registers
        self._register_utils = {}  # Store module specific FEI4 register utils
        self._raw_data_files = {}  # Store module specific raw data files
        self._scan_parameters = {}  # Store module specific scan parameters
        self._module_attr = {}  # Store module specific scan attributes
        self._module_dut = {}  # Store module specific DUT handle
        self.fifo_readout = None  # FIFO readout instances
        self._selected_modules = []
        self._selected_fifos = []  # currently activated FIFOs
        self._readout_fifos = []
        self._converter = []
        self._filter = []
        self._enabled_fe_channels = []  # currently activated receivers
        self._current_module_handle = None  # setting "None" module as default module
        self._scan_threads = []  # list of currently running scan threads
        self._curr_readout_threads = []  # list of currently running threads awaiting start of FIFO readout
        self._readout_lock = Lock()
        self._starting_readout_event = Event()
        self._starting_readout_event.clear()
        self._stopping_readout_event = Event()
        self._stopping_readout_event.clear()
        self._curr_sync_threads = []
        self._sync_lock = Lock()
        self._enter_sync_event = Event()
        self._enter_sync_event.clear()
        self._exit_sync_event = Event()
        self._exit_sync_event.clear()
        self._parse_module_cfgs()
        self._init_default_run_conf()
        # after initialized is set to True, all new attributes are belonging to selected mudule
        # by default the "None" module is selected (current_module_handle is None)
        self._initialized = True

    @property
    def is_initialized(self):
        if "_initialized" in self.__dict__ and self._initialized:
            return True
        else:
            return False

    @property
    def current_module_handle(self):
        if self._current_module_handle is None:
            thread_name = current_thread().name
            module_handles = [module_id for module_id in self._module_cfgs if (module_id is not None and module_id == thread_name)]
            if len(module_handles) > 1:
                raise RuntimeError("Could not determine module handle. Thread name contains multiple module IDs: %s" % ", ".join(module_handles))
            if len(module_handles) == 0:
                return None
#                 raise RuntimeError('Could not determine module handle from thread name "%s"' % thread_name)
            return module_handles[0]
        else:
            return self._current_module_handle

    @property
    def register(self):
        return self._registers[self.current_module_handle]

    @property
    def register_utils(self):
        return self._register_utils[self.current_module_handle]

    @property
    def output_filename(self):
        return self.get_output_filename(module_id=self.current_module_handle)

    @property
    def run_conf(self):
        run_conf = namedtuple('run_conf', field_names=self._module_run_conf[self.current_module_handle].keys())
        return run_conf(*self._module_run_conf[self.current_module_handle])  # prevent changing dict

    @property
    def scan_parameters(self):
        return self._scan_parameters[self.current_module_handle]

    @property
    def dut(self):
        return self._module_dut[self.current_module_handle]

    @property
    def raw_data_file(self):
        return self._raw_data_files[self.current_module_handle]

    def _parse_module_cfgs(self):
        ''' Extracts the configuration of the modules.
        '''
        # Adding here default run config parameters.
        if "dut" not in self._conf or self._conf["dut"] is None:
            raise ValueError('Parameter "dut" not defined.')
        if "dut_configuration" not in self._conf or self._conf["dut_configuration"] is None:
            raise ValueError('Parameter "dut_configuration" not defined.')
        self._conf.setdefault('working_dir', None)  # string, if None, absolute path of configuration.yaml file will be used

        if 'modules' in self._conf and self._conf['modules']:
            for module_id, module_cfg in [(key, value) for key, value in self._conf['modules'].items() if ("activate" not in value or ("activate" in value and value["activate"] is True))]:
                # Check here for missing module config items.
                # Capital letter keys are Basil drivers, other keys are parameters.
                # FIFO, RX, TX, TLU and TDC are generic driver names which are used in the scan implementations.
                # The use of these reserved driver names allows for abstraction.
                # Accessing Basil drivers with real name is still possible.
                if "module_group" in module_id:
                    raise ValueError('The module ID "%s" contains the reserved name "module_group".' % module_id)
                if "flavor" not in module_cfg or module_cfg["flavor"] is None:
                    raise ValueError('No parameter "flavor" defined for module "%s".' % module_id)
                if module_cfg["flavor"] in fe_flavors:
                    for driver_name in _reserved_driver_names:
                        # TDC is not mandatory
                        if driver_name == "TDC":
                            # TDC is allowed to have set None
                            module_cfg.setdefault('TDC', None)
                            continue
                        if driver_name not in module_cfg or module_cfg[driver_name] is None:
                            raise ValueError('No parameter "%s" defined for module "%s".' % (driver_name, module_id))
                    if "rx_channel" not in module_cfg or module_cfg["rx_channel"] is None:
                        raise ValueError('No parameter "rx_channel" defined for module "%s".' % module_id)
                    if "tx_channel" not in module_cfg or module_cfg["tx_channel"] is None:
                        raise ValueError('No parameter "tx_channel" defined for module "%s".' % module_id)
                    if "chip_address" not in module_cfg:
                        raise ValueError('No parameter "chip_address" defined for module "%s".' % module_id)
                    module_cfg.setdefault("tdc_channel", None)
                    module_cfg.setdefault("configuration", None)  # string or number, if None, using the last valid configuration
                    module_cfg.setdefault("send_data", None)  # address string of PUB socket
                    module_cfg.setdefault("activate", True)  # set module active by default
                    # Save config to dict.
                    self._module_cfgs[module_id] = module_cfg
                    self._modules[module_id] = [module_id]
        else:
            raise ValueError("No module configuration specified")

    def _init_default_run_conf(self):
        # set up default run conf parameters
        self._default_run_conf.setdefault('comment', '{}'.format(self.__class__.__name__))
        self._default_run_conf.setdefault('reset_rx_on_error', False)
        # Enabling broadcast commands will significantly improve the speed of scans.
        # Only those scans can be accelerated which commands can be broadcastet and
        # which commands are not individual for each module.
        self._default_run_conf.setdefault('broadcast_commands', False)
        # Enabling threaded scan improves the speed of scans
        # and require multiple TX for sending commands.
        # If only a single TX is available, no speed improvement is gained.
        self._default_run_conf.setdefault('threaded_scan', False)
        # If True, send full configuration to the FE-I4 before the configuration step.
        self._default_run_conf.setdefault('configure_fe', True)
        # If True, perform a FE-I4 reset (ECR and BCR).
        self._default_run_conf.setdefault('reset_fe', True)

    def _init_run_conf(self, run_conf):
        # same implementation as in base class, but ignore "scan_parameters" property
        attribute_names = [key for key in self._default_run_conf.keys() if (key != "scan_parameters" and (key in self.__dict__ or (hasattr(self.__class__, key) and isinstance(getattr(self.__class__, key), property))))]
        if attribute_names:
            raise RuntimeError('Attribute names already in use. Rename the following parameters in run conf: %s' % ', '.join(attribute_names))
        sc = namedtuple('run_configuration', field_names=self._default_run_conf.keys())
        default_run_conf = sc(**self._default_run_conf)
        if run_conf:
            self._run_conf = default_run_conf._replace(**run_conf)._asdict()
        else:
            self._run_conf = default_run_conf._asdict()

        # check for invalid run conf parameters
        if self._run_conf['broadcast_commands'] and not self._default_run_conf['broadcast_commands']:
            raise RuntimeError('Changing "broadcast_commands" parameter from False (default) to True.')
        if self._run_conf['broadcast_commands'] and 'modules' in self._conf and self._conf['modules']:
            tx_groups = groupby_dict({key: value for (key, value) in self._module_cfgs.items() if key in self._modules}, "TX")
            for module_group in tx_groups.values():
                for module_id in module_group:
                    if self.__class__.__name__ in self._conf["modules"][module_id] and self._conf["modules"][module_id][self.__class__.__name__] is not None:
                        for other_module_id in module_group:
                            if self.__class__.__name__ in self._conf["modules"][other_module_id] and self._conf["modules"][other_module_id][self.__class__.__name__] is not None:
                                if any(dict_compare(self._conf["modules"][module_id][self.__class__.__name__], self._conf["modules"][other_module_id][self.__class__.__name__])[:3]):
                                    raise RuntimeError('Module "%s" has specific run configuration that is different from module "%s" for "%s" and "broadcast_commands" parameter is set to True.' % (other_module_id, module_id, self.__class__.__name__))
                            else:
                                raise RuntimeError('Module "%s" has no specific run configuration for "%s" and "broadcast_commands" parameter is set to True.' % (other_module_id, self.__class__.__name__))

    def _set_default_cfg(self):
        ''' Sets the default parameters if they are not specified.
        '''
        # adding special conf for accessing all DUT drivers
        self._module_cfgs[None] = {
            'flavor': None,
            'chip_address': None,
            'FIFO': list(set([self._module_cfgs[module_id]['FIFO'] for module_id in self._modules])),
            'RX': list(set([self._module_cfgs[module_id]['RX'] for module_id in self._modules])),
            'rx_channel': list(set([self._module_cfgs[module_id]['rx_channel'] for module_id in self._modules])),
            'TX': list(set([self._module_cfgs[module_id]['TX'] for module_id in self._modules])),
            'tx_channel': list(set([self._module_cfgs[module_id]['tx_channel'] for module_id in self._modules])),
            'TDC': list(set([self._module_cfgs[module_id]['TDC'] for module_id in self._modules])),
            'tdc_channel': list(set([self._module_cfgs[module_id]['tdc_channel'] for module_id in self._modules])),
            'TLU': list(set([self._module_cfgs[module_id]['TLU'] for module_id in self._modules])),
            'configuration': None,
            'send_data': None}

        tx_groups = groupby_dict({key: value for (key, value) in self._module_cfgs.items() if key in self._modules}, "TX")
        for tx, module_group in tx_groups.items():
            flavors = list(set([module_cfg['flavor'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group]))
            if len(flavors) != 1:
                raise ValueError("Parameter 'flavor' must be the same for module group TX=%s." % tx)

            chip_addresses = list(set([module_cfg['chip_address'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group]))
            if len(module_group) != len(chip_addresses) or (len(module_group) != 1 and None in chip_addresses):
                raise ValueError("Parameter 'chip_address' must be different for each module in module group TX=%s." % tx)

            # Adding broadcast config for parallel mode.
            self._module_cfgs["module_group_TX=" + tx] = {
                'flavor': flavors[0],
                'chip_address': None,  # broadcast
                'FIFO': list(set([module_cfg['FIFO'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'RX': list(set([module_cfg['RX'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'rx_channel': list(set([module_cfg['rx_channel'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'TX': tx,
                'tx_channel': list(set([module_cfg['tx_channel'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'TDC': list(set([module_cfg['TDC'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'tdc_channel': list(set([module_cfg['tdc_channel'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'TLU': list(set([module_cfg['TLU'] for module_id, module_cfg in self._module_cfgs.items() if module_id in module_group])),
                'configuration': None,
                'send_data': None}
            self._tx_module_groups["module_group_TX=" + tx] = module_group

        # Setting up per module attributes
        self._module_attr = {key: {} for key in self._module_cfgs}
        # Setting up per module run conf
        for module_id in self._module_cfgs:
            sc = namedtuple('run_configuration', field_names=self._default_run_conf.keys())
            run_conf = sc(**self._run_conf)
            # update run configuration if provided by module configuration
            if module_id in self._modules and self.__class__.__name__ in self._conf["modules"][module_id] and self._conf["modules"][module_id][self.__class__.__name__] is not None:
                self._module_run_conf[module_id] = run_conf._replace(**self._conf["modules"][module_id][self.__class__.__name__])._asdict()
            else:
                self._module_run_conf[module_id] = run_conf._asdict()
                # update module group with run specific configuration
                if module_id in self._tx_module_groups and self._tx_module_groups[module_id]:
                    selected_module_id = self._tx_module_groups[module_id][0]
                    if self.__class__.__name__ in self._conf["modules"][selected_module_id] and self._conf["modules"][selected_module_id][self.__class__.__name__] is not None:
                        self._module_run_conf[module_id] = run_conf._replace(**self._conf["modules"][selected_module_id][self.__class__.__name__])._asdict()

    def init_dut(self):
        if self.dut.name == 'mio':  # MIO2 with Single Chip Adapter Card (SCAC) or QUAD Module Adapter Card
            if self.dut.get_modules('FEI4AdapterCard') and [adapter_card for adapter_card in self.dut.get_modules('FEI4AdapterCard') if adapter_card.name == 'SINGLE_CHIP_ADAPTER_CARD']:
                try:
                    self.dut['SINGLE_CHIP_ADAPTER_CARD'].set_voltage('VDDA1', 1.5)
                    self.dut['SINGLE_CHIP_ADAPTER_CARD'].set_voltage('VDDA2', 1.5)
                    self.dut['SINGLE_CHIP_ADAPTER_CARD'].set_voltage('VDDD1', 1.2)
                    self.dut['SINGLE_CHIP_ADAPTER_CARD'].set_voltage('VDDD2', 1.2)
                except struct.error:
                    logging.warning('Cannot set voltages. Adapter card not calibrated? Voltages out of range?')
                self.dut['POWER_SCC']['EN_VD1'] = 1
                self.dut['POWER_SCC']['EN_VD2'] = 1  # also EN_VPLL on old SCAC
                self.dut['POWER_SCC']['EN_VA1'] = 1
                self.dut['POWER_SCC']['EN_VA2'] = 1
                self.dut['POWER_SCC'].write()
                self.dut['ENABLE_CHANNEL']['DATA_CH1'] = 0  # RD2Bar on SCAC
                self.dut['ENABLE_CHANNEL']['DATA_CH2'] = 0  # RD1Bar on SCAC
                self.dut['ENABLE_CHANNEL']['DATA_CH3'] = 0  # RABar on SCAC
                self.dut['ENABLE_CHANNEL']['DATA_CH4'] = 1
                self.dut['ENABLE_CHANNEL']['TLU'] = 1
                self.dut['ENABLE_CHANNEL']['TDC'] = 1
                self.dut['ENABLE_CHANNEL'].write()
            elif self.dut.get_modules('FEI4QuadModuleAdapterCard') and [adapter_card for adapter_card in self.dut.get_modules('FEI4QuadModuleAdapterCard') if adapter_card.name == 'QUAD_MODULE_ADAPTER_CARD']:
                # resetting over current status
                self.dut['POWER_QUAD']['EN_DATA_CH1'] = 0
                self.dut['POWER_QUAD']['EN_DATA_CH2'] = 0
                self.dut['POWER_QUAD']['EN_DATA_CH3'] = 0
                self.dut['POWER_QUAD']['EN_DATA_CH4'] = 0
                self.dut['POWER_QUAD'].write()
                try:
                    self.dut['QUAD_MODULE_ADAPTER_CARD'].set_voltage('CH1', 2.1)
                    self.dut['QUAD_MODULE_ADAPTER_CARD'].set_voltage('CH2', 2.1)
                    self.dut['QUAD_MODULE_ADAPTER_CARD'].set_voltage('CH3', 2.1)
                    self.dut['QUAD_MODULE_ADAPTER_CARD'].set_voltage('CH4', 2.1)
                except struct.error:
                    logging.warning('Cannot set voltages. Adapter card not calibrated? Voltages out of range?')
                rx_names = [rx.name for rx in self.dut.get_modules('fei4_rx')]
                active_rx_names = [module_cfg["RX"] for (name, module_cfg) in self._module_cfgs.items() if name in self._modules]
                for rx_name in rx_names:
                    # enabling/disabling Rx
                    if rx_name in active_rx_names:
                        self.dut['ENABLE_CHANNEL'][rx_name] = 1
                        self.dut['POWER_QUAD']['EN_' + rx_name] = 1
                    else:
                        self.dut['ENABLE_CHANNEL'][rx_name] = 0
                        self.dut['POWER_QUAD']['EN_' + rx_name] = 0
                self.dut['ENABLE_CHANNEL']['TLU'] = 1
                self.dut['ENABLE_CHANNEL']['TDC'] = 1
                self.dut['ENABLE_CHANNEL'].write()
                self.dut['POWER_QUAD'].write()
            else:
                logging.warning('Unknown adapter card')
                # do the minimal configuration here
                self.dut['ENABLE_CHANNEL']['DATA_CH1'] = 0  # RD2Bar on SCAC
                self.dut['ENABLE_CHANNEL']['DATA_CH2'] = 0  # RD1Bar on SCAC
                self.dut['ENABLE_CHANNEL']['DATA_CH3'] = 0  # RABar on SCAC
                self.dut['ENABLE_CHANNEL']['DATA_CH4'] = 1
                self.dut['ENABLE_CHANNEL']['TLU'] = 1
                self.dut['ENABLE_CHANNEL']['TDC'] = 1
                self.dut['ENABLE_CHANNEL'].write()
        elif self.dut.name == 'mio_gpac':  # MIO2 with Genaral Purpose Analog Card (GPAC)
            # PWR
            self.dut['V_in'].set_current_limit(0.1, unit='A')  # one for all, max. 1A
            # V_in
            self.dut['V_in'].set_voltage(2.1, unit='V')
            self.dut['V_in'].set_enable(True)
            if self.dut['V_in'].get_over_current():
                self.power_off()
                raise Exception('V_in overcurrent detected')
            # Vdd, also enabling LVDS transceivers
            self.dut['CCPD_Vdd'].set_voltage(1.80, unit='V')
            self.dut['CCPD_Vdd'].set_enable(True)
            if self.dut['CCPD_Vdd'].get_over_current():
                self.power_off()
                raise Exception('Vdd overcurrent detected')
            # Vssa
            self.dut['CCPD_Vssa'].set_voltage(1.50, unit='V')
            self.dut['CCPD_Vssa'].set_enable(True)
            if self.dut['CCPD_Vssa'].get_over_current():
                self.power_off()
                raise Exception('Vssa overcurrent detected')
            # VGate
            self.dut['CCPD_VGate'].set_voltage(2.10, unit='V')
            self.dut['CCPD_VGate'].set_enable(True)
            if self.dut['CCPD_VGate'].get_over_current():
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
        elif self.dut.name in ['mmc3_8chip_eth', 'mmc3_8chip_multi_tx_eth', 'mmc3_16chip_multi_tx_eth']:  # Multi Module Card (MMC3)
            for register in self.dut.get_modules('StdRegister'):
                if 'DLY_CONFIG' in register.name:
                    register['CLK_DLY'] = 0
                    register.write()
        elif self.dut.name == 'mmc3_beast_eth':  # MMC3 for BEAST/FANGS experiment at KEK
            for register in self.dut.get_modules('StdRegister'):
                if 'DLY_CONFIG' in register.name:
                    register['CLK_DLY'] = 0
                    register.write()
        else:
            # This helps to enable regulators on Single Chip Adapter Card (SCAC) in a multi-board configuration
            # Note: Keep the original basil names and add a string to it, e.g.:
            #       SINGLE_CHIP_ADAPTER_CARD -> SINGLE_CHIP_ADAPTER_CARD_TELESCOPE_0
            #       POWER_SCC -> POWER_SCC_TELESCOPE_0
            #       ENABLE_CHANNEL -> ENABLE_CHANNEL_TELESCOPE_0
            for adapter_card in self.dut.get_modules('FEI4AdapterCard'):
                if 'SINGLE_CHIP_ADAPTER_CARD' in adapter_card.name:
                    try:
                        adapter_card.set_voltage('VDDA1', 1.5)
                        adapter_card.set_voltage('VDDA2', 1.5)
                        adapter_card.set_voltage('VDDD1', 1.2)
                        adapter_card.set_voltage('VDDD2', 1.2)
                    except struct.error:
                        logging.warning('Cannot set voltages. Adapter card not calibrated? Voltages out of range?')
            for register in self.dut.get_modules('StdRegister'):
                if 'POWER_SCC' in register.name:
                    register['EN_VD1'] = 1
                    register['EN_VD2'] = 1  # also EN_VPLL on old SCAC
                    register['EN_VA1'] = 1
                    register['EN_VA2'] = 1
                    register.write()
            for register in self.dut.get_modules('StdRegister'):
                if 'ENABLE_CHANNEL' in register.name:
                    register['DATA_CH1'] = 0  # RD2Bar on SCAC, CH1 on quad module adapter card
                    register['DATA_CH2'] = 0  # RD1Bar on SCAC, CH2 on quad module adapter card
                    register['DATA_CH3'] = 0  # RABar on SCAC, CH3 on quad module adapter card
                    register['DATA_CH4'] = 1
                    register['TLU'] = 1
                    register['TDC'] = 1
                    register.write()
#        else:
#            logging.warning('Unknown DUT name: %s', self.dut.name)

    def init_modules(self):
        ''' Initialize all modules consecutively'''
        for module_id, module_cfg in self._module_cfgs.items():
            if module_id in self._modules or module_id in self._tx_module_groups:
                if module_id in self._modules:
                    module_id_str = "module " + module_id
                else:
                    module_id_str = module_id.split('=', 1)
                    module_id_str[0] = module_id_str[0].replace("_", " ")
                    module_id_str = "=".join(module_id_str)
                logging.info("Initializing configuration for %s..." % module_id_str)
                # adding scan parameters to dict
                if 'scan_parameters' in self._module_run_conf[module_id] and self._module_run_conf[module_id]['scan_parameters'] is not None:
                    # evaluating string for support of nested lists and other complex data structures
                    if isinstance(self._module_run_conf[module_id]['scan_parameters'], basestring):
                        self._module_run_conf[module_id]['scan_parameters'] = ast.literal_eval(self._module_run_conf[module_id]['scan_parameters'])
                    sp = namedtuple('scan_parameters', field_names=zip(*self._module_run_conf[module_id]['scan_parameters'])[0])
                    self._scan_parameters[module_id] = sp(*zip(*self._module_run_conf[module_id]['scan_parameters'])[1])
                else:
                    sp = namedtuple_with_defaults('scan_parameters', field_names=[])
                    self._scan_parameters[module_id] = sp()
                # init FE config
                if module_id in self._modules:
                    # only real modules can have an existing configuration
                    last_configuration = self.get_configuration(module_id=module_id)
                else:
                    last_configuration = None
                if (('configuration' not in module_cfg or module_cfg['configuration'] is None) and last_configuration is None) or (isinstance(module_cfg['configuration'], (int, long)) and module_cfg['configuration'] <= 0):
                    if 'chip_address' in module_cfg:
                        if module_cfg['chip_address'] is None:
                            chip_address = 0
                            broadcast = True
                        else:
                            chip_address = module_cfg['chip_address']
                            broadcast = False
                    else:
                        raise ValueError('Parameter "chip_address" not specified for module "%s".' % module_id)
                    if 'flavor' in module_cfg and module_cfg['flavor']:
                        module_cfg['configuration'] = FEI4Register(fe_type=module_cfg['flavor'], chip_address=chip_address, broadcast=broadcast)
                    else:
                        raise ValueError('Parameter "flavor" not specified for module "%s".' % module_id)
                # use existing config
                elif not module_cfg['configuration'] and last_configuration:
                    module_cfg['configuration'] = FEI4Register(configuration_file=last_configuration)
                # path string
                elif isinstance(module_cfg['configuration'], basestring):
                    if os.path.isabs(module_cfg['configuration']):  # absolute path
                        module_cfg['configuration'] = FEI4Register(configuration_file=module_cfg['configuration'])
                    else:  # relative path
                        module_cfg['configuration'] = FEI4Register(configuration_file=os.path.join(module_cfg['working_dir'], module_cfg['configuration']))
                # run number
                elif isinstance(module_cfg['configuration'], (int, long)) and module_cfg['configuration'] > 0:
                    module_cfg['configuration'] = FEI4Register(configuration_file=self.get_configuration(module_id=module_id, run_number=module_cfg['configuration']))
                # assume configuration already initialized
                elif not isinstance(module_cfg['configuration'], FEI4Register):
                    raise ValueError('Found no valid value for parameter "configuration" for module "%s".' % module_id)

                # init register utils
                self._registers[module_id] = self._module_cfgs[module_id]['configuration']
                self._register_utils[module_id] = FEI4RegisterUtils(self._module_dut[module_id], self._module_cfgs[module_id]['configuration'])

                if module_id in self._modules:
                    # Create module data path for real modules
                    module_path = self.get_module_path(module_id)
                    if not os.path.exists(module_path):
                        os.makedirs(module_path)

        # Set all modules to conf mode to prevent from receiving BCR and ECR broadcast
        for module_id in self._tx_module_groups:
            with self.access_module(module_id=module_id):
                self.register_utils.set_conf_mode()

        # Initial configuration (reset and configuration) of all modules.
        # This is done by iterating over each module individually
        for module_id in self._modules:
            logging.info("Configuring %s..." % module_id)
            with self.access_module(module_id=module_id):
                if self._run_conf['configure_fe']:
                    self.register_utils.global_reset()
                    self.register_utils.configure_all()
                else:
                    self.register_utils.set_conf_mode()
                if is_fe_ready(self):
                    fe_not_ready = False
                else:
                    fe_not_ready = True
                # BCR and ECR might result in RX errors
                # a reset of the RX and FIFO will happen just before scan()
                if self._run_conf['reset_fe']:
                    self.register_utils.reset_bunch_counter()
                    self.register_utils.reset_event_counter()
                if fe_not_ready:
                    # resetting service records must be done once after power up
                    self.register_utils.reset_service_records()
                    if not is_fe_ready(self):
                        logging.warning('Module "%s" is not sending any data.' % module_id)
                # set all modules to conf mode afterwards to be immune to ECR and BCR
                self.register_utils.set_conf_mode()

    def pre_run(self):
        # clear error queue in case run is executed another time
        self.err_queue.queue.clear()
        # set default configuration, revert any changes that were done by last run
        self._set_default_cfg()

        # init DUT
        if not isinstance(self._conf['dut'], Dut):  # Check if already initialized
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
                    # working dir, and directorys upwards
                    elif find_file_dir_up(filename=self._conf['dut_configuration'], path=self._conf['working_dir']):
                        dut_configuration = find_file_dir_up(filename=self._conf['dut_configuration'], path=self._conf['working_dir'])
                    # path of this file
                    elif os.path.isfile(os.path.join(module_path, self._conf['dut_configuration'])):
                        dut_configuration = os.path.join(module_path, self._conf['dut_configuration'])
                    else:
                        raise ValueError("Parameter 'dut_configuration' is not a valid path: %s" % self._conf['dut_configuration'])
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
            # check for existence of reserved driver names
            found_reserved_names = []
            for driver_name in _reserved_driver_names:
                try:
                    dut[driver_name]
                    found_reserved_names.append(driver_name)
                except KeyError:
                    pass
            if found_reserved_names:
                raise RuntimeError("The basil DUT contains reserved driver names: %s" % ", ".join(found_reserved_names))
            logging.info('Initializing basil...')
            dut.init(dut_configuration)
            # assign dut after init in case of exceptions during init
            self._conf['dut'] = dut
            # adding DUT handles
            for module_id, module_cfg in self._module_cfgs.items():
                self._module_dut[module_id] = DutHandle(dut=self._conf['dut'], module_cfg=module_cfg)
            self.fifo_readout = FifoReadout(dut=self._conf['dut'])
            # additional init of the DUT
            self.init_dut()
        else:
            # adding DUT handles
            for module_id, module_cfg in self._module_cfgs.items():
                self._module_dut[module_id] = DutHandle(dut=self._conf['dut'], module_cfg=module_cfg)
            self.fifo_readout = FifoReadout(dut=self._conf['dut'])

        # initialize the modules
        self.init_modules()

    def do_run(self):
        ''' Start runs on all modules sequentially.

        Sets properties to access current module properties.
        '''
        if self.broadcast_commands:  # Broadcast FE commands
            if self.threaded_scan:
                with ExitStack() as restore_config_stack:
                    # Configure each FE individually
                    # Sort module config keys, configure broadcast modules first
                    for module_id in itertools.chain(self._tx_module_groups, self._modules):
                        if self.abort_run.is_set():
                            break
                        with self.access_module(module_id=module_id):
                            if module_id in self._modules:
                                module_id_str = "module " + module_id
                            else:
                                module_id_str = module_id.split('=', 1)
                                module_id_str[0] = module_id_str[0].replace("_", " ")
                                module_id_str = "=".join(module_id_str)
                            logging.info('Scan parameter(s) for %s: %s', module_id_str, ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')
                            # storing register values until scan has finished and then restore configuration
                            restore_config_stack.enter_context(self.register.restored(name=self.run_number))
                            self.configure()
                    for module_id in self._tx_module_groups:
                        if self.abort_run.is_set():
                            break
                        with self.access_module(module_id=module_id):
                            # set all modules to run mode by before entering scan()
                            self.register_utils.set_run_mode()

                    with self.access_module(module_id=None):
                        self.fifo_readout.reset_rx()
                        self.fifo_readout.reset_fifo(self._selected_fifos)
                        self.fifo_readout.print_fei4_rx_status()

                        with self.access_files():
                            self._scan_threads = []
                            for module_id in self._tx_module_groups:
                                if self.abort_run.is_set():
                                    break
                                t = ExcThread(target=self.scan, name=module_id)
                                t.daemon = True  # exiting program even when thread is alive
                                self._scan_threads.append(t)
                            for t in self._scan_threads:
                                t.start()
                            while any([t.is_alive() for t in self._scan_threads]):
#                                 if self.abort_run.is_set():
#                                     break
                                for t in self._scan_threads:
                                    try:
                                        t.join(0.01)
                                    except Exception:
                                        self._scan_threads.remove(t)
                                        self.handle_err(sys.exc_info())
#                             alive_threads = [t.name for t in self._scan_threads if (not t.join(10.0) and t.is_alive())]
#                             if alive_threads:
#                                 raise RuntimeError("Scan thread(s) not finished: %s" % ", ".join(alive_threads))
                            self._scan_threads = []
                for module_id in self._tx_module_groups:
                    if self.abort_run.is_set():
                        break
                    with self.access_module(module_id=module_id):
                        # set modules to conf mode by after finishing scan()
                        self.register_utils.set_conf_mode()
            else:
                for tx_module_id, tx_group in self._tx_module_groups.items():
                    if self.abort_run.is_set():
                        break
                    with ExitStack() as restore_config_stack:
                        for module_id in itertools.chain([tx_module_id], tx_group):
                            if self.abort_run.is_set():
                                break
                            with self.access_module(module_id=module_id):
                                logging.info('Scan parameter(s) for module %s: %s', module_id, ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')
                                # storing register values until scan has finished and then restore configuration
                                restore_config_stack.enter_context(self.register.restored(name=self.run_number))
                                self.configure()
                        with self.access_module(module_id=tx_module_id):
                            # set all modules to run mode by before entering scan()
                            self.register_utils.set_run_mode()

                            self.fifo_readout.reset_rx()
                            self.fifo_readout.reset_fifo(self._selected_fifos)
                            self.fifo_readout.print_fei4_rx_status()

                            # some scans use this event to stop scan loop, clear event here to make another scan possible
                            self.stop_run.clear()
                            with self.access_files():
                                self.scan()

                    with self.access_module(module_id=tx_module_id):
                        # set modules to conf mode by after finishing scan()
                        self.register_utils.set_conf_mode()
        else:  # Scan each FE individually
            if self.threaded_scan:
                self._scan_threads = []
                # loop over grpups of modules with different TX
                for tx_module_ids in zip_nofill(*self._tx_module_groups.values()):
                    if self.abort_run.is_set():
                        break
                    with ExitStack() as restore_config_stack:
                        for module_id in tx_module_ids:
                            if self.abort_run.is_set():
                                break
                            with self.access_module(module_id=module_id):
                                logging.info('Scan parameter(s) for module %s: %s', module_id, ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')
                                # storing register values until scan has finished and then restore configuration
                                restore_config_stack.enter_context(self.register.restored(name=self.run_number))
                                self.configure()
                                # set modules to run mode by before entering scan()
                                self.register_utils.set_run_mode()
                            t = ExcThread(target=self.scan, name=module_id)
                            t.daemon = True  # exiting program even when thread is alive
                            self._scan_threads.append(t)
                        with self.access_module(module_id=tx_module_ids):
                            self.fifo_readout.reset_rx()
                            self.fifo_readout.reset_fifo(self._selected_fifos)
                            self.fifo_readout.print_fei4_rx_status()

                            with self.access_files():
                                # some scans use this event to stop scan loop, clear event here to make another scan possible
                                self.stop_run.clear()
                                for t in self._scan_threads:
                                    t.start()
                                while any([t.is_alive() for t in self._scan_threads]):
#                                     if self.abort_run.is_set():
#                                         break
                                    for t in self._scan_threads:
                                        try:
                                            t.join(0.01)
                                        except Exception:
                                            self._scan_threads.remove(t)
                                            self.handle_err(sys.exc_info())
#                                 alive_threads = [t.name for t in self._scan_threads if (not t.join(10.0) and t.is_alive())]
#                                 if alive_threads:
#                                     raise RuntimeError("Scan thread(s) not finished: %s" % ", ".join(alive_threads))
                                self._scan_threads = []

                    for module_id in tx_module_ids:
                        if self.abort_run.is_set():
                            break
                        with self.access_module(module_id=module_id):
                            # set modules to conf mode by after finishing scan()
                            self.register_utils.set_conf_mode()
            else:
                for module_id in self._modules:
                    if self.abort_run.is_set():
                        break
                    # some scans use this event to stop scan loop, clear event here to make another scan possible
                    self.stop_run.clear()
                    with self.access_module(module_id=module_id):
                        logging.info('Scan parameter(s) for module %s: %s', module_id, ', '.join(['%s=%s' % (key, value) for (key, value) in self.scan_parameters._asdict().items()]) if self.scan_parameters else 'None')
                        with self.register.restored(name=self.run_number):
                            self.configure()
                            # set modules to run mode by before entering scan()
                            self.register_utils.set_run_mode()

                            self.fifo_readout.reset_rx()
                            self.fifo_readout.reset_fifo(self._selected_fifos)
                            self.fifo_readout.print_fei4_rx_status()

                            # some scans use this event to stop scan loop, clear event here to make another scan possible
                            self.stop_run.clear()
                            with self.access_files():
                                self.scan()
                            # set modules to conf mode by after finishing scan()
                            self.register_utils.set_conf_mode()

        if self._modules:
            self.fifo_readout.print_readout_status()

    def post_run(self):
        # analyzing data and store register cfg per front end one by one
        for module_id in [name for name in self._modules if self._module_cfgs[name]["activate"] is True]:
            if self.abort_run.is_set():
                    break
            with self.access_module(module_id=module_id):
                try:
                    self.analyze()
                except Exception:  # analysis errors
                    exc = sys.exc_info()
                    self.err_queue.put(sys.exc_info())
                    logging.warning(exc[1].__class__.__name__ + ": " + str(exc[1]))
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
        pass

    def close(self):
        '''Releasing hardware resources.
        '''
        try:
            self.dut.close()
        except Exception:
            logging.warning('Closing DUT was not successful')
        else:
            logging.debug('Closed DUT')

    def handle_data(self, data, new_file=False, flush=True):
        '''Handling of the data.

        Parameters
        ----------
        data : list, tuple
            Data tuple of the format (data (np.array), last_time (float), curr_time (float), status (int))
        '''
        for i, module_id in enumerate(self._selected_modules):
            if data[i] is None:
                continue
            self._raw_data_files[module_id].append(data_iterable=data[i], scan_parameters=self._scan_parameters[module_id]._asdict(), new_file=new_file, flush=flush)

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
        if module_id not in self._modules:
            raise ValueError('Module ID "%s" is not a valid name.' % module_id)
        return os.path.join(self.working_dir, module_id)

    def get_configuration(self, module_id, run_number=None):
        ''' Returns the configuration for a given module ID.

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
            run_numbers = sorted(self._get_run_numbers(status='FINISHED').keys(), reverse=True)
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
        if self.current_module_handle is None:
            selected_modules = self._modules.keys()
        elif self.current_module_handle in self._modules:
            selected_modules = [self.current_module_handle]
        elif self.current_module_handle in self._tx_module_groups:
            selected_modules = self._tx_module_groups[self.current_module_handle]
        else:
            RuntimeError('Cannot change scan parameters. Module handle "%s" is not valid.' % self.current_module_handle)
        scan_parameters_old = self.scan_parameters._asdict()
        with self.global_lock:
            for module_id in selected_modules:
                self._scan_parameters[module_id] = self.scan_parameters._replace(**fields)
        scan_parameters_new = self.scan_parameters._asdict()
        diff = [name for name in scan_parameters_old.keys() if np.any(scan_parameters_old[name] != scan_parameters_new[name])]
        if diff:
            logging.info('Changing scan parameter(s): %s', ', '.join([('%s=%s' % (name, fields[name])) for name in diff]))

    def __setattr__(self, name, value):
        ''' Always called to retrun the value for an attribute.
        '''
        if self.is_initialized and name not in self.__dict__:
            if name in self._module_run_conf[self.current_module_handle]:
                raise RuntimeError('"%s" (current module handle "%s") cannot use attribute "%s" because it is already used in run conf.' % (self.__class__.__name__, self.current_module_handle, name))
            self._module_attr[self.current_module_handle][name] = value
            # set attribute for all other mudules in module group
            if self.current_module_handle in self._tx_module_groups:
                for module_id in self._tx_module_groups[self.current_module_handle]:
                    self._module_attr[module_id][name] = value
        else:
            super(Fei4RunBase, self).__setattr__(name, value)

    def __getattr__(self, name):
        ''' This is called in a last attempt to receive the value for an attribute that was not found in the usual places.
        '''
        # test for attribute name in module attribute dict first
        if self.is_initialized and name in self._module_attr[self.current_module_handle]:
            return self._module_attr[self.current_module_handle][name]
        else:
            try:
                return self._module_run_conf[self.current_module_handle][name]  # Accessing run conf parameters
            except KeyError:
                try:
                    return super(Fei4RunBase, self).__getattr__(name)
                except AttributeError:
                    if self.is_initialized:
                        raise AttributeError('"%s" (current module handle "%s") has no attribute "%s"' % (self.__class__.__name__, self.current_module_handle, name))
                    else:
                        raise

    @contextmanager
    def access_module(self, module_id):
        self.select_module(module_id=module_id)
        try:
            yield
        finally:
            try:
                self.deselect_module()
            except Exception:
                # in case something fails, call this on last resort
                self._current_module_handle = None
                if isinstance(current_thread(), _MainThread):
                    current_thread().name = "MainThread"

    def select_module(self, module_id):
        ''' Select module and give access to the module.
        '''
        if not isinstance(module_id, basestring) and isinstance(module_id, Iterable) and set(module_id) - set(self._modules):
            raise ValueError('Module IDs invalid:' % ", ".join(set(module_id) - set(self._modules)))
        if isinstance(module_id, basestring) and module_id not in self._module_cfgs:
            raise ValueError('Module ID "%s" is not valid' % module_id)
        if self._current_module_handle is not None:
            raise RuntimeError('Module handle "%s" cannot be set because another module is active' % module_id)

        if module_id is None:
            self._selected_modules = self._modules.keys()
        elif not isinstance(module_id, basestring) and isinstance(module_id, Iterable):
            self._selected_modules = module_id
        elif module_id in self._modules:
            self._selected_modules = [module_id]
        elif module_id in self._tx_module_groups:
            self._selected_modules = self._tx_module_groups[module_id]
        else:
            RuntimeError('Cannot open files. Module handle "%s" is not valid.' % self.current_module_handle)

        # FIFO readout
        self._selected_fifos = list(set([module_cfg['FIFO'] for (name, module_cfg) in self._module_cfgs.items() if name in self._selected_modules]))

        # Module filter functions dict for quick lookup
        self._readout_fifos = []
        self._filter = []
        self._converter = []
        for selected_module_id in self._selected_modules:
            module_cfg = self._module_cfgs[selected_module_id]
            self._readout_fifos.append(module_cfg['FIFO'])
            if 'tdc_channel' not in module_cfg:
                tdc_filter = false
                self._converter.append(None)
            elif module_cfg['tdc_channel'] is None:
                tdc_filter = is_tdc_word
                self._converter.append(convert_tdc_to_channel(channel=module_cfg['tdc_channel']))  # for the raw data analyzer
            else:
                tdc_filter = logical_and(is_tdc_word, is_tdc_from_channel(module_cfg['tdc_channel']))
                self._converter.append(convert_tdc_to_channel(channel=module_cfg['tdc_channel']))  # for the raw data analyzer
            if 'rx_channel' not in module_cfg:
                self._filter.append(logical_or(is_trigger_word, tdc_filter))
            elif module_cfg['rx_channel'] is None:
                self._filter.append(logical_or(is_trigger_word, logical_or(tdc_filter, is_fe_word)))
            else:
                self._filter.append(logical_or(is_trigger_word, logical_or(tdc_filter, logical_and(is_fe_word, is_data_from_channel(module_cfg['rx_channel'])))))

        # select readout channels and report sync status only from actively selected modules
        self._enabled_fe_channels = list(set([config['RX'] for (name, config) in self._module_cfgs.items() if name in self._selected_modules]))

        # enabling specific TX channels
        tx_channels = list(set([1 << config['tx_channel'] for (name, config) in self._module_cfgs.items() if name in self._selected_modules]))
        if tx_channels:
            self.dut['TX']['OUTPUT_ENABLE'] = reduce(lambda x, y: x | y, tx_channels)
        else:
            self.dut['TX']['OUTPUT_ENABLE'] = 0

        if not isinstance(module_id, basestring) and isinstance(module_id, Iterable):
            self._current_module_handle = None
        else:
            self._current_module_handle = module_id

        if module_id is not None and isinstance(module_id, basestring):
            current_thread().name = module_id

    def deselect_module(self):
        ''' Deselect module and cleanup.
        '''
        self._enabled_fe_channels = []  # ignore any RX sync errors
        self._readout_fifos = []
        self._filter = []
        self._converter = []
        self.dut['TX']['OUTPUT_ENABLE'] = 0
        self._current_module_handle = None
        if isinstance(current_thread(), _MainThread):
            current_thread().name = "MainThread"

    @contextmanager
    def access_files(self):
        try:
            self.open_files()
            yield
            self.close_files()
        finally:
            # in case something fails, call this on last resort
            self._raw_data_files.clear()

    def open_files(self):
        for selected_module_id in self._selected_modules:
            self._raw_data_files[selected_module_id] = open_raw_data_file(filename=self.get_output_filename(module_id=selected_module_id),
                                                                          mode='w',
                                                                          title=self.run_id,
                                                                          scan_parameters=self._scan_parameters[selected_module_id]._asdict(),
                                                                          socket_address=self._module_cfgs[selected_module_id]['send_data'])
            # save configuration data to raw data file
            self._registers[selected_module_id].save_configuration(self._raw_data_files[selected_module_id].h5_file)
            save_configuration_dict(self._raw_data_files[selected_module_id].h5_file, 'conf', self._conf)
            save_configuration_dict(self._raw_data_files[selected_module_id].h5_file, 'run_conf', self._module_run_conf[selected_module_id])
            # send configuration data to online monitor
            if self._raw_data_files[selected_module_id].socket:
                send_meta_data(self._raw_data_files[selected_module_id].socket, selected_module_id, name='Filename')
                global_register_config = {}
                for global_reg in sorted(self._registers[selected_module_id].get_global_register_objects(readonly=False), key=itemgetter('name')):
                    global_register_config[global_reg['name']] = global_reg['value']
                send_meta_data(self._raw_data_files[selected_module_id].socket, global_register_config, name='GlobalRegisterConf')
                send_meta_data(self._raw_data_files[selected_module_id].socket, self._run_conf, name='RunConf')

    def close_files(self):
        # close all file objects
        for f in self._raw_data_files.values():
            f.close()
        # delete all file objects
        self._raw_data_files.clear()

    def get_output_filename(self, module_id):
        if module_id not in self._modules:
            raise ValueError('Module ID "%s" is not a valid name.' % module_id)
        module_path = os.path.join(self.working_dir, module_id)
        return os.path.join(module_path, str(self.run_number) + "_" + module_id + "_" + self.run_id)

    def read_data(self, filter_func=None, converter_func=None):
        with self._readout_lock:
            if self.fifo_readout.fill_buffer:
                return self.get_raw_data_from_buffer(filter_func=None, converter_func=None)[self._selected_modules.index(self.current_module_handle)]
            else:
                return self.read_raw_data_from_fifo(filter_func=filter_func, converter_func=converter_func)

    def get_raw_data_from_buffer(self, filter_func=None, converter_func=None):
        return self.fifo_readout.get_raw_data_from_buffer(filter_func=filter_func, converter_func=converter_func)

    def read_raw_data_from_fifo(self, filter_func=None, converter_func=None):
        return self.fifo_readout.read_raw_data_from_fifo(filter_func=filter_func, converter_func=converter_func)

    def data_words_per_second(self):
        if self.current_module_handle is None:
            return sum(self.fifo_readout.data_words_per_second())
        elif self.current_module_handle in self._modules:
            return self.fifo_readout.data_words_per_second()[self._selected_modules.index(self.current_module_handle)]
        elif self.current_module_handle in self._tx_module_groups:
            return sum([dw_per_s for i, dw_per_s in enumerate(self.fifo_readout.data_words_per_second()) if self._selected_modules[i] in self._tx_module_groups[self.current_module_handle]])
        else:
            RuntimeError('Module handle "%s" is not valid.' % self.current_module_handle)

    @contextmanager
    def synchronized(self):
        ''' Synchronize the execution of a section of code between threads.
        '''
        self.enter_sync()
        try:
            yield
            self.exit_sync()
        finally:
            # in case something fails, call this on last resort
            pass

    def enter_sync(self):
        ''' Waiting for all threads to appear, then continue.
        '''
        if self._scan_threads and self.current_module_handle not in [t.name for t in self._scan_threads]:
            raise RuntimeError('Thread name "%s" is not valid.')
        if self._scan_threads and self.current_module_handle in self._curr_sync_threads:
            raise RuntimeError('Thread "%s" is already actively reading FIFO.')
        with self._sync_lock:
            self._curr_sync_threads.append(self.current_module_handle)
        self._enter_sync_event.clear()
        while not self._enter_sync_event.wait(0.01):
            if self.abort_run.is_set():
                break
            with self._sync_lock:
                if len(set(self._curr_sync_threads) & set([t.name for t in self._scan_threads if t.is_alive()])) == len(set([t.name for t in self._scan_threads if t.is_alive()])) or not self._scan_threads:
                    self._enter_sync_event.set()

    def exit_sync(self):
        ''' Waiting for all threads to appear, then continue.
        '''
        if self._scan_threads and self.current_module_handle not in [t.name for t in self._scan_threads]:
            raise RuntimeError('Thread name "%s" is not valid.')
        if self._scan_threads and self.current_module_handle not in self._curr_sync_threads:
            raise RuntimeError('Thread "%s" is not reading FIFO.')
        with self._sync_lock:
            self._curr_sync_threads.remove(self.current_module_handle)
        self._exit_sync_event.clear()
        while not self._exit_sync_event.wait(0.01):
            if self.abort_run.is_set():
                break
            with self._sync_lock:
                if len(set(self._curr_sync_threads) & set([t.name for t in self._scan_threads if t.is_alive()])) == 0 or not self._scan_threads:
                    self._exit_sync_event.set()

    @contextmanager
    def readout(self, *args, **kwargs):
        ''' Running the FIFO readout while executing other statements.

        Starting and stopping of the FIFO readout is synchronized between the threads.
        '''
        timeout = kwargs.pop('timeout', 10.0)
        self.start_readout(*args, **kwargs)
        try:
            yield
        finally:
            try:
                self.stop_readout(timeout=timeout)
            except Exception:
                # in case something fails, call this on last resort
                # if run was aborted, immediately stop readout
                if self.abort_run.is_set():
                    with self._readout_lock:
                        if self.fifo_readout.is_running:
                            self.fifo_readout.stop(timeout=0.0)

    def start_readout(self, *args, **kwargs):
        ''' Starting the FIFO readout.

        Starting of the FIFO readout is executed only once by a random thread.
        Starting of the FIFO readout is synchronized between all threads reading out the FIFO.
        '''
        # Pop parameters for fifo_readout.start
        callback = kwargs.pop('callback', self.handle_data)
        errback = kwargs.pop('errback', self.handle_err)
        reset_rx = kwargs.pop('reset_rx', True)
        reset_fifo = kwargs.pop('reset_fifo', True)
        fill_buffer = kwargs.pop('fill_buffer', False)
        no_data_timeout = kwargs.pop('no_data_timeout', None)
        enabled_fe_channels = kwargs.pop('enabled_fe_channels', self._enabled_fe_channels)
        if args or kwargs:
            self.set_scan_parameters(*args, **kwargs)
        if self._scan_threads and self.current_module_handle not in [t.name for t in self._scan_threads]:
            raise RuntimeError('Thread name "%s" is not valid.' % t.name)
        if self._scan_threads and self.current_module_handle in self._curr_readout_threads:
            raise RuntimeError('Thread "%s" is already actively reading FIFO.')
        with self._readout_lock:
            self._curr_readout_threads.append(self.current_module_handle)
        self._starting_readout_event.clear()
        while not self._starting_readout_event.wait(0.01):
            if self.abort_run.is_set():
                break
            with self._readout_lock:
                if len(set(self._curr_readout_threads) & set([t.name for t in self._scan_threads if t.is_alive()])) == len(set([t.name for t in self._scan_threads if t.is_alive()])) or not self._scan_threads:
                    if not self.fifo_readout.is_running:
                        self.fifo_readout.start(fifos=self._selected_fifos, callback=callback, errback=errback, reset_rx=reset_rx, reset_fifo=reset_fifo, fill_buffer=fill_buffer, no_data_timeout=no_data_timeout, filter_func=self._filter, converter_func=self._converter, fifo_select=self._readout_fifos, enabled_fe_channels=enabled_fe_channels)
                        self._starting_readout_event.set()

    def stop_readout(self, timeout=10.0):
        ''' Stopping the FIFO readout.

        Stopping of the FIFO readout is executed only once by a random thread.
        Stopping of the FIFO readout is synchronized between all threads reading out the FIFO.
        '''
        if self._scan_threads and self.current_module_handle not in [t.name for t in self._scan_threads]:
            raise RuntimeError('Thread name "%s" is not valid.')
        if self._scan_threads and self.current_module_handle not in self._curr_readout_threads:
            raise RuntimeError('Thread "%s" is not reading FIFO.')
        with self._readout_lock:
            self._curr_readout_threads.remove(self.current_module_handle)
        self._stopping_readout_event.clear()
        while not self._stopping_readout_event.wait(0.01):
            with self._readout_lock:
                if len(set(self._curr_readout_threads) & set([t.name for t in self._scan_threads if t.is_alive()])) == 0 or not self._scan_threads or self.abort_run.is_set():
                    if self.fifo_readout.is_running:
                        self.fifo_readout.stop(timeout=timeout)
                    self._stopping_readout_event.set()

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


class ExcThread(Thread):
    def run(self):
        self.exc = None
        try:
            if hasattr(self, '_Thread__target'):
                # Thread uses name mangling prior to Python 3.
                self._Thread__target(*self._Thread__args, **self._Thread__kwargs)
            else:
                self._target(*self._args, **self._kwargs)
        except Exception:
            self.exc = sys.exc_info()

    def join(self, timeout=None):
        super(ExcThread, self).join(timeout=timeout)
        if self.exc:
            raise self.exc[0], self.exc[1], self.exc[2]


class RhlHandle(object):
    ''' Handle for basil.HL.RegisterHardwareLayer.

    Mimic register interface of RegisterHardwareLayer objects and allows for consecutively reading/writing values in all given modules.
    '''
    def __init__(self, dut, module_names):
        self._dut = dut
        if not module_names:
            module_names = []
        if len(set(module_names)) != len(module_names):
            raise ValueError('Parameter "module_names" contains duplicate entries.')
        if module_names and not all([isinstance(dut[module_name], basil.HL.RegisterHardwareLayer.RegisterHardwareLayer) for module_name in module_names]):
            raise ValueError("Not all modules are of type basil.HL.RegisterHardwareLayer.RegisterHardwareLayer.")
        self.module_names = module_names

    def __getitem__(self, name):
        values = []
        for module_name in self.module_names:
            values.append(self._dut[module_name][name])
        if not len(set(values)) == 1:
            raise RuntimeError("Returned values for %s are different." % (name,))
        return values[0]

    def __setitem__(self, name, value):
        for module_name in self.module_names:
            self._dut[module_name][name] = value

    def __getattr__(self, name):
        '''called only on last resort if there are no attributes in the instance that match the name
        '''
        if name.isupper():
            return self[name]
        else:
            def method(*args, **kwargs):
                nsplit = name.split('_', 1)
                if len(nsplit) == 2 and nsplit[0] == 'set' and nsplit[1].isupper() and len(args) == 1 and not kwargs:
                    self[nsplit[1]] = args[0]  # returns None
                elif len(nsplit) == 2 and nsplit[0] == 'get' and nsplit[1].isupper() and not args and not kwargs:
                    return self[nsplit[1]]
                else:
                    values = []
                    for module_name in self.module_names:
                        values.append(getattr(self._dut[module_name], name)(*args, **kwargs))
                    if not len(set(values)) == 1:
                        raise RuntimeError("Returned values for %s are different." % (name,))
                    return values[0]
#                     raise AttributeError("%r object has no attribute %r" % (self.__class__, name))
            return method

    def __setattr__(self, name, value):
        if name.isupper():
            self[name] = value
        else:
            super(RhlHandle, self).__setattr__(name, value)


class DutHandle(object):
    ''' Handle for DUT.

    Providing interface to Basil DUT object and gives access only to those drivers which are specified in the module configuration.
    '''
    def __init__(self, dut, module_cfg):
        self._dut = dut
        self._module_cfg = module_cfg

    def __getitem__(self, name):
        try:
            return self._dut[name]
        except KeyError:
            pass
        try:
            return self._dut[self._module_cfg[name]]
        except TypeError:
            # dict item is list
            module_names = self._module_cfg[name]
            if len(module_names) > 1:
                return RhlHandle(dut=self._dut, module_names=module_names)
            else:
                return self._dut[module_names[0]]

    def __getattr__(self, name):
        '''called only on last resort if there are no attributes in the instance that match the name
        '''
        return getattr(self._dut, name)


def timed(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        start = time()
        result = f(*args, **kwargs)
        elapsed = time() - start
        print("%s took %fs to finish" % (f.__name__, elapsed))
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
