from scan.run_manager import RunManager

if __name__ == "__main__":
    runmngr = RunManager('configuration.yaml')
    runmngr.run_primlist('primlist.plst')
