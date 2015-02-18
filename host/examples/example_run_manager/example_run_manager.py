from pybar.run_manager import RunManager  # importing run manager
from pybar.scans.scan_analog import AnalogScan
from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.run_manager import run_status

if __name__ == "__main__":
    # The FE flavor can be set in configuration.yaml (for that use either fei4a or fei4b).
    runmngr = RunManager('../../pybar/configuration.yaml')  # loading configuration file, specifying hardware configuration and module configuration.
    #
    # Running primlist:
    runmngr.run_primlist('example_run_manager.plst', skip_remaining=True)  # executing primlist.plst file, specific scan parameters are set inside the primlist file, skip remaining scans on error
    # Each scan has a default run configuration, which is defined inside the corresponding scan file in /host/pybar/scans/. It is not necessary to define scan parameters inside primlist file.
    #
    # Running single scan and changing scan parameters:
    join = runmngr.run_run(run=AnalogScan, run_conf={"scan_parameters": [('PlsrDAC', 500)], "n_injections": 1000}, use_thread=True)  # run_run returns a function object when use_thread is True
    status = join()
    print 'Status:', status  # will wait for scan to be finished and returns run status
    #
    # Or use a run configuration file:
    status = runmngr.run_run(run=AnalogScan, run_conf="run_configuration.txt")  # using no thread
    print 'Status:', status
    #
    # Example for a loop of scans, which is failing:
    for delay in range(14, 50, 16):
        join = runmngr.run_run(ExtTriggerScan, run_conf={"trigger_delay": delay, "no_data_timeout": 60}, use_thread=True)  # use thread
        print 'Status:', join(timeout=5)  # join has a timeout, return None if run has not yet finished
        runmngr.abort_current_run()  # stopping/aborting run from outside
        if join() != run_status.finished:  # status OK?
            print 'ERROR!'
            break  # jump out
    #
    # After finishing the primlist/run: you will find the module data relative to the configuration.yaml file.
    # If configuration.yaml is in /host/pybar/ the module data will be /host/pybar/<module_id> (where <module_id> is defined inside configuration.yaml).
    # After finishing the first scan, the FE flavor can be commented out in configuration.yaml (for that use '#'):
    #
    # (from configuration.yaml)
    # fe_configuration : # fei4a
    # ...
    #
    # If fe_configuration is not given, the latest valid FE configuration will be taken (highest run number with status 'FINISHED').
    # To load a specific configuration file, a path to FE configuration file or a run number (e.g. 5) can be used:
    #
    # (from configuration.yaml)
    # fe_configuration: 5
    # ...
    #
    # The configuration.yaml can be extended to change the default run parameters for each scan:
    #
    # (from configuration.yaml)
    # AnalogScan:
    #     scan_parameters : {'PlsrDAC': 100} # inject 100 PlsrDAC
    #     enable_shift_masks : ["Enable", "C_Low"] # use C_Low only
    #
    # It is recommended to keep a copy of configuration.yaml for each module.
    #
    # Feel free to modify / change / update the code :-)
    #
