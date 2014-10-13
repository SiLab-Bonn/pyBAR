from pybar.run_manager import RunManager  # importing run manager

if __name__ == "__main__":
    runmngr = RunManager('../../pybar/configuration.yaml')  # loading configuration file, specifying hardware configuration and module configuration.
    runmngr.run_primlist('primlist.plst')  # executing primlist.plst file, specific scan parameters are set inside the primlist file
    #
    # After finishing the primlist: you will find the module data relative to the configuration.yaml file
    # If configuration.yaml is in /host/pybar/ the module data will be /host/pybar/<module_id> (where <module_id> is given from configuration.yaml)
    # After finishing the first scan, FE configuration can be commented out in configuration.yaml (for that use '#'):
    #
    # (from configuration.yaml)
    # fe_configuration:
    #     configuration : #config/fei4/configs/std_cfg_fei4a.cfg
    #     ...
    #
    # The latest FE configuration (highest run number with status 'FINISHED') will be taken from module data folder if no FE configuration is given.
    # Instead of a path to FE configuration file, a run number can be entered to load a specific FE configuration:
    #
    # (from configuration.yaml)
    # fe_configuration:
    #     configuration : 5 # run number
    #     ...
    #
    # It is recommended to make copy of configuration.yaml for each module / specific hardware configuration.
    #
    # Feel free to modify / change the code :-)
    #
