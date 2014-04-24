""" Script to tune the GDAC to the threshold value given in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Only the pixels used in the analog injection are taken into account.
"""
import numpy as np
import logging

from daq.readout import open_raw_data_file, get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel, logical_and
from analysis.plotting.plotting import plotThreeWay
from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "target_threshold": 5,  # target threshold in PlsrDAC to tune to
    "gdac_tune_bits": range(7, -1, -1),  # GDAC bits to change during tuning
    "n_injections": 50,  # number of injections per GDAC bit setting
    "abort_precision_occ": 2,  # minimum difference to the target_threshold to abort the tuning
    "mask_steps": 3,  # mask
    "enable_mask_steps": [0],  # mask steps to do per GDAC setting
    "plot_intermediate_steps": False,  # plot intermediate steps (takes time)
    "plots_filename": None  # file name to store the plot to, if None show on screen
}


class GdacTune(ScanBase):
    scan_identifier = "gdac_tune"

    def set_abort_precision(self, delta_occupancy=2):
        self.abort_precision = delta_occupancy

    def set_target_threshold(self, PlsrDAC=50):
        self.target_threshold = PlsrDAC

    def write_target_threshold(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register.set_global_register_value("PlsrDAC", self.target_threshold)
        commands.extend(self.register.get_commands("wrregister", name="PlsrDAC"))
        self.register_utils.send_commands(commands)

    def set_gdac_bit(self, bit_position, bit_value=1):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        if(bit_position < 8):
            if(bit_value == 1):
                self.register.set_global_register_value("Vthin_AltFine", self.register.get_global_register_value("Vthin_AltFine") | (1 << bit_position))
            else:
                self.register.set_global_register_value("Vthin_AltFine", self.register.get_global_register_value("Vthin_AltFine") & ~(1 << bit_position))
        else:
            if(bit_value == 1):
                self.register.set_global_register_value("Vthin_AltCoarse", self.register.get_global_register_value("Vthin_AltCoarse") | (1 << (bit_position - 8)))
            else:
                self.register.set_global_register_value("Vthin_AltCoarse", self.register.get_global_register_value("Vthin_AltCoarse") & ~(1 << bit_position))
        commands.extend(self.register.get_commands("wrregister", name=["Vthin_AltFine", "Vthin_AltCoarse"]))
        self.register_utils.send_commands(commands)

    def set_gdac_tune_bits(self, gdac_tune_bits=range(7, -1, -1)):
        self.gdac_tune_bits = gdac_tune_bits

    def set_n_injections(self, n_injections=50):
        self.n_injections = n_injections

    def scan(self, target_threshold, gdac_tune_bits=range(7, -1, -1), n_injections=50, abort_precision_occ=2, enable_mask_steps=[0], mask_steps=3, plots_filename=None, plot_intermediate_steps=False, **kwargs):
        #  set scan settings
        self.set_target_threshold(target_threshold)
        self.set_gdac_tune_bits(gdac_tune_bits)
        self.set_n_injections(n_injections)
        self.set_abort_precision(abort_precision_occ)

        self.write_target_threshold()
        for gdac_bit in self.gdac_tune_bits:  # reset all GDAC bits
            self.set_gdac_bit(gdac_bit, bit_value=0)

        added_additional_last_bit_scan = False
        last_bit_result = self.n_injections
        decreased_threshold = False  # needed to determine if the FE is noisy
        all_bits_zero = True

        def bits_set(int_type):
            int_type = int(int_type)
            count = 0
            position = 0
            bits_set = []
            while(int_type):
                if(int_type & 1):
                    bits_set.append(position)
                position += 1
                int_type = int_type >> 1
                count += 1
            return bits_set

        # calculate selected pixels from the mask and the disabled columns
        select_mask_array = np.zeros(shape=(80, 336), dtype=np.uint8)
        if enable_mask_steps is None or not enable_mask_steps:
            enable_mask_steps = range(mask_steps)
        for mask_step in enable_mask_steps:
            select_mask_array += self.register_utils.make_pixel_mask(steps=mask_steps, shift=mask_step)
        for column in bits_set(self.register.get_global_register_value("DisableColumnCnfg")):
            logging.info('Deselect double column %d' % column)
            select_mask_array[column, :] = 0

        scan_parameter = 'GDAC'

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:
            occupancy_best = 0
            vthin_af_best = self.register.get_global_register_value("Vthin_AltFine")
            vthin_ac_best = self.register.get_global_register_value("Vthin_AltCoarse")
            for gdac_bit in self.gdac_tune_bits:

                if(not added_additional_last_bit_scan):
                    self.set_gdac_bit(gdac_bit)
                    scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                    logging.info('GDAC setting: %d, bit %d = 1' % (scan_parameter_value, gdac_bit))
                else:
                    self.set_gdac_bit(gdac_bit, bit_value=0)
                    scan_parameter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")
                    logging.info('GDAC setting: %d, bit %d = 0' % (scan_parameter_value, gdac_bit))

                self.readout.start()

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
                self.scan_loop(cal_lvl1_command, repeat_command=self.n_injections, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None)

                self.readout.stop()

                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value})

                occupancy_array, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4)), converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
                occ_array_sel_pixel = np.ma.array(occupancy_array, mask=np.logical_not(np.ma.make_mask(select_mask_array)))  # take only selected pixel into account by creating a mask
                median_occupancy = np.ma.median(occ_array_sel_pixel)
                if abs(median_occupancy - self.n_injections / 2) < abs(occupancy_best - self.n_injections / 2):
                    occupancy_best = median_occupancy
                    vthin_af_best = self.register.get_global_register_value("Vthin_AltFine")
                    vthin_ac_best = self.register.get_global_register_value("Vthin_AltCoarse")

                if plot_intermediate_steps:
                    plotThreeWay(occ_array_sel_pixel.transpose(), title="Occupancy (GDAC " + str(scan_parameter_value) + " with tuning bit " + str(gdac_bit) + ")", x_axis_title='Occupancy', filename=plots_filename, maximum=self.n_injections)

                if(abs(median_occupancy - self.n_injections / 2) < self.abort_precision and gdac_bit > 0):  # abort if good value already found to save time
                    logging.info('Median = %f, good result already achieved (median - Ninj/2 < %f), skipping not varied bits' % (median_occupancy, self.abort_precision))
                    break

                if median_occupancy == 0 and decreased_threshold and all_bits_zero:
                    logging.warning('Noisy FE detected, tuning will most likely fail!')

                if(gdac_bit > 0):
                    if (median_occupancy < self.n_injections / 2):  # set GDAC bit to 0 if the occupancy is too lowm, thus decrease threshold
                        logging.info('Median = %f < %f, set bit %d = 0' % (median_occupancy, self.n_injections / 2, gdac_bit))
                        self.set_gdac_bit(gdac_bit, bit_value=0)
                        decreased_threshold = True
                    else:  # set GDAC bit to 1 if the occupancy is too high, thus increase threshold
                        logging.info('Median = %f > %f, leave bit %d = 1' % (median_occupancy, self.n_injections / 2, gdac_bit))
                        decreased_threshold = False
                        all_bits_zero = False

                if(gdac_bit == 0):
                    if not(added_additional_last_bit_scan):  # scan bit = 0 with the correct value again
                        added_additional_last_bit_scan = True
                        last_bit_result = occ_array_sel_pixel.copy()
                        self.gdac_tune_bits.append(0)  # bit 0 has to be scanned twice
                    else:
                        lastBitResultMedian = np.median(last_bit_result[select_mask_array > 0])
                        logging.info('Scanned bit 0 = 0 with %f instead of %f' % (median_occupancy, lastBitResultMedian))
                        if(abs(median_occupancy - self.n_injections / 2) > abs(lastBitResultMedian - self.n_injections / 2)):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                            self.set_gdac_bit(gdac_bit, bit_value=1)
                            logging.info('Set bit 0 = 1')
                            occ_array_sel_pixel = last_bit_result
                            median_occupancy = np.ma.median(occ_array_sel_pixel)
                        else:
                            logging.info('Set bit 0 = 0')
                        if abs(occupancy_best - self.n_injections / 2) < abs(median_occupancy - self.n_injections / 2):
                            logging.info("Binary search converged to non optimal value, take best measured value instead")
                            median_occupancy = occupancy_best
                            self.register.set_global_register_value("Vthin_AltFine", vthin_af_best)
                            self.register.set_global_register_value("Vthin_AltCoarse", vthin_ac_best)

            if (self.register.get_global_register_value("Vthin_AltFine") == 0 and self.register.get_global_register_value("Vthin_AltCoarse") == 0) or self.register.get_global_register_value("Vthin_AltFine") == 254:
                logging.warning('GDAC reached minimum/maximum value')

            if(abs(median_occupancy - self.n_injections / 2) > 2 * self.abort_precision):
                logging.warning('Tuning of Vthin_AltCoarse/Vthin_AltFine failed. Difference = %f. Vthin_AltCoarse/Vthin_AltFine = %d/%d' % (abs(median_occupancy - self.n_injections / 2), self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
            else:
                logging.info('Tuned GDAC to Vthin_AltCoarse/Vthin_AltFine = %d/%d' % (self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))

            self.result = occ_array_sel_pixel
            plotThreeWay(occ_array_sel_pixel.transpose(), title="Occupancy after GDAC tuning (GDAC " + str(scan_parameter_value) + ")", x_axis_title='Occupancy', filename=plots_filename, maximum=self.n_injections)

if __name__ == "__main__":
    import configuration
    scan = GdacTune(**configuration.scc30_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
#     scan.register.save_configuration(configuration.device_configuration['configuration_file'])
#     scan.register.save_configuration('SCC_99_tuning_new')
