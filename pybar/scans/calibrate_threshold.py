"""A script that runs a fast threshold scan for different parameter (e.g. GDAC, TDACVbp) to get a threshold calibration.
To save time the PlsrDAC start position is the start position determined from the previous threshold scan. So the
scan parameter values should be chosen in a ways that the threshold increases for each step.
After the data taking the data is analyzed and the calibration is written into a h5 file.
"""
import logging
import os
import ast

from matplotlib.backends.backend_pdf import PdfPages
import tables as tb
import numpy as np

import progressbar

from pybar_fei4_interpreter import data_struct
from pybar.run_manager import RunManager
from pybar.scans.scan_threshold_fast import FastThresholdScan
from pybar.analysis import analysis_utils
from pybar.analysis.plotting.plotting import plot_three_way, plot_scurves, plot_scatter
from pybar.analysis.analyze_raw_data import AnalyzeRawData


def create_threshold_calibration(scan_base_file_name, create_plots=True):  # Create calibration function, can be called stand alone
    def analyze_raw_data_file(file_name):
        if os.path.isfile(os.path.splitext(file_name)[0] + '_interpreted.h5'):  # skip analysis if already done
            logging.warning('Analyzed data file ' + file_name + ' already exists. Skip analysis for this file.')
        else:
            with AnalyzeRawData(raw_data_file=file_name, create_pdf=False) as analyze_raw_data:
                analyze_raw_data.create_tot_hist = False
                analyze_raw_data.create_tot_pixel_hist = False
                analyze_raw_data.create_fitted_threshold_hists = True
                analyze_raw_data.create_threshold_mask = True
                analyze_raw_data.interpreter.set_warning_output(False)  # RX errors would fill the console
                analyze_raw_data.interpret_word_table()

    def store_calibration_data_as_table(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration, parameter_values):
        logging.info("Storing calibration data in a table...")
        filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        mean_threshold_calib_table = out_file_h5.create_table(out_file_h5.root, name='MeanThresholdCalibration', description=data_struct.MeanThresholdCalibrationTable, title='mean_threshold_calibration', filters=filter_table)
        threshold_calib_table = out_file_h5.create_table(out_file_h5.root, name='ThresholdCalibration', description=data_struct.ThresholdCalibrationTable, title='threshold_calibration', filters=filter_table)
        for column in range(80):
            for row in range(336):
                for parameter_value_index, parameter_value in enumerate(parameter_values):
                    threshold_calib_table.row['column'] = column
                    threshold_calib_table.row['row'] = row
                    threshold_calib_table.row['parameter_value'] = parameter_value
                    threshold_calib_table.row['threshold'] = threshold_calibration[column, row, parameter_value_index]
                    threshold_calib_table.row.append()
        for parameter_value_index, parameter_value in enumerate(parameter_values):
            mean_threshold_calib_table.row['parameter_value'] = parameter_value
            mean_threshold_calib_table.row['mean_threshold'] = mean_threshold_calibration[parameter_value_index]
            mean_threshold_calib_table.row['threshold_rms'] = mean_threshold_rms_calibration[parameter_value_index]
            mean_threshold_calib_table.row.append()
        threshold_calib_table.flush()
        mean_threshold_calib_table.flush()
        logging.info("done")

    def store_calibration_data_as_array(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration, parameter_name, parameter_values):
        logging.info("Storing calibration data in an array...")
        filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        mean_threshold_calib_array = out_file_h5.create_carray(out_file_h5.root, name='HistThresholdMeanCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_calibration', filters=filter_table)
        mean_threshold_calib_rms_array = out_file_h5.create_carray(out_file_h5.root, name='HistThresholdRMSCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_rms_calibration', filters=filter_table)
        threshold_calib_array = out_file_h5.create_carray(out_file_h5.root, name='HistThresholdCalibration', atom=tb.Atom.from_dtype(threshold_calibration.dtype), shape=threshold_calibration.shape, title='threshold_calibration', filters=filter_table)
        mean_threshold_calib_array[:] = mean_threshold_calibration
        mean_threshold_calib_rms_array[:] = mean_threshold_rms_calibration
        threshold_calib_array[:] = threshold_calibration
        mean_threshold_calib_array.attrs.dimensions = ['column', 'row', parameter_name]
        mean_threshold_calib_rms_array.attrs.dimensions = ['column', 'row', parameter_name]
        threshold_calib_array.attrs.dimensions = ['column', 'row', parameter_name]
        mean_threshold_calib_array.attrs.scan_parameter_values = parameter_values
        mean_threshold_calib_rms_array.attrs.scan_parameter_values = parameter_values
        threshold_calib_array.attrs.scan_parameter_values = parameter_values

        logging.info("done")

    def mask_columns(pixel_array, ignore_columns):
        idx = np.array(ignore_columns) - 1  # from FE to Array columns
        m = np.zeros_like(pixel_array)
        m[:, idx] = 1
        return np.ma.masked_array(pixel_array, m)

    raw_data_files = analysis_utils.get_data_file_names_from_scan_base(scan_base_file_name)
    first_scan_base_file_name = scan_base_file_name if isinstance(scan_base_file_name, basestring) else scan_base_file_name[0]  # multilpe scan_base_file_names for multiple runs

    with tb.open_file(first_scan_base_file_name + '.h5', mode="r") as in_file_h5:  # deduce scan parameters from the first (and often only) scan base file name
        ignore_columns = in_file_h5.root.configuration.run_conf[:][np.where(in_file_h5.root.configuration.run_conf[:]['name'] == 'ignore_columns')]['value'][0]
        parameter_name = in_file_h5.root.configuration.run_conf[:][np.where(in_file_h5.root.configuration.run_conf[:]['name'] == 'scan_parameters')]['value'][0]
        ignore_columns = ast.literal_eval(ignore_columns)
        parameter_name = ast.literal_eval(parameter_name)[1][0]

    calibration_file = first_scan_base_file_name + '_calibration'

    for raw_data_file in raw_data_files:  # analyze each raw data file, not using multithreading here, it is already used in s-curve fit
        analyze_raw_data_file(raw_data_file)

    files_per_parameter = analysis_utils.get_parameter_value_from_file_names([os.path.splitext(file_name)[0] + '_interpreted.h5' for file_name in raw_data_files], parameter_name, unique=True, sort=True)

    logging.info("Create calibration from data")
    mean_threshold_calibration = np.empty(shape=(len(raw_data_files),), dtype='<f8')
    mean_threshold_rms_calibration = np.empty(shape=(len(raw_data_files),), dtype='<f8')
    threshold_calibration = np.empty(shape=(80, 336, len(raw_data_files)), dtype='<f8')

    if create_plots:
        logging.info('Saving calibration plots in: %s', calibration_file + '.pdf')
        output_pdf = PdfPages(calibration_file + '.pdf')

    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(files_per_parameter.items()), term_width=80)
    progress_bar.start()
    parameter_values = []
    for index, (analyzed_data_file, parameters) in enumerate(files_per_parameter.items()):
        parameter_values.append(parameters.values()[0][0])
        with tb.open_file(analyzed_data_file, mode="r") as in_file_h5:
            occupancy_masked = mask_columns(pixel_array=in_file_h5.root.HistOcc[:], ignore_columns=ignore_columns)  # mask the not scanned columns for analysis and plotting
            thresholds_masked = mask_columns(pixel_array=in_file_h5.root.HistThresholdFitted[:], ignore_columns=ignore_columns)
            if create_plots:
                plot_three_way(hist=thresholds_masked, title='Threshold Fitted for ' + parameters.keys()[0] + ' = ' + str(parameters.values()[0][0]), filename=output_pdf)
                plsr_dacs = analysis_utils.get_scan_parameter(meta_data_array=in_file_h5.root.meta_data[:])['PlsrDAC']
                plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=plsr_dacs, scan_parameter_name='PlsrDAC', filename=output_pdf)
            # fill the calibration data arrays
            mean_threshold_calibration[index] = np.ma.mean(thresholds_masked)
            mean_threshold_rms_calibration[index] = np.ma.std(thresholds_masked)
            threshold_calibration[:, :, index] = thresholds_masked.T
        progress_bar.update(index)
    progress_bar.finish()

    with tb.open_file(calibration_file + '.h5', mode="w") as out_file_h5:
        store_calibration_data_as_array(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration, parameter_name=parameter_name, parameter_values=parameter_values)
        store_calibration_data_as_table(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration, parameter_values=parameter_values)

    if create_plots:
        plot_scatter(x=parameter_values, y=mean_threshold_calibration, title='Threshold calibration', x_label=parameter_name, y_label='Mean threshold', log_x=False, filename=output_pdf)
        plot_scatter(x=parameter_values, y=mean_threshold_calibration, title='Threshold calibration', x_label=parameter_name, y_label='Mean threshold', log_x=True, filename=output_pdf)
        output_pdf.close()


class ThresholdCalibration(FastThresholdScan):

    ''' Threshold calibration scan
    '''
    _default_run_conf = FastThresholdScan._default_run_conf.copy()
    _default_run_conf['scan_parameters'] = [('PlsrDAC', (0, None)), ('GDAC', np.unique(np.logspace(1.7, 4.0, 10).astype(np.int)).tolist())]
    _default_run_conf.update({
        "ignore_columns": (1, 78, 79, 80),
        'reset_rx_on_error': True,  # long scans have a high propability for ESD related data transmission errors; recover and continue here
        "create_plots": True,
    })

    def scan(self):
        logging.info('Taking threshold data at following ' + self.scan_parameters._fields[1] + ' values: %s', str(self.scan_parameters[1]))

        for index, parameter_value in enumerate(self.scan_parameters[1]):
            if self.scan_parameters._fields[1] == 'GDAC':  # if scan parameter = GDAC needs special registers set function
                self.register_utils.set_gdac(parameter_value)
            else:
                self.register.set_global_register_value(self.scan_parameters._fields[1], parameter_value)

            if index == 0:
                actual_scan_parameters = {'PlsrDAC': self.scan_parameters.PlsrDAC, self.scan_parameters._fields[1]: parameter_value}
            else:
                self.curr_minimum_data_points = self.data_points  # Take settings from last fast threshold scan for speed up
                actual_scan_parameters = {'PlsrDAC': (self.scan_parameter_start, None), self.scan_parameters._fields[1]: parameter_value}  # Start the PlsrDAC at last start point to save time
            self.set_scan_parameters(**actual_scan_parameters)
            super(ThresholdCalibration, self).scan()
        logging.info("Finished!")

    def handle_data(self, data, new_file=['GDAC'], flush=True):  # Create new file for each scan parameter change
        super(ThresholdCalibration, self).handle_data(data=data, new_file=new_file, flush=flush)

    def analyze(self):
        create_threshold_calibration(self.output_filename, create_plots=self.create_plots)


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(ThresholdCalibration)
