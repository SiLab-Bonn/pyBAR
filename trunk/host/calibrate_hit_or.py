"""A script that changes the PlsrDAC in a certain range for selected pixels and measures the length of the hit OR signal with a Tektronix TDS5104B oscilloscope.
    This calibration can be used to measure charge information for single pixels with higher precision than with the quantized TOT information.
"""
import numpy as np
import visa
import tables as tb
from scan.scan import ScanBase
from daq.readout import open_raw_data_file
import matplotlib.pyplot as plt

from analysis.analyze_raw_data import AnalyzeRawData
from analysis import analysis_utils
from matplotlib.backends.backend_pdf import PdfPages

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "GPIB_prim_address": 1,
    "histogram_box": '-193.000000000000000E-9, 200.0000E-3, 200.000000000000060E-9, 200.0000E-3',  # position of the histogram box in absolute coordinates in ns, the left most limit has to be chosen carfully not to histogram the leading tot edge
    "oszi_channel": 'CH1',
    "repeat_command": 10000,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_values": [i for j in (range(40, 70, 5), range(70, 100, 10), range(100, 600, 20), range(600, 801, 40)) for i in j],  # list of scan parameters to use
    "pixels": [(30, 30), ]  # list of (col,row) tupel of pixels to use
}


class HitOrScan(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(HitOrScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="hit_or_scan")

    def init_oscilloscope(self, GPIB_prim_address, histogram_box, oszi_channel):
        ''' Initializes the histogram and throws exceptions if it is not found'''
        try:
            self.oszi = visa.instrument("GPIB::" + str(GPIB_prim_address), timeout=4)
        except:
            logging.error('No device found ?!')
            raise
        if not 'TDS5104B' in self.oszi.ask("*IDN?"):  # check if the correct oszilloscope was found
            raise RuntimeError('Reading of histogram data from ' + self.oszi.ask("*IDN?") + ' is not supported')
        self.oszi.write('FASTA:STATE ON')  # set fast aquisition
        self.oszi.write('ACQ:STATE OFF')  # stop getting data
        self.oszi.write('HIS:STATE ON')
        self.oszi.write('HIS:COUN RESET')  # reset the histogram count
        scan.oszi.write('HOR:POS 5')  # workaround to really reset histogram count
        scan.oszi.write('HOR:POS 0')  # workaround to really reset histogram count
        self.oszi.write('HOR:SCA 40E-9')  # set the scale to fit the TOT nicely
        scan.oszi.write(oszi_channel + ':POS -1')
        scan.oszi.write(oszi_channel + ':SCA 200.0000E-3')
        self.oszi.write('TRIG:A:LEV 80.0000E-3')
        self.oszi.write('TRIG:A:EDGE:SOU ' + oszi_channel)
        self.oszi.write('HIS:SOU ' + oszi_channel)
        self.oszi.write('HIS:BOX ' + histogram_box)
        logging.info('Found oscilloscope with histogram settings ' + self.oszi.ask('HIS?'))

    def get_tdc_histogram(self):
        ''' Reads the histogram from the oscilloscope and returns it
        Returns
        -------
        list of counts : list
        '''
        return [int(token) for token in self.oszi.ask('HIS:DATA?')[16:].split(',') if token.isdigit()]

    def start_histograming(self):
        logging.info('Reset histogram counts and start oszi')
        self.oszi.write('ACQ:STATE OFF')
        self.oszi.write('HIS:COUN RESET')  # reset the histogram count, does not work for all entries, most likely bug
        scan.oszi.write('HOR:POS 5')  # workaround to reset histogram count
        scan.oszi.write('HOR:POS 0')  # workaround to reset histogram count
        self.oszi.write('HOR:SCA 80E-9')  # set the scale to fit the TOT nicely
        self.oszi.write('HOR:SCA 40E-9')  # set the scale to fit the TOT nicely
        self.oszi.write('ACQ:STATE RUN')

    def stop_histograming(self):
        logging.info('Stop histograming with oszi')
        self.oszi.write('ACQ:STATE OFF')

    def get_dc_and_mask_step(self, column, row):
        ''' Returns the double columns and the mask step for the given pixel in column, row coordinates '''
        return column / 2, 335 + row if column % 2 == 0 else row - 1

    def scan(self, histogram_box, pixels, GPIB_prim_address=1, repeat_command=100, scan_parameter='PlsrDAC', scan_parameter_values=(55, 100, 150, 250), oszi_channel='CH1', **kwarg):
        '''Scan loop

        Parameters
        ----------
        GPIB_prim_address : int
            The primary address of the oscilloscope
        repeat_command : int
            Number of injections per scan step.
        scan_parameter : string
            Name of global register.
        scan_parameter_range : list, tuple
            Specify the minimum and maximum value for scan parameter range. Upper value not included.
        scan_parameter_stepsize : int
            The minimum step size of the parameter. Used when start condition is not triggered.
        '''

        self.init_oscilloscope(GPIB_prim_address, histogram_box, oszi_channel)

        calibration_data = np.zeros(shape=(len(scan_parameter_values), 500), dtype='uint8')  # oszi gives 500 values

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter, 'column', 'row']) as raw_data_file:
            calibration_data_group = raw_data_file.raw_data_file_h5.createGroup(raw_data_file.raw_data_file_h5.root, 'calibration_data', title='Calibration data')
            for pixel in pixels:
                column = pixel[0]
                row = pixel[1]
                calibration_data_array = raw_data_file.raw_data_file_h5.createCArray(calibration_data_group, name='col_row_' + str(column) + '_' + str(row), title='Calibration col/row = ' + str(column) + '/' + str(row), atom=tb.Atom.from_dtype(calibration_data.dtype), shape=(len(scan_parameter_values), 500))
                for scan_parameter_index, scan_parameter_value in enumerate(scan_parameter_values):
                    if self.stop_thread_event.is_set():
                        break
                    logging.info('Scan step: %s %d' % (scan_parameter, scan_parameter_value))

                    commands = []
                    commands.extend(self.register.get_commands("confmode"))
                    self.register.set_global_register_value(scan_parameter, scan_parameter_value)
                    commands.extend(self.register.get_commands("wrregister", name=[scan_parameter]))
                    self.register_utils.send_commands(commands)

                    self.readout.start()

                    double_column, mask_step = self.get_dc_and_mask_step(column=column, row=row)  # translate the selected pixel into DC, mask_step info to be able to used the scan_loop

                    cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]  # + self.register.get_commands("zeros", length=12000)[0]
                    self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, use_delay=True, hardware_repeat=True, mask_steps=672, enable_mask_steps=[mask_step], enable_double_columns=[double_column], same_mask_for_all_dc=False, eol_function=self.stop_histograming(), digital_injection=False, enable_c_high=None, enable_c_low=None, disable_shift_masks=["Imon"], enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None, bol_function=self.start_histograming())
                    self.stop_histograming()

                    self.readout.stop(timeout=10)

                    # saving data
                    raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value, 'column': column, 'row': row})
                    actual_data_hist = np.array(self.get_tdc_histogram())
                    calibration_data_array[scan_parameter_index, :] = actual_data_hist

    def analyze(self):
        logging.info('Analyze and plot results')
        # interpreting results
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)
        # creation of a calibration: charge [PlsrDAC] <-> TOT [ns] per pixel; TOT is taken from the discrete hit tot info and the Oszi histogram
        with tb.openFile(scan.scan_data_filename + "_calibration.h5", mode="w") as calibration_data_file:  # create new h5 file with the calibration data
            with tb.openFile(self.scan_data_filename + ".h5", mode="r") as raw_data_file:  # open the raw data file to access the oszi histograms
                output_pdf = PdfPages(scan.scan_data_filename + "_calibration.pdf")
                # determine the time info of the oszi histogram from the oszi settings
                rel_start_time = float(raw_data_file.root.scan_configuration[:]['histogram_box'][0].split(',')[0]) * 10. ** 9  # in ns
                rel_stop_time = float(raw_data_file.root.scan_configuration[:]['histogram_box'][0].split(',')[2]) * 10. ** 9  # in ns
                abs_start_time = 40 * 5 + rel_start_time
                abs_stop_time = 40 * 5 + rel_stop_time
                time_bin = np.arange(abs_start_time, abs_stop_time, (abs_stop_time - abs_start_time) / 500.)  # calculate the time at each hist bin in ns
                logging.info('Calculate mean TOT from hit info and oszi hisogram')
                with tb.openFile(self.scan_data_filename + "_interpreted.h5", mode="r+") as in_hit_file_h5:  # open interpreted data file to access the hit table for tot histograming
                    analysis_utils.index_event_number(in_hit_file_h5.root.Hits)  # create index to efficiently work on data based on event numbers
                    meta_data_array = in_hit_file_h5.root.meta_data[:]  # get the meta data array to select be able to select hits per scan parameter
                    scan_parameter_values = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array, selected_columns_only=True)  # get the PlsrDAC values
                    event_numbers = analysis_utils.get_unique_scan_parameter_combinations(meta_data_array)['event_number']  # get the event numbers in meta_data where the scan parameters have different settings
                    parameter_ranges = np.column_stack((scan_parameter_values, analysis_utils.get_event_range(event_numbers)))  # list with entries [scan_parameter_value, start_event_number, stop_event_number]
                    calibration_data = np.zeros(shape=(80, 336, len(scan_configuration['scan_parameter_values']), 4), dtype='f4')  # result of the calibration is a histogram with col_index, row_index, plsrDAC value, mean discrete tot, rms discrete tot, mean tot from oszi, rms tot from oszi
                    for scan_parameter_value, start_event_number, stop_event_number in parameter_ranges:  # loop over the different PlsrDAC settings
                        scan_parameter_index = scan_configuration['scan_parameter_values'].index(scan_parameter_value[0])  # translate the scan parameter value to an index for the result histogram
                        column = scan_parameter_value[1]
                        row = scan_parameter_value[2]
                        if column > 80 or row > 336:
                            logging.warning('Selected pixel col/row = ' + str(column) + '/' + str(row) + ' is out of bound, omit.')
                            continue
                        for hits, _ in analysis_utils.data_aligned_at_events(in_hit_file_h5.root.Hits, start_event_number=start_event_number, stop_event_number=stop_event_number):  # loop over hits for one PlsrDAC setting in chunks
                            col_row_tot_hist, _ = np.histogramdd((hits['column'], hits['row'], hits['tot']), bins=(80, 336, 16), range=[[1, 80], [1, 336], [0, 15]])
                            col_row_mean_tot_hist = np.average(col_row_tot_hist, axis=2, weights=range(0, 16)) * sum(range(0, 16)) / hits['tot'].shape[0]
                            calibration_data[column - 1, row - 1, scan_parameter_index, 0] = col_row_mean_tot_hist[column - 1, row - 1]  # just add data of the selected pixel
                        calibration_data[column - 1, row - 1, scan_parameter_index, 2] = analysis_utils.get_median_from_histogram(raw_data_file.root.calibration_data._f_get_child('col_row_' + str(column) + '_' + str(row))[scan_parameter_index, :], time_bin)
                        calibration_data[column - 1, row - 1, scan_parameter_index, 3] = analysis_utils.get_rms_from_histogram(raw_data_file.root.calibration_data._f_get_child('col_row_' + str(column) + '_' + str(row))[scan_parameter_index, :], time_bin)
                    self.plot_calibration(plsrdac=scan_configuration['scan_parameter_values'], calibration_data=calibration_data, filename=output_pdf)
                    calibration_data_out = calibration_data_file.createCArray(calibration_data_file.root, name='HitOrCalibration', title='Hit OR calibration data', atom=tb.Atom.from_dtype(calibration_data.dtype), shape=calibration_data.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    calibration_data_out[:] = calibration_data
                output_pdf.close()

    def plot_calibration(self, plsrdac, calibration_data, filename=None):
        for pixel in scan_configuration['pixels']:
            column = pixel[0]
            row = pixel[1]
            logging.info("Plot calibration for pixel " + str(column) + '/' + str(row))
            plt.plot(plsrdac, calibration_data[column - 1, row - 1, :, 0] * 25. + 25., 'o')  # plot discrete real tot from hit onfo
#             plt.errorbar(plsrdac, calibration_data[column - 1, row - 1, :, 2], yerr=[calibration_data[column - 1, row - 1, :, 2], calibration_data[column - 1, row - 1, :, 2]], fmt='o')
            plt.plot(plsrdac, calibration_data[column - 1, row - 1, :, 2], 'o')
            plt.title('Calibration for pixel ' + str(column) + '/' + str(row) + '; ' + str(scan_configuration['repeat_command']) + ' injections per PlsrDAC')
            plt.xlabel('charge [PlsrDAC]')
            plt.ylabel('TOT [ns]')
            plt.grid(True)
            plt.legend(['hit tot', 'oscilloscope tot'], loc=0)
            if filename is None:
                plt.show()
            elif type(filename) == PdfPages:
                filename.savefig()
            else:
                plt.savefig(filename)
            plt.close()


if __name__ == "__main__":
    import configuration
    scan = HitOrScan(**configuration.scc50_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()
#     print [i for j in (range(40, 70, 5), range(70, 100, 10), range(100, 600, 20), range(600, 801, 40)) for i in j]
  
