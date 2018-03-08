import logging

import numpy as np

from pybar.scans.scan_digital import DigitalScan
from pybar.fei4.register_utils import invert_pixel_mask
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.run_manager import RunManager
from pybar.analysis.plotting.plotting import plot_occupancy


class StuckPixelScan(DigitalScan):
    '''Stuck pixel scan to detect and disable stuck pixels (Hitbus/HitOR always high).
    '''
    _default_run_conf = DigitalScan._default_run_conf.copy()
    _default_run_conf = {
        "broadcast_commands": True,
        "threaded_scan": True,
        "mask_steps": 3,  # mask steps
        "n_injections": 100,  # number of injections
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "disable_for_mask": ['Enable'],  # list of masks for which noisy pixels will be disabled
        "enable_for_mask": ['Imon'],  # list of masks for which noisy pixels will be enabled
        "overwrite_mask": False  # if True, overwrite existing masks
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name=pixel_reg))
        self.register_utils.send_commands(commands)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_source_scan_hist = True
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.plot_histograms()
            analyze_raw_data.interpreter.print_summary()

            occ_hist = analyze_raw_data.out_file_h5.root.HistOcc[:, :, 0].T
            occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
            # noisy pixels are set to 1
            occ_mask[occ_hist < self.n_injections] = 1
            # make inverse
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

            plot_occupancy(occ_mask.T, title='Stuck Pixels', z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.disable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.enable_for_mask:
                mask_name = self.register.pixel_registers[mask]['name']
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(StuckPixelScan)
