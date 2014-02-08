"""A script that changes the PlsrDAC in a certain range for selected pixels and measures the length of the hit OR signal with a Tektronix TDS5104B oscilloscope.
    This calibration can be used to measure charge information for single pixels with higher precision than with the quantized TOT information.
"""
import numpy as np
import visa
import math
import time
import tables as tb
from scan.scan import ScanBase
from daq.readout import open_raw_data_file

from analysis.analyze_raw_data import AnalyzeRawData
from analysis.plotting import plotting
from analysis import analysis_utils
from matplotlib.backends.backend_pdf import PdfPages

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


scan_configuration = {
    "GPIB_prim_address": 1,
    "histogram_box": '-160.000000000000000E-9, 200.0000E-3, 200.000000000000060E-9, 200.0000E-3',  # position of the histogram box in absolute coordinates
    "repeat_command": 10000,
    "scan_parameter": 'PlsrDAC',
    "scan_parameter_range": (50, 701),
    "scan_parameter_stepsize": 10,
    "pixels": [(30, 30), ]  # a list of (col,row) tupel of pixels to use
}


class HitOrScan(ScanBase):
    def __init__(self, configuration_file, definition_file=None, bit_file=None, force_download=False, device=None, scan_data_path=None, device_identifier=""):
        super(HitOrScan, self).__init__(configuration_file=configuration_file, definition_file=definition_file, bit_file=bit_file, force_download=force_download, device=device, scan_data_path=scan_data_path, device_identifier=device_identifier, scan_identifier="hit_or_scan")

    def init_oscilloscope(self, GPIB_prim_address, histogram_box):
        ''' Initializes the histogram and throws exceptions if it is not found'''
        try:
            self.oszi = visa.instrument("GPIB::" + str(GPIB_prim_address), timeout=1)
        except:
            logging.error('No device found ?!')
            raise
        if not 'TDS5104B' in self.oszi.ask("*IDN?"):  # check if the correct oszilloscope was found
            raise RuntimeError('Reading of histogram data from ' + self.oszi.ask("*IDN?") + ' is not supported')
        self.oszi.write('ACQ:STATE OFF')  # stop getting data
        self.oszi.write('FASTA:STATE ON')  # set fast aquisition
        self.oszi.write('HIS:STATE ON')
        self.oszi.write('HIS:COUN RESET')  # reset the histogram count
        self.oszi.write('HOR:POS 0')  # set the courser to the left most position
        self.oszi.write('HOR:SCA 40E-9')  # set the scale to fit the TOT nicely
        self.oszi.write('HIS:BOX ' + histogram_box)
        logging.info('Found oscilloscope with histogram settings ' + self.oszi.ask('HIS?'))

    def get_tdc_histogram(self):
        ''' Reads the histogram from the oscilloscope and returns it
        Returns
        -------
        list of counts : list
        '''
        hist = [int(token) for token in self.oszi.ask('HIS:DATA?')[16:].split(',') if token.isdigit()]
        self.oszi.write('HIS:COUN RESET')  # reset the histogram count
        return hist

    def start_histograming(self):
        logging.info('Reset histogram counts and start oszi')
        self.oszi.write('ACQ:STATE OFF')
        self.oszi.write('HIS:COUN RESET')  # reset the histogram count
        self.oszi.write('ACQ:STATE RUN')

    def stop_histograming(self):
        logging.info('Stop histograming with oszi')
        self.oszi.write('ACQ:STATE OFF')

    def get_dc_and_mask_step(self, column, row):
        ''' Returns the double columns and the mask step for the given pixel in column, row coordinates '''
        return column / 2, 335 + row if column % 2 == 0 else row - 1

    def scan(self, histogram_box, pixels, GPIB_prim_address=1, repeat_command=100, scan_parameter='PlsrDAC', scan_parameter_range=(0, 100), scan_parameter_stepsize=1, **kwarg):
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

        self.init_oscilloscope(GPIB_prim_address, histogram_box)

        if scan_parameter_range is None or not scan_parameter_range:
            scan_parameter_values = range(0, (2 ** self.register.get_global_register_objects(name=[scan_parameter])[0].bitlength), scan_parameter_stepsize)
        else:
            scan_parameter_values = range(scan_parameter_range[0], scan_parameter_range[1], scan_parameter_stepsize)
        logging.info("Scanning %s from %d to %d" % (scan_parameter, scan_parameter_values[0], scan_parameter_values[-1]))

#         self.configure_fe(pixels)
        calibration_data = np.zeros(shape=(len(scan_parameter_values), 500), dtype='uint8')  # oszi gives 500 values

        with open_raw_data_file(filename=self.scan_data_filename, title=self.scan_identifier, scan_parameters=[scan_parameter]) as raw_data_file:
            calibration_data_group = raw_data_file.raw_data_file_h5.createGroup(raw_data_file.raw_data_file_h5.root, 'calibration_data', title='Calibration data')
            for pixel in pixels:
                calibration_data_array = raw_data_file.raw_data_file_h5.createCArray(calibration_data_group, name='col_row_' + str(pixel[0]) + '_' + str(pixel[1]), title='Calibration col/row = ' + str(pixel[0]) + '/' + str(pixel[1]), atom=tb.Atom.from_dtype(calibration_data.dtype), shape=(len(scan_parameter_values), 500))
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

                    double_column, mask_step = self.get_dc_and_mask_step(column=pixel[0], row=pixel[1])  # translate the selected pixel into DC, mask_step info to be able to used the scan_loop

                    cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]# + self.register.get_commands("zeros", length=12000)[0]
                    self.scan_loop(cal_lvl1_command, repeat_command=repeat_command, use_delay=True, hardware_repeat=True, mask_steps=672, enable_mask_steps=[mask_step], enable_double_columns=[double_column], same_mask_for_all_dc=False, eol_function=self.stop_histograming(), digital_injection=False, enable_c_high=None, enable_c_low=None, disable_shift_masks=["Imon"], enable_shift_masks=["Enable", "C_High", "C_Low"], restore_shift_masks=True, mask=None, bol_function=self.start_histograming())
                    self.stop_histograming()

                    self.readout.stop(timeout=10)

                    # saving data
                    raw_data_file.append(self.readout.data, scan_parameters={scan_parameter: scan_parameter_value})
                    actual_data_hist = np.array(self.get_tdc_histogram())
                    calibration_data_array[scan_parameter_index, :] = actual_data_hist

    def analyze(self):
        logging.info('Analyze and plot results')
        with AnalyzeRawData(raw_data_file=self.scan_data_filename + ".h5", analyzed_data_file=self.scan_data_filename + "_interpreted.h5") as analyze_raw_data:
            analyze_raw_data.interpreter.set_trig_count(self.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.interpret_word_table(fei4b=scan.register.fei4b)
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms(scan_data_filename=self.scan_data_filename)
        with tb.openFile(self.scan_data_filename + ".h5", mode="r") as raw_data_file:
            output_pdf = PdfPages(scan.scan_data_filename + "_calibration.pdf")
            with tb.openFile(scan.scan_data_filename + "_calibration.h5", mode="w") as calibration_data_file:
                for node in raw_data_file.root.calibration_data:
                    x = []
                    y = []
                    for scan_parameter_index, scan_parameter_value in enumerate(np.unique(raw_data_file.root.scan_parameters[:])):
                        rel_start_time = float(raw_data_file.root.scan_configuration[:]['histogram_box'][0].split(',')[0]) * 10.**9  # in ns
                        rel_stop_time = float(raw_data_file.root.scan_configuration[:]['histogram_box'][0].split(',')[2]) * 10.**9  # in ns
                        abs_start_time = 40 * 5 + rel_start_time
                        abs_stop_time = 40 * 5 + rel_stop_time
                        time_bin = np.arange(abs_start_time, abs_stop_time, (abs_stop_time - abs_start_time) / 500.)  # calculate the time at each hist bin in ns
                        x.extend(scan_parameter_value)
                        y.extend([analysis_utils.get_median_from_histogram(node[scan_parameter_index, :], time_bin)])
                        plotting.plot_scatter(x=time_bin, y=node[scan_parameter_index, :], title='Time over threshold for pixel ' + str(node.name.split('_')[2]) + '/' + str(node.name.split('_')[3]) + ' and PlsrDAC ' + str(scan_parameter_value[0]), x_label='time [ns]', y_label='#', filename=output_pdf)
                        plotting.plot_1d_hist(node[scan_parameter_index, :], 'Time over threshold for pixel ' + str(node.name.split('_')[2]) + '/' + str(node.name.split('_')[3]) + ' and PlsrDAC ' + str(scan_parameter_value[0]), x_axis_title='time [ a.u.]', y_axis_title='#', filename=output_pdf)
                    plotting.plot_scatter(x, y, title='Calibration for pixel ' + str(node.name.split('_')[2]) + '/' + str(node.name.split('_')[3]), x_label='PlsrDAC', y_label='TOT [ns]', filename=output_pdf)
                output_pdf.close()


if __name__ == "__main__":
    import configuration
    scan = HitOrScan(**configuration.scc50_configuration)
    scan.start(use_thread=False, **scan_configuration)
    scan.stop()
    scan.analyze()