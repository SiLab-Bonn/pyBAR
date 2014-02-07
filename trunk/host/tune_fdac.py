""" Script to tune the FDAC to the ToT@charge given in ToT/PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0. Due to the nonlinearity it can happen that the binary search does not reach the best FDAC. Therefore the best FDAC is always set and taken at the end.
    Pixel below threshold get ToT = 0.
"""
import numpy as np
import logging

from daq.readout import open_raw_data_file, get_col_row_tot_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel, logical_and
from analysis.plotting.plotting import plotThreeWay
from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "target_charge": 280,
    "target_tot": 5,
    "fdac_tune_bits": range(3, -1, -1),
    "n_injections": 30,
    "plot_intermediate_steps": False,
    "plots_filename": None
}


class FdacTune(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(FdacTune, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="fdac_tune")

    def set_target_charge(self, plsr_dac=30):
        self.target_charge = plsr_dac

    def write_target_charge(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", self.target_charge)
        commands.extend(self.register.get_commands("wrregister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_target_tot(self, tot=5):
        self.TargetTot = tot

    def set_fdac_bit(self, bit_position, bit_value=1):
        if(bit_value == 1):
            self.register.set_pixel_register_value("Fdac", self.register.get_pixel_register_value("Fdac") | (1 << bit_position))
        else:
            self.register.set_pixel_register_value("Fdac", self.register.get_pixel_register_value("Fdac") & ~(1 << bit_position))

    def write_fdac_config(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=False, name=["Fdac"]))
        self.register_utils.send_commands(commands)

    def set_fdac_tune_bits(self, FdacTuneBits=range(3, -1, -1)):
        self.FdacTuneBits = FdacTuneBits

    def set_start_fdac(self):
        start_fdac_setting = self.register.get_pixel_register_value("FDAC")
        for bit_position in self.FdacTuneBits:  # reset all FDAC bits, FIXME: speed up
            start_fdac_setting = start_fdac_setting & ~(1 << bit_position)
        self.register.set_pixel_register_value("FDAC", start_fdac_setting)

    def set_n_injections(self, Ninjections=20):
        self.Ninjections = Ninjections

    def scan(self, target_tot, target_charge, fdac_tune_bits=range(3, -1, -1), n_injections=30, plots_filename=None, plot_intermediate_steps=False, **kwarg):
        #  set scan settings
        self.set_target_charge(target_charge)
        self.set_target_tot(target_tot)
        self.set_n_injections(n_injections)
        self.set_fdac_tune_bits(fdac_tune_bits)

        self.write_target_charge()
        addedAdditionalLastBitScan = False
        lastBitResult = np.zeros(shape=self.register.get_pixel_register_value("Fdac").shape, dtype=self.register.get_pixel_register_value("Fdac").dtype)

        self.set_start_fdac()

        mask_steps = 3
        enable_mask_steps = []

        scan_parameter = 'FDAC'

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:
            fdac_mask = []

            tot_mean_best = np.empty(shape=(80, 336))  # array to store the best occupancy (closest to Ninjections/2) of the pixel
            tot_mean_best.fill(0)
            fdac_mask_best = self.register.get_pixel_register_value("FDAC")

            for index, Fdac_bit in enumerate(self.FdacTuneBits):
                if(not addedAdditionalLastBitScan):
                    self.set_fdac_bit(Fdac_bit)
                    logging.info('FDAC setting: bit %d = 1' % Fdac_bit)
                else:
                    self.set_fdac_bit(Fdac_bit, bit_value=0)
                    logging.info('FDAC setting: bit %d = 0' % Fdac_bit)

                self.write_fdac_config()
                scan_parameter_value = index

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
                self.scan_loop(cal_lvl1_command, repeat_command=self.Ninjections, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None)

                self.readout.stop()

                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value})

                col_row_tot = np.column_stack(convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4)), converter_func=get_col_row_tot_array_from_data_record_array))
                tot_array = np.histogramdd(col_row_tot, bins=(80, 336, 16), range=[[1, 80], [1, 336], [0, 15]])[0]
                tot_mean_array = np.average(tot_array, axis=2, weights=range(0, 16)) * sum(range(0, 16)) / self.Ninjections
                select_better_pixel_mask = abs(tot_mean_array - self.TargetTot) <= abs(tot_mean_best - self.TargetTot)
                pixel_with_too_small_mean_tot_mask = tot_mean_array < self.TargetTot
                tot_mean_best[select_better_pixel_mask] = tot_mean_array[select_better_pixel_mask]

                if plot_intermediate_steps:
                    plotThreeWay(hist=tot_mean_array.transpose().transpose(), title="Mean ToT (FDAC tuning bit " + str(Fdac_bit) + ")", x_axis_title='mean ToT', filename=plots_filename, minimum=0, maximum=15)

                fdac_mask = self.register.get_pixel_register_value("FDAC")
                fdac_mask_best[select_better_pixel_mask] = fdac_mask[select_better_pixel_mask]
                if(Fdac_bit > 0):
                    fdac_mask[pixel_with_too_small_mean_tot_mask] = fdac_mask[pixel_with_too_small_mean_tot_mask] & ~(1 << Fdac_bit)
                    self.register.set_pixel_register_value("FDAC", fdac_mask)

                if(Fdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  # scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan = True
                        lastBitResult = tot_mean_array.copy()
                        self.FdacTuneBits.append(0)  # bit 0 has to be scanned twice
                    else:
                        fdac_mask[abs(tot_mean_array - self.TargetTot) > abs(lastBitResult - self.TargetTot)] = fdac_mask[abs(tot_mean_array - self.TargetTot) > abs(lastBitResult - self.TargetTot)] | (1 << Fdac_bit)
                        tot_mean_array[abs(tot_mean_array - self.TargetTot) > abs(lastBitResult - self.TargetTot)] = lastBitResult[abs(tot_mean_array - self.TargetTot) > abs(lastBitResult - self.TargetTot)]
                        tot_mean_best[abs(tot_mean_array - self.TargetTot) <= abs(tot_mean_best - self.Ninjections / 2)] = tot_mean_array[abs(tot_mean_array - self.TargetTot) <= abs(tot_mean_best - self.Ninjections / 2)]
                        fdac_mask_best[abs(tot_mean_array - self.TargetTot) <= abs(tot_mean_best - self.Ninjections / 2)] = fdac_mask[abs(tot_mean_array - self.TargetTot) <= abs(tot_mean_best - self.Ninjections / 2)]

            self.register.set_pixel_register_value("FDAC", fdac_mask_best)
            self.result = tot_mean_best

            plotThreeWay(hist=self.result.transpose(), title="Mean ToT after FDAC tuning", x_axis_title="ToT mean", filename=plots_filename, minimum=0, maximum=15)
            plotThreeWay(hist=self.register.get_pixel_register_value("FDAC").transpose(), title="FDAC distribution after tuning", x_axis_title="FDAC", filename=plots_filename, minimum=0, maximum=15)

            logging.info('Tuned FDAC!')

if __name__ == "__main__":
    import configuration
    scan = FdacTune(**configuration.device_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.register.save_configuration(configuration.device_configuration['configuration_file'])
