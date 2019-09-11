"""A script that runs a threshold scan for different command string send to the FE. Can be used to determine if there is a threshold shift if the LVL1/CAL is send.
Command sequence:
    arbitrary FE command + delay + CAL + fixed delay + LVL1
"""
import logging
import os
import math
from datetime import datetime

from matplotlib.backends.backend_pdf import PdfPages
import tables as tb
import numpy as np

import progressbar

import configuration
from scan_threshold_fast import FastThresholdScan
from analysis import analysis_utils
from analysis.RawDataConverter import data_struct
from analysis.plotting import plotting
from analysis.analyze_raw_data import AnalyzeRawData


local_configuration = {
    "delays": [1, 10, 50] + list(range(100, 3000, 100)),  # the delay between the arbitrary command and the CAL command
    "n_injections": 100,  # how often one injects per PlsrDAC setting and pixel
    "output_data_filename": 'threshold_stability',  # the file name to store the result data / plots to, no file suffix required
    "analysis_two_trigger": True,  # set to true if the analysis should be done per trigger
    "ignore_columns": (1, 2, 77, 78, 79, 80),
    "create_plots": True,
    "create_result_plots": True,
    "overwrite_output_files": False
}


def select_trigger_hits(input_file_hits, output_file_hits_1, output_file_hits_2):
    if (not os.path.isfile(output_file_hits_1) and not os.path.isfile(output_file_hits_2)) or local_configuration['overwrite_output_files']:
        with tb.open_file(input_file_hits, mode="r") as in_hit_file_h5:
            hit_table_in = in_hit_file_h5.root.Hits
            with tb.open_file(output_file_hits_1, mode="w") as out_hit_file_1_h5:
                with tb.open_file(output_file_hits_2, mode="w") as out_hit_file_2_h5:
                    hit_table_out_1 = out_hit_file_1_h5.create_table(out_hit_file_1_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    hit_table_out_2 = out_hit_file_2_h5.create_table(out_hit_file_2_h5.root, name='Hits', description=data_struct.HitInfoTable, title='hit_data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=hit_table_in.shape[0], term_width=80)
                    progress_bar.start()
                    for data, index in analysis_utils.data_aligned_at_events(hit_table_in, chunk_size=5000000):
                        hit_table_out_1.append(data[data['LVL1ID'] % 2 == 1])  # first trigger hits
                        hit_table_out_2.append(data[data['LVL1ID'] % 2 == 0])  # second trigger hits
                        progress_bar.update(index)
                    progress_bar.finish()
                    in_hit_file_h5.root.meta_data.copy(out_hit_file_1_h5.root)  # copy meta_data note to new file
                    in_hit_file_h5.root.meta_data.copy(out_hit_file_2_h5.root)  # copy meta_data note to new file


def analyze(raw_data_file, analyzed_data_file, fei4b=False):
    if not os.path.isfile(analyzed_data_file) or local_configuration['overwrite_output_files']:
        logging.info('Analyze all trigger')
        with AnalyzeRawData(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file) as analyze_raw_data:
            if local_configuration['analysis_two_trigger']:
                analyze_raw_data.create_hit_table = True
            analyze_raw_data.n_injections = local_configuration["n_injections"] * 2
            analyze_raw_data.create_threshold_hists = True
            analyze_raw_data.create_threshold_mask = True
            analyze_raw_data.create_fitted_threshold_hists = True
            analyze_raw_data.create_fitted_threshold_mask = True
            analyze_raw_data.interpreter.set_trig_count(scan_threshold_fast.register.get_global_register_value("Trig_Count"))
            analyze_raw_data.create_tot_hist = False
            analyze_raw_data.interpreter.set_warning_output(False)  # so far the data structure in a threshold scan was always bad, too many warnings given
            analyze_raw_data.interpret_word_table(fei4b=fei4b)
    else:
        logging.debug(analyzed_data_file + ' exists already, skip analysis.')
    if local_configuration['analysis_two_trigger']:
        logging.info('Analyze 1. trigger')
        select_trigger_hits(analyzed_data_file, os.path.splitext(analyzed_data_file)[0] + '_1.h5', os.path.splitext(analyzed_data_file)[0] + '_2.h5')
        if not os.path.isfile(os.path.splitext(analyzed_data_file)[0] + '_analyzed_1.h5') or local_configuration['overwrite_output_files']:
            with AnalyzeRawData(raw_data_file=None, analyzed_data_file=os.path.splitext(analyzed_data_file)[0] + '_1.h5') as analyze_raw_data:
                analyze_raw_data.interpreter.set_trig_count(scan_threshold_fast.register.get_global_register_value("Trig_Count"))
                analyze_raw_data.create_threshold_hists = True
                analyze_raw_data.create_threshold_mask = True
                analyze_raw_data.create_fitted_threshold_hists = True
                analyze_raw_data.create_fitted_threshold_mask = True
                analyze_raw_data.n_injections = local_configuration["n_injections"]
                analyze_raw_data.analyze_hit_table(analyzed_data_out_file=os.path.splitext(analyzed_data_file)[0] + '_analyzed_1.h5')
                analyze_raw_data.plot_histograms(pdf_filename=os.path.splitext(analyzed_data_file)[0] + '_analyzed_1.pdf', analyzed_data_file=os.path.splitext(analyzed_data_file)[0] + '_analyzed_1.h5')
        logging.info('Analyze 2. trigger')
        if not os.path.isfile(os.path.splitext(analyzed_data_file)[0] + '_analyzed_2.h5') or local_configuration['overwrite_output_files']:
            with AnalyzeRawData(raw_data_file=None, analyzed_data_file=os.path.splitext(analyzed_data_file)[0] + '_2.h5') as analyze_raw_data:
                analyze_raw_data.interpreter.set_trig_count(scan_threshold_fast.register.get_global_register_value("Trig_Count"))
                analyze_raw_data.create_threshold_hists = True
                analyze_raw_data.create_threshold_mask = True
                analyze_raw_data.create_fitted_threshold_hists = True
                analyze_raw_data.create_fitted_threshold_mask = True
                analyze_raw_data.n_injections = local_configuration["n_injections"]
                analyze_raw_data.analyze_hit_table(analyzed_data_out_file=os.path.splitext(analyzed_data_file)[0] + '_analyzed_2.h5')
                analyze_raw_data.plot_histograms(pdf_filename=os.path.splitext(analyzed_data_file)[0] + '_analyzed_2.pdf', analyzed_data_file=os.path.splitext(analyzed_data_file)[0] + '_analyzed_2.h5')


def store_calibration_data_as_table(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration, mean_noise_calibration, mean_noise_rms_calibration, noise_calibration):
    logging.info("Storing calibration data in a table...")
    filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    mean_threshold_calib_table = out_file_h5.create_table(out_file_h5.root, name='MeanThreshold', description=data_struct.MeanThresholdTable, title='mean_threshold_calibration', filters=filter_table)
    threshold_calib_table = out_file_h5.create_table(out_file_h5.root, name='Threshold', description=data_struct.ThresholdTable, title='threshold_calibration', filters=filter_table)
    for column in range(0, 80):
        for row in range(0, 336):
            for delay_index, delay_value in enumerate(local_configuration['delays']):
                threshold_calib_table.row['column'] = column
                threshold_calib_table.row['row'] = row
                threshold_calib_table.row['parameter'] = delay_value
                threshold_calib_table.row['threshold'] = threshold_calibration[column, row, delay_index]
                threshold_calib_table.row['noise'] = threshold_calibration[column, row, delay_index]
                threshold_calib_table.row.append()
    for delay_index, delay_value in enumerate(local_configuration['delays']):
        mean_threshold_calib_table.row['parameter'] = delay_value
        mean_threshold_calib_table.row['mean_threshold'] = mean_threshold_calibration[delay_index]
        mean_threshold_calib_table.row['threshold_rms'] = mean_threshold_rms_calibration[delay_index]
        mean_threshold_calib_table.row['mean_noise'] = mean_noise_calibration[delay_index]
        mean_threshold_calib_table.row['noise_rms'] = mean_noise_rms_calibration[delay_index]
        mean_threshold_calib_table.row.append()

    threshold_calib_table.flush()
    mean_threshold_calib_table.flush()
    logging.info("done")


def store_calibration_data_as_array(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration, mean_noise_calibration, mean_noise_rms_calibration, noise_calibration):
    logging.info("Storing calibration data in an array...")
    filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    mean_threshold_calib_array = out_file_h5.create_carray(out_file_h5.root, name='HistThresholdMeanCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_calibration', filters=filter_table)
    mean_threshold_calib_rms_array = out_file_h5.create_carray(out_file_h5.root, name='HistThresholdRMSCalibration', atom=tb.Atom.from_dtype(mean_threshold_calibration.dtype), shape=mean_threshold_calibration.shape, title='mean_threshold_rms_calibration', filters=filter_table)
    threshold_calib_array = out_file_h5.create_carray(out_file_h5.root, name='HistThresholdCalibration', atom=tb.Atom.from_dtype(threshold_calibration.dtype), shape=threshold_calibration.shape, title='threshold_calibration', filters=filter_table)
    mean_noise_calib_array = out_file_h5.create_carray(out_file_h5.root, name='HistNoiseMeanCalibration', atom=tb.Atom.from_dtype(mean_noise_calibration.dtype), shape=mean_noise_calibration.shape, title='mean_noise_calibration', filters=filter_table)
    mean_noise_calib_rms_array = out_file_h5.create_carray(out_file_h5.root, name='HistNoiseRMSCalibration', atom=tb.Atom.from_dtype(mean_noise_calibration.dtype), shape=mean_noise_calibration.shape, title='mean_noise_rms_calibration', filters=filter_table)
    noise_calib_array = out_file_h5.create_carray(out_file_h5.root, name='HistNoiseCalibration', atom=tb.Atom.from_dtype(noise_calibration.dtype), shape=noise_calibration.shape, title='noise_calibration', filters=filter_table)
    mean_threshold_calib_array[:] = mean_threshold_calibration
    mean_threshold_calib_rms_array[:] = mean_threshold_rms_calibration
    threshold_calib_array[:] = threshold_calibration
    mean_noise_calib_array[:] = mean_noise_calibration
    mean_noise_calib_rms_array[:] = mean_noise_rms_calibration
    noise_calib_array[:] = noise_calibration
    logging.info("done")


def analyze_data(scan_data_filenames, ignore_columns, fei4b=False):
    logging.info("Analyzing and plotting results...")
    output_h5_filename = local_configuration['output_data_filename'] + '.h5'
    logging.info('Saving calibration in: %s' % output_h5_filename)

    if local_configuration['create_plots'] or local_configuration['create_result_plots']:
        output_pdf_filename = local_configuration['output_data_filename'] + '.pdf'
        logging.info('Saving plots in: %s' % output_pdf_filename)
        output_pdf = PdfPages(output_pdf_filename)

    # define output data structures
    mean_threshold_calibration = np.zeros(shape=(len(local_configuration['delays']),), dtype='<f8')  # array to hold the analyzed data in ram
    mean_threshold_rms_calibration = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    mean_noise_calibration = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    mean_noise_rms_calibration = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    threshold_calibration = np.zeros(shape=(80, 336, len(local_configuration['delays'])), dtype='<f8')  # array to hold the analyzed data in ram
    noise_calibration = np.zeros_like(threshold_calibration)  # array to hold the analyzed data in ram
    mean_threshold_calibration_1 = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    mean_threshold_rms_calibration_1 = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    threshold_calibration_1 = np.zeros_like(threshold_calibration)  # array to hold the analyzed data in ram
    mean_threshold_calibration_2 = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    mean_threshold_rms_calibration_2 = np.zeros_like(mean_threshold_calibration)  # array to hold the analyzed data in ram
    threshold_calibration_2 = np.zeros_like(threshold_calibration)  # array to hold the analyzed data in ram
    # initialize progress bar
    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', analysis_utils.ETA()], maxval=len(local_configuration['delays']), term_width=80)
    progress_bar.start()
    # loop over all delay values and analyze the corresponding data
    for delay_index, delay_value in enumerate(local_configuration['delays']):
        # interpret the raw data from the actual delay value
        raw_data_file = scan_data_filenames[delay_value]
        analyzed_data_file = os.path.splitext(raw_data_file)[0] + '_interpreted.h5'
        analyze(raw_data_file=raw_data_file, analyzed_data_file=analyzed_data_file, fei4b=fei4b)

        scan_parameters = None
        with tb.open_file(analyzed_data_file, mode="r") as in_file_h5:
            # mask the not scanned columns for analysis and plotting
            mask = np.logical_or(mask_columns(pixel_array=in_file_h5.root.HistThresholdFitted[:], ignore_columns=ignore_columns), mask_pixel(steps=3, shift=0).T) == 0
            occupancy_masked = mask_columns(pixel_array=in_file_h5.root.HistOcc[:], ignore_columns=ignore_columns)
            thresholds_masked = np.ma.masked_array(in_file_h5.root.HistThresholdFitted[:], mask)
            noise_masked = np.ma.masked_array(in_file_h5.root.HistNoiseFitted[:], mask)
            # plot the threshold distribution and the s curves
            if local_configuration['create_plots']:
                plotting.plot_three_way(hist=thresholds_masked * 55.0, title='Threshold Fitted for delay = ' + str(delay_value), x_axis_title='threshold [e]', filename=output_pdf)
                plotting.plot_relative_bcid(hist=in_file_h5.root.HistRelBcid[0:16], title='Relative BCID (former LVL1ID) for delay = ' + str(delay_value), filename=output_pdf)
                plotting.plot_event_status(hist=in_file_h5.root.HistEventStatusCounter[:], title='Event status for delay = ' + str(delay_value), filename=output_pdf)
            meta_data_array = in_file_h5.root.meta_data[:]
            parameter_settings = analysis_utils.get_scan_parameter(meta_data_array=meta_data_array)
            scan_parameters = parameter_settings['PlsrDAC']
            if local_configuration['create_plots']:
                plotting.plot_scurves(occupancy_hist=occupancy_masked, title='S-Curves, delay ' + str(delay_value), scan_parameters=scan_parameters, scan_parameter_name='PlsrDAC', filename=output_pdf)
            # fill the calibration data arrays
            mean_threshold_calibration[delay_index] = np.ma.mean(thresholds_masked)
            mean_threshold_rms_calibration[delay_index] = np.ma.std(thresholds_masked)
            threshold_calibration[:, :, delay_index] = thresholds_masked.T
            mean_noise_calibration[delay_index] = np.ma.mean(noise_masked)
            mean_noise_rms_calibration[delay_index] = np.ma.std(noise_masked)
            noise_calibration[:, :, delay_index] = noise_masked.T

        # if activated analyze also the trigger seperately
        if local_configuration['analysis_two_trigger']:
            with tb.open_file(os.path.splitext(analyzed_data_file)[0] + '_analyzed_1.h5', mode="r") as in_file_1_h5:
                with tb.open_file(os.path.splitext(analyzed_data_file)[0] + '_analyzed_2.h5', mode="r") as in_file_2_h5:
                    # mask the not scanned columns for analysis and plotting
                    try:
                        occupancy_masked_1 = occupancy_masked = mask_columns(pixel_array=in_file_1_h5.root.HistOcc[:], ignore_columns=ignore_columns)
                        thresholds_masked_1 = np.ma.masked_array(in_file_1_h5.root.HistThresholdFitted[:], mask)
                        rel_bcid_1 = in_file_1_h5.root.HistRelBcid[0:16]
                    except tb.exceptions.NoSuchNodeError:
                        occupancy_masked_1 = np.zeros(shape=(336, 80, 2))
                        thresholds_masked_1 = np.zeros(shape=(336, 80))
                        rel_bcid_1 = np.zeros(shape=(16, ))
                    try:
                        occupancy_masked_2 = occupancy_masked = mask_columns(pixel_array=in_file_2_h5.root.HistOcc[:], ignore_columns=ignore_columns)
                        thresholds_masked_2 = np.ma.masked_array(in_file_2_h5.root.HistThresholdFitted[:], mask)
                        rel_bcid_2 = in_file_2_h5.root.HistRelBcid[0:16]
                    except tb.exceptions.NoSuchNodeError:
                        occupancy_masked_2 = np.zeros(shape=(336, 80, 2))
                        thresholds_masked_2 = np.zeros(shape=(336, 80))
                        rel_bcid_2 = np.zeros(shape=(16, ))
                    # plot the threshold distribution and the s curves
                    if local_configuration['create_plots']:
                        plotting.plot_three_way(hist=thresholds_masked_1 * 55.0, title='Threshold Fitted for 1. trigger, delay ' + str(delay_value), x_axis_title='threshold [e]', filename=output_pdf)
                        plotting.plot_relative_bcid(hist=rel_bcid_1, title='Relative BCID (former LVL1ID) for 1. trigger, delay = ' + str(delay_value), filename=output_pdf)
                        plotting.plot_three_way(hist=thresholds_masked_2 * 55.0, title='Threshold Fitted for 2. trigger, delay ' + str(delay_value), x_axis_title='threshold [e]', filename=output_pdf)
                        plotting.plot_relative_bcid(hist=rel_bcid_2, title='Relative BCID (former LVL1ID) for 2. trigger, delay = ' + str(delay_value), filename=output_pdf)
                    if local_configuration['create_plots']:
                        plotting.plot_scurves(occupancy_hist=occupancy_masked_1, title='S-Curves 1. trigger, delay ' + str(delay_value), scan_parameters=scan_parameters, scan_parameter_name='PlsrDAC', filename=output_pdf)
                        plotting.plot_scurves(occupancy_hist=occupancy_masked_2, title='S-Curves 2. trigger, delay ' + str(delay_value), scan_parameters=scan_parameters, scan_parameter_name='PlsrDAC', filename=output_pdf)
                    # fill the calibration data arrays
                    mean_threshold_calibration_1[delay_index] = np.ma.mean(thresholds_masked_1)
                    mean_threshold_rms_calibration_1[delay_index] = np.ma.std(thresholds_masked_1)
                    threshold_calibration_1[:, :, delay_index] = thresholds_masked_1.T
                    mean_threshold_calibration_2[delay_index] = np.ma.mean(thresholds_masked_2)
                    mean_threshold_rms_calibration_2[delay_index] = np.ma.std(thresholds_masked_2)
                    threshold_calibration_2[:, :, delay_index] = thresholds_masked_2.T
        progress_bar.update(delay_index)
    progress_bar.finish()

    # plot the parameter against delay plots
    if local_configuration['create_result_plots']:
        plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_calibration * 55.0, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Mean threshold [e]', log_x=False, filename=output_pdf)
        plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_calibration * 55.0, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Mean threshold [e]', log_x=True, filename=output_pdf)
        plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_rms_calibration * 55.0, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Threshold RMS [e]', log_x=False, filename=output_pdf)
        plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_rms_calibration * 55.0, title='Threshold as a function of the delay', x_label='delay [BCID]', y_label='Threshold RMS [e]', log_x=True, filename=output_pdf)
        if local_configuration['analysis_two_trigger']:
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_calibration_1 * 55.0, title='Threshold as a function of the delay, 1. trigger', x_label='delay [BCID]', y_label='Mean threshold [e]', log_x=False, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_calibration_1 * 55.0, title='Threshold as a function of the delay, 1. trigger', x_label='delay [BCID]', y_label='Mean threshold [e]', log_x=True, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_rms_calibration_1 * 55.0, title='Threshold as a function of the delay, 1. trigger', x_label='delay [BCID]', y_label='Threshold RMS [e]', log_x=False, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_rms_calibration_1 * 55.0, title='Threshold as a function of the delay, 1. trigger', x_label='delay [BCID]', y_label='Threshold RMS [e]', log_x=True, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_calibration_2 * 55.0, title='Threshold as a function of the delay, 2. trigger', x_label='delay [BCID]', y_label='Mean threshold [e]', log_x=False, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_calibration_2 * 55.0, title='Threshold as a function of the delay, 2. trigger', x_label='delay [BCID]', y_label='Mean threshold [e]', log_x=True, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_rms_calibration_2 * 55.0, title='Threshold as a function of the delay, 2. trigger', x_label='delay [BCID]', y_label='Threshold RMS [e]', log_x=False, filename=output_pdf)
            plotting.plot_scatter(x=local_configuration['delays'], y=mean_threshold_rms_calibration_2 * 55.0, title='Threshold as a function of the delay, 2. trigger', x_label='delay [BCID]', y_label='Threshold RMS [e]', log_x=True, filename=output_pdf)

        plotting.plot_scatter(x=local_configuration['delays'], y=mean_noise_calibration * 55.0, title='Noise as a function of the delay', x_label='delay [BCID]', y_label='Mean noise [e]', log_x=False, filename=output_pdf)
        plotting.plot_scatter(x=local_configuration['delays'], y=mean_noise_rms_calibration * 55.0, title='Noise as a function of the delay', x_label='delay [BCID]', y_label='Noise RMS [e]', log_x=False, filename=output_pdf)

    if local_configuration['create_plots'] or local_configuration['create_result_plots']:
        output_pdf.close()

    # store the calibration data into a hdf5 file as an easy to read table and as an array for quick data access
    with tb.open_file(output_h5_filename, mode="w") as out_file_h5:
        store_calibration_data_as_array(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration, mean_noise_calibration, mean_noise_rms_calibration, noise_calibration)
        store_calibration_data_as_table(out_file_h5, mean_threshold_calibration, mean_threshold_rms_calibration, threshold_calibration, mean_noise_calibration, mean_noise_rms_calibration, noise_calibration)


def reanalyze(fei4b=False):
    data_files = analysis_utils.get_data_file_names_from_scan_base(local_configuration['data_file'])
    import pprint
    data_files_par = analysis_utils.get_parameter_value_from_file_names(data_files, parameters='stability')
    pprint.pprint(data_files_par)
    scan_data_filenames = {}
    local_configuration['delays'] = []
    for file_name, parameter in data_files_par.items():
        scan_data_filenames[parameter['stability'][0]] = file_name
        local_configuration['delays'].append(parameter['stability'][0])
    local_configuration['stability'] = sorted(scan_data_filenames.keys())
    analyze_data(scan_data_filenames=scan_data_filenames, ignore_columns=local_configuration['ignore_columns'], fei4b=fei4b)


def mask_pixel(steps, shift, default=0, value=1, mask=None):

    def cartesian(arrays, out=None):
        arrays = [np.asarray(x) for x in arrays]
        dtype = arrays[0].dtype

        n = np.prod([x.size for x in arrays])
        if out is None:
            out = np.zeros([n, len(arrays)], dtype=dtype)

        m = n / arrays[0].size
        out[:, 0] = np.repeat(arrays[0], m)
        if arrays[1:]:
            cartesian(arrays[1:], out=out[0:m, 1:])
            for j in xrange(1, arrays[0].size):
                out[j * m:(j + 1) * m, 1:] = out[0:m, 1:]
        return out

    shape = (80, 336)
    mask_array = np.full(shape, fill_value=default, dtype=np.uint8)
    # FE columns and rows are starting from 1
    odd_columns = np.arange(0, 80, 2)
    even_columns = np.arange(1, 80, 2)
    odd_rows = np.arange((0 + shift) % steps, 336, steps)
    even_row_offset = (int(math.floor(steps / 2) + shift)) % steps
    even_rows = np.arange(0 + even_row_offset, 336, steps)
    odd_col_row = cartesian((odd_columns, odd_rows))  # get any combination of column and row, no for loop needed
    even_col_row = cartesian((even_columns, even_rows))
    mask_array[odd_col_row[:, 0], odd_col_row[:, 1]] = value  # advanced indexing
    mask_array[even_col_row[:, 0], even_col_row[:, 1]] = value
    if mask is not None:
        mask_array = np.ma.array(mask_array, mask=mask, fill_value=default)
        mask_array = mask_array.filled()
    return mask_array


def mask_columns(pixel_array, ignore_columns):
    idx = np.array(ignore_columns) - 1  # from FE to Array columns
    m = np.zeros_like(pixel_array)
    m[:, idx] = 1
    return np.ma.masked_array(pixel_array, m)


if __name__ == "__main__":
    startTime = datetime.now()
#     reanalyze()
    logging.info('Taking threshold data for following delay: %s' % str(local_configuration['delays']))
    scan_data_filenames = {}
    scan_threshold_fast = FastThresholdScan(**configuration.scc112_configuration)
    for i, delay_value in enumerate(local_configuration['delays']):
        logging.info('Taking threshold data for delay %s' % str(delay_value))
        command = scan_threshold_fast.register.get_commands("CAL")[0] + scan_threshold_fast.register.get_commands("zeros", length=40)[0] + scan_threshold_fast.register.get_commands("LV1")[0] + scan_threshold_fast.register.get_commands("zeros", length=delay_value)[0] + scan_threshold_fast.register.get_commands("CAL")[0] + scan_threshold_fast.register.get_commands("zeros", length=40)[0] + scan_threshold_fast.register.get_commands("LV1")[0] + scan_threshold_fast.register.get_commands("zeros", length=delay_value)[0]
        scan_threshold_fast.scan_id = 'test_threshold_stability_' + str(delay_value)
        scan_threshold_fast.start(configure=True, scan_parameter_range=(0, 70), scan_parameter_stepsize=2, search_distance=10, minimum_data_points=15, ignore_columns=local_configuration['ignore_columns'], command=command)
        scan_threshold_fast.stop()
        scan_data_filenames[delay_value] = scan_threshold_fast.scan_data_filename

    logging.info("Measurement finished in " + str(datetime.now() - startTime))

#     analyze and plot the data from all scans
    analyze_data(scan_data_filenames=scan_data_filenames, ignore_columns=local_configuration['ignore_columns'], fei4b=scan_threshold_fast.register.fei4b)

    logging.info("Finished!")
