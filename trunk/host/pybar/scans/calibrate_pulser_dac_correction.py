from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from analysis.analyze_raw_data import AnalyzeRawData

from scan_threshold import ThresholdScan

import numpy as np
import tables as tb

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


local_configuration = {
    "cfg_name": '',
    "mask_steps": 3,
    "repeat_command": 100,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_range": (0, 100),
    "scan_parameter_stepsize": 1,
    "use_enable_mask": False,
    "enable_shift_masks": ["Enable", "C_High", "C_Low"],
    "disable_shift_masks": []
}


class PulserDacCorrectionCalibration(ThresholdScan):
    scan_id = "pulser_dac_correction_calibration"

    def analyze(self):
        super(PulserDacCorrectionCalibration, self).analyze()

        with tb.open_file(self.scan_data_filename + "_interpreted.h5") as t:
            thr = t.root.HistThresholdFitted[:]
            thr_masked = np.ma.masked_where(np.isclose(thr, 0), thr)
            corr = [thr_masked[:, i * 2 + 1:i * 2 + 3].mean() for i in range(0, 38)]
            corr = np.array(corr)
            corr -= corr.min()
            corr = np.around(corr).astype(int)

        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks) and "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.calibration_config['Pulser_Corr_C_Inj_High'] = list(corr)
        elif "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.calibration_config['Pulser_Corr_C_Inj_Med'] = list(corr)
        elif "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.calibration_config['Pulser_Corr_C_Inj_Low'] = list(corr)
        else:
            raise ValueError('Unknown C_Inj')

if __name__ == "__main__":
    import configuration
    scan = PulserDacCorrectionCalibration(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=True, restore_configuration=True, **local_configuration)
    scan.stop()
    scan.save_configuration(scan.cfg_name)
