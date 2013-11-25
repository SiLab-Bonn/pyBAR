""" Script to tune the GDAC to the threshold value given in PlsrDAC. Binary search algorithm. Bit 0 is always scanned twice with value 1 and 0.
    Only the pixels used in the analog injection are taken into account.
"""
import numpy as np
import logging

from daq.readout import open_raw_data_file, get_col_row_array_from_data_record_array, convert_data_array, data_array_from_data_dict_iterable, is_data_record, is_data_from_channel, logical_and
from analysis.plotting.plotting import plotThreeWay
from scan.scan import ScanBase

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class GdacTune(ScanBase):
    def __init__(self, config_file, definition_file=None, bit_file=None, device=None, scan_identifier="tune_gdac", scan_data_path=None):
        super(GdacTune, self).__init__(config_file=config_file, definition_file=definition_file, bit_file=bit_file, device=device, scan_identifier=scan_identifier, scan_data_path=scan_data_path)
        self.set_gdac_tune_bits()
        self.set_target_threshold()
        self.set_n_injections()
        self.set_abort_precision()

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

    def set_gdac_tune_bits(self, GdacTuneBits=range(7, -1, -1)):
        self.GdacTuneBits = GdacTuneBits

    def set_n_injections(self, Ninjections=50):
        self.Ninjections = Ninjections

    def test_global_register(self):
        from daq.readout import FEI4Record

        '''Test Global Register
        '''
        self.register_utils.configure_global()
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        self.register_utils.send_commands(commands)
        commands = []
        self.register.set_global_register_value('Conf_AddrEnable', 1)
        commands.extend(self.register.get_commands("wrregister", name='Conf_AddrEnable'))
        read_from_address = range(1, 64)
        self.register_utils.send_commands(commands)
        self.readout.reset_sram_fifo()
        commands = []
        commands.extend(self.register.get_commands("rdregister", addresses=read_from_address))
        self.register_utils.send_commands(commands)

        data = self.readout.read_data()
        print data
        checked_address = []
        number_of_errors = 0
        for index, word in enumerate(np.nditer(data)):
            fei4_data = FEI4Record(word, self.register.chip_flavor)
            # print fei4_data
            if fei4_data == 'AR':
                read_value = FEI4Record(data[index + 1], self.register.chip_flavor)['value']
                set_value = int(self.register.get_global_register_bitsets([fei4_data['address']])[0])
                checked_address.append(fei4_data['address'])
                # print int(self.register.get_global_register_bitsets([fei4_data['address']])[0])
                if read_value == set_value:
                    # print 'Register Test:', 'Address', fei4_data['address'], 'PASSED'
                    pass
                else:
                    number_of_errors += 1
                    logging.warning('Global Register Test: Wrong data for Global Register at address %d (read: %d, expected: %d)' % (fei4_data['address'], read_value, set_value))

        commands = []
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)
        not_read_registers = set.difference(set(read_from_address), checked_address)
        not_read_registers = list(not_read_registers)
        not_read_registers.sort()
        for address in not_read_registers:
            logging.warning('Global Register Test: Data for Global Register at address %d missing' % address)
            number_of_errors += 1
        return number_of_errors

    def scan(self):
        self.write_target_threshold()
        for gdac_bit in self.GdacTuneBits:  # reset all GDAC bits
            self.set_gdac_bit(gdac_bit, bit_value=0)

        addedAdditionalLastBitScan = False
        lastBitResult = self.Ninjections

        mask_steps = 3
        enable_mask_steps = [0]  # one mask step to increase speed, no effect on precision

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
            for gdac_bit in self.GdacTuneBits:
                scan_paramter_value = (self.register.get_global_register_value("Vthin_AltCoarse") << 8) + self.register.get_global_register_value("Vthin_AltFine")

                if(not addedAdditionalLastBitScan):
                    self.set_gdac_bit(gdac_bit)
                    logging.info('GDAC setting: %d, bit %d = 1' % (scan_paramter_value, gdac_bit))
                else:
                    self.set_gdac_bit(gdac_bit, bit_value=0)
                    logging.info('GDAC setting: %d, bit %d = 0' % (scan_paramter_value, gdac_bit))

                self.readout.start()

                repeat_command = self.Ninjections

                cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0] + self.register.get_commands("zeros", mask_steps=mask_steps)[0]
                self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, hardware_repeat=True, mask_steps=mask_steps, enable_mask_steps=enable_mask_steps, enable_double_columns=None, same_mask_for_all_dc=False, eol_function=None, digital_injection=False, enable_c_high=None, enable_c_low=None, shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None)

                self.readout.stop()

                raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_paramter_value})

                OccupancyArray, _, _ = np.histogram2d(*convert_data_array(data_array_from_data_dict_iterable(self.readout.data), filter_func=logical_and(is_data_record, is_data_from_channel(4)), converter_func=get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
                OccArraySelPixel = OccupancyArray[select_mask_array > 0]  # take only selected pixel
                median_occupancy = np.median(OccArraySelPixel)
#                 plotThreeWay(OccupancyArray.transpose(), title = "Occupancy (GDAC tuning bit "+str(gdac_bit)+")", label = 'Occupancy', filename = None)#self.scan_data_filename+".pdf")

                if(abs(median_occupancy - repeat_command / 2) < self.abort_precision and gdac_bit > 0):  # abort if good value already found to save time
                    logging.info('Good result already achieved (median - Ninj/2 < %f), skipping not varied bits' % self.abort_precision)
                    break

                if(gdac_bit > 0 and median_occupancy < repeat_command / 2):
                    logging.info('Median = %f < %f, set bit %d = 0' % (median_occupancy, repeat_command / 2, gdac_bit))
                    self.set_gdac_bit(gdac_bit, bit_value=0)
                else:
                    logging.info('Median = %f > %f, leave bit %d = 1' % (median_occupancy, repeat_command / 2, gdac_bit))

                if(gdac_bit == 0):
                    if not(addedAdditionalLastBitScan):  # scan bit = 0 with the correct value again
                        addedAdditionalLastBitScan = True
                        lastBitResult = OccupancyArray
                        self.GdacTuneBits.append(0)  # bit 0 has to be scanned twice
                    else:
                        lastBitResultMedian = np.median(lastBitResult[select_mask_array > 0])
                        logging.info('Scanned bit 0 = 0 with %f instead of %f' % (median_occupancy, lastBitResultMedian))
                        if(abs(median_occupancy - repeat_command / 2) > abs(lastBitResultMedian - repeat_command / 2)):  # if bit 0 = 0 is worse than bit 0 = 1, so go back
                            self.set_gdac_bit(gdac_bit, bit_value=1)
                            logging.info('Set bit 0 = 1')
                            OccupancyArray = lastBitResult
                            OccArraySelPixel = OccupancyArray[select_mask_array > 0]  # take only selected pixel
                            median_occupancy = np.median(OccArraySelPixel)
                        else:
                            logging.info('Set bit 0 = 0')

            if(abs(median_occupancy - repeat_command / 2) > 2 * self.abort_precision):
                logging.warning('Tuning of Vthin_AltCoarse/Vthin_AltFine failed. Difference = %f. Vthin_AltCoarse/Vthin_AltFine = %d/%d' % (abs(median_occupancy - repeat_command / 2), self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))
            else:
                logging.info('Tuned GDAC to Vthin_AltCoarse/Vthin_AltFine = %d/%d' % (self.register.get_global_register_value("Vthin_AltCoarse"), self.register.get_global_register_value("Vthin_AltFine")))

            plotThreeWay(OccupancyArray.transpose(), title="Occupancy after GDAC tuning", x_axis_title='Occupancy', filename=None)

if __name__ == "__main__":
    import configuration
    scan = GdacTune(config_file=configuration.config_file, bit_file=configuration.bit_file, scan_data_path=configuration.scan_data_path)
    scan.set_target_threshold(PlsrDAC=50)
    scan.set_abort_precision(delta_occupancy=2)
    scan.set_gdac_tune_bits(range(7, -1, -1))
    scan.set_n_injections(Ninjections=50)
    scan.start(use_thread=False)
    scan.stop()
    scan.register.save_configuration(configuration.config_file)
