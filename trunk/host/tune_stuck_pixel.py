import time
import logging
import numpy as np

from analysis.plotting.plotting import plot_occupancy, make_occupancy_hist
from daq.readout import get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel

from scan.scan import ScanBase
from daq.readout import save_raw_data_from_data_dict_iterable

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "mask_steps": 3,
    "repeat_command": 100,
    "disable_for_mask": ['Enable'],
    "enable_for_mask": ['Imon'],
    "overwrite_mask": False
}


class StuckPixelScan(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(StuckPixelScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="stuck_pixel_scan")

    def scan(self, mask_steps=3, repeat_command=100, disable_for_mask=['Enable'], enable_for_mask=['Imon'], overwrite_mask=False):
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
        self.register.create_restore_point()
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", 0)  # has to be 0, otherwise you also have analog injections
        commands.extend(self.register.get_commands("wrregister", name=["PlsrDAC"]))
        self.register_utils.send_commands(commands)

        self.readout.start()

        cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
        self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, hardware_repeat=True, use_delay=True, mask_steps=mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=True, enable_c_high=False, enable_c_low=False, enable_shift_masks=["Enable"], restore_shift_masks=False, mask=None)

        self.readout.stop()

        self.register.restore()

        # plotting data
#         plot_occupancy(hist=make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)), z_max='median', filename=self.scan_data_filename + "_occupancy.pdf")

        # saving data
        save_raw_data_from_data_dict_iterable(self.readout.data, filename=self.scan_data_filename, title=self.scan_identifier)

        occ_hist = make_occupancy_hist(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=is_data_record, converter_func=get_col_row_array_from_data_record_array)).T

        self.occ_mask = np.zeros(shape=occ_hist.shape, dtype=np.dtype('>u1'))
        # noisy pixels are set to 1
        self.occ_mask[occ_hist < repeat_command] = 1
        # make inverse
        self.inv_occ_mask = self.register_utils.invert_pixel_mask(self.occ_mask)
        self.disable_for_mask = disable_for_mask
        if overwrite_mask:
            self.register.set_pixel_register_value(disable_for_mask, self.inv_occ_mask)
        else:
            for mask in disable_for_mask:
                enable_mask = np.logical_and(self.inv_occ_mask, self.register.get_pixel_register_value(mask))
                self.register.set_pixel_register_value(mask, enable_mask)

        self.enable_for_mask = enable_for_mask
        if overwrite_mask:
            self.register.set_pixel_register_value(enable_for_mask, self.occ_mask)
        else:
            for mask in enable_for_mask:
                disable_mask = np.logical_or(self.occ_mask, self.register.get_pixel_register_value(mask))
                self.register.set_pixel_register_value(mask, disable_mask)

#             plot_occupancy(self.col_arr, self.row_arr, max_occ=None, filename=self.scan_data_filename + "_occupancy.pdf")

    def analyze(self):
        from analysis.analyze_raw_data import AnalyzeRawData
        output_file = self.scan_data_filename + "_interpreted.h5"
        with AnalyzeRawData(raw_data_file=scan.scan_data_filename, analyzed_data_file=output_file, create_pdf=True) as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_source_scan_hist = True
#             analyze_raw_data.create_hit_table = True
#             analyze_raw_data.interpreter.debug_events(0, 0, True)  # events to be printed onto the console for debugging, usually deactivated
            analyze_raw_data.interpreter.set_warning_output(False)
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
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
    scan = StuckPixelScan(**configuration.device_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()
    scan.register.save_configuration(configuration.device_configuration["configuration_file"])
