""" Script to tune the TDAC to the threshold value given in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0. Due to the nonlinearity it can happen that the binary search does not reach the best TDAC. Therefore the best TDAC is always set and taken at the end.
"""
import numpy as np
import logging

from daq.readout import open_raw_data_file, get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel, logical_and
from analysis.plotting.plotting import plotThreeWay
from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "target_threshold": 50,
    "tdac_tune_bits": range(4, -1, -1),
    "n_injections": 100,
    "plot_intermediate_steps": False,
    "plots_filename": None
}


class TdacTune(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(TdacTune, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="tdac_tune")

    def set_target_threshold(self, PlsrDAC=50):
        self.target_threshold = PlsrDAC

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("wrregister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_tdac_bit(self, bit_position, bit_value=1):
        if(bit_value == 1):
            self.register.set_pixel_register_value("TDAC", self.register.get_pixel_register_value("TDAC") | (1 << bit_position))
        else:
            self.register.set_pixel_register_value("TDAC", self.register.get_pixel_register_value("TDAC") & ~(1 << bit_position))

    def set_start_tdac(self):
        start_tdac_setting = self.register.get_pixel_register_value("TDAC")
        for bit_position in self.TdacTuneBits:  # reset all TDAC bits, FIXME: speed up
            start_tdac_setting = start_tdac_setting & ~(1 << bit_position)
        self.register.set_pixel_register_value("TDAC", start_tdac_setting)

    def write_tdac_config(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=["Tdac"]))
        self.register_utils.send_commands(commands)

    def set_tdac_tune_bits(self, TdacTuneBits=range(4, -1, -1)):
        self.TdacTuneBits = TdacTuneBits

    def set_n_injections(self, Ninjections=100):
        self.Ninjections = Ninjections

    def scan(self, target_threshold, tdac_tune_bits=range(4, -1, -1), n_injections=100, plots_filename=None, plot_intermediate_steps=False, **kwarg):
        #  set scan settings
        self.set_n_injections(n_injections)
        self.set_target_threshold(target_threshold)
        self.set_tdac_tune_bits(tdac_tune_bits)

        self.write_target_threshold()
        addedAdditionalLastBitScan = False
        lastBitResult = np.zeros(shape=self.register.get_pixel_register_value("TDAC").shape, dtype=self.register.get_pixel_register_value("TDAC").dtype)

        self.set_start_tdac()

        mask_steps = 3
        enable_mask_steps = []

        scan_parameter = 'TDAC'

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:
            tdac_mask = []

            occupancy_best = np.empty(shape=(80, 336))  # array to store the best occupancy (closest to Ninjections/2) of the pixel
            occupancy_best.fill(self.Ninjections)
            tdac_mask_best = self.register.get_pixel_register_value("TDAC")

            for index, Tdac_bit in enumerate(self.TdacTuneBits):
                if(not addedAdditionalLastBitScan):
                    self.set_tdac_bit(Tdac_bit)
                    logging.info('TDAC setting: bit %d = 1' % Tdac_bit)
                else:
                    self.set_tdac_bit(Tdac_bit, bit_value=0)
                    logging.info('TDAC setting: bit %d = 0' % Tdac_bit)

                self.write_tdac_config()
                scan_parameter_value = index

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
                self.scan_loop(cal_lvl1_command, repeat_command=self.Ninjections, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None)

                self.readout.stop()

                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value})

                occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4)), converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
                select_better_pixel_mask = abs(occupancy_array - self.Ninjections / 2) <= abs(occupancy_best - self.Ninjections / 2)
                pixel_with_too_high_occupancy_mask = occupancy_array > self.Ninjections / 2
                occupancy_best[select_better_pixel_mask] = occupancy_array[select_better_pixel_mask]

                if plot_intermediate_steps:
                    plotThreeWay(occupancy_array.transpose(), title="Occupancy (TDAC tuning bit " + str(Tdac_bit) + ")", x_axis_title='Occupancy', filename=plots_filename, maximum=self.Ninjections)

                tdac_mask = self.register.get_pixel_register_value("TDAC")
                tdac_mask_best[select_better_pixel_mask] = tdac_mask[select_better_pixel_mask]

                if(Tdac_bit > 0):
                    tdac_mask[pixel_with_too_high_occupancy_mask] = tdac_mask[pixel_with_too_high_occupancy_mask] & ~(1 << Tdac_bit)
                    self.register.set_pixel_register_value("TDAC", tdac_mask)

                if(Tdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  # scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan = True
                        lastBitResult = occupancy_array.copy()
                        self.TdacTuneBits.append(0)  # bit 0 has to be scanned twice
                    else:
                        tdac_mask[abs(occupancy_array - self.Ninjections / 2) > abs(lastBitResult - self.Ninjections / 2)] = tdac_mask[abs(occupancy_array - self.Ninjections / 2) > abs(lastBitResult - self.Ninjections / 2)] | (1 << Tdac_bit)
                        occupancy_array[abs(occupancy_array - self.Ninjections / 2) > abs(lastBitResult - self.Ninjections / 2)] = lastBitResult[abs(occupancy_array - self.Ninjections / 2) > abs(lastBitResult - self.Ninjections / 2)]
                        occupancy_best[abs(occupancy_array - self.Ninjections / 2) <= abs(occupancy_best - self.Ninjections / 2)] = occupancy_array[abs(occupancy_array - self.Ninjections / 2) <= abs(occupancy_best - self.Ninjections / 2)]
                        tdac_mask_best[abs(occupancy_array - self.Ninjections / 2) <= abs(occupancy_best - self.Ninjections / 2)] = tdac_mask[abs(occupancy_array - self.Ninjections / 2) <= abs(occupancy_best - self.Ninjections / 2)]

            self.register.set_pixel_register_value("TDAC", tdac_mask_best)
            self.result = occupancy_best

            plotThreeWay(hist=self.result.transpose(), title="Occupancy after TDAC tuning", x_axis_title="Occupancy", filename=plots_filename, maximum=self.Ninjections)
            plotThreeWay(hist=self.register.get_pixel_register_value("TDAC").transpose(), title="TDAC distribution after tuning", x_axis_title="TDAC", filename=plots_filename, maximum=32)
            logging.info('Tuned TDAC!')

            # additional analog scan to get final results, not needed, just for checking
#             logging.info('Do analog scan with actual TDAC settings after TDAC tuning')
#             self.write_tdac_config()
#             self.readout.start()
#             cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
#             self.scan_loop(cal_lvl1_command, repeat_command=self.Ninjections, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None)
#             self.readout.stop()
#             occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4)), converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
#             plotThreeWay(hist=occupancy_array.transpose(), title="Occupancy check", x_axis_title="Occupancy", filename=plots_filename, maximum = self.Ninjections)
#             plotThreeWay(hist=self.register.get_pixel_register_value("TDAC").transpose(), title="TDAC check distribution after tuning", x_axis_title="TDAC", filename=plots_filename, maximum = 32)

if __name__ == "__main__":
    import configuration
    scan = TdacTune(**configuration.device_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.register.save_configuration(configuration.device_configuration['configuration_file'])
