"""A script that changes the PlsrDAC in a certain range and measures the voltage step from the transient injection signal.
Since the minimum and maximum of the signal is measured, this script gives a more precise PlsrDAC calibration than
the normal PlsrDAC calibration. Do not forget to add the oscilloscope device in dut_mio.yaml.
The oscilloscope can be any device supported by basil, but the string interpretation here is only implemented for Tektronix oscilloscopes!
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
def interpret_data_from_tektronix(preamble, data):
    ''' Interprets raw data from Tektronix
    returns: lists of x, y values in seconds/volt'''
    # Y mode ("WFMPRE:PT_FMT"):
    # Xn = XZEro + XINcr (n - PT_Off)
    # Yn = YZEro + YMUlt (yn - YOFf)
    voltage = np.array(data, dtype=np.float)
    meta_data = preamble.split(',')[5].split(';')
    time_unit = meta_data[3][1:-1]
    XZEro = float(meta_data[5])
    XINcr = float(meta_data[4])
    PT_Off = float(meta_data[6])
    voltage_unit = meta_data[7][1:-1]
    YZEro = float(meta_data[10])
    YMUlt = float(meta_data[8])
    YOFf = float(meta_data[9])
    time = XZEro + XINcr * (np.arange(0, voltage.size) - PT_Off)
    voltage = YZEro + YMUlt * (voltage - YOFf)
    return time, voltage, time_unit, voltage_unit

# Select actual interpretation function
interpret_oscilloscope_data = interpret_data_from_tektronix


class PlsrDacTransientCalibration(AnalogScan):
    ''' Transient PlsrDAC calibration scan
    '''
    _default_run_conf = AnalogScan._default_run_conf.copy()
    _default_run_conf.update({
        "scan_parameters": [('PlsrDAC', range(25, 1024, 25))],  # plsr dac settings, be aware: too low plsDAC settings are difficult to trigger
        "enable_double_column": 20,  # double columns which will be enabled during scan
        "enable_mask_steps": [0],  # Scan only one mask step to save time
        "n_injections": 512,  # number of injections, has to be > 260 to allow for averaging 256 injection signals
        "channel": 1,  # oscilloscope channel
        "show_debug_plots": False,
        "trigger_level_offset": 10,  # offset of the PlsrDAC baseline in mV
        "data_points": 10000,
        "max_data_index": None,  # maximum data index to be read out; e.g. 2000 reads date from 1 to 2000, if None, use max record length
        "horizontal_scale": 0.0000004,
        "horizontal_delay_time": 0.0000016,
        "vertical_scale": 0.2,
        "vertical_offset": 0.0,
        "vertical_position": -4,
        "impedance": "MEG",
        "coupling": "DC",
        "bandwidth": "FULl",
        "trigger_mode": "NORMal",
        "trigger_edge_slope": "FALL",
        "trigger_level": 0.0, # trigger level in V of for the first measurement
        "fit_range_step": [(-750, -250), (500, 1000)],  # the fit range for the voltage step in relative indices from the voltage step position
        "fit_range": [0, 700]  # fit range for the linear PlsrDAC transfer function
    })

    def write_global_register(self, parameter, value):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value(parameter, value)
        commands.extend(self.register.get_commands("WrRegister", name=[parameter]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def configure(self):
        super(PlsrDacTransientCalibration, self).configure()
        # data acquisition
        self.dut['Oscilloscope'].data_init()  # Resert to factory settings
        self.dut['Oscilloscope'].set_data_width(2)  # 2 byte per value
        self.dut['Oscilloscope'].set_data_encoding("RIBINARY")  # signed integer
        self.dut['Oscilloscope'].set_horizontal_record_length(self.data_points)
        self.dut['Oscilloscope'].set_data_start(1)  # Set readout fraction of waveform
        if not self.max_data_index:
            self.max_data_index = int(self.dut['Oscilloscope'].get_horizontal_record_length())
        self.dut['Oscilloscope'].set_data_stop(self.max_data_index)  # Set readout fraction of waveform

        # waveform parameters
        self.dut['Oscilloscope'].set_average_waveforms(self.n_injections)  # For Tektronix it has to be power of 2

        # horizontal axis
        self.dut['Oscilloscope'].set_horizontal_scale(self.horizontal_scale)
        self.dut['Oscilloscope'].set_horizontal_delay_time(self.horizontal_delay_time)

        # vertical axis
        self.dut['Oscilloscope'].set_vertical_scale(self.vertical_scale, channel=self.channel)
        self.dut['Oscilloscope'].set_vertical_offset(self.vertical_offset, channel=self.channel)
        self.dut['Oscilloscope'].set_vertical_position(self.vertical_position, channel=self.channel)

        # input
        self.dut['Oscilloscope'].set_impedance(self.impedance, channel=self.channel)
        self.dut['Oscilloscope'].set_coupling(self.coupling, channel=self.channel)
        self.dut['Oscilloscope'].set_bandwidth(self.bandwidth, channel=self.channel)

        # trigger
        self.dut['Oscilloscope'].set_trigger_mode(self.trigger_mode)
        self.dut['Oscilloscope'].set_trigger_edge_slope(self.trigger_edge_slope)
        self.dut['Oscilloscope'].set_trigger_level(self.trigger_level)

        # get final preamble parameters
        self.preamble = self.dut['Oscilloscope'].get_parameters(channel=self.channel)

        logging.info('Initialized oscilloscope %s' % self.dut['Oscilloscope'].get_name())
        # Route Vcal to pin
        commands = []
        self.register.set_global_register_value('Colpr_Mode', 0)  # one DC only
        self.register.set_global_register_value('Colpr_Addr', self.enable_double_column)
        self.register.set_global_register_value('ExtDigCalSW', 0)
        self.register.set_global_register_value('ExtAnaCalSW', 1)  # Route Vcal to external pin
        commands.extend(self.register.get_commands("WrRegister", name=['Colpr_Addr', 'Colpr_Mode', 'ExtDigCalSW', 'ExtAnaCalSW']))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def scan(self):
        # Output data structures
        scan_parameter_values = self.scan_parameters.PlsrDAC
        shape=(len(scan_parameter_values), self.max_data_index)
        atom = tb.FloatAtom()
        data_out = self.raw_data_file.h5_file.createCArray(self.raw_data_file.h5_file.root, name='PlsrDACwaveforms', title='Waveforms from transient PlsrDAC calibration scan', atom=atom, shape=shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        shape=(self.max_data_index,)
        atom = tb.FloatAtom()
        time_out = self.raw_data_file.h5_file.createCArray(self.raw_data_file.h5_file.root, name='Times', title='Time values', atom=atom, shape=shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        data_out.attrs.scan_parameter_values = scan_parameter_values
        data_out.attrs.enable_double_column = self.enable_double_column
        trigger_levels = []

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=len(scan_parameter_values), term_width=80)
        progress_bar.start()

        for index, scan_parameter_value in enumerate(scan_parameter_values):
            if self.stop_run.is_set():
                break
            # Update PlsrDAC parameter
            self.set_scan_parameters(PlsrDAC=scan_parameter_value)  # set scan parameter
            self.write_global_register('PlsrDAC', scan_parameter_value)  # write to FE
            self.dut['Oscilloscope'].set_acquire_mode('SAMple')
            self.dut['Oscilloscope'].set_acquire_stop_after("RUNSTop")
            self.dut['Oscilloscope'].set_acquire_state("RUN")
            time.sleep(1.5)
            self.dut['Oscilloscope'].force_trigger()
            self.dut['Oscilloscope'].set_acquire_state("STOP")
            data = self.dut['Oscilloscope']._intf._resource.query_binary_values("DATA:SOURCE CH1;:CURVe?", datatype='h', is_big_endian=True)
            times, voltages, time_unit, voltage_unit = interpret_oscilloscope_data(self.preamble, data)
            if len(data):
                trigger_level = (np.mean(voltages) - self.trigger_level_offset * 1e-3) / 2.0 + self.trigger_level_offset * 1e-3
            else:
                trigger_level = trigger_levels[-1]
            self.dut['Oscilloscope'].set_trigger_level(trigger_level)

            if self.show_debug_plots:
                plt.clf()
                plt.grid()
                plt.plot(times * 1e9, voltages * 1e3, label='PlsrDAC Pulse')
                plt.axhline(y=trigger_level * 1e3, linewidth=2, linestyle="--", color='r', label='Trigger (%d mV)' % (trigger_level * 1e3))
                plt.xlabel('Time [ns]')
                plt.ylabel('Voltage [mV]')
                plt.legend(loc=0)
                plt.show()

            # Setup data aquisition and start scan loop
            self.dut['Oscilloscope'].set_acquire_mode('AVErage')  # average to get rid of noise and keeping high band width
            self.dut['Oscilloscope'].set_acquire_stop_after("SEQuence")
            self.dut['Oscilloscope'].set_acquire_state("RUN")
            time.sleep(1.5)
            super(PlsrDacTransientCalibration, self).scan()  # analog scan loop
            self.dut['Oscilloscope'].set_acquire_state("STOP")
            # get final number of data points
#             if not self.dut['Oscilloscope'].get_number_points():
#                 raise RuntimeError()
            data = self.dut['Oscilloscope']._intf._resource.query_binary_values("DATA:SOURCE CH1;:CURVe?", datatype='h', is_big_endian=True)
            times, voltages, time_unit, voltage_unit = interpret_oscilloscope_data(self.preamble, data)
            data_out[index, :] = voltages[:]
            trigger_level = float(self.dut['Oscilloscope'].get_trigger_level())
            trigger_levels.append(trigger_level)
            progress_bar.update(index)

            if self.show_debug_plots:
                plt.clf()
                plt.ylim(0, 1500)
                plt.grid()
                plt.plot(times * 1e9, voltages * 1e3, label='PlsrDAC Pulse')
                plt.axhline(y=trigger_level * 1e3, linewidth=2, linestyle="--", color='r', label='Trigger (%d mV)' % (trigger_level * 1e3))
                plt.xlabel('Time [ns]')
                plt.ylabel('Voltage [mV]')
                plt.legend(loc=0)
                plt.show()

        time_out[:] = times
        data_out.attrs.trigger_levels = trigger_levels
        progress_bar.finish()

    def analyze(self):
        logging.info('Analyzing the PlsrDAC waveforms')
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            data = in_file_h5.root.PlsrDACwaveforms[:]
            times = in_file_h5.root.Times[:]
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
                        # index of first value below trigger level
                        step_index = np.argmin(voltages>trigger_level)
                        # fit range
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
                        plt.plot(times * 1e9, voltages * 1e3, label='PlsrDAC Pulse')
                        plt.plot(times * 1e9, np.repeat([trigger_level * 1e3], len(times)), '--', label='Trigger (%d mV)' % (trigger_level * 1000))
                        plt.plot(times_left_step * 1e9, np.repeat(median_left_step * 1e3, times_left_step.shape[0]), '-', linewidth=2, label='Left of step constant fit')
                        plt.plot(times_right_step * 1e9, np.repeat(median_right_step * 1e3, times_right_step.shape[0]), '-', linewidth=2, label='Right of step constant fit')
                        plt.title('PulserDAC=%d Waveform' % plsr_dac)
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
                    plt.plot(x, y, '.-', label='PlsrDAC Voltage Step')
                    plt.plot(x, fit_fn(x), '--k', label=str(fit_fn))
                    plt.title('PlsrDAC Calibration')
                    plt.xlabel('PlsrDAC')
                    plt.ylabel('Voltage Step [V]')
                    plt.grid(True)
                    plt.legend(loc=0)
                    output_pdf.savefig()
                    # Store result in file
                    self.register.calibration_parameters['Vcal_Coeff_0'] = fit[1] * 1000.  # store in mV
                    self.register.calibration_parameters['Vcal_Coeff_1'] = fit[0] * 1000.  # store in mV/DAC
            progress_bar.finish()

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(PlsrDacTransientCalibration)
