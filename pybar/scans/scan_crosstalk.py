import logging

from pybar.scans.scan_threshold import ThresholdScan
from pybar.run_manager import RunManager


class CrosstalkScan(ThresholdScan):
    '''Crosstalk Scan

    Implementation of a crosstalk scan based on the threshold scan.
    '''
    _default_run_conf = ThresholdScan._default_run_conf.copy()
    _default_run_conf.update({
        "mask_steps": 3,  # number of injections per PlsrDAC step
        "n_injections": 100,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', [None, 100])],  # the PlsrDAC range
        "step_size": 1,  # step size of the PlsrDAC during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable"],  # enable masks shifted during scan
        "disable_shift_masks": ["C_High", "C_Low"],  # disable masks shifted during scan
        "pulser_dac_correction": False  # PlsrDAC correction for each double column
    })


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(CrosstalkScan)
