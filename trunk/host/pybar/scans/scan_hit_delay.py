''' This script changes the injection delay of the internal PlsrDAC (with global register PlsrDelay or PlsrIdacRamp) and measures the mean BCID for each pixel.
The mean BCID changes for an increasing injection delay every 25 ns due to the clock in an S-curve like shape. 
The mu of the S-curves is monitored for different charges injected in an outer loop. The change of the mu as a function of the charge 
is the timewalk that is calculated for each pixel. The absolute value of mu for the same mean BCID gives the hit delay for the pixel.
Time walk and hit delay are calculated and plotted in different ways.
'''
import logging
import progressbar
import re
import tables as tb

from pybar.fei4.register_utils import invert_pixel_mask
from pybar.fei4_run_base import Fei4RunBase
from pybar.fei4.register_utils import scan_loop
from pybar.run_manager import RunManager
from pybar.analysis.analysis_utils import get_hits_of_scan_parameter, hist_3d_index, get_scan_parameter, ETA
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.plotting.plotting import plot_scurves

import numpy as np


class HitDelayScan(Fei4RunBase):
    '''Standard Hit Delay Scan

    Implementation of a hit delay scan.
    '''
    _default_run_conf = {
        "mask_steps": 3,  # number of injections per PlsrDAC step
        "n_injections": 20,  # number of injections per PlsrDAC step
        "scan_parameters": [('PlsrDAC', range(50, 250, 8)), ('PlsrDelay', range(1, 43))],  # the scan parameter + the scan parameter range, only one scan parameter is supported
        "step_size": 1,  # step size of the PlsrDelay during scan
        "use_enable_mask": False,  # if True, use Enable mask during scan, if False, all pixels will be enabled
        "enable_shift_masks": ["Enable", "C_High", "C_Low"],  # enable masks shifted during scan
        "disable_shift_masks": [],  # disable masks shifted during scan
        "pulser_dac_correction": False,  # PlsrDAC correction for each double column
        "pulser_dac_slope": 55.  # PlsrDAC calibration (charge / plsrDAC), usually 55.
    }

    def configure(self):
        commands = []
        commands.extend(self.register.get_commands("confmode"))
        # C_Low
        if "C_Low".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_Low', 1)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_Low'))
        else:
            self.register.set_pixel_register_value('C_Low', 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_Low'))
        # C_High
        if "C_High".lower() in map(lambda x: x.lower(), self.enable_shift_masks):
            self.register.set_pixel_register_value('C_High', 1)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_High'))
        else:
            self.register.set_pixel_register_value('C_High', 0)
            commands.extend(self.register.get_commands("wrfrontend", same_mask_for_all_dc=True, name='C_High'))
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        delay_parameter_name = self.scan_parameters._fields[1]
        logging.info("Scanning PlsrDAC = %s and %s = %s" % (str(self.scan_parameters[0]), delay_parameter_name, str(self.scan_parameters[1])))

        plsr_dac_values = self.scan_parameters.PlsrDAC[:]  # create deep copy of scan_parameters, they are overwritten in self.readout
        delay_parameter_values = self.scan_parameters.PlsrDelay[:]  # create deep copy of scan_parameters, they are overwritten in self.readout

        for plsr_dac_value in plsr_dac_values:
            # Change the Plsr DAC parameter
            commands = []
            commands.extend(self.register.get_commands("confmode"))
            self.register.set_global_register_value('PlsrDAC', plsr_dac_value)
            commands.extend(self.register.get_commands("wrregister", name=['PlsrDAC']))
            self.register_utils.send_commands(commands)
            for delay_parameter_value in delay_parameter_values:  # Loop over the Plsr delay parameter
                if self.stop_run.is_set():
                    break
                logging.info('Scan step: PlsrDAC %s, %s %d' % (plsr_dac_value, delay_parameter_name, delay_parameter_value))

                # Change the Plsr delay parameter
                commands = []
                commands.extend(self.register.get_commands("confmode"))
                self.register.set_global_register_value(delay_parameter_name, delay_parameter_value)
                commands.extend(self.register.get_commands("wrregister", name=[delay_parameter_name]))
                self.register_utils.send_commands(commands)

                with self.readout(plsr_dac_value, delay_parameter_value):
                    cal_lvl1_command = self.register.get_commands("cal")[0] + self.register.get_commands("zeros", length=40)[0] + self.register.get_commands("lv1")[0]
                    scan_loop(self, cal_lvl1_command, repeat_command=self.n_injections, use_delay=True, mask_steps=self.mask_steps, enable_mask_steps=None, enable_double_columns=None, same_mask_for_all_dc=True, eol_function=None, digital_injection=False, enable_shift_masks=self.enable_shift_masks, disable_shift_masks=self.disable_shift_masks, restore_shift_masks=False, mask=invert_pixel_mask(self.register.get_pixel_register_value('Enable')) if self.use_enable_mask else None, double_column_correction=self.pulser_dac_correction)

    def analyze(self):
        # Interpret data and create hit table
        with AnalyzeRawData(raw_data_file=self.output_filename, create_pdf=False) as analyze_raw_data:
            analyze_raw_data.create_occupancy_hist = False  # too many scan parameters to do in ram histograming
            analyze_raw_data.create_hit_table = True
            analyze_raw_data.interpret_word_table()
            analyze_raw_data.interpreter.print_summary()

        # Create relative BCID and mean relative BCID histogram for each pixel / injection delay / PlsrDAC setting
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="w") as out_file_h5:
            hists_folder = out_file_h5.create_group(out_file_h5.root, 'PixelHistsMeanRelBcid')
            hists_folder_2 = out_file_h5.create_group(out_file_h5.root, 'PixelHistsRelBcid')

            def store_bcid_histograms(bcid_array):
                logging.info('Store relative BCID histogram for PlsrDAC ' + str(old_plsr_dac))
                bcid_mean_array = np.average(bcid_array, axis=3, weights=range(0, 16)) * sum(range(0, 16)) / np.sum(bcid_array, axis=3)  # calculate the mean BCID per pixel and scan parameter
                bcid_mean_result = np.swapaxes(bcid_mean_array, 0, 1)
                bcid_result = np.swapaxes(bcid_array, 0, 1)
                out = out_file_h5.createCArray(hists_folder, name='HistPixelMeanRelBcidPerDelayPlsrDac_%03d' % old_plsr_dac, title='Mean relative BCID hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(bcid_mean_result.dtype), shape=bcid_mean_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out.attrs.dimensions = 'column, row, injection delay'
                out.attrs.injection_delay_values = injection_delay
                out[:] = bcid_mean_result
                out_2 = out_file_h5.createCArray(hists_folder_2, name='HistPixelRelBcidPerDelayPlsrDac_%03d' % old_plsr_dac, title='Relative BCID hist per pixel and different PlsrDAC delays for PlsrDAC ' + str(old_plsr_dac), atom=tb.Atom.from_dtype(bcid_result.dtype), shape=bcid_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_2.attrs.dimensions = 'column, row, injection delay, relative bcid'
                out_2[:] = bcid_result

            old_plsr_dac = None

            with tb.open_file(self.output_filename + '_interpreted.h5', 'r') as in_file_h5:
                scan_parameters_dict = get_scan_parameter(in_file_h5.root.meta_data[:])
                plsr_dac = scan_parameters_dict['PlsrDAC']
                hists_folder._v_attrs.plsr_dac_values = plsr_dac
                hists_folder_2._v_attrs.plsr_dac_values = plsr_dac
                injection_delay = scan_parameters_dict[scan_parameters_dict.keys()[1]]  # injection delay par is unknown but should  be in the inner loop
                injection_delay_step_size = injection_delay[1] - injection_delay[0]
                scan_parameters = scan_parameters_dict.keys()

            bcid_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.int8)  # bcid array of actual PlsrDAC

            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', ETA()], maxval=max(plsr_dac))
            progress_bar.start()

            for parameters, hits in get_hits_of_scan_parameter(self.output_filename + '_interpreted.h5', scan_parameters, verbosity=1, chunk_size=1e7):
                actual_plsr_dac, actual_injection_delay = parameters[0], parameters[1]
                column, row, rel_bcid = hits['column'] - 1, hits['row'] - 1, hits['relative_BCID']
                bcid_array_fast = hist_3d_index(column, row, rel_bcid, shape=(80, 336, 16))

                if old_plsr_dac != actual_plsr_dac:
                    if old_plsr_dac:
                        store_bcid_histograms(bcid_array)
                        progress_bar.update(old_plsr_dac - min(plsr_dac))
                    bcid_array = np.zeros((80, 336, len(injection_delay), 16), dtype=np.int8)
                    old_plsr_dac = actual_plsr_dac
                bcid_array[:, :, (actual_injection_delay - min(injection_delay)) / injection_delay_step_size, :] += bcid_array_fast
            else:  # save last histogram
                store_bcid_histograms(bcid_array)
            progress_bar.finish()

        # Take the mean relative BCID histogram of each PlsrDAC value and calculate the delay for each pixel
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="r") as in_file_h5:
            plsr_dac_values = in_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values

            plsr_dac_min = min(plsr_dac_values)
            plsr_dac_stepsize = plsr_dac_values[1] - plsr_dac_values[0]
            timewalk = np.zeros(shape=(80, 336, len(plsr_dac_values)), dtype=np.int8)

            min_rel_bcid = np.zeros(shape=(80, 336), dtype=np.int8)

            for node in in_file_h5.root.PixelHistsMeanRelBcid:
                plsr_dac = int(re.search(r'\d+', node.name).group())
                logging.info('Create timewalk info for PlsrDAC ' + str(plsr_dac))
                pixel_data = node[:, :, :]
                pixel_data_round = np.round(pixel_data)
                pixel_data_round_diff = np.diff(pixel_data_round, axis=2)

                index_sel = np.where(pixel_data_round_diff > 0.)

                first_scurve_mean = np.zeros(shape=(80, 336), dtype=np.int8)
                second_scurve_mean = np.zeros(shape=(80, 336), dtype=np.int8)

                for bcid_jump in np.column_stack((index_sel)):
                    if pixel_data_round[bcid_jump[0], bcid_jump[1], bcid_jump[2]] and pixel_data_round[bcid_jump[0], bcid_jump[1], bcid_jump[2]] >= min_rel_bcid[bcid_jump[1], bcid_jump[0]]:
                        if first_scurve_mean[bcid_jump[1], bcid_jump[0]] == 0:
                            first_scurve_mean[bcid_jump[1], bcid_jump[0]] = bcid_jump[2]
                            min_rel_bcid[bcid_jump[1], bcid_jump[0]] = pixel_data_round[bcid_jump[0], bcid_jump[1], bcid_jump[2]]
                        elif second_scurve_mean[bcid_jump[1], bcid_jump[0]] == 0:
                            second_scurve_mean[bcid_jump[1], bcid_jump[0]] = bcid_jump[2]
                timewalk[:, :, (plsr_dac - plsr_dac_min) / plsr_dac_stepsize] = first_scurve_mean

        # Save the absolute time-walk (=hit delay)
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="r+") as out_file_h5:
            timewalk_result = np.swapaxes(timewalk, 0, 1)
            out = out_file_h5.createCArray(out_file_h5.root, name='HistPixelTimewalkPerPlsrDac', title='Timewalk per pixel and PlsrDAC', atom=tb.Atom.from_dtype(timewalk_result.dtype), shape=timewalk_result.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            out.attrs.dimensions = 'column, row, PlsrDAC'
            out.attrs.plsr_dac_values = plsr_dac_values
            out[:] = timewalk_result

        # Mask the pixels that have non valid data an create plot with the relative time walk for all pixels
        with tb.open_file(self.output_filename + '_analyzed.h5', mode="r") as in_file_h5:
            plsr_dac_values = in_file_h5.root.PixelHistsMeanRelBcid._v_attrs.plsr_dac_values
            mask = np.ones(shape=(336, 80), dtype=np.int8)
            for node in in_file_h5.root.PixelHistsMeanRelBcid:
                pixel_data = node[:, :, :]
                mask[np.where(np.isfinite(np.sum(pixel_data, axis=2)))] = 0
            charge_values = np.array(in_file_h5.root.HistPixelTimewalkPerPlsrDac.attrs.plsr_dac_values)[:] * 55
            hist_timewalk = in_file_h5.root.HistPixelTimewalkPerPlsrDac[:, :, :]
            hist_rel_timewalk = np.amax(hist_timewalk, axis=2)[:, :, np.newaxis] - hist_timewalk
            plot_scurves(np.swapaxes(hist_rel_timewalk, 0, 1), scan_parameters=charge_values, title='Timewalk of the FE-I4', scan_parameter_name='Charge [e]', ylabel='Timewalk [ns]', filename=self.output_filename + '_analyzed.pdf')


if __name__ == "__main__":
    RunManager('K:\pyBAR\host\pybar\configuration.yaml').run_run(HitDelayScan)
