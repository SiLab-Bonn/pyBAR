#!/usr/bin/env python2

import logging
import sys
from optparse import OptionParser
from time import time, strftime, gmtime, sleep

import numpy as np
from PyEUDAQWrapper import PyProducer

from pybar.run_manager import RunManager, run_status
from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.daq.readout_utils import build_events_from_raw_data, is_trigger_word


sys.path.append('/home/telescope/eudaq/python/')


class EudaqExtTriggerScan(ExtTriggerScan):
    '''External trigger scan that connects to EUDAQ producer (EUDAQ 1.4 and higher).
    '''
    _default_run_conf = {
        "broadcast_commands": True,
        "threaded_scan": False,
        "trig_count": 0,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "trigger_latency": 232,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220
        "trigger_delay": 8,  # trigger delay, in BCs
        "trigger_rate_limit": 1000,  # artificially limiting the trigger rate, in BCs (25ns)
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": False,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": None,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": None,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": 0,  # maximum triggers after which the scan will be stopped, if 0, no maximum triggers are set
        "enable_tdc": False  # if True, enables TDC
    }

    def scan(self):
        self.data_error_occurred = False
        self.last_trigger_number = None
        clock_cycles = self.dut['TLU']['TRIGGER_CLOCK_CYCLES']
        if clock_cycles:
            self.max_trigger_counter = 2 ** (clock_cycles - 1)
        else:
            self.max_trigger_counter = 2 ** 31
        start = time()
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.register_utils.set_command(lvl1_command)

        self.remaining_data = np.ndarray((0,), dtype=np.uint32)

        with self.readout(**self.scan_parameters._asdict()):
            got_data = False
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                else:
                    triggers = self.dut['TLU']['TRIGGER_COUNTER']
                    data_words = self.data_words_per_second()
                    logging.info('Runtime: %s\nTriggers: %d\nData words/s: %s\n' % (strftime('%H:%M:%S', gmtime(time() - start)), triggers, str(data_words)))
                    if self.max_triggers and triggers >= self.max_triggers:
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)

        pp.SendEvent(self.remaining_data)

        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

#     def analyze(self):
#         pass

    def handle_err(self, exc):
        super(EudaqExtTriggerScan, self).handle_err(exc=exc)
        self.data_error_occurred = True

    def handle_data(self, data, new_file=False, flush=True):
        events = build_events_from_raw_data(data[0])
        for item in events:
            if item.shape[0] == 0:
                continue
            if is_trigger_word(item[0]):
                if self.remaining_data.shape[0] > 0:
                    # check trigger number
                    if is_trigger_word(self.remaining_data[0]):
                        trigger_number = self.remaining_data[0] & (self.max_trigger_counter - 1)
                        if self.last_trigger_number is not None and ((self.last_trigger_number + 1 != trigger_number and self.last_trigger_number + 1 != self.max_trigger_counter) or (self.last_trigger_number + 1 == self.max_trigger_counter and trigger_number != 0)):
                            if self.data_error_occurred:
                                if trigger_number > self.last_trigger_number:
                                    missing_trigger_numbers = trigger_number - self.last_trigger_number - 1
                                else:
                                    missing_trigger_numbers = self.max_trigger_counter - (self.last_trigger_number - trigger_number) - 1
                                logging.warning('Data errors detected: trigger number read: %d, expected: %d, sending %d empty events', trigger_number, 0 if (self.last_trigger_number + 1 == self.max_trigger_counter) else (self.last_trigger_number + 1), missing_trigger_numbers)
                                for missing_trigger_number in range(self.last_trigger_number + 1, self.last_trigger_number + missing_trigger_numbers + 1):
                                    pp.SendEvent(np.asarray([missing_trigger_number & (self.max_trigger_counter - 1)], np.uint32))
                                self.data_error_occurred = False
                                self.last_trigger_number = trigger_number
                            else:
                                logging.warning('Trigger number not increasing: read: %d, expected: %d', trigger_number, 0 if (self.last_trigger_number + 1 == self.max_trigger_counter) else (self.last_trigger_number + 1))
                                self.last_trigger_number = (self.last_trigger_number + 1) & (self.max_trigger_counter - 1)
                        else:
                            self.last_trigger_number = trigger_number
                    pp.SendEvent(self.remaining_data)
                self.remaining_data = item
            else:
                self.remaining_data = np.concatenate([self.remaining_data, item])
        super(EudaqExtTriggerScan, self).handle_data(data=data, new_file=new_file, flush=flush)


if __name__ == "__main__":
    usage = "Usage: %prog [options] ADDRESS"
    description = "Optional: Start EUDAQ Producer with destination ADDRESS (e.g. 'tcp://localhost:44000')."
    parser = OptionParser(usage, description=description)
#     parser.add_option("-c", "--column", dest="col_span", type="int", nargs=2, help="2-tuple of columns (from and to)", default=(1, 80))
#     parser.add_option("-r", "--row", dest="row_span", type="int", nargs=2, help="2-tuple of rows (from and to)", default=(1, 336))
    options, args = parser.parse_args()
    if len(args) == 1:
        rcaddr = args[0]

    else:
        parser.error("incorrect number of arguments")
    run_conf = vars(options)
    # create PyProducer instance
    pp = PyProducer("PyBAR", rcaddr)
    while not pp.Error and not pp.Terminating:
        # wait for configure cmd from RunControl
        while not pp.Configuring and not pp.Terminating:
            if pp.StartingRun:
                break
            sleep(1)
        # check if configuration received
        if pp.Configuring:
            print "Configuring..."
    #         for item in run_conf:
    #             try:
    #                 run_conf[item] = pp.GetConfigParameter(item)
    #             except:
    #                 pass
            rmngr = RunManager('../configuration.yaml')  # TODO: get conf from EUDAQ
            pp.Configuring = True
        # check for start of run cmd from RunControl
        while not pp.StartingRun and not pp.Terminating:
            if pp.Configuring:
                break
            sleep(1)
        # check if we are starting:
        if pp.StartingRun:
            print "Starting run..."
#             join = rmngr.run_run(EudaqExtTriggerScan, run_conf=run_conf, use_thread=True)
            join = rmngr.run_run(EudaqExtTriggerScan, use_thread=True)
            sleep(5)
            pp.StartingRun = True  # set status and send BORE
            # starting to run
            while join(timeout=1) is None:
                if pp.Error or pp.Terminating:
                    rmngr.abort_current_run()
                if pp.StoppingRun:
                    rmngr.stop_current_run()
            status = join()
            # abort conditions
            if status is not run_status.finished or pp.Error or pp.Terminating:
                pp.StoppingRun = False  # set status and send EORE
            # check if the run is stopping regularly
            if pp.StoppingRun:
                pp.StoppingRun = True  # set status and send EORE
