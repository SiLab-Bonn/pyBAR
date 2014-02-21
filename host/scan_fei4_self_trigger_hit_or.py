''' This script enables the hit or consecutively for selected pixel and histograms the TOT from source hits with a Tektronix TDS5104B ocilloscope.
'''
import logging
import math
import numpy as np
import time

from scan.scan import ScanBase
from daq.readout import open_raw_data_file
from analysis.analyze_raw_data import AnalyzeRawData
from threading import Event
import glob


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "pixels": [(40, 90), ],  # list of (col,row) tupel of pixels to use
    "timeout_no_data": 30,
    "scan_timeout": 1 * 10,
    "trig_latency": 239,
    "trig_count": 4
}


class FEI4SelfTriggerHitOr(ScanBase):
    scan_identifier = "fei4_self_trigger_hit_or"

    def scan(self, pixels, timeout_no_data=10, scan_timeout=1 * 60, trig_latency=239, trig_count=4):
        '''Scan loop

        Parameters
        ----------
        pixels : list of tuples (column, row) for the pixels to scan
        GPIB_prim_address : int
            The primary address of the oscilloscope
        scan_timeout : int
            In seconds; stop scan after given time.
        trig_latency : int
            FE global register Trig_Lat.
        trig_count : int
            FE global register Trig_Count.
        '''

        logging.info('Start self trigger source scan with TDC tot histograming for %d pixels' % len(pixels))
        logging.info('Estimated scan time %dh' % (len(pixels) * scan_timeout / 3600.))

        self.stop_loop_event = Event()
        self.stop_loop_event.clear()
        self.repeat_scan_step = True

        self.register.create_restore_point()

        for column, row  in pixels:
            self.register.restore(keep=True, global_register=False)
            self.configure_fe(column, row, trig_latency, trig_count)
            if self.stop_thread_event.is_set():
                break
            self.repeat_scan_step = True
            while self.repeat_scan_step and not self.stop_thread_event.is_set():
                with open_raw_data_file(filename=self.scan_data_filename + '_col_row_' + str(column) + '_' + str(row), title=self.scan_identifier, scan_parameters=['column', 'row'], mode='w') as raw_data_file:
                    self.repeat_scan_step = False
                    self.stop_loop_event.clear()
                    self.readout.start()
                    self.readout_utils.configure_tdc_fsm(enable_tdc=True, enable_tdc_arming=False)
                    self.set_self_trigger(True)
                    wait_for_first_data = True
                    show_trigger_message_at = 10 ** (int(math.floor(math.log10(scan_timeout) - math.log10(3) / math.log10(10))))
                    time_current_iteration = time.time()
                    saw_no_data_at_time = time_current_iteration
                    saw_data_at_time = time_current_iteration
                    scan_start_time = time_current_iteration
                    no_data_at_time = time_current_iteration
                    time_from_last_iteration = 0
                    scan_stop_time = scan_start_time + scan_timeout
                    while not self.stop_loop_event.is_set() and not self.stop_thread_event.wait(self.readout.readout_interval):
                        time_last_iteration = time_current_iteration
                        time_current_iteration = time.time()
                        time_from_last_iteration = time_current_iteration - time_last_iteration
                        if ((time_current_iteration - scan_start_time) % show_trigger_message_at < (time_last_iteration - scan_start_time) % show_trigger_message_at):
                            logging.info('Scan runtime: %d seconds', time_current_iteration - scan_start_time)
                            if not any(self.readout.get_rx_sync_status()):
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                                logging.error('No RX sync. Stopping Scan...')
                            if any(self.readout.get_rx_8b10b_error_count()):
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                                logging.error('RX 8b10b error(s) detected. Stopping Scan...')
                            if any(self.readout.get_rx_fifo_discard_count()):
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                                logging.error('RX FIFO discard error(s) detected. Stopping Scan...')
                        if scan_timeout is not None and time_current_iteration > scan_stop_time:
                            logging.info('Reached maximum scan time. Stopping Scan...')
                            self.stop_loop_event.set()
                        try:
                            raw_data_file.append((self.readout.data.popleft(),), scan_parameters={'column': column, 'row': row})
                        except IndexError:  # no data
                            no_data_at_time = time_current_iteration
                            if timeout_no_data is not None and wait_for_first_data == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                                logging.info('Reached no data timeout. Stopping Scan...')
                                self.repeat_scan_step = True
                                self.stop_loop_event.set()
                            elif wait_for_first_data == False:
                                saw_no_data_at_time = no_data_at_time

                            if no_data_at_time > (saw_data_at_time + 10):
                                scan_stop_time += time_from_last_iteration
                        else:
                            saw_data_at_time = time_current_iteration

                            if wait_for_first_data == True:
                                logging.info('Taking data...')
                                wait_for_first_data = False

                    self.readout_utils.configure_tdc_fsm(enable_tdc=False, enable_tdc_arming=False)
                    self.set_self_trigger(False)
                    self.readout.stop()

                    if self.repeat_scan_step:
                        self.readout.print_readout_status()
                        logging.warning('Repeating scan for pixel %d/%d' % (column, row))
                        self.register_utils.configure_all()
                        self.readout.reset_rx()
                    else:
                        raw_data_file.append(self.readout.data, scan_parameters={'column': column, 'row': row})

                        logging.info('Total scan runtime for pixel %d/%d: %d seconds' % (column, row, (time_current_iteration - scan_start_time)))

    def configure_fe(self, column, row, trig_latency, trig_count):
        pixel_reg = "Enable"
        mask = np.zeros(shape=(80, 336))
        mask[column - 1, row - 1] = 1  # just enable one pixel
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        enable_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))

        pixel_reg = "Imon"
        mask = np.ones(shape=(80, 336))
        mask[column - 1, row - 1] = 0  # just enable one pixel
        imon_mask = np.logical_or(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, imon_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        # enable GateHitOr that enables FE self-trigger mode
        self.register.set_global_register_value("Trig_Lat", trig_latency)  # set trigger latency, this latency sets the hits at the first relative BCID bins
        self.register.set_global_register_value("Trig_Count", trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        # send commands
        self.register_utils.send_commands(commands)

    def set_self_trigger(self, enable=True):
        logging.info('%s FEI4 self-trigger' % ('Enable' if enable == True else "Disable"))
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("GateHitOr", 1 if enable else 0)  # enable FE self-trigger mode
        commands.extend(self.register.get_commands("wrregister", name=["GateHitOr"]))
        if enable:
            commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

    def analyze(self):
        for raw_data_file in glob.glob(self.scan_data_filename + '_*.h5'):  # loop over all created raw data files
            with AnalyzeRawData(raw_data_file=raw_data_file, analyzed_data_file=raw_data_file[:-3] + "_interpreted.h5") as analyze_raw_data:
                analyze_raw_data.interpreter.set_trig_count(scan_configuration['trig_count'])
                analyze_raw_data.create_tdc_hist = True
                analyze_raw_data.interpreter.use_tdc_word(True)  # align events at TDC words, first word of event has to be a tdc word
                analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
                analyze_raw_data.interpreter.print_summary()
                analyze_raw_data.plot_histograms(scan_data_filename=raw_data_file[:-3])

if __name__ == "__main__":
    import configuration
    scan = FEI4SelfTriggerHitOr(**configuration.scc99_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()
