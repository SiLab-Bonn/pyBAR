import itertools
import struct
import time
import datetime
import logging
from collections import deque
import math

import numpy as np
from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

class FEI4SelfTriggerScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "scan_fei4_self_trigger", scan_data_path = None):
        super(FEI4SelfTriggerScan, self).__init__(config_file = config_file, definition_file = definition_file, bit_file = bit_file, device = device, scan_identifier = scan_identifier, scan_data_path = scan_data_path)
        
    def scan(self, **kwargs):
        col_span = [1,80] # column range (from minimum to maximum value)
        row_span = [1,336] # row range
        # generate ROI mask for Enable mask
        pixel_reg = "Enable"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_pixel_register_value(pixel_reg, mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = pixel_reg))
        # generate ROI mask for Imon mask
        pixel_reg = "Imon"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)
        self.register.set_pixel_register_value(pixel_reg, mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc = False, name = pixel_reg))
        # enable GateHitOr that enables FE self-trigger mode
        self.register.set_global_register_value("GateHitOr", 1)
        commands.extend(self.register.get_commands("wrregister", name = "GateHitOr"))
        commands.extend(self.register.get_commands("runmode"))
        # send commands
        self.register_utils.send_commands(commands)
        # preload command
        #lvl1_command = self.register.get_commands("zeros", length=24)[0]+self.register.get_commands("lv1")[0]#+BitVector.BitVector(size = 10000)
        #self.register_utils.set_command(lvl1_command)
        with open_raw_data_file(filename = self.scan_data_filename, title=self.scan_identifier) as raw_data_file:
            self.readout.start()
            
            wait_for_first_data = True
            
            
            timeout_no_data = 60 # secs
            scan_timeout = 1200
            last_iteration = time.time()
            saw_no_data_at_time = last_iteration
            saw_data_at_time = last_iteration
            scan_start_time = last_iteration
            no_data_at_time = last_iteration
            time_from_last_iteration = 0
            scan_stop_time = scan_start_time + scan_timeout
            while not self.stop_thread_event.wait(self.readout.readout_interval):
                
    #                 if logger.isEnabledFor(logging.DEBUG):
    #                     lost_data = self.readout.get_lost_data_count()
    #                     if lost_data != 0:
    #                         logging.debug('Lost data count: %d', lost_data)
    #                         logging.debug('FIFO fill level: %4f', (float(fifo_size)/2**20)*100)
    #                         logging.debug('Collected triggers: %d', self.readout_utils.get_trigger_number())
    
                if scan_start_time is not None and time.time() > scan_stop_time:
                    logging.info('Reached maximum scan time. Stopping Scan...')
                    self.stop_thread_event.set()
                # TODO: read 8b10b decoder err cnt
    #                 if not self.readout_utils.read_rx_status():
    #                     logging.info('Lost data sync. Starting synchronization...')
    #                     self.readout_utils.set_ext_cmd_start(False)
    #                     if not self.readout_utils.reset_rx(1000):
    #                         logging.info('Failed. Stopping scan...')
    #                         self.stop_thread_event.set()
    #                     else:
    #                         logging.info('Done!')
    #                         self.readout_utils.set_ext_cmd_start(True)
    
                time_from_last_iteration = time.time() - last_iteration
                last_iteration = time.time()
                try:
                    raw_data_file.append((self.readout.data.popleft(),))
                    #logging.info('data words')
                except IndexError:
                    #logging.info('no data words')
                    no_data_at_time = last_iteration
                    if wait_for_first_data == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                        logging.info('Reached no data timeout. Stopping Scan...')
                        self.stop_thread_event.set()
                    elif wait_for_first_data == False:
                        saw_no_data_at_time = no_data_at_time
                    
                    if no_data_at_time > (saw_data_at_time + 10):
                        scan_stop_time += time_from_last_iteration
                        
                    continue
                
                saw_data_at_time = last_iteration
                
                if wait_for_first_data == True:
                    logging.info('Taking data...')
                    wait_for_first_data = False
            
            self.stop_thread_event.set()
            
            self.readout.stop()

if __name__ == "__main__":
    import configuration
    scan = FEI4SelfTriggerScan(config_file = configuration.config_file, bit_file  = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    scan.start(configure=True, use_thread = False)
    scan.stop()
