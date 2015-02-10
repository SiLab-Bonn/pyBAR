"""A script that runs a fast threshold scan for different parameter (e.g. GDAC, TDACVbp) to get a threshold calibration. 
To save time the PlsrDAC start position is the start position determined from the previous threshold scan. So the
scan parameter values should be chosen in a ways that the threshold increases for each step.
After the data taking the data is analyzed and the calibration is written into a h5 file.
"""
from datetime import datetime
import progressbar
import tables as tb
import numpy as np
import logging
import os

from matplotlib.backends.backend_pdf import PdfPages

from pybar.run_manager import RunManager
from pybar.scans.scan_threshold_fast import FastThresholdScan
from pybar.analysis import analysis_utils
from pybar.analysis.RawDataConverter import data_struct
from pybar.analysis.plotting.plotting import plotThreeWay, plot_scurves, plot_scatter
from pybar.analysis.analyze_raw_data import AnalyzeRawData


class ThresholdCalibration(FastThresholdScan):
    ''' Threshold calibration scan
    '''
    _default_run_conf = FastThresholdScan._default_run_conf
    _default_run_conf['scan_parameters'] = [('PlsrDAC', (0, None)), ('GDAC', np.linspace(60., 120., num=4, dtype=np.uint32).tolist())]
#     _default_run_conf['scan_parameters'].extend([('GDAC', np.linspace(50., 100., num=2, dtype=np.uint32).tolist())])
    _default_run_conf.update({
        "ignore_columns": (1, 78, 79, 80),
        "ignore_parameter_values": None,  # do not use data for these parameter values for the calibration
        "create_plots": True,
        "create_result_plots": True,
        "configuration_file": "K:\\pyBAR\\host\\data\\threshold_calibration",  # output file with the calibration data
        "overwrite_output_files": False,
        "send_data": 'tcp://127.0.0.1:5678',  # send data to socket (e.g. for Online Monitor)
    })

    def scan(self):
        return
        logging.info('Taking threshold data at following ' + self.scan_parameters._fields[1] + ' values: %s' % str(self.scan_parameters[1]))

        for index, parameter_value in enumerate(self.scan_parameters[1]):
            if self.scan_parameters._fields[1] == 'GDAC':
                self.register_utils.set_gdac(parameter_value)
            else:
                self.register.set_global_register_value(self.scan_parameters._fields[1], parameter_value)

            if index == 0:
                actual_scan_parameters = {'PlsrDAC': self.scan_parameters.PlsrDAC, self.scan_parameters._fields[1]: parameter_value}
            else:
                self.minimum_data_points = self.data_points
                actual_scan_parameters = {'PlsrDAC': (self.scan_parameter_start, None), self.scan_parameters._fields[1]: parameter_value}
            self.set_scan_parameters(**actual_scan_parameters)
            super(ThresholdCalibration, self).scan()
        logging.info("Finished!")

    def handle_data(self, data):
        self.raw_data_file.append_item(data, scan_parameters=self.scan_parameters._asdict(), new_file=True, flush=False,)

    def analyze(self):
        with AnalyzeRawData(raw_data_file=r'C:\Users\DavidLP\git\pyBAR\host\pybar\module_test\44_module_test_threshold_calibration.h5', create_pdf=True) as analyze_raw_data:
            analyze_raw_data.create_hit_table = True
            # Turn off all hit histograms; created for each GDAC setting later
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.create_tot_pixel_hist = False
            analyze_raw_data.create_occupancy_hist = False
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()
            analyze_raw_data.plot_histograms()
        
        
        
#         def store_calibration_data_as_table(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration):
#             logging.info("Storing calibration data in a table...")
#             filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
#             mean_threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='MeanThresholdCalibration', description=data_struct.MeanThresholdCalibrationTable, title='mean_threshold_calibration', filters=filter_table)
#             threshold_calib_table = out_file_h5.createTable(out_file_h5.root, name='ThresholdCalibration', description=data_struct.ThresholdCalibrationTable, title='threshold_calibration', filters=filter_table)
#             for column in range(0, 80):
#                 for row in range(0, 336):
#                     for parameter_value_index, parameter_value in enumerate(calibration_configuration['parameter_values']):
#                         threshold_calib_table.row['column'] = column
#                         threshold_calib_table.row['row'] = row
#                         threshold_calib_table.row['parameter_value'] = parameter_value
#                         threshold_calib_table.row['threshold'] = threshold_calibration[column, row, parameter_value_index]
#                         threshold_calib_table.row.append()
#             for parameter_value_index, parameter_value in enumerate(calibration_configuration['parameter_values']):
#                 mean_threshold_calib_table.row['parameter_value'] = parameter_value
#                 mean_threshold_calib_table.row['mean_threshold'] = mean_threshold_calibration[parameter_value_index]
#                 mean_threshold_calib_table.row['threshold_rms'] = mean_threshold_rms_calibration[parameter_value_index]
#                 mean_threshold_calib_table.row.append()
#  
#             threshold_calib_table.flush()
#             mean_threshold_calib_table.flush()
#             logging.info("done")
#  
#         def store_calibration_data_as_array(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration):
#             logging.info("Storing calibration data in an array...")
#             filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
#             mean_threshold_calib_array = out_file_h5.createCArray(out_file_h5.root, name='HistThresholdMeanCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_calibration', filters=filter_table)
#             mean_threshold_calib_rms_array = out_file_h5.createCArray(out_file_h5.root, name='HistThresholdRMSCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_rms_calibration', filters=filter_table)
#             threshold_calib_array = out_file_h5.createCArray(out_file_h5.root, name='HistThresholdCalibration', atom=tb.Atom.from_dtype(threshold_calibration.dtype), shape=threshold_calibration.shape, title='threshold_calibration', filters=filter_table)
#             mean_threshold_calib_array[:] = mean_threshold_calibration
#             mean_threshold_calib_rms_array[:] = mean_threshold_rms_calibration
#             threshold_calib_array[:] = threshold_calibration
#             logging.info("done")
#      
#         def create_calibration(scan_data_filenames, ignore_columns, fei4b=False):
#             logging.info("Analyzing and plotting results...")
#             output_h5_filename = calibration_configuration['configuration_file'] + '.h5'
#             logging.info('Saving calibration in: %s' % output_h5_filename)
#      
#             if calibration_configuration['create_plots'] or calibration_configuration['create_result_plots']:
#                 output_pdf_filename = calibration_configuration['configuration_file'] + '.pdf'
#                 logging.info('Saving plot in: %s' % output_pdf_filename)
#                 output_pdf = PdfPages(output_pdf_filename)
#      
#             mean_threshold_calibration = np.empty(shape=(len(calibration_configuration['parameter_values']),), dtype='<f8')  # array to hold the analyzed data in ram
#             mean_threshold_rms_calibration = np.empty(shape=(len(calibration_configuration['parameter_values']),), dtype='<f8')  # array to hold the analyzed data in ram
#             threshold_calibration = np.empty(shape=(80, 336, len(calibration_configuration['parameter_values'])), dtype='<f8')  # array to hold the analyzed data in ram
#      
#             progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=len(calibration_configuration['parameter_values']))
#             progress_bar.start()
#      
#             for parameter_value_index, parameter_value in enumerate(calibration_configuration['parameter_values']):
#                 if calibration_configuration['ignore_parameter_values'] is not None and parameter_value in calibration_configuration['ignore_parameter_values']:
#                     continue
#      
#                 raw_data_file = scan_data_filenames[parameter_value]
#                 analyzed_data_file = raw_data_file[:-3] + '_interpreted.h5'
#                 analyze(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file, fei4b=fei4b)
#      
#                 with tb.openFile(analyzed_data_file, mode="r") as in_file_h5:
#                     # mask the not scanned columns for analysis and plotting
#                     occupancy_masked = mask_columns(pixel_array=in_file_h5.root.HistOcc[:], ignore_columns=ignore_columns)
#                     thresholds_masked = mask_columns(pixel_array=in_file_h5.root.HistThresholdFitted[:], ignore_columns=ignore_columns)
#                     # plot the threshold distribution and the s curves
#                     if calibration_configuration['create_plots']:
#                         plotThreeWay(hist=thresholds_masked, title='Threshold Fitted for ' + calibration_configuration['parameter_name'] + ' = ' + str(parameter_value), filename=output_pdf)
#                     meta_data_array = in_file_h5.root.meta_data[:]
#                     parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
#                     scan_parameters = parameter_settings['PlsrDAC']
#                     if calibration_configuration['create_plots']:
#                         plot_scurves(occupancy_hist=occupancy_masked, scan_parameters=scan_parameters, scan_parameter_name='PlsrDAC', filename=output_pdf)
#                     # fill the calibration data arrays
#                     mean_threshold_calibration[parameter_value_index] = np.ma.mean(thresholds_masked)
#                     mean_threshold_rms_calibration[parameter_value_index] = np.ma.std(thresholds_masked)
#                     threshold_calibration[:, :, parameter_value_index] = thresholds_masked.T
#                 progress_bar.update(parameter_value_index)
#             progress_bar.finish()
#      
#             if calibration_configuration['create_result_plots']:
#                 plot_scatter(x=calibration_configuration['parameter_values'], y=mean_threshold_calibration, title='Threshold calibration', x_label=calibration_configuration["parameter_name"], y_label='Mean threshold', log_x=False, filename=output_pdf)
#                 plot_scatter(x=calibration_configuration['parameter_values'], y=mean_threshold_calibration, title='Threshold calibration', x_label=calibration_configuration["parameter_name"], y_label='Mean threshold', log_x=True, filename=output_pdf)
#                 plot_scatter(x=calibration_configuration['parameter_values'], y=mean_threshold_rms_calibration, title='Threshold calibration', x_label=calibration_configuration["parameter_name"], y_label='Threshold RMS', log_x=False, filename=output_pdf)
#                 plot_scatter(x=calibration_configuration['parameter_values'], y=mean_threshold_rms_calibration, title='Threshold calibration', x_label=calibration_configuration["parameter_name"], y_label='Threshold RMS', log_x=True, filename=output_pdf)
#      
#             if calibration_configuration['create_plots'] or calibration_configuration['create_result_plots']:
#                 output_pdf.close()
#      
#             # store the calibration data into a hdf5 file as an easy to read table and as an array for quick data access
#             with tb.openFile(output_h5_filename, mode="w") as out_file_h5:
#                 store_calibration_data_as_array(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)
#                 store_calibration_data_as_table(out_file_h5=out_file_h5, mean_threshold_calibration=mean_threshold_calibration, mean_threshold_rms_calibration=mean_threshold_rms_calibration, threshold_calibration=threshold_calibration)
#      
#             if not os.path.isfile(analyzed_data_file) or calibration_configuration['overwrite_output_files']:
#                 with AnalyzeRawData(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file) as analyze_raw_data:
#                     analyze_raw_data.create_tot_hist = False
#                     analyze_raw_data.create_threshold_hists = True
#                     analyze_raw_data.create_fitted_threshold_hists = True
#                     analyze_raw_data.create_threshold_mask = True
#                     analyze_raw_data.n_injections = 100
#                     analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
#                     analyze_raw_data.interpret_word_table(fei4b=fei4b)
#             #         analyze_raw_data.interpreter.print_summary()
#             else:
#                 logging.debug(analyzed_data_file + ' exists already, skip analysis.')
#  
#     def reanalyze(fei4b=False):
#         data_files = analysis_utils.get_data_file_names_from_scan_base(calibration_configuration['scan_name'], filter_file_words=['analyzed', 'interpreted', 'cut_', 'cluster_sizes', 'trigger_fe'], parameter=True)
#         data_files_par = analysis_utils.get_parameter_from_files(data_files, parameters=calibration_configuration["parameter_name"], unique=True, sort=True)
#         scan_data_filenames = {}
#         for file_name, parameter in data_files_par.items():
#             scan_data_filenames[parameter[calibration_configuration["parameter_name"]][0]] = file_name
#         calibration_configuration['parameter_values'] = sorted(scan_data_filenames.keys())
#         create_calibration(scan_data_filenames=scan_data_filenames, ignore_columns=calibration_configuration['ignore_columns'], fei4b=fei4b)
#  
#     def mask_columns(pixel_array, ignore_columns):
#         idx = np.array(ignore_columns) - 1  # from FE to Array columns
#         m = np.zeros_like(pixel_array)
#         m[:, idx] = 1
#         return np.ma.masked_array(pixel_array, m)


if __name__ == "__main__":
    RunManager('../../configuration.yaml').run_run(ThresholdCalibration)
