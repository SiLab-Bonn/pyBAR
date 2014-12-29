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
    _default_run_conf = ExtTriggerScan._default_run_conf
    _default_run_conf.update({
        "scan_parameters": [('GDAC', )],
    })

    def configure(self):
        super(ExtTriggerGdacScan, self).configure()
        # GDAC
        if not self.scan_parameters.GDAC:
            altc = self.register.get_global_register_value("Vthin_AltCoarse")
            altf = self.register.get_global_register_value("Vthin_AltFine")
            curr_gdac = self.register_utils.get_gdac(self, altc, altf)
            self.gdacs = np.logspace(curr_gdac, 25000, num=50)
        else:
            self.gdacs = self.scan_parameters.GDAC

        logging.info("Scanning %s from %d to %d in %d steps" % ('GDAC', self.gdacs[0], self.gdacs[-1], len(self.gdacs)))

    def scan(self):
        for gdac in self.gdacs:
            self.register_utils.set_gdac(gdac)
            self.set_scan_parameters(GDAC=gdac)
            ExtTriggerScan.scan(self)

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), new_file=True, flush=False, )

    def get_gdacs_from_mean_threshold_calibration(self, calibration_file, thresholds):
        with tb.openFile(calibration_file, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
            interpolation = interp1d(in_file_calibration_h5.root.MeanThresholdCalibration[:]['mean_threshold'], in_file_calibration_h5.root.MeanThresholdCalibration[:]['gdac'], kind='slinear', bounds_error=True)
            return np.unique(interpolation(thresholds).astype(np.uint32))

    def get_gdacs_from_calibration_file(self, calibration_file):
        with tb.openFile(calibration_file, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
            return in_file_calibration_h5.root.MeanThresholdCalibration[:]['gdac']


if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(ExtTriggerGdacScan)
