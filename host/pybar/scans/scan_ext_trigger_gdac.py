import logging
import numpy as np
import tables as tb
from scipy.interpolate import interp1d

from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.run_manager import RunManager


def get_gdacs_from_mean_threshold_calibration(thresholds, mean_threshold_calibration):
    interpolation = interp1d(mean_threshold_calibration['mean_threshold'], mean_threshold_calibration['gdac'], kind='slinear', bounds_error=True)
    return np.unique(interpolation(thresholds).astype(np.uint32))


def get_gdacs_from_calibration_file(calibration_file):
    # the file with the GDAC <-> PlsrDAC calibration
    with tb.openFile(calibration_file, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
    #     threshold_range = np.arange(30, 600, 16)  # threshold range in PlsrDAC to scan
    #     return get_gdacs_from_mean_threshold_calibration(threshold_range, in_file_calibration_h5.root.MeanThresholdCalibration[:])
        return in_file_calibration_h5.root.MeanThresholdCalibration[:]['gdac']


class ExtTriggerGdacScan(ExtTriggerScan):
    '''External trigger scan with FE-I4 and adjustable GDAC

    For use with external scintillator (user RX0), TLU (use RJ45), USBpix self-trigger (loop back TX2 into RX0.)
    '''
    _scan_id = "ext_trigger_gdac_scan"
    _default_scan_configuration = ExtTriggerScan._default_scan_configuration
    _default_scan_configuration.update({
        "scan_parameters": {'GDAC': None},
    })

    def configure(self):
        super(ExtTriggerGdacScan, self).configure()
        # GDAC
        if self.scan_parameters.GDAC:
            self.register_utils.set_gdac(self.scan_parameters.GDAC)


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(ExtTriggerGdacScan)
