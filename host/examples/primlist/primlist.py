from pybar.run_manager import RunManager

if __name__ == "__main__":
    runmngr = RunManager('../../pybar/configuration.yaml')
    runmngr.run_primlist('primlist.plst')
