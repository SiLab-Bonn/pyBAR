import os
import inspect
import logging
import numpy as np
import progressbar
from threading import Timer
from collections import namedtuple, Mapping, OrderedDict

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask, make_box_pixel_mask_from_col_row
from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager

from basil.utils.BitLogic import BitLogic


class M26TelescopeScan(Fei4RunBase):
    '''External trigger scan with FE-I4 and up to 6 Mimosa26 telescope planes.

    For use with external scintillator (user RX0), TLU (use RJ45), FE-I4 HitOR (USBpix self-trigger).

    Note:
    Set up trigger in DUT configuration file (e.g. dut_configuration_mio.yaml).
    '''
    _default_run_conf = {
        "trig_count": 0,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "trigger_latency": 232,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220
        "trigger_delay": 8,  # trigger delay, in BCs
        "trigger_rate_limit": 0,  # artificially limiting the trigger rate, in BCs (25ns)
        "col_span": [1, 79],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": True,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 120,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 120,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": False,  # maximum triggers after which the scan will be stopped, in seconds
        "enable_tdc": False,  # if True, enables TDC (use RX2)
        "reset_rx_on_error": False  # long scans have a high propability for ESD related data transmission errors; recover and continue here
    }

    def init_dut(self): 
        map(lambda channel: channel.reset(), self.dut.get_modules('m26_rx'))
        self.dut['jtag'].reset()
        
        if 'm26_configuration' in self._conf:
            m26_config_file =  os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))), self._conf['m26_configuration'])
            
            logging.info('Loading m26 configuration file %s', m26_config_file)
            self.dut.set_configuration(m26_config_file)
            
            IR={"BSR_ALL":'00101',"DEV_ID_ALL":'01110',"BIAS_DAC_ALL":'01111',"LINEPAT0_REG_ALL":'10000',
                "DIS_DISCRI_ALL":'10001',"SEQUENCER_PIX_REG_ALL":'10010',"CONTROL_PIX_REG_ALL":'10011',
                "LINEPAT1_REG_ALL":'10100',"SEQUENCER_SUZE_REG_ALL":'10101',"HEADER_REG_ALL":'10110',
                "CONTROL_SUZE_REG_ALL":'10111',
                "CTRL_8b10b_REG0_ALL":'11000',"CTRL_8b10b_REG1_ALL":'11001',"RO_MODE1_ALL":'11101',
                "RO_MODE0_ALL":'11110',
                "BYPASS_ALL":'11111'}
            ## write JTAG
            irs = ["BIAS_DAC_ALL","BYPASS_ALL","BSR_ALL","RO_MODE0_ALL","RO_MODE1_ALL",
            "DIS_DISCRI_ALL","LINEPAT0_REG_ALL","LINEPAT1_REG_ALL","CONTROL_PIX_REG_ALL","SEQUENCER_PIX_REG_ALL",
            "HEADER_REG_ALL","CONTROL_SUZE_REG_ALL","SEQUENCER_SUZE_REG_ALL","CTRL_8b10b_REG0_ALL",
            "CTRL_8b10b_REG1_ALL"]
            for i,ir in enumerate(irs):
                logging.info('Programming M26 JATG configuration reg %s', ir)
                logging.debug(self.dut[ir][:])
                self.dut['jtag'].scan_ir([BitLogic(IR[ir])]*6)
                ret = self.dut['jtag'].scan_dr([self.dut[ir][:]])[0]
            ## read JTAG  and check
            irs=["DEV_ID_ALL","BSR_ALL","BIAS_DAC_ALL","RO_MODE1_ALL","RO_MODE0_ALL",
               "DIS_DISCRI_ALL","LINEPAT0_REG_ALL","LINEPAT1_REG_ALL","CONTROL_PIX_REG_ALL",
               "SEQUENCER_PIX_REG_ALL",
               "HEADER_REG_ALL","CONTROL_SUZE_REG_ALL","SEQUENCER_SUZE_REG_ALL","CTRL_8b10b_REG0_ALL",
               "CTRL_8b10b_REG1_ALL","BYPASS_ALL"]
            ret={}
            for i,ir in enumerate(irs):
                logging.info('Reading M26 JATG configuration reg %s', ir)
                self.dut['jtag'].scan_ir([BitLogic(IR[ir])]*6)
                ret[ir]= self.dut['jtag'].scan_dr([self.dut[ir][:]])[0]
            ## check
            for k,v in ret.iteritems():
                if k=="CTRL_8b10b_REG1_ALL":
                    pass
                elif k=="BSR_ALL":
                    pass #TODO mask clock bits and check others
                elif self.dut[k][:]!=v:
                    logging.error("JTAG data does not match %s get=%s set=%s"%(k,v,self.dut[k][:]))
                else:
                    logging.info("Checking M26 JTAG %s ok"%k)        
            #START procedure
            logging.info('Starting M26')
            temp=self.dut['RO_MODE0_ALL'][:]
              #disable extstart
            for reg in self.dut["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['En_ExtStart']=0
                reg['JTAG_Start']=0
            self.dut['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])]*6)
            self.dut['jtag'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
              #JTAG start
            for reg in self.dut["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['JTAG_Start']=1
            self.dut['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])]*6)
            self.dut['jtag'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
            for reg in self.dut["RO_MODE0_ALL"]["RO_MODE0"]:
                reg['JTAG_Start']=0
            self.dut['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])]*6)
            self.dut['jtag'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
              #write original configuration
            self.dut['RO_MODE0_ALL'][:]=temp
            self.dut['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])]*6)
            self.dut['jtag'].scan_dr([self.dut['RO_MODE0_ALL'][:]])
              #readback?
            self.dut['jtag'].scan_ir([BitLogic(IR['RO_MODE0_ALL'])]*6)
            self.dut['jtag'].scan_dr([self.dut['RO_MODE0_ALL'][:]]*6)           
        else:
            logging.info('Skipping m26 configuration')
   

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # Enable
        enable_pixel_mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span)
        if not self.overwrite_enable_mask:
            enable_pixel_mask = np.logical_and(enable_pixel_mask, self.register.get_pixel_register_value('Enable'))
        self.register.set_pixel_register_value('Enable', enable_pixel_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Enable'))
        # Imon
        if self.use_enable_mask_for_imon:
            imon_pixel_mask = invert_pixel_mask(enable_pixel_mask)
        else:
            imon_pixel_mask = make_box_pixel_mask_from_col_row(column=self.col_span, row=self.row_span, default=1, value=0)  # 0 for selected columns, else 1
            imon_pixel_mask = np.logical_or(imon_pixel_mask, self.register.get_pixel_register_value('Imon'))
        self.register.set_pixel_register_value('Imon', imon_pixel_mask)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=False, name='Imon'))
        # C_High
        self.register.set_pixel_register_value('C_High', 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        # C_Low
        self.register.set_pixel_register_value('C_Low', 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # Registers
        self.register.set_global_register_value("Trig_Lat", self.trigger_latency)  # set trigger latency
        self.register.set_global_register_value("Trig_Count", self.trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("WrRegister", name=["Trig_Lat", "Trig_Count"]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)
        self.dut['TLU']['RESET']=1
        for plane in range(1,7):
            self.dut['M26_RX%d'%plane].reset()
            self.dut['M26_RX%d'%plane]['TIMESTAMP_HEADER']=1

    def scan(self):
        # preload command
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.register_utils.set_command(lvl1_command)

        with self.readout(**self.scan_parameters._asdict()):
            got_data = False
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                        self.progressbar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=self.max_triggers, poll=10, term_width=80).start()
                else:
                    triggers = self.dut['TLU']['TRIGGER_COUNTER']
                    try:
                        self.progressbar.update(triggers)
                    except ValueError:
                        pass
                    if self.max_triggers and triggers >= self.max_triggers:
                        self.progressbar.finish()
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)
#                 print self.fifo_readout.data_words_per_second()
#                 if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
#                     logging.info('Collected triggers: %d', current_trigger_number)

        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

    def analyze(self):
        pass
        #with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
        #    analyze_raw_data.create_source_scan_hist = True
        #    analyze_raw_data.create_cluster_size_hist = True
        #    analyze_raw_data.create_cluster_tot_hist = True
        #    analyze_raw_data.align_at_trigger = True
        #    if self.enable_tdc:
        #        analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
        #        analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
        #        analyze_raw_data.align_at_tdc = False  # align events at the TDC word
        #    analyze_raw_data.interpreter.set_warning_output(False)
        #    analyze_raw_data.interpret_word_table()
        #    analyze_raw_data.interpreter.print_summary()
        #    analyze_raw_data.plot_histograms()

    def start_readout(self, **kwargs):
        if kwargs:
            self.set_scan_parameters(**kwargs)
        self.fifo_readout.start(reset_sram_fifo=False, clear_buffer=True, callback=self.handle_data, errback=self.handle_err, no_data_timeout=self.no_data_timeout)
        #self.dut['TDC']['ENABLE'] = self.enable_tdc
        self.dut['TLU']['RESET']=1
        self.dut['TLU']['TRIGGER_MODE']=3
        self.dut['TLU']['TRIGGER_LOW_TIMEOUT']=200
        self.dut['TLU']['TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES']=20
        self.dut['TLU']['DATA_FORMAT']=2
        self.dut['TLU']['TRIGGER_DATA_DELAY']=8
        self.dut['TLU']['TRIGGER_COUNTER'] = 0
        self.dut['TLU']['TRIGGER_VETO_SELECT'] = 0
        self.dut['TLU']['EN_TLU_VETO'] = 0

        self.dut['M26_RX1'].set_en(True)
        self.dut['M26_RX2'].set_en(True)
        self.dut['M26_RX3'].set_en(True)
        self.dut['M26_RX4'].set_en(True)
        self.dut['M26_RX5'].set_en(True)
        self.dut['M26_RX6'].set_en(True)

        if self.max_triggers:
            self.dut['TLU']['MAX_TRIGGERS'] = self.max_triggers
        else:
            self.dut['TLU']['MAX_TRIGGERS'] = 0  # infinity triggers
        # use this with FE-I4 connected
        self.dut['CMD']['EN_EXT_TRIGGER'] = True
        # use this if no FE-I4 is connected
#         self.dut['TLU']['TRIGGER_ENABLE'] = True
    

        def timeout():
            try:
                self.progressbar.finish()
            except AttributeError:
                pass
            self.stop(msg='Scan timeout was reached')

        self.scan_timeout_timer = Timer(self.scan_timeout, timeout)
        if self.scan_timeout:
            self.scan_timeout_timer.start()

    def stop_readout(self, timeout=10.0):
        self.scan_timeout_timer.cancel()
        self.dut['TLU']['TRIGGER_ENABLE'] = False
        self.dut['CMD']['EN_EXT_TRIGGER'] = False
        self.dut['M26_RX1'].set_en(False)
        self.dut['M26_RX2'].set_en(False)
        self.dut['M26_RX3'].set_en(False)
        self.dut['M26_RX4'].set_en(False)
        self.dut['M26_RX5'].set_en(False)
        self.dut['M26_RX6'].set_en(False)
        self.fifo_readout.stop(timeout=timeout)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(M26TelescopeScan)
