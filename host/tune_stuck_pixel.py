import logging
import numpy as np

from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from daq.readout import save_raw_data_from_data_dict_iterable, get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel
from fei4.register_utils import invert_pixel_mask
from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class StuckPixelScan(ScanBase):
    scan_id = "stuck_pixel_scan"

    scan_configuration = {
        "mask_steps": 3,
        "repeat_command": 100,
        "disable_for_mask": ['Enable'],
        "enable_for_mask": ['Imon'],
        "overwrite_mask": False
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        pixel_reg = "C_High"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        pixel_reg = "C_Low"
        self.register.set_pixel_register_value(pixel_reg, 0)
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name=pixel_reg))
        self.register_utils.send_commands(commands)

    def scan(self):
        '''Disable stuck pixels (hitbus always high). Based on digital scan.

        Parameters
        ----------
        mask : int
            Number of mask steps.
        repeat : int
            Number of injections.
        disable_for_mask : list, tuple
            List of masks for which noisy pixels will be disabled.
        enable_for_mask : list, tuple
            List of masks for which noisy pixels will be enabled.
        overwrite_mask : bool
            Overwrite masks (disable_for_mask, enable_for_mask) if set to true. If set to false, make a combination of existing mask and new mask.
        '''
        self.readout.start()

        cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
        self.scan_loop(cal_lvl1_command, repeat_command=self.repeat_command, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=True, enable_shift_masks=["Enable", "EnableDigInj"], restore_shift_masks=False, mask=None)

        self.readout.stop()
        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_id)
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

    def analyze(self):
        occ_hist = make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)).T

        self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
        # noisy pixels are set to 1
        self.occ_mask[occ_hist < self.repeat_command] = 1
        # make inverse
        self.inv_occ_mask = invert_pixel_mask(self.occ_mask)
        self.disable_for_mask = self.disable_for_mask
        if self.overwrite_mask:
            for mask in self.disable_for_mask:
                self.register.set_pixel_register_value(mask, self.inv_occ_mask)
        else:
            for mask in self.disable_for_mask:
                enable_mask = np.logical_and(self.inv_occ_mask, self.register.get_pixel_register_value(mask))
                self.register.set_pixel_register_value(mask, enable_mask)

        self.enable_for_mask = self.enable_for_mask
        if self.overwrite_mask:
            for mask in self.enable_for_mask:
                self.register.set_pixel_register_value(mask, self.occ_mask)
        else:
            for mask in self.enable_for_mask:
                disable_mask = np.logical_or(self.occ_mask, self.register.get_pixel_register_value(mask))
                self.register.set_pixel_register_value(mask, disable_mask)

#             plot_occupancy(self.col_arr, self.row_arr, max_occ=None, filename=self.scan_data_filename + "_occupancy.pdf")

        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=self.scan_data_filename, analyzed_data_file=output_file, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_source_scan_hist = True
#             analyze_raw_data.create_hit_table = True
#             analyze_raw_data.interpreter.debug_events(0, 0, True)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
            plot_occupancy(self.occ_mask.T, title='Stuck Pixels', z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.disable_for_mask:
                mask_name = self.register.get_pixel_register_attributes("full_name", do_sort=True, name=[mask])[0]
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)
            for mask in self.enable_for_mask:
                mask_name = self.register.get_pixel_register_attributes("full_name", do_sort=True, name=[mask])[0]
                plot_occupancy(self.register.get_pixel_register_value(mask).T, title='%s Mask' % mask_name, z_max=1, filename=analyze_raw_data.output_pdf)


if __name__ == "__main__":
    import configuration
    scan = StuckPixelScan(**configuration.default_configuration)
    scan.start(run_configure=True, run_analyze=True, use_thread=True, restore_configuration=True, **local_configuration)
    scan.stop()
