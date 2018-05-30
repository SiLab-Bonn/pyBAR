import logging

import numpy as np

from pybar.daq.fifo_readout import FifoError
from pybar.scans.scan_fei4_self_trigger import Fei4SelfTriggerScan
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy, plot_fancy_occupancy


class HotPixelTuning(Fei4SelfTriggerScan):
    '''FE-I4 hot pixels tuning

    Masking hot pixels based on FEI4 self-trigger scan.
    '''
    _default_run_conf = {
        "trig_count": 4,  # FE-I4 trigger count, number of consecutive BCs, 0 means 16, from 0 to 15
        "trigger_latency": 239,  # FE-I4 trigger latency, in BCs, external scintillator / TLU / HitOR: 232, USBpix self-trigger: 220, from 0 to 255
        "col_span": [1, 80],  # defining active column interval, 2-tuple, from 1 to 80
        "row_span": [1, 336],  # defining active row interval, 2-tuple, from 1 to 336
        "overwrite_enable_mask": False,  # if True, use col_span and row_span to define an active region regardless of the Enable pixel register. If False, use col_span and row_span to define active region by also taking Enable pixel register into account.
        "use_enable_mask_for_imon": True,  # if True, apply inverted Enable pixel mask to Imon pixel mask
        "no_data_timeout": 0,  # no data timeout after which the scan will be aborted, in seconds
        "scan_timeout": 60,  # timeout for scan after which the scan will be stopped, in seconds
        "disable_for_mask": ['Enable'],  # list of masks for which noisy pixels will be disabled
        "enable_for_mask": ['Imon'],  # list of masks for which noisy pixels will be disabled
        "overwrite_mask": False,  # if True, overwrite existing masks
        "mask_high_count": 10,  # masking the largest mask_high_count number of pixels with occupancy greater than low_value
        "low_value": 1  # only pixels with occupancy greater than low_value can be masked
    }

    def scan(self):
        self.suppress_warning = False
        super(HotPixelTuning, self).scan()

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_cluster_size_hist = False
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.create_cluster_tot_hist = False
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()

            occ_hist = analyze_raw_data.out_file_h5.root.HistOcc[:, :, 0].T
            self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
            # n largest elements
            n_largest_elements = np.sort(occ_hist[occ_hist > self.low_value])[-self.mask_high_count:]
            # noisy pixels are set to 1
            if n_largest_elements.shape[0] > 0:
                self.occ_mask[occ_hist >= n_largest_elements[0]] = 1
            # make inverse
            self.inv_occ_mask = invert_pixel_mask(self.occ_mask)
            if self.overwrite_mask:
                for mask in self.disable_for_mask:
                    self.register.set_pixel_register_value(mask, self.inv_occ_mask)
            else:
                for mask in self.disable_for_mask:
                    enable_mask = np.logical_and(self.inv_occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, enable_mask)

            if self.overwrite_mask:
                for mask in self.enable_for_mask:
                    self.register.set_pixel_register_value(mask, self.occ_mask)
            else:
                for mask in self.enable_for_mask:
                    disable_mask = np.logical_or(self.occ_mask, self.register.get_pixel_register_value(mask))
                    self.register.set_pixel_register_value(mask, disable_mask)
            plot_occupancy(self.occ_mask.T, title='Noisy Pixels', z_max=1, filename=analyze_raw_data.output_pdf)
            plot_fancy_occupancy(self.occ_mask.T, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.disable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.enable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)

    def handle_err(self, exc):
        if isinstance(exc[1], FifoError):
            if not self.suppress_warning:
                logging.warning(str(exc[1]))
                self.suppress_warning = True
            return
        super(HotPixelTuning, self).handle_err(exc=exc)


if __name__ == "__main__":
    RunManager('configuration.yaml').run_run(HotPixelTuning)
