import time
import logging
import numpy as np

from scan.scan import ScanBase
from daq.readout import open_raw_data_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "col_span": [2, 77],
    "row_span": [2, 335],
    "timeout_no_data": 10,
    "scan_timeout": 1 * 20,
    "trig_latency": 239,
    "trig_count": 4
}


class FEI4SelfTriggerScan(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(FEI4SelfTriggerScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="fei4_self_trigger_scan")

    def scan(self, col_span=[1, 80], row_span=[1, 336], timeout_no_data=10, scan_timeout=10 * 60, trig_latency=239, trig_count=4):
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
        self.register.create_restore_point()
        self.configure_fe(col_span, row_span, trig_latency, trig_count)

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier) as raw_data_file:
            self.readout.start()
            self.set_self_trigger()
            wait_for_first_data = True
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
                except IndexError:  # no data
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

            self.register.restore()
            self.register_utils.configure_all()

            self.readout.stop()

            raw_data_file.append(self.readout.data)

    def configure_fe(self, col_span, row_span, trig_latency, trig_count):
        # generate ROI mask for Enable mask
        pixel_reg = "Enable"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span)
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        enable_mask = np.logical_and(mask, self.register.get_pixel_register_value(pixel_reg))
        self.register.set_pixel_register_value(pixel_reg, enable_mask)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=pixel_reg))
        # generate ROI mask for Imon mask
        pixel_reg = "Imon"
        mask = self.register_utils.make_box_pixel_mask_from_col_row(column=col_span, row=row_span, default=1, value=0)
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
        self.register.set_global_register_value("Trig_Lat", trig_latency)  # set trigger latency, this latency sets the hits at the first rel. BCID bins
        self.register.set_global_register_value("Trig_Count", trig_count)  # set number of consecutive triggers
        commands.extend(self.register.get_commands("wrregister", name=["Trig_Lat", "Trig_Count"]))
        # send commands
        self.register_utils.send_commands(commands)

    def set_self_trigger(self):
        logging.info('Activate self trigger feature')
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("GateHitOr", 1)  # enable FE self-trigger mode
        commands.extend(self.register.get_commands("wrregister", name=["GateHitOr"]))
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename + ".h5", analyzed_data_file=output_file) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(scan_configuration['trig_count'])
            analyze_raw_data.create_cluster_size_hist = True  # can be set to false to omit cluster hit creation, can save some time, std. setting is false
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_tot_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.clusterizer.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=scan.scan_data_filename)

if __name__ == "__main__":
    import configuration
#     scan = FEI4SelfTriggerScan(**configuration.scc99_configuration)
    scan = FEI4SelfTriggerScan(**configuration.mdbm30_configuration)
    scan.start(use_thread=True, **scan_configuration)
    scan.stop()
    scan.analyze()
