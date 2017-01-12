import logging
import numpy as np
import tables as tb
from scipy.interpolate import interp1d

from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.run_manager import RunManager


class ExtTriggerGdacScan(ExtTriggerScan):

    '''External trigger scan with FE-I4 and adjustable GDAC range

    For use with external scintillator (user RX0), TLU (use RJ45), USBpix self-trigger (loop back TX2 into RX0.)
    '''
    _default_run_conf = ExtTriggerScan._default_run_conf.copy()
    _default_run_conf.update({
        "scan_parameters": [('GDAC', None)],  # list of values, string with calibration file name, None: use 50 GDAC values
        "interpolate_calibration": True,  # interpolate GDAC values to have equally spaced thresholds, otherwise take GDACs used during calibration
        "interpolation_thresholds": range(30, 600, 5)  # threshold values in PlsrDAC
    })

    def configure(self):
        super(ExtTriggerGdacScan, self).configure()
        # Set GDACs to be used during scan
        if not self.scan_parameters.GDAC:  # distribute logarithmically if no GDAC was specified
            altc = self.register.get_global_register_value("Vthin_AltCoarse")
            altf = self.register.get_global_register_value("Vthin_AltFine")
            curr_gdac = self.register_utils.get_gdac(altc=altc, altf=altf)
            self.gdacs = np.unique(np.logspace(np.log10(curr_gdac), np.log10(6000), 60).astype(np.int)).tolist() + range(6500, 25001, 500)
        elif isinstance(self.scan_parameters.GDAC, basestring):  # deduce GDACs from calibration file
            if self.interpolate_calibration:
                self.gdacs = self.get_gdacs_from_interpolated_calibration(self.scan_parameters.GDAC, self.interpolation_thresholds)
            else:
                self.gdacs = self.get_gdacs_from_calibration_file(self.scan_parameters.GDAC)
        else:  # Use defined GDACs
            self.gdacs = self.scan_parameters.GDAC

        logging.info("Scanning %s from %d to %d in %d steps", 'GDAC', self.gdacs[0], self.gdacs[-1], len(self.gdacs))

    def scan(self):
        for gdac in self.gdacs:
            if self.abort_run.is_set():
                break
            self.register_utils.set_gdac(gdac)
            self.set_scan_parameters(GDAC=gdac)
            ExtTriggerScan.scan(self)
            self.stop_run.clear()

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), new_file=True, flush=True)

    def get_gdacs_from_interpolated_calibration(self, calibration_file, thresholds):
        logging.info('Interpolate GDAC calibration for the thresholds %s', str(thresholds))
        with tb.open_file(calibration_file, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
            interpolation = interp1d(in_file_calibration_h5.root.MeanThresholdCalibration[:]['mean_threshold'], in_file_calibration_h5.root.MeanThresholdCalibration[:]['parameter_value'], kind='slinear', bounds_error=True)
            return np.unique(interpolation(thresholds).astype(np.uint32))

    def get_gdacs_from_calibration_file(self, calibration_file):
        logging.info('Take GDAC values from calibration file')
        with tb.open_file(calibration_file, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
            return in_file_calibration_h5.root.MeanThresholdCalibration[:]['parameter_value']


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(ExtTriggerGdacScan)
