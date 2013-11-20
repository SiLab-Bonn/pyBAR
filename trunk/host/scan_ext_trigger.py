import time
import logging
import math

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class ExtTriggerScan(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="scan_ext_trigger", scan_data_path=None):
        super(ExtTriggerScan, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)

    def scan(self, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, scan_timeout=60, max_triggers=10000, **kwargs):
        '''Scan loop

        Parameters
        ----------
        col_span : list, tuple
            Column range (from minimum to maximum value). From 1 to 80.
        row_span : list, tuple
            Row range (from minimum to maximum value). From 1 to 336.
        timeout_no_data : int
            In seconds; if no data, stop scan after given time.
        scan_timeout : int
            In seconds; stop scan after given time.
        '''
        # generate mask for Enable mask
        pixel_reg = "Enable"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_pixel_register_value(pixel_reg, mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # generate mask for Imon mask
        pixel_reg = "Imon"
#         mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # disable C_inj mask
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # setting FE into runmode
        commands.extend(self.register.get_commands("runmode"))
        # append_size = 50000
        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier) as raw_data_file:
            self.readout.start()

            # preload command
            lvl1_command = self.register.get_commands("zeros", length=24)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=1000)[0]
            self.register_utils.set_command(lvl1_command)
            self.readout_utils.configure_trigger_fsm(mode=0, disable_veto=False, enable_reset=False, invert_lemo_trigger_input=False, trigger_clock_cycles=16, trigger_data_delay=4, trigger_low_timeout=0)
            self.readout_utils.configure_command_fsm(enable_ext_trigger=True)

            wait_for_first_trigger = True

            show_trigger_message_at = 10 ** (int(math.ceil(math.log10(max_triggers))) - 1)
            last_iteration = time.time()
            saw_no_data_at_time = last_iteration
            saw_data_at_time = last_iteration
            scan_start_time = last_iteration
            no_data_at_time = last_iteration
            time_from_last_iteration = 0
            scan_stop_time = scan_start_time + scan_timeout
            current_trigger_number = 0
            last_trigger_number = 0
            while not self.stop_thread_event.wait(self.readout.readout_interval):

#                 if logger.isEnabledFor(logging.DEBUG):
#                     lost_data = self.readout.get_lost_data_count()
#                     if lost_data != 0:
#                         logging.debug('Lost data count: %d', lost_data)
#                         logging.debug('FIFO fill level: %4f', (float(fifo_size)/2**20)*100)
#                         logging.debug('Collected triggers: %d', self.readout.get_trigger_number())

                current_trigger_number = self.readout_utils.get_trigger_number()
                if (current_trigger_number % show_trigger_message_at < last_trigger_number % show_trigger_message_at):
                    logging.info('Collected triggers: %d', current_trigger_number)
                last_trigger_number = current_trigger_number
                if max_triggers is not None and current_trigger_number >= max_triggers:
                    logging.info('Reached maximum triggers. Stopping Scan...')
                    self.stop_thread_event.set()
                if scan_start_time is not None and time.time() > scan_stop_time:
                    logging.info('Reached maximum scan time. Stopping Scan...')
                    self.stop_thread_event.set()
                # TODO: read 8b10b decoder err cnt
#                 if not self.readout.read_rx_status():
#                     logging.info('Lost data sync. Starting synchronization...')
#                     self.readout.configure_command_fsm(False)
#                     if not self.readout.reset_rx(1000):
#                         logging.info('Failed. Stopping scan...')
#                         self.stop_thread_event.set()
#                     else:
#                         logging.info('Done!')
#                         self.readout.configure_command_fsm(True)

                time_from_last_iteration = time.time() - last_iteration
                last_iteration = time.time()
                while True:
                    try:
                        raw_data_file.append((self.readout.data.popleft(),))
                    except IndexError:  # no data
                        no_data_at_time = last_iteration
                        if wait_for_first_trigger == False and saw_no_data_at_time > (saw_data_at_time + timeout_no_data):
                            logging.info('Reached no data timeout. Stopping Scan...')
                            self.stop_thread_event.set()
                        elif wait_for_first_trigger == False:
                            saw_no_data_at_time = no_data_at_time

                        if no_data_at_time > (saw_data_at_time + 10):
                            scan_stop_time += time_from_last_iteration

                        break  # jump out while loop

                    saw_data_at_time = last_iteration

                    if wait_for_first_trigger == True:
                        logging.info('Taking data...')
                        wait_for_first_trigger = False

            self.readout_utils.configure_command_fsm(enable_ext_trigger=False)
            self.readout_utils.configure_trigger_fsm(mode=0)

            logging.info('Total amount of triggers collected: %d', self.readout_utils.get_trigger_number())

        self.readout.stop()

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.create_cluster_size_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(FEI4B=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)


if __name__ == "__main__":
    import configuration
    scan = ExtTriggerScan(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.start(configure=True, use_thread=True, timeout_no_data=5, scan_timeout=100, max_triggers=1000, col_span=[1, 1], row_span=[336, 336])
    scan.stop()
    scan.analyze()
