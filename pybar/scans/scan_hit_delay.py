''' This script changes the injection delay of the internal PlsrDAC (with global register PlsrDelay or PlsrIdacRamp) and measures the mean BCID for each pixel.
The mean BCID changes for an increasing injection delay every 25 ns due to the clock in an S-curve like shape. 
The mu of the S-curves is monitored for different charges injected in an outer loop (but wothout S-Curve fit, resolution of mu is PlsrDAC delay step). 
The change of the mu as a function of the charge is the timewalk that is calculated for each pixel. 
The absolute value of mu for the same mean BCID gives the hit delay for the pixel.
Time walk and hit delay are calculated and plotted in different ways.
The PlsrDAC and injection delay values should be chosen equidistant.
'''
import logging
import progressbar
import re
import tables as tb
import numpy as np
from scipy.optimize import curve_fit
from scipy.interpolate import interp1d
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.analysis.analysis_utils import get_hits_of_scan_parameter, hist_1d_index, hist_3d_index, get_scan_parameter, get_mean_from_histogram
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_scurves, plotThreeWay


class HitDelayScan(Fei4RunBase):
    '''Standard Hit Delay Scan

    Implementation of a hit delay scan.
    '''
    _default_run_conf = {
        "mask_steps": 3,  # number of injections per PlsrDAC step
        "n_injections": 20,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', range(55, 801, 15)), ('PlsrDelay', range(1, 63))],  # the scan parameter + the scan parameter range, only one scan parameter is supported
        "step_size": 1,  # step size of the PlsrDelay during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("WrFrontEnd", same_mask_for_all_dc=True, name='C_High'))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        delay_parameter_name = self.scan_parameters._fields[1]
        logging.info("Scanning PlsrDAC = %s and %s = %s", str(self.scan_parameters[0]), delay_parameter_name, str(self.scan_parameters[1]))

        plsr_dac_values = self.scan_parameters.PlsrDAC[:]  # create deep copy of scan_parameters, they are overwritten in self.readout
        delay_parameter_values = self.scan_parameters.PlsrDelay[:]  # create deep copy of scan_parameters, they are overwritten in self.readout

        for plsr_dac_value in plsr_dac_values:
            # Change the Plsr DAC parameter
            commands = []
            commands.extend(self.register.get_commands("ConfMode"))
            self.register.set_global_register_value('PlsrDAC', plsr_dac_value)
            commands.extend(self.register.get_commands("WrRegister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)
            for delay_parameter_value in delay_parameter_values:  # Loop over the Plsr delay parameter
                if self.stop_run.is_set():
                    break
                logging.info('Scan step: PlsrDAC %s, %s %d', plsr_dac_value, delay_parameter_name, delay_parameter_value)

                # Change the Plsr delay parameter
                commands = []
                commands.extend(self.register.get_commands("ConfMode"))
                self.register.set_global_register_value(delay_parameter_name, delay_parameter_value)
                commands.extend(self.register.get_commands("WrRegister", name=[delay_parameter_name]))
                self.register_utils.send_commands(commands)

                with self.readout(plsr_dac_value, delay_parameter_value):
                    cal_lvl1_command = self.register.get_commands("CAL")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("LV1")[0]
                    scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

    def analyze(self):
    #         plsr_dac_slope = self.register.calibration_parameters['C_Inj_High'] * self.register.calibration_parameters['Vcal_Coeff_1']
        plsr_dac_slope = 55.

        # Interpret data and create hit table
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=False) as analyze_raw_data:
            analyze_raw_data.create_occupancy_hist = False  # too many scan parameters to do in ram histograming
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpreter.set_warning_output(False)  # a lot of data produces unknown words
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()

        # Create relative BCID and mean relative BCID histogram for each pixel / injection delay / PlsrDAC setting
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="w") as out_file_h5:
            hists_folder = out_file_h5.create_group(out_file_h5.root, 'PixelHistsMeanRelBcid')
            hists_folder_2 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsRelBcid')
            hists_folder_3 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsTot')
            hists_folder_4 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsMeanTot')
            hists_folder_5 = out_file_h5.create_group(out_file_h5.root, 'HistsTot')

            def store_bcid_histograms(bcid_array, tot_array, tot_pixel_array):
                logging.debug('Store histograms for PlsrDAC ' + str(old_plsr_dac))
                bcid_mean_array = np.average(bcid_array, axis=3, weights=range(0, 16)) * sum(range(0, 16)) / np.sum(bcid_array, axis=3).astype('f4')  # calculate the mean BCID per pixel and scan parameter
                tot_pixel_mean_array = np.average(tot_pixel_array, axis=3, weights=range(0, 16)) * sum(range(0, 16)) / np.sum(tot_pixel_array, axis=3).astype('f4')  # calculate the mean tot per pixel and scan parameter
                bcid_mean_result = np.swapaxes(bcid_mean_array, 0, 1)
                bcid_result = np.swapaxes(bcid_array, 0, 1)
                tot_pixel_result = np.swapaxes(tot_pixel_array, 0, 1)
                tot_mean_pixel_result = np.swapaxes(tot_pixel_mean_array, 0, 1)

                out = out_file_h5.createCArray(hists_folder, name='HistPixelMeanRelBcidPerDelayPlsrDac_%03d' % old_plsr_dac, title='Mean relative BCID hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(bcid_mean_result.dtype), shape=bcid_mean_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out.attrs.dimensions = 'column, row, injection delay'
                out.attrs.injection_delay_values = injection_delay
                out[:] = bcid_mean_result
                out_2 = out_file_h5.createCArray(hists_folder_2, name='HistPixelRelBcidPerDelayPlsrDac_%03d' % old_plsr_dac, title='Relative BCID hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(bcid_result.dtype), shape=bcid_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_2.attrs.dimensions = 'column, row, injection delay, relative bcid'
                out_2.attrs.injection_delay_values = injection_delay
                out_2[:] = bcid_result
                out_3 = out_file_h5.createCArray(hists_folder_3, name='HistPixelTotPerDelayPlsrDac_%03d' % old_plsr_dac, title='Tot hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(tot_pixel_result.dtype), shape=tot_pixel_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_3.attrs.dimensions = 'column, row, injection delay'
                out_3.attrs.injection_delay_values = injection_delay
                out_3[:] = tot_pixel_result
                out_4 = out_file_h5.createCArray(hists_folder_4, name='HistPixelMeanTotPerDelayPlsrDac_%03d' % old_plsr_dac, title='Mean tot hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(tot_mean_pixel_result.dtype), shape=tot_mean_pixel_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_4.attrs.dimensions = 'column, row, injection delay'
                out_4.attrs.injection_delay_values = injection_delay
                out_4[:] = tot_mean_pixel_result
                out_5 = out_file_h5.createCArray(hists_folder_5, name='HistTotPlsrDac_%03d' % old_plsr_dac, title='Tot histogram for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(tot_array.dtype), shape=tot_array.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_5.attrs.injection_delay_values = injection_delay
                out_5[:] = tot_array

            old_plsr_dac = None

            # Get scan parameters from interpreted file
            with tb.open_file(self.output_filename + '_interpreted.h5', 'r') as in_file_h5:
                scan_parameters_dict = get_scan_parameter(in_file_h5.root.meta_data[:])
                plsr_dac = scan_parameters_dict['PlsrDAC']
                hists_folder._v_attrs.plsr_dac_values = plsr_dac
                hists_folder_2._v_attrs.plsr_dac_values = plsr_dac
                hists_folder_3._v_attrs.plsr_dac_values = plsr_dac
                hists_folder_4._v_attrs.plsr_dac_values = plsr_dac
                injection_delay = scan_parameters_dict[scan_parameters_dict.keys()[1]]  # injection delay par name is unknown and should  be in the inner loop
                scan_parameters = scan_parameters_dict.keys()

            bcid_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.int16)  # bcid array of actual PlsrDAC
            tot_pixel_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.int16)  # tot pixel array of actual PlsrDAC
            tot_array = np.zeros((16,), dtype=np.int32)  # tot array of actual PlsrDAC

            logging.info('Store histograms for PlsrDAC values ' + str(plsr_dac))
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=max(plsr_dac) - min(plsr_dac), term_width=80)

            for index, (parameters, hits) in enumerate(get_hits_of_scan_parameter(self.output_filename + '_interpreted.h5', scan_parameters, chunk_size=1.5e7)):
                if index == 0:
                    progress_bar.start()  # start after the event index is created to get reasonable ETA
                actual_plsr_dac, actual_injection_delay = parameters[0], parameters[1]
                column, row, rel_bcid, tot = hits['column'] - 1, hits['row'] - 1, hits['relative_BCID'], hits['tot']
                bcid_array_fast = hist_3d_index(column, row, rel_bcid, shape=(80, 336, 16))
                tot_pixel_array_fast = hist_3d_index(column, row, tot, shape=(80, 336, 16))
                tot_array_fast = hist_1d_index(tot, shape=(16,))

                if old_plsr_dac != actual_plsr_dac:  # Store the data of the actual PlsrDAC value
                    if old_plsr_dac:  # Special case for the first PlsrDAC setting
                        store_bcid_histograms(bcid_array, tot_array, tot_pixel_array)
                        progress_bar.update(old_plsr_dac - min(plsr_dac))
                    # Reset the histrograms for the next PlsrDAC setting
                    bcid_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.int8)
                    tot_pixel_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.int8)
                    tot_array = np.zeros((16,), dtype=np.int32)
                    old_plsr_dac = actual_plsr_dac
                injection_delay_index = np.where(np.array(injection_delay) == actual_injection_delay)[0][0]
                bcid_array[:, :, injection_delay_index, :] += bcid_array_fast
                tot_pixel_array[:, :, injection_delay_index, :] += tot_pixel_array_fast
                tot_array += tot_array_fast
            store_bcid_histograms(bcid_array, tot_array, tot_pixel_array)  # save histograms of last PlsrDAC setting
            progress_bar.finish()

        # Take the mean relative BCID histogram of each PlsrDAC value and calculate the delay for each pixel
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="r") as in_file_h5:
            # Create temporary result data structures
            plsr_dac_values = in_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values
            timewalk = np.zeros(shape=(80, 336, len(plsr_dac_values)), dtype=np.int8)  # result array
            tot = np.zeros(shape=(len(plsr_dac_values),), dtype=np.float16)  # result array
            hit_delay = np.zeros(shape=(80, 336, len(plsr_dac_values)), dtype=np.int8)  # result array
            min_rel_bcid = np.zeros(shape=(80, 336), dtype=np.int8)  # Temp array to make sure that the Scurve from the same BCID is used
            delay_calibration_data = []
            delay_calibration_data_error = []

            # Calculate the minimum BCID. That is chosen to calculate the hit delay. Calculation does not have to work.
            plsr_dac_min = min(plsr_dac_values)
            rel_bcid_min_injection = in_file_h5.get_node(in_file_h5.root.PixelHistsMeanRelBcid, 'HistPixelMeanRelBcidPerDelayPlsrDac_%03d' % plsr_dac_min)
            injection_delays = np.array(rel_bcid_min_injection.attrs.injection_delay_values)
            injection_delay_min = np.where(injection_delays == np.amax(injection_delays))[0][0]
            bcid_min = int(round(np.mean(np.ma.masked_array(rel_bcid_min_injection[:, :, injection_delay_min], np.isnan(rel_bcid_min_injection[:, :, injection_delay_min]))))) - 1

            # Info output with progressbar
            logging.info('Create timewalk info for PlsrDACs ' + str(plsr_dac_values))
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(plsr_dac_values), term_width=80)
            progress_bar.start()

            for index, node in enumerate(in_file_h5.root.PixelHistsMeanRelBcid):  # loop over all mean relative BCID hists for all PlsrDAC values
                # Select the S-curves
                pixel_data = node[:, :, :]
                pixel_data_fixed = pixel_data.reshape(pixel_data.shape[0] * pixel_data.shape[1] * pixel_data.shape[2])  # Reshape for interpolation of Nans
                nans, x = np.isnan(pixel_data_fixed), lambda z: z.nonzero()[0]
                pixel_data_fixed[nans] = np.interp(x(nans), x(~nans), pixel_data_fixed[~nans])  # interpolate Nans
                pixel_data_fixed = pixel_data_fixed.reshape(pixel_data.shape[0], pixel_data.shape[1], pixel_data.shape[2])  # Reshape after interpolation of Nans
                pixel_data_round = np.round(pixel_data_fixed)
                pixel_data_round_diff = np.diff(pixel_data_round, axis=2)
                index_sel = np.where(np.logical_and(pixel_data_round_diff > 0., np.isfinite(pixel_data_round_diff)))

                # Temporary result histograms to be filled
                first_scurve_mean = np.zeros(shape=(80, 336), dtype=np.int8)  # the first S-curve in the data for the lowest injection (for time walk)
                second_scurve_mean = np.zeros(shape=(80, 336), dtype=np.int8)  # the second S-curve in the data (to calibrate one inj. delay step)
                a_scurve_mean = np.zeros(shape=(80, 336), dtype=np.int8)  # the mean of the S-curve at a given rel. BCID (for hit delay)

                # Loop over the S-curve means
                for (row_index, col_index, delay_index) in np.column_stack((index_sel)):
                    delay = injection_delays[delay_index]
                    if first_scurve_mean[col_index, row_index] == 0:
                        if delay_index == 0:  # ignore the first index, can be wrong due to nan filling
                            continue
                        if pixel_data_round[row_index, col_index, delay] >= min_rel_bcid[col_index, row_index]:  # make sure to always use the data of the same BCID
                            first_scurve_mean[col_index, row_index] = delay
                            min_rel_bcid[col_index, row_index] = pixel_data_round[row_index, col_index, delay]
                    elif second_scurve_mean[col_index, row_index] == 0 and (delay - first_scurve_mean[col_index, row_index]) > 20:  # minimum distance 10, can otherwise be data 'jitter'
                        second_scurve_mean[col_index, row_index] = delay
                    if pixel_data_round[row_index, col_index, delay] == bcid_min:
                        if a_scurve_mean[col_index, row_index] == 0:
                            a_scurve_mean[col_index, row_index] = delay

                plsr_dac = int(re.search(r'\d+', node.name).group())
                plsr_dac_index = np.where(plsr_dac_values == plsr_dac)[0][0]
                if (np.count_nonzero(first_scurve_mean) - np.count_nonzero(a_scurve_mean)) > 1e3:
                    logging.warning("The common BCID to find the absolute hit delay was set wrong! Hit delay calculation will be wrong.")
                selection = (second_scurve_mean - first_scurve_mean)[np.logical_and(second_scurve_mean > 0, first_scurve_mean < second_scurve_mean)]
                delay_calibration_data.append(np.mean(selection))
                delay_calibration_data_error.append(np.std(selection))
                # Store the actual PlsrDAC data into result hist
                timewalk[:, :, plsr_dac_index] = first_scurve_mean  # Save the plsr delay of first s-curve (for time walk calc.)
                hit_delay[:, :, plsr_dac_index] = a_scurve_mean  # Save the plsr delay of s-curve of fixed rel. BCID (for hit delay calc.)
                progress_bar.update(index)

            for index, node in enumerate(in_file_h5.root.HistsTot):  # loop over tot hist for all PlsrDAC values
                plsr_dac = int(re.search(r'\d+', node.name).group())
                plsr_dac_index = np.where(plsr_dac_values == plsr_dac)[0][0]
                tot_data = node[:]
                tot[plsr_dac_index] = get_mean_from_histogram(tot_data, range(16))

            # Calibrate the step size of the injection delay by the average difference of two Scurves of all pixels
            delay_calibration_mean = np.mean(np.array(delay_calibration_data[2:])[np.isfinite(np.array(delay_calibration_data[2:]))])
            delay_calibration, delay_calibration_error = curve_fit(lambda x, par: (par), injection_delays, delay_calibration_data, p0=delay_calibration_mean, sigma=delay_calibration_data_error, absolute_sigma=True)
            delay_calibration, delay_calibration_error = delay_calibration[0], delay_calibration_error[0][0]

            progress_bar.finish()

        #  Save time walk / hit delay hists
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="r+") as out_file_h5:
            timewalk_result = np.swapaxes(timewalk, 0, 1)
            hit_delay_result = np.swapaxes(hit_delay, 0, 1)
            out = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTimewalkPerPlsrDac', title='Time walk per pixel and PlsrDAC', atom=tb.Atom.from_dtype(timewalk_result.dtype), shape=timewalk_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out_2 = out_file_h5.createCArray(out_file_h5.root, name='HistPixelHitDelayPerPlsrDac', title='Hit delay per pixel and PlsrDAC', atom=tb.Atom.from_dtype(hit_delay_result.dtype), shape=hit_delay_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out_3 = out_file_h5.createCArray(out_file_h5.root, name='HistTotPerPlsrDac', title='Tot per PlsrDAC', atom=tb.Atom.from_dtype(tot.dtype), shape=tot.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out.attrs.dimensions = 'column, row, PlsrDAC'
            out.attrs.delay_calibration = delay_calibration
            out.attrs.delay_calibration_error = delay_calibration_error
            out.attrs.plsr_dac_values = plsr_dac_values
            out_2.attrs.dimensions = 'column, row, PlsrDAC'
            out_2.attrs.delay_calibration = delay_calibration
            out_2.attrs.delay_calibration_error = delay_calibration_error
            out_2.attrs.plsr_dac_values = plsr_dac_values
            out_3.attrs.dimensions = 'PlsrDAC'
            out_3.attrs.plsr_dac_values = plsr_dac_values
            out[:] = timewalk_result
            out_2[:] = hit_delay_result
            out_3[:] = tot

        # Mask the pixels that have non valid data an create plot with the relative time walk for all pixels
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="r") as in_file_h5:
            def plot_hit_delay(hist_3d, charge_values, title, xlabel, ylabel, filename, threshold=None, tot_values=None):
                # Interpolate tot values for second tot axis
                interpolation = interp1d(tot_values, charge_values, kind='slinear', bounds_error=True)
                tot = np.arange(16)
                tot = tot[np.logical_and(tot >= np.amin(tot_values), tot <= np.amax(tot_values))]

                array = np.transpose(hist_3d, axes=(2, 1, 0)).reshape(hist_3d.shape[2], hist_3d.shape[0] * hist_3d.shape[1])
                y = np.mean(array, axis=1)
                y_err = np.std(array, axis=1)

                fig = Figure()
                FigureCanvas(fig)
                ax = fig.add_subplot(111)
                fig.patch.set_facecolor('white')
                ax.grid(True)
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_xlim((0, np.amax(charge_values)))
                ax.set_ylim((np.amin(y - y_err), np.amax(y + y_err)))
                ax.plot(charge_values, y, '.-', color='black', label=title)
                if threshold is not None:
                    ax.plot([threshold, threshold], [np.amin(y - y_err), np.amax(y + y_err)], linestyle='--', color='black', label='Threshold\n%d e' % (threshold))
                ax.fill_between(charge_values, y - y_err, y + y_err, color='gray', alpha=0.5, facecolor='gray', label='RMS')
                ax2 = ax.twiny()
                ax2.set_xlabel("ToT")

                ticklab = ax2.xaxis.get_ticklabels()[0]
                trans = ticklab.get_transform()
                ax2.xaxis.set_label_coords(np.amax(charge_values), 1, transform=trans)
                ax2.set_xlim(ax.get_xlim())
                ax2.set_xticks(interpolation(tot))
                ax2.set_xticklabels([str(int(i)) for i in tot])
                ax.text(0.5, 1.07, title, horizontalalignment='center', fontsize=18, transform=ax2.transAxes)
                ax.legend()
                filename.savefig(fig)
            plsr_dac_values = in_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values
            delay_calibration = in_file_h5.root.HistPixelHitDelayPerPlsrDac._v_attrs.delay_calibration
            charge_values = np.array(plsr_dac_values)[:] * plsr_dac_slope
            hist_timewalk = in_file_h5.root.HistPixelTimewalkPerPlsrDac[:, :, :]
            hist_hit_delay = in_file_h5.root.HistPixelHitDelayPerPlsrDac[:, :, :]
            tot = in_file_h5.root.HistTotPerPlsrDac[:]

            hist_rel_timewalk = np.amax(hist_timewalk, axis=2)[:, :, np.newaxis] - hist_timewalk
            hist_rel_hit_delay = np.mean(hist_hit_delay[:, :, -1]) - hist_hit_delay

            # Create mask and apply for bad pixels
            mask = np.ones(hist_rel_timewalk.shape, dtype=np.int8)
            for node in in_file_h5.root.PixelHistsMeanRelBcid:
                pixel_data = node[:, :, :]
                a = (np.sum(pixel_data, axis=2))
                mask[np.isfinite(a), :] = 0

            hist_rel_timewalk = np.ma.masked_array(hist_rel_timewalk, mask)
            hist_hit_delay = np.ma.masked_array(hist_hit_delay, mask)

            output_pdf = PdfPages(self.output_filename + '.pdf')
            plot_hit_delay(np.swapaxes(hist_rel_timewalk, 0, 1) * 25. / delay_calibration, charge_values=charge_values, title='Time walk', xlabel='Charge [e]', ylabel='Time walk [ns]', filename=output_pdf, threshold=np.amin(charge_values), tot_values=tot)
            plot_hit_delay(np.swapaxes(hist_rel_hit_delay, 0, 1) * 25. / delay_calibration, charge_values=charge_values, title='Hit delay', xlabel='Charge [e]', ylabel='Hit delay [ns]', filename=output_pdf, threshold=np.amin(charge_values), tot_values=tot)
            plot_scurves(np.swapaxes(hist_rel_timewalk, 0, 1), scan_parameters=charge_values, title='Timewalk of the FE-I4', scan_parameter_name='Charge [e]', ylabel='Timewalk [ns]', min_x=0, y_scale=25. / delay_calibration, filename=output_pdf)
            plot_scurves(np.swapaxes(hist_hit_delay[:, :, :], 0, 1), scan_parameters=charge_values, title='Hit delay (T0) with internal charge injection\nof the FE-I4', scan_parameter_name='Charge [e]', ylabel='Hit delay [ns]', min_x=0, y_scale=25. / delay_calibration, filename=output_pdf)

            for i in [0, 1, len(plsr_dac_values) / 4, len(plsr_dac_values) / 2, -1]:  # plot 2d hist at min, 1/4, 1/2, max PlsrDAC setting
                plotThreeWay(hist_rel_timewalk[:, :, i] * 25. / delay_calibration, title='Time walk at %.0f e' % (charge_values[i]), x_axis_title='Time walk [ns]', filename=output_pdf)
                plotThreeWay(hist_hit_delay[:, :, i] * 25. / delay_calibration, title='Hit delay (T0) with internal charge injection at %.0f e' % (charge_values[i]), x_axis_title='Hit delay [ns]', minimum=np.amin(hist_hit_delay[:, :, i]), maximum=np.amax(hist_hit_delay[:, :, i]), filename=output_pdf)
            output_pdf.close()


if __name__ == "__main__":
    RunManager('..\configuration.yaml').run_run(HitDelayScan)
