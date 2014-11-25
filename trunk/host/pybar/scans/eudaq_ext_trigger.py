#!/usr/bin/env python2

import logging
from optparse import OptionParser
import numpy as np
from time import time, strftime, gmtime, sleep

from pybar.run_manager import RunManager, run_status
from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.daq.readout_utils import build_events_from_raw_data, is_trigger_word

import sys
sys.path.append('/home/telescope/eudaq/python/')
from PyEUDAQWrapper import PyProducer


class EudaqExtTriggerScan(ExtTriggerScan):
    '''EUDAQ producer
    '''
#     _default_run_conf = ExtTriggerScan._default_run_conf
#     _default_run_conf.update({
#         "trigger_mode": 3,
#         "no_data_timeout": 600,
#         "scan_timeout": 0,
#     })
    _default_run_conf = {
        "trigger_mode": 3,  # trigger mode, more details in basil.HL.tlu, from 0 to 3
        "trigger_latency": 232,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220
        "trigger_delay": 14,  # trigger delay, in BCs
        "trigger_rate_limit": 1000,  # artificially limiting the trigger rate, in BCs (25ns)
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": False,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 600,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": None,  # timeout for scan after which the scan will be stopped, in seconds
        "max_triggers": None,  # maximum triggers after which the scan will be stopped, in seconds
        "enable_tdc": False  # if True, enables TDC (use RX2)
    }

    def scan(self):
        start = time()
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("LV1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.register_utils.set_command(lvl1_command)

        self.remaining_data = np.ndarray((0,), dtype=np.uint32)

        with self.readout(**self.scan_parameters._asdict()):
            got_data = False
            while not self.stop_run.wait(1.0):
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
                else:
                    triggers = self.dut['tlu']['TRIGGER_COUNTER']
                    data_words = self.fifo_readout.data_words_per_second()
                    print 'Runtime: %s\nTriggers: %d\nData words / s: %d\n' % (strftime('%H:%M:%S', gmtime(time() - start)), triggers, data_words)
                    if self.max_triggers is not None and triggers >= self.max_triggers:
                        self.stop(msg='Trigger limit was reached: %i' % self.max_triggers)

        pp.SendEvent(self.remaining_data)

        logging.info('Total amount of triggers collected: %d', self.dut['tlu']['TRIGGER_COUNTER'])

#     def analyze(self):
#         pass

    def handle_data(self, data):
        events = build_events_from_raw_data(data[0])
        for item in events:
            if item.shape[0] == 0:
                continue
            if is_trigger_word(item[0]):
                if self.remaining_data.shape[0] > 0:
                    pp.SendEvent(self.remaining_data)
                self.remaining_data = item
            else:
                self.remaining_data = np.concatenate([self.remaining_data, item])

        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), flush=True)


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
    pp = PyProducer("pyBAR", rcaddr)
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

