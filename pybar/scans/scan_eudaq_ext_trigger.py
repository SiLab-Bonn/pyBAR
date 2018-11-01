#!/usr/bin/env python2

import logging
import sys
import argparse
from time import time, strftime, gmtime

import numpy as np

from pybar.run_manager import RunManager, run_status
from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.daq.readout_utils import build_events_from_raw_data, is_trigger_word

# set path to PyEUDAQWrapper
sys.path.append('/path/to/eudaq/python/')
from PyEUDAQWrapper import PyProducer
default_address = 'localhost:44000'


class EudaqExtTriggerScan(ExtTriggerScan):
    '''External trigger scan that connects to EUDAQ producer for EUDAQ 1.7 and higher (1.x-dev).
    '''
    _default_run_conf = {
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
        "enable_tdc": False  # if True, enables TDC (use RX2)
    }

    def scan(self):
        self.data_error_occurred = False
        self.last_trigger_number = None
        # set TLU max trigger counter
        self.max_trigger_counter = 2 ** 15
        start = time()
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.register_utils.set_command(lvl1_command)

        self.remaining_data = np.ndarray((0,), dtype=np.uint32)

        with self.readout(**self.scan_parameters._asdict()):
            pp.StartingRun = True  # set status and send BORE
            got_data = False
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                else:
                    triggers = self.dut['TLU']['TRIGGER_COUNTER']
                    data_words = self.fifo_readout.data_words_per_second()
                    logging.info('Runtime: %s\nTriggers: %d\nData words/s: %s\n' % (strftime('%H:%M:%S', gmtime(time() - start)), triggers, str(data_words)))
                    if self.max_triggers and triggers >= self.max_triggers:
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)

        if self.remaining_data.shape[0] > 0:
            pp.SendEvent(self.remaining_data)

        logging.info('Total amount of triggers collected: %d', self.dut['TLU']['TRIGGER_COUNTER'])

#     def analyze(self):
#         pass

    def handle_err(self, exc):
        super(EudaqExtTriggerScan, self).handle_err(exc=exc)
        self.data_error_occurred = True

    def handle_data(self, data, new_file=False, flush=True):
        for data_tuple in data[0]:  # only use data from first module
            events = build_events_from_raw_data(data_tuple[0])  # build events from raw data array
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
    parser = argparse.ArgumentParser(description='pyBAR with EUDAQ support')
    parser.add_argument('address', type=str, metavar='address:port', action='store', help='IP address and port of the RunControl PC (default: %s)' % default_address, nargs='?')
    args = parser.parse_args()
    address = args.address
    if address is None:
        address = default_address
    if 'tcp://' not in address:
        address = 'tcp://' + address

    pp = PyProducer("PyBAR", address)
    runmngr = None
    while not pp.Error and not pp.Terminating:
        # check if configuration received
        if pp.Configuring:
            logging.info("Configuring...")
#             for item in run_conf:
#                 try:
#                     run_conf[item] = pp.GetConfigParameter(item)
#                 except Exception:
#                     pass
            if runmngr:
                runmngr.close()
                runmngr = None
            runmngr = RunManager('configuration.yaml')  # TODO: get conf from EUDAQ
            pp.Configuring = True

        # check if we are starting:
        if pp.StartingRun:
            run_number = pp.GetRunNumber()
            logging.info("Starting run EUDAQ run %d..." % run_number)
#             join = runmngr.run_run(EudaqExtTriggerScan, run_conf=run_conf, use_thread=True)
            join = runmngr.run_run(EudaqExtTriggerScan, use_thread=True, run_conf={"comment": "EUDAQ run %d" % run_number})
#             sleep(5)
#             pp.StartingRun = True  # set status and send BORE
            # starting run
            while join(timeout=1) == run_status.running:
                if pp.Error or pp.Terminating or pp.StoppingRun:
                    runmngr.cancel_current_run(msg="Run stopped by RunControl")
            status = join()
            logging.info("Run status: %s" % status)
            # abort conditions
            if pp.StoppingRun:
                pp.StoppingRun = True  # set status and send EORE
    if runmngr is not None:
        runmngr.close()
