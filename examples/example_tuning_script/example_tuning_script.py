'''Example: tuning script

Note:
To change tuning parameters, change configuration.yaml, or use run_conf parameter.
'''

from pybar import *

# additional run configuration (optinal)
run_conf = None  # use path to YAML file, or dict

if __name__ == "__main__":
    runmngr = RunManager('../../pybar/configuration.yaml')  # configuration YAML file, open it for more details, it may contain run configuration

    # pre tuning
    status = runmngr.run_run(run=DigitalScan, run_conf=run_conf)
    print('Status: %s' % (status,))

    status = runmngr.run_run(run=ThresholdScan, run_conf=run_conf)
    print('Status: %s' % (status,))

    status = runmngr.run_run(run=AnalogScan, run_conf=run_conf)
    print('Status: %s' % (status,))

    # tuning
    status = runmngr.run_run(run=Fei4Tuning, run_conf=run_conf)
    print('Status: %s' % (status,))

    # post tuning
    status = runmngr.run_run(run=ThresholdScan, run_conf=run_conf)
    print('Status: %s' % (status,))

    status = runmngr.run_run(run=AnalogScan, run_conf=run_conf)
    print('Status: %s' % (status,))

    # masking noisy and hot pixels
    status = runmngr.run_run(run=StuckPixelTuning, run_conf=run_conf)
    print('Status: %s' % (status,))

    status = runmngr.run_run(run=NoiseOccupancyTuning, run_conf=run_conf)
    print('Status: %s' % (status,))

    # masking merged pixels
    # status = runmngr.run_run(run=MergedPixelsTuning)
    # print('Status: %s' % (status,))
