import logging

import numpy as np

from pybar.run_manager import RunManager
from pybar.scans.scan_threshold import ThresholdScan
from pybar.analysis.analyze_raw_data import AnalyzeRawData


class PulserDacCorrectionCalibration(ThresholdScan):
    '''Measure and write PlsrDAC correction to configuration file.

    Note:
    It is necessary to run threshold baseline tuning before running this calibration.
    '''
    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.n_injections = 100
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

            thr = analyze_raw_data.out_file_h5.root.HistThresholdFitted[:]
            thr_masked = np.ma.masked_where(np.isclose(thr, 0), thr)
            corr = [thr_masked[:, 0].mean()]
            corr.extend([thr_masked[:, i * 2 + 1:i * 2 + 3].mean() for i in range(0, 38)])
            corr.extend([thr_masked[:, 77:79].mean()])
            corr = np.array(corr)
            corr -= corr.min()
            corr = np.around(corr, decimals=2)

        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks) and "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.calibration_parameters['Pulser_Corr_C_Inj_High'] = list(corr)
        elif "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.calibration_parameters['Pulser_Corr_C_Inj_Med'] = list(corr)
        elif "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.calibration_parameters['Pulser_Corr_C_Inj_Low'] = list(corr)
        else:
            raise ValueError('Unknown C_Inj')


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(PulserDacCorrectionCalibration)
