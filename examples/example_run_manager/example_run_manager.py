from pybar import *

# Execute this script from the shell: python example_run_manager.py
#
# This script can also be run from a Python interactive shell (e.g. IPython).

if __name__ == "__main__":
    # The FE flavor can be set inside configuration.yaml (set the value to fei4a or fei4b).
    # The initial FE configuration will be created during the first run.
    #
    # (from configuration.yaml)
    # flavor : fei4a
    # ...
    #
    # Initializing the run manager:
    runmngr = RunManager('../../pybar/configuration.yaml')  # loading configuration file, specifying hardware configuration and module configuration.
    #
    # During the first run, an module data directory relative to the configuration.yaml file will be created.
    # If configuration.yaml is placed inside /host/pybar/ the module data will be stored inside /host/pybar/<module_id> (where <module_id> is defined inside configuration.yaml).
    #
    # If configuration inside configuration.yaml is not given, the latest valid FE configuration file will be taken (the file with the highest run number and run status 'FINISHED').
    #
    # (from configuration.yaml)
    # configuration:
    # ...
    #
    # If no configuration file exists, a initial configuration will be create according to flavor.
    # To load a specific configuration file, a path to FE configuration file or a run number (e.g. 5) can be given:
    #
    # (from configuration.yaml)
    # configuration: 1
    # ...
    #
    # This will retain the configuration for the following scans.
    # Please note: no configuration file exists at this stage because no run was executed so far.
    #
    # Executing runs defined by a primlist:
    runmngr.run_primlist('example_run_manager.plst', skip_remaining=True)  # executing primlist.plst file, specific run configuration are set inside the primlist file, skip remaining scans on error
    # press Ctrl-C to abort the run at any time
    # Each scan has a default run configuration, which is defined inside the corresponding scan file in /host/pybar/scans/.
    # It is not necessary to add run parameters to the primlist file. If not given they are taken from the default run configuration (_default_run_conf).
    #
    # Running a single scan and changing default run configuration (_default_run_conf):
    join = runmngr.run_run(run=AnalogScan, run_conf={"scan_parameters": [('PlsrDAC', 500)], "n_injections": 1000}, use_thread=True)  # run_run returns a function object when use_thread is True
    status = join()  # waiting here for finishing the run, press Ctrl-C to abort the run at any time
    print('Status: %s' % (status,))  # will wait for run to be finished and returns run status
    #
    # Or use a run configuration file:
    status = runmngr.run_run(run=AnalogScan, run_conf="example_run_manager_run_config.txt")  # using no thread
    print('Status: %s' % (status,))
    #
    # Example for a loop of runs, which is failing:
    for delay in range(14, 50, 16):
        join = runmngr.run_run(ExtTriggerScan, run_conf={"trigger_delay": delay, "no_data_timeout": 60}, use_thread=True)  # use thread
        print('Status: %s' % (join(timeout=5),))  # join has a timeout, return None if run has not yet finished
        runmngr.abort_current_run("Calling abort_current_run(). This scan was aborted by intention")  # stopping/aborting run from outside (same effect has Ctrl-C)
        if join() != run_status.finished:  # status OK?
            print('ERROR! This error was made by intention!')
            break  # jump out
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
