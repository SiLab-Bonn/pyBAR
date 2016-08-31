"""A script that changes the PlsrDAC in a certain range and measures the voltage step from the transient injection signal.
Since the minimum and maximum of the signal is measured, this script gives a more precise PlsrDAC calibration than
the normal PlsrDAC calibration. Do not forget to add the oscilloscope device in dut_mio.yaml.
The oscilloscope can be any device supported by basil, but the string interpretation here is only implemented for Tektronix oscilloscopes!
"""
import time
import numpy as np
import tables as tb
from pylab import polyfit, poly1d
from matplotlib.backends.backend_pdf import PdfPages
import logging
import progressbar
import matplotlib.pyplot as plt

from pybar.run_manager import RunManager
from pybar.scans.scan_analog import AnalogScan
from pybar.scans.calibrate_plsr_dac import plot_pulser_dac


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


class PlsrDacTransientCalibrationAdvanced(AnalogScan):
    ''' Transient PlsrDAC calibration scan
    '''
    _default_run_conf = AnalogScan._default_run_conf.copy()
    _default_run_conf.update({
        "scan_parameters": [('PlsrDAC', range(25, 1024, 25))],  # plsr dac settings, be aware: too low plsDAC settings are difficult to trigger
        "enable_double_columns": [20],  # double columns which will be enabled during scan
        "enable_mask_steps": [0],  # Scan only one mask step to save time
        "n_injections": 512,  # number of injections, has to be > 260 to allow for averaging 256 injection signals
        "channel": 1,  # oscilloscope channel
        "show_debug_plots": False,
        "trigger_level_offset": 10,  # offset of the PlsrDAC baseline in mV, usually the offset voltage at PlsrDAC=0
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
        "fit_ranges": [(-1000, -100), (200, 450)],  # the fit range (in ns) relative to the trigger (t=0ns), first tuple: baseline, second tuple: peak
    })

    def write_global_register(self, parameter, value):
        commands = []
        commands.extend(self.register.get_commands("ConfMode"))
        self.register.set_global_register_value(parameter, value)
        commands.extend(self.register.get_commands("WrRegister", name=[parameter]))
        commands.extend(self.register.get_commands("RunMode"))
        self.register_utils.send_commands(commands)

    def configure(self):
        super(PlsrDacTransientCalibrationAdvanced, self).configure()
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
        scan_parameter_values = self.scan_parameters.PlsrDAC
        shape=(len(scan_parameter_values), self.max_data_index)
        atom = tb.FloatAtom()
        data_out = self.raw_data_file.h5_file.createCArray(self.raw_data_file.h5_file.root, name='PlsrDACwaveforms', title='Waveforms from transient PlsrDAC calibration scan', atom=atom, shape=shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        shape=(self.max_data_index,)
        atom = tb.FloatAtom()
        time_out = self.raw_data_file.h5_file.createCArray(self.raw_data_file.h5_file.root, name='Times', title='Time values', atom=atom, shape=shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        data_out.attrs.scan_parameter_values = scan_parameter_values
        data_out.attrs.enable_double_columns = self.enable_double_columns
        data_out.attrs.fit_ranges = self.fit_ranges
        data_out.attrs.trigger_level_offset = self.trigger_level_offset
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
            data = self.dut['Oscilloscope']._intf._resource.query_binary_values("DATA:SOURCE CH%d;:CURVe?" % self.channel, datatype='h', is_big_endian=True)
            self.preamble = self.dut['Oscilloscope'].get_parameters(channel=self.channel)
            times, voltages, time_unit, voltage_unit = interpret_oscilloscope_data(self.preamble, data)
            if len(data):
                trigger_level = (np.mean(voltages) - self.trigger_level_offset * 1e-3) / 2.0 + self.trigger_level_offset * 1e-3
            else:
                trigger_level = trigger_levels[-1]
            self.dut['Oscilloscope'].set_trigger_level(trigger_level)
            self.dut['Oscilloscope'].set_vertical_scale(min(self.vertical_scale, (np.mean(voltages) + 0.2 * np.mean(voltages)) / 10), channel=self.channel)
            #self.dut['Oscilloscope'].set_vertical_scale(0.05, channel=self.channel)

            if self.show_debug_plots:
                plt.clf()
                plt.grid()
                plt.plot(times * 1e9, voltages * 1e3, label='PlsrDAC Pulse')
                plt.axhline(y=trigger_level * 1e3, linewidth=2, linestyle="--", color='r', label='Trigger (%0.1f mV)' % (trigger_level * 1e3))
                plt.xlabel('Time [ns]')
                plt.ylabel('Voltage [mV]')
                plt.legend(loc=0)
                plt.show()

            # Setup data aquisition and start scan loop
            self.dut['Oscilloscope'].set_acquire_mode('AVErage')  # average to get rid of noise and keeping high band width
            self.dut['Oscilloscope'].set_acquire_stop_after("SEQuence")
            self.dut['Oscilloscope'].set_acquire_state("RUN")
            time.sleep(1.5)
            super(PlsrDacTransientCalibrationAdvanced, self).scan()  # analog scan loop
            self.dut['Oscilloscope'].set_acquire_state("STOP")
            # get final number of data points
#             if not self.dut['Oscilloscope'].get_number_points():
#                 raise RuntimeError()
            data = self.dut['Oscilloscope']._intf._resource.query_binary_values("DATA:SOURCE CH%d;:CURVe?" % self.channel, datatype='h', is_big_endian=True)
            self.preamble = self.dut['Oscilloscope'].get_parameters(channel=self.channel)
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
                plt.axhline(y=trigger_level * 1e3, linewidth=2, linestyle="--", color='r', label='Trigger (%0.1f mV)' % (trigger_level * 1e3))
                plt.xlabel('Time [ns]')
                plt.ylabel('Voltage [mV]')
                plt.legend(loc=0)
                plt.show()

            self.dut['Oscilloscope'].set_vertical_scale(self.vertical_scale, channel=self.channel)

        time_out[:] = times
        data_out.attrs.trigger_levels = trigger_levels
        progress_bar.finish()

    def analyze(self):
        logging.info('Analyzing the PlsrDAC waveforms')
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            data = in_file_h5.root.PlsrDACwaveforms[:]
            try:
                times = in_file_h5.root.Times[:]
            except NoSuchNodeError:  # for backward compatibility
                times = np.array(in_file_h5.root.PlsrDACwaveforms._v_attrs.times)
            scan_parameter_values = in_file_h5.root.PlsrDACwaveforms._v_attrs.scan_parameter_values
            enable_double_columns = in_file_h5.root.PlsrDACwaveforms._v_attrs.enable_double_columns
            trigger_levels = in_file_h5.root.PlsrDACwaveforms._v_attrs.trigger_levels
            trigger_level_offset = in_file_h5.root.PlsrDACwaveforms._v_attrs.trigger_level_offset
            fit_ranges = in_file_h5.root.PlsrDACwaveforms._v_attrs.fit_ranges
            progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=data.shape[0], term_width=80)

            with tb.open_file(self.output_filename + '_interpreted.h5', 'w') as out_file_h5:
                description = [('PlsrDAC', np.uint32), ('voltage_step', np.float)]  # output data table description
                data_array = np.zeros((data.shape[0],), dtype=description)
                data_table = out_file_h5.create_table(out_file_h5.root, name='plsr_dac_data', description=np.zeros((1,), dtype=description).dtype, title='Voltage steps from transient PlsrDAC calibration scan')
                with PdfPages(self.output_filename + '_interpreted.pdf') as output_pdf:
                    progress_bar.start()

                    start_index_baseline = np.argmin(np.abs(times * 1e9 - fit_ranges[0][0]))
                    stop_index_baseline = np.argmin(np.abs(times * 1e9 - fit_ranges[0][1]))
                    start_index_peak = np.argmin(np.abs(times * 1e9 - fit_ranges[1][0]))
                    stop_index_peak = np.argmin(np.abs(times * 1e9 - fit_ranges[1][1]))
                    times_baseline = times[start_index_baseline:stop_index_baseline]
                    times_peak = times[start_index_peak:stop_index_peak]

                    for index in range(data.shape[0]):
                        voltages = data[index]
                        trigger_level = trigger_levels[index]
                        plsr_dac = scan_parameter_values[index]

                        # index of first value below trigger level
                        step_index = np.argmin(voltages>trigger_level)
                        if not (step_index > start_index_baseline and step_index > stop_index_baseline):
                            logging.warning("Baseline fit range might be too large")
                        if not (step_index < start_index_peak and step_index < stop_index_peak):
                            logging.warning("Peak fit range might be too small")

                        voltage_baseline = voltages[start_index_baseline:stop_index_baseline]
                        voltage_peak = voltages[start_index_peak:stop_index_peak]

                        median_baseline = np.median(voltage_baseline)
                        median_peak = np.median(voltage_peak)
                        # sanity check
                        if not (median_baseline > trigger_level and median_peak < trigger_level and trigger_level * 1e3 >= trigger_level_offset):
                            logging.warning('Skipping PlsrDAC=%d because the trigger level of %.1f mV is too low.', plsr_dac, trigger_level * 1e3)
                            data_array['voltage_step'][index] = np.NaN
                            continue

                        data_array['PlsrDAC'][index] = plsr_dac
                        data_array['voltage_step'][index] = median_baseline - median_peak

                        # Plot waveform + fit
                        plt.clf()
                        plt.grid()
                        plt.plot(times * 1e9, voltages * 1e3, label='PlsrDAC Pulse')
                        plt.axhline(y=trigger_level * 1e3, linewidth=2, linestyle="--", color='r', label='Trigger (%0.f mV)' % (trigger_level * 1e3))
                        plt.plot(times_baseline * 1e9, np.repeat(median_baseline * 1e3, times_baseline.size), '-', linewidth=2, label='Baseline (%.1f mV)' % (median_baseline * 1e3))
                        plt.plot(times_peak * 1e9, np.repeat(median_peak * 1e3, times_peak.size), '-', linewidth=2, label='Peak (%.1f mV)' % (median_peak * 1e3))
                        plt.title('PulserDAC=%d Waveform' % plsr_dac)
                        plt.xlabel('Time [ns]')
                        plt.ylabel('Voltage [mV]')
                        plt.legend(loc=4)  # lower right
                        output_pdf.savefig()
                        progress_bar.update(index)
                    data_table.append(data_array[np.isfinite(data_array['voltage_step'])])  # store valid data

                    # Plot, fit and store linear PlsrDAC transfer function
                    select = np.isfinite(data_array['voltage_step'])
                    x = data_array[select]['PlsrDAC']
                    y = data_array[select]['voltage_step']
                    slope_fit, slope_err, plateau_fit, plateau_err = plot_pulser_dac(x, y, output_pdf=output_pdf, title_suffix="(DC %d)" % (enable_double_columns[0],))

                    # Store result in file
                    self.register.calibration_parameters['Vcal_Coeff_0'] = np.nan_to_num(slope_fit[0] * 1000.0)  # store in mV
                    self.register.calibration_parameters['Vcal_Coeff_1'] = np.nan_to_num(slope_fit[1] * 1000.0)  # store in mV/DAC
            progress_bar.finish()

if __name__ == "__main__":
    RunManager('../configuration.yaml').run_run(PlsrDacTransientCalibrationAdvanced)
