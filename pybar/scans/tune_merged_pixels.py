import logging

import tables as tb
import numpy as np

from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.scans.scan_analog import AnalogScan
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy


class MergedPixelsTuning(AnalogScan):
    '''Merged Pixels Tuning

    Masking merged pixels. Injecting in every n-th pixel, and reading out everywhere else.
    '''
    _default_run_conf = AnalogScan._default_run_conf.copy()
    _default_run_conf.update({
        "mask_steps": 6,  # number of injections per PlsrDAC step
        "n_injections": 100,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', 1023)],  # the PlsrDAC setting
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": ["Enable"],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "same_mask_for_all_dc": False,  # if True, all columns have the same mask, if False, mask will be enabled only where injected
        "disable_for_mask": ['Enable'],  # list of masks for which noisy pixels will be disabled
        "enable_for_mask": ['Imon'],  # list of masks for which noisy pixels will be disabled
        "overwrite_mask": False  # if True, overwrite existing masks
    })

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_tot_hist = True
            if self.enable_tdc:
                analyze_raw_data.create_tdc_counter_hist = True  # histogram all TDC words
                analyze_raw_data.create_tdc_hist = True  # histogram the hit TDC information
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

            with tb.open_file(analyze_raw_data._analyzed_data_file, 'r') as out_file_h5:
                occ_hist = out_file_h5.root.HistOcc[:, :, 0].T
            occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
            occ_mask[occ_hist > 1] = 1

            inv_occ_mask = invert_pixel_mask(occ_mask)
            if self.overwrite_mask:
                for mask in self.disable_for_mask:
                    self.register.set_pixel_register_value(mask, inv_occ_mask)
            else:
                for mask in self.disable_for_mask:
                    enable_mask = np.logical_and(inv_occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, enable_mask)

            if self.overwrite_mask:
                for mask in self.enable_for_mask:
                    self.register.set_pixel_register_value(mask, occ_mask)
            else:
                for mask in self.enable_for_mask:
                    disable_mask = np.logical_or(occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, disable_mask)
            plot_occupancy(occ_mask.T, title='Merged Pixels', z_max=1, filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(occ_mask.T, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.disable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.enable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(MergedPixelsTuning)
