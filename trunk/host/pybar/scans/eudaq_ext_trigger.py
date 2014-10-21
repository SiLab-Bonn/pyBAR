#!/usr/bin/env python2

import logging
from optparse import OptionParser
from PyEUDAQWrapper import PyProducer
from time import time, strftime, gmtime, sleep

from pybar.run_manager import RunManager, run_status
from pybar.scans.scan_ext_trigger import ExtTriggerScan


class EudaqExtTriggerScan(ExtTriggerScan):
    _scan_id = "eudaq_ext_trigger_scan"
    _default_scan_configuration = ExtTriggerScan._default_scan_configuration
    _default_scan_configuration.update({
        "trigger_mode": 3,
        "no_data_timeout": 600,
        "scan_timeout": 0,
    })

    def scan(self):
        start = time()
        lvl1_command = self.register.get_commands("zeros", length=self.trigger_delay)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", length=self.trigger_rate_limit)[0]
        self.register_utils.set_command(lvl1_command)

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

        logging.info('Total amount of triggers collected: %d', self.dut['tlu']['TRIGGER_COUNTER'])

#     def analyze(self):
#         pass

    def handle_data(self, data):
        self.pp.SendEvent(data)  # send event off
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
#         vars.update(vars(options))
    else:
        parser.error("incorrect number of arguments")

    # create PyProducer instance
    pp = PyProducer("pyBAR", rcaddr)
    # wait for configure cmd from RunControl
    while not pp.Configuring and not pp.Terminating:
        sleep(1)
    # check if configuration received
    if pp.Configuring:
        print "Ready to configure..."
#         for item in vars:
#             try:
#                 vars[item] = pp.GetConfigParameter(item)
#             except:
#                 pass
        rmngr = RunManager('../configuration.yaml')  # TODO: get conf from EUDAQ
        pp.Configuring = True
    # check for start of run cmd from RunControl
    while not pp.Error and not pp.Terminating:
        while not pp.StartingRun and not pp.Terminating:
            sleep(1)
        # check if we are starting:
        if pp.StartingRun:
            print "Ready to run!"
            join = rmngr.run_run(run_conf='../configuration.yaml', use_thread=True)
            pp.StartingRun = True  # set status and send BORE
        # starting to run
        status = False
        while join(timeout=1) is None:
            if pp.Error or pp.Terminating:
                rmngr.abort_current_run()
            if pp.StoppingRun:
                rmngr.stop_current_run()
        status = join()
        if status is not None:
                break
        # check if the run is stopping regularly
        if pp.StoppingRun and status == run_status.finished:
            pp.StoppingRun = True  # set status and send EORE
