"""A script that changes the PlsrDAC in a certain range and measures the voltage step from the transient injection signal.
Since the minimum and maximum of the signal is measured, this script gives a more precise PlsrDAC calibration than
the normal PlsrDAC calibration. Do not forget to add the oscilloscope device in dut_mio.yaml.
The oscilloscope can be any device supported by basil, but the string interpretation here is only implemented for Tektronix oscilloscopes!

Settings for Tektronix that should be set before running this script:
- Trigger mode: Normal, NOT auto roll!
- X-Scale: 400 ns / Div
- Y-Scale: 200 mV / Div
- Trigger horizontal position: within first division
- Baseline: low enough that 1.5 V fits the screen
- 10k data points
- acquisition mode: average over 512 injections
- full band width
- be aware: first 2500 data points of waveform should be read (read start/stop = 0/2500)
"""
import time
import ast
import numpy as np
import tables as tb
from pylab import polyfit, poly1d
from matplotlib.backends.backend_pdf import PdfPages
import logging
import progressbar
import matplotlib.pyplot as plt

from pybar.run_manager import RunManager
from pybar.scans.scan_analog import AnalogScan


# Add oscilloscope interpretation functions below
def interpret_data_from_tektronix(raw_data):
    ''' Interprets raw data from Tektronix
    returns: lists of x, y values in seconds/volt'''
    meta_data = raw_data.split(',')[5].split(';')
    scale_x, scale_y = float(meta_data[5]), float(meta_data[9])  # x, y scaling factor (units/x unit, units/digitizing level)
    offset_x, offset_y = float(meta_data[6]), float(meta_data[10])  # y offset (in x unit / digits)
    raw_voltages = raw_data.split(',')[6:]
    voltages = [(float(voltage) - offset_y) * scale_y for voltage in raw_voltages]
    times = [(float(time) - offset_x) * scale_x for time in range(len(voltages))]
    return np.array(times), np.array(voltages)

# Select actual interpretation function
interpret_oscilloscope_data = interpret_data_from_tektronix


class PlsrDacTransientCalibration(AnalogScan):
    ''' Transient PlsrDAC calibration scan
    '''
    _default_run_conf = AnalogScan._default_run_conf.copy()
    _default_run_conf.update({
        "scan_parameter_values": range(25, 1024, 25),  # plsr dac settings, be aware: too low plsDAC settings are difficult to trigger
        "enable_double_columns": range(0, 16),  # list of double columns which will be enabled during scan. None will select all double columns, first double column defines first trigger level
        "enable_mask_steps": [0],  # Scan only one mask step to save time
        "n_injections": 512,  # number of injections, has to be > 260 to allow for averaging 256 injection signals
        "channel": 1,  # oscilloscope channel
        "show_debug_plots": False,
        "trigger_level_offset": 0, # trigger is automatically set between the maximum / minimum of the baseline; this can be changed by this offset in mV; for low PLsrDAC sometimes needed
        "trigger_level_start": 60, # trigger level in mV of for the first measurement
        "max_data_index": 2001,  # maximum data index to be read out; 2001 reads date from 0 to 1999
        "fit_range_step": [(-150, -50), (50, 150)],  # the fit range for the voltage step in relative indices from the voltage step position
        "fit_range": [0, 700]  # fit range for the linear PlsrDAC transfer function
    })

    def set_scan_parameter(self, parameter, value):  # set the new PlsrDAc value
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value(parameter, value)
        commands.extend(self.register.get_commands("WrRegister", name=[parameter]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def configure(self):
        super(PlsrDacTransientCalibration, self).configure()
        # Init Oscilloscope
        self.dut['Oscilloscope'].init()
        self.dut['Oscilloscope'].data_init()  # Resert data taking settings
        self.dut['Oscilloscope'].set_data_start(0)  # Set readout fraction of waveform
        self.dut['Oscilloscope'].set_data_stop(self.max_data_index)  # Set readout fraction of waveform
        self.dut['Oscilloscope'].set_average_waveforms(2 ** 8)  # For tetronix has to be 2^x
        self.dut['Oscilloscope'].set_trigger_level(self.trigger_level_start)
        logging.info('Initialized oscilloscope %s' % self.dut['Oscilloscope'].get_name())
        # Route Vcal to pin
        commands = []
        self.register.set_global_register_value('Colpr_Mode', 0)  # one DC only
        self.register.set_global_register_value('Colpr_Addr', self.enable_double_columns[0])
        self.register.set_global_register_value('ExtDigCalSW', 0)
        self.register.set_global_register_value('ExtAnaCalSW', 1)  # Route Vcal to external pin
        commands.extend(self.register.get_commands("WrRegister", name=['Colpr_Addr', 'Colpr_Mode', 'ExtDigCalSW', 'ExtAnaCalSW']))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        # Output data structures
        data_array = np.zeros(shape=(len(self.scan_parameter_values), self.max_data_index - 1), dtype=np.float16)
        data_out = self.raw_data_file.h5_file.create_carray(self.raw_data_file.h5_file.root, name='PlsrDACwaveforms', title='Waveforms from transient PlsrDAC calibration scan', atom=tb.Atom.from_dtype(data_array.dtype), shape=data_array.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        data_out.attrs.scan_parameter_values = self.scan_parameter_values
        data_out.attrs.dimensions = ['plsrdac', 'time', 'voltage']
        trigger_levels = []

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(self.scan_parameter_values), term_width=80)
        progress_bar.start()

        for index, scan_parameter in enumerate(self.scan_parameter_values):
            # Update PlsrDAC parameter
            self.set_scan_parameters(** {'PlsrDAC': scan_parameter})  # tell run base
            self.set_scan_parameter('PlsrDAC', scan_parameter)  # set in FE
            # Get actual high level and set trigger level to the middle
            self.dut['Oscilloscope'].set_acquire_mode('SAMPLE')  # clears also averaging storage
            time.sleep(1.5)  # tektronix needs time to change mode and clear averaging storage (bad programing...)
            self.dut['Oscilloscope'].force_trigger()
            time.sleep(1.5)  # give the trigger some time
            raw_data = self.dut['Oscilloscope'].get_data(channel=self.channel)
            times, voltages = interpret_oscilloscope_data(raw_data)
            trigger_level = (np.amax(voltages) - np.amin(voltages)) / 2. + self.trigger_level_offset * 1e-3
            self.dut['Oscilloscope'].set_trigger_level(trigger_level)

            if self.show_debug_plots:
                plt.clf()
                plt.grid()
                plt.plot(times * 1e9, voltages * 1e3, label='Data')
                plt.plot(times * 1e9, np.repeat([trigger_level * 1e3], len(times)), '--', label='Trigger (%d mV)' % (trigger_level * 1000))
                plt.xlabel('Time [ns]')
                plt.ylabel('Voltage [mV]')
                plt.legend(loc=0)
                plt.show()

            # Setup data aquisition and start scan loop
            self.dut['Oscilloscope'].set_acquire_mode('AVERAGE')  # average to get rid of noise and keeping high band width
            time.sleep(1.5)  # tektronix needs time to change mode (bad programing...)
            super(PlsrDacTransientCalibration, self).scan()  # analog scan loop
            raw_data = self.dut['Oscilloscope'].get_data(channel=self.channel)
            times, voltages = interpret_oscilloscope_data(raw_data)
            data_array[index, :] = voltages[:self.max_data_index]
            trigger_levels.append(float(self.dut['Oscilloscope'].get_trigger_level()))
            progress_bar.update(index)

            if self.show_debug_plots:
                plt.clf()
                plt.ylim(0, 1500)
                plt.grid()
                plt.plot(times * 1e9, voltages * 1e3, label='Data')
                plt.plot(times * 1e9, np.repeat([trigger_level * 1e3], len(times)), '--', label='Trigger (%d mV)' % (trigger_level * 1000))
                plt.xlabel('Time [ns]')
                plt.ylabel('Voltage [mV]')
                plt.legend(loc=0)
                plt.show()

        data_out[:] = data_array
        data_out.attrs.trigger_levels = trigger_levels
        data_out.attrs.times = times.tolist()
        progress_bar.finish()

    def analyze(self):
        logging.info('Analysing the PlsrDAC waveforms')
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            data = in_file_h5.root.PlsrDACwaveforms[:]
            times = np.array(in_file_h5.root.PlsrDACwaveforms._v_attrs.times)
            scan_parameter_values = in_file_h5.root.PlsrDACwaveforms._v_attrs.scan_parameter_values
            trigger_levels = in_file_h5.root.PlsrDACwaveforms._v_attrs.trigger_levels
            fit_range = ast.literal_eval(in_file_h5.root.configuration.run_conf[:][np.where(in_file_h5.root.configuration.run_conf[:]['name'] == 'fit_range')]['value'][0])
            fit_range_step = ast.literal_eval(in_file_h5.root.configuration.run_conf[:][np.where(in_file_h5.root.configuration.run_conf[:]['name'] == 'fit_range_step')]['value'][0])
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=data.shape[0], term_width=80)

            with tb.open_file(self.output_filename + '_interpreted.h5', 'w') as out_file_h5:
                description = [('PlsrDAC', np.uint32), ('voltage_step', np.float)]  # output data table description
                data_array = np.zeros((data.shape[0],), dtype=description)
                data_table = out_file_h5.create_table(out_file_h5.root, name='plsr_dac_data', description=np.zeros((1,), dtype=description).dtype, title='Voltage steps from transient PlsrDAC calibration scan')
                with PdfPages(self.output_filename + '_interpreted.pdf') as output_pdf:
                    progress_bar.start()
                    for index in range(data.shape[0]):
                        voltages = data[index]
                        trigger_level = trigger_levels[index]
                        plsr_dac = scan_parameter_values[index]
                        if abs(trigger_level) < 0.005:
                            logging.warning('The trigger threshold for PlsrDAC %d is with %d mV too low. Thus this setting is omitted in the analysis!', plsr_dac, trigger_level * 1000.)
                            data_array['voltage_step'][index] = np.NaN
                            continue
                        step_index = np.where(np.abs(voltages - trigger_level) == np.amin(np.abs(voltages - trigger_level)))[0][0]

                        left_step_fit_range = (step_index + fit_range_step[0][0], step_index + fit_range_step[0][1])
                        right_step_fit_range = (step_index + fit_range_step[1][0], step_index + fit_range_step[1][1])

                        # Error handling if selected fit range exeeds limits
                        if left_step_fit_range[0] < 0 or left_step_fit_range[1] < 0 or right_step_fit_range[0] >= data.shape[1] or right_step_fit_range[1] >= data.shape[1] or left_step_fit_range[0] >= left_step_fit_range[1] or right_step_fit_range[0] >= right_step_fit_range[1]:
                            logging.warning('The step fit limits for PlsrDAC %d are out of bounds. Omit this data!', plsr_dac)
                            data_array['voltage_step'][index] = np.NaN
                            continue

                        times_left_step, voltage_left_step = times[left_step_fit_range[0]:left_step_fit_range[1]], voltages[left_step_fit_range[0]:left_step_fit_range[1]]
                        times_right_step, voltage_right_step = times[right_step_fit_range[0]:right_step_fit_range[1]], voltages[right_step_fit_range[0]:right_step_fit_range[1]]

                        median_left_step = np.median(voltage_left_step)
                        median_right_step = np.median(voltage_right_step)

                        data_array['PlsrDAC'][index] = plsr_dac
                        data_array['voltage_step'][index] = median_left_step - median_right_step

                        # Plot waveform + fit
                        plt.clf()
                        plt.grid()
                        plt.plot(times * 1e9, voltages * 1e3, label='Data')
                        plt.plot(times * 1e9, np.repeat([trigger_level * 1e3], len(times)), '--', label='Trigger (%d mV)' % (trigger_level * 1000))
                        plt.plot(times_left_step * 1e9, np.repeat(median_left_step * 1e3, times_left_step.shape[0]), '-', linewidth=2, label='Left of step constant fit')
                        plt.plot(times_right_step * 1e9, np.repeat(median_right_step * 1e3, times_right_step.shape[0]), '-', linewidth=2, label='Right of step constant fit')
                        plt.title('PulserDAC %d waveform' % plsr_dac)
                        plt.xlabel('Time [ns]')
                        plt.ylabel('Voltage [mV]')
                        plt.legend(loc=0)
                        output_pdf.savefig()
                        progress_bar.update(index)
                    data_table.append(data_array[np.isfinite(data_array['voltage_step'])])  # store valid data

                    # Plot, fit and store linear PlsrDAC transfer function
                    x, y = data_array[np.isfinite(data_array['voltage_step'])]['PlsrDAC'], data_array[np.isfinite(data_array['voltage_step'])]['voltage_step']
                    fit = polyfit(x[np.logical_and(x >= fit_range[0], x <= fit_range[1])], y[np.logical_and(x >= fit_range[0], x <= fit_range[1])], 1)
                    fit_fn = poly1d(fit)
                    plt.clf()
                    plt.plot(x, y, '.-', label='data')
                    plt.plot(x, fit_fn(x), '--k', label=str(fit_fn))
                    plt.title('PlsrDAC calibration')
                    plt.xlabel('PlsrDAC')
                    plt.ylabel('Voltage step [V]')
                    plt.grid(True)
                    plt.legend(loc=0)
                    output_pdf.savefig()
                    # Store result in file
                    self.register.calibration_parameters['Vcal_Coeff_0'] = fit[1] * 1000.  # store in mV
                    self.register.calibration_parameters['Vcal_Coeff_1'] = fit[0] * 1000.  # store in mV/DAC
            progress_bar.finish()

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(PlsrDacTransientCalibration)