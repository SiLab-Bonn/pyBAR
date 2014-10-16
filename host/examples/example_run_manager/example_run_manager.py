from pybar.run_manager import RunManager  # importing run manager
from pybar.scans.scan_analog import AnalogScan
from pybar.scans.scan_ext_trigger_gdac import ExtTriggerGdacScan
from pybar.run_manager import run_status

if __name__ == "__main__":
    runmngr = RunManager('../../pybar/configuration.yaml')  # loading configuration file, specifying hardware configuration and module configuration.
    #
    # Running primlist:
    runmngr.run_primlist('example_run_manager.plst', skip_remaining=True)  # executing primlist.plst file, specific scan parameters are set inside the primlist file, skip remaining scans on error
    # Each scan has a default configuration, which is defined inside the corresponding scan file in /host/pybar/scans/. It is not necessary to define scan parameters inside primlist file.
    #
    # Running single scan and changing scan parameters:
    join = runmngr.run_run(run=AnalogScan, run_conf={"scan_parameters": {'PlsrDAC': 500}, "n_injections": 1000})  # run_run returns a function object
    status = join()
    print 'Status:', status  # will wait for scan to be finished and returns run status
    #
    # Or use a run configuration file:
    join = runmngr.run_run(run=AnalogScan, run_conf="run_configuration.txt")
    status = join()
    print 'Status:', status
    #
    # Example for a loop:
    for gdac in range(50, 200, 10):
        join = runmngr.run_run(ExtTriggerGdacScan, run_conf={'scan_parameters': {'GDAC': gdac}})
        print 'Status:', join(timeout=5)  # join has a timeout, return None if run has not yet finished
        runmngr.abort_current_run()  # stopping/aborting run from outside
        if join() != run_status.finished:  # status OK?
            print 'ERROR!'
            break  # jump out
    #
    # After finishing the primlist/run: you will find the module data relative to the configuration.yaml file.
    # If configuration.yaml is in /host/pybar/ the module data will be /host/pybar/<module_id> (where <module_id> is given from configuration.yaml).
    # After finishing the first scan, FE configuration can be commented out in configuration.yaml (for that use '#'):
    #
    # (from configuration.yaml)
    # fe_configuration:
    #     configuration : #config/fei4/configs/std_cfg_fei4a.cfg
    #     ...
    #
    # The latest FE configuration (highest run number with status 'FINISHED') will be taken from module data folder if no FE configuration is given.
    # Instead of a path to FE configuration file, a run number (e.g. 5) can be entered to load a specific FE configuration:
    #
    # (from configuration.yaml)
    # fe_configuration:
    #     configuration : 5 # run number
    #     ...
    #
    # It is recommended to make copy of configuration.yaml for each module / specific hardware configuration.
    #
    # Feel free to modify / change / update the code :-)
    #
