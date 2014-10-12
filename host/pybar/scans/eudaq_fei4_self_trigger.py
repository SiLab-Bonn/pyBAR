#!/usr/bin/env python2

import logging
from PyEUDAQWrapper import PyProducer
from time import sleep, time
import numpy as np

from pybar.run_manager import RunManager
from pybar.scans.scan_fei4_self_trigger import FEI4SelfTriggerScan


class EudaqFEI4SelfTriggerScan(FEI4SelfTriggerScan):
    _scan_id = "eudaq_fei4_self_trigger_scan"
    _default_scan_configuration = FEI4SelfTriggerScan._default_scan_configuration
    _default_scan_configuration.update({
        "producer": "pyBAR",
        "destination": "tcp://localhost:44000"
    })

    def configure(self):
        FEI4SelfTriggerScan.configure(self)
        print "Starting PyProducer"
        self.pp = PyProducer(self.producer, self.destination)

    def scan(self):
        i = 0  # counter variables for wait routines
        maxwait = 100
        waittime = .5
        # wait for configure cmd from RunControl
        while i < maxwait and not self.pp.Configuring:
            sleep(waittime)
            print "Waiting for configure for ", i * waittime, " seconds"
            i += 1
        # check if configuration received
        if self.pp.Configuring:
            print "Ready to configure, received config string 'Parameter'=", self.pp.GetConfigParameter("Parameter")
            # .... do your config stuff here ...
            sleep(5)
            self.pp.Configuring = True
        # check for start of run cmd from RunControl
        while i < maxwait and not self.pp.StartingRun:
            sleep(waittime)
            print "Waiting for run start for ", i * waittime, " seconds"
            i += 1
        # check if we are starting:
        if self.pp.StartingRun:
            print "Ready to run!"
            # ... prepare your system for the immanent run start
            sleep(5)
            self.pp.StartingRun = True  # set status and send BORE
        # starting to run
        with self.readout():
            got_data = False
            while not self.pp.Error and not self.pp.Stoself.ppingRun and not self.pp.Terminating:
                if self.stop_run.wait(1.0):
                    pass  # TODO: what shall we do when error happens? send message...
                if not got_data:
                    if self.fifo_readout.data_words_per_second() > 0:
                        got_data = True
                        logging.info('Taking data...')
        if self.pp.StoppingRun:
            self.pp.StoppingRun = True  # set status and send EORE

    def handle_data(self, data):
        data_uint64 = data[0].astype(np.uint64)  # copy
        self.pp.SendEvent(data_uint64)  # send event off
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), flush=True)

if __name__ == "__main__":
    from optparse import OptionParser
    usage = "Usage: %prog [options] ADDRESS"
    description = "Start EUDAQ Producer with destination ADDRESS (e.g. tcp://localhost:44000)."
    parser = OptionParser(usage, description=description)
    parser.add_option("-c", "--column", dest="col_span", type="int", nargs=2, help="2-tuple of columns (from and to)", default=(1, 80))
    parser.add_option("-r", "--row", dest="row_span", type="int", nargs=2, help="2-tuple of rows (from and to)", default=(1, 336))
    options, args = parser.parse_args()
    if len(args) != 1:
        parser.error("Incorrect number of arguments")
    mngr = RunManager('../configuration.yaml')  # TODO: add options to configuration
    join = mngr.run_run(EudaqFEI4SelfTriggerScan)
    join()
