# A complete prim list utilizing the TDC method to extract the Landau MPV.
# Do not forget to set the TDC module in dut_comfiguration_mio.yaml correctly.
import os.path
import numpy as np
import tables as tb
import progressbar
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit, leastsq

from pyLandau import landau

from pybar.run_manager import RunManager  # importing run manager
from pybar.scans.scan_iv import IVScan
from pybar.scans.scan_init import InitScan
from pybar.scans.test_register import RegisterTest
from pybar.scans.scan_digital import DigitalScan
from pybar.scans.scan_analog import AnalogScan
from pybar.scans.tune_fei4 import Fei4Tuning
from pybar.scans.tune_stuck_pixel import StuckPixelScan
from pybar.scans.scan_threshold_fast import FastThresholdScan
from pybar.scans.tune_noise_occupancy import NoiseOccupancyTuning
from pybar.scans.calibrate_plsr_dac import PlsrDacScan
from pybar.scans.calibrate_hit_or import HitOrCalibration
from pybar.scans.scan_ext_trigger import ExtTriggerScan
from pybar.fei4.register_utils import make_box_pixel_mask_from_col_row, parse_global_config
import pybar.scans.analyze_source_scan_tdc_data as tdc_analysis


def analyze_tdc(source_scan_filename, calibration_filename, col_span, row_span):
    # Data files
    calibation_file = calibration_filename
    raw_data_file = source_scan_filename
    hit_file = os.path.splitext(raw_data_file)[0] + r'_interpreted.h5'
    # Selection criterions, change this to your needs
    hit_selection = '(column > %d) & (column < %d) & (row > %d) & (row < %d)' % (col_span[0] + 1, col_span[1] - 1, row_span[0] + 5, row_span[1] - 5)  # deselect edge pixels for better cluster size cut
    hit_selection_conditions = ['(n_cluster==1)', '(n_cluster==1) & (cluster_size == 1)', '(n_cluster==1) & (cluster_size == 1) & (relative_BCID > 1) & (relative_BCID < 4) & ((tot > 12) | ((TDC * 1.5625 - tot * 25 < 100) & (tot * 25 - TDC * 1.5625 < 100))) & %s' % hit_selection]
    event_status_select_mask = 0b0000111111011111
    event_status_condition = 0b0000000100000000  # trigger, one in-time tdc word and perfect event structure required
    # Interpret raw data and create hit table
    tdc_analysis.analyze_raw_data(input_files=raw_data_file,
                                  output_file_hits=hit_file,
                                  interpreter_plots=True,
                                  overwrite_output_files=True,
                                  pdf_filename=raw_data_file,
                                  align_at_trigger=True,
                                  use_tdc_trigger_time_stamp=True,
                                  max_tdc_delay=253)
    # Select TDC histograms for different cut criterions, use the charge calibrations
    tdc_analysis.histogram_tdc_hits(hit_file,
                                    hit_selection_conditions,
                                    event_status_select_mask,
                                    event_status_condition,
                                    calibation_file,
                                    max_tdc=1500,
                                    n_bins=350)

    return os.path.splitext(hit_file)[0] + '_tdc_hists.h5'


def plsr_dac_to_charge(source_scan_filename, plsr_dac):
    with tb.open_file(source_scan_filename, 'r') as in_file_h5:
        vcal_c0 = float(in_file_h5.root.configuration.calibration_parameters[:][np.where(in_file_h5.root.configuration.calibration_parameters[:]['name'] == 'Vcal_Coeff_0')]['value'][0])
        vcal_c1 = float(in_file_h5.root.configuration.calibration_parameters[:][np.where(in_file_h5.root.configuration.calibration_parameters[:]['name'] == 'Vcal_Coeff_1')]['value'][0])
        c_high = float(in_file_h5.root.configuration.calibration_parameters[:][np.where(in_file_h5.root.configuration.calibration_parameters[:]['name'] == 'C_Inj_High')]['value'][0])
        voltage = vcal_c0 + vcal_c1 * plsr_dac
        return voltage * c_high / 0.16022


def fit_landau_bootstrap(x, y, p0, n_sigma=1, n_iterations=500, **kwargs):  # fit the landau with bootstrap to give reasonable fit errors
    def errfunc(p, x, y):  # langau errorfunktion to minimize in fit
        return landau.langau(x, *p) - y

    yerr = kwargs.get('yerr', None)
    pfit, _ = curve_fit(landau.langau, x, y, p0=p0)

    residuals = errfunc(pfit, x, y)
    s_res = np.std(residuals)
    ps = []

    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=n_iterations, term_width=80)
    progress_bar.start()
    for i in range(n_iterations):
        if yerr is None:
            randomDelta = np.random.normal(0.0, s_res, len(y))
            randomdataY = y + randomDelta
        else:
            randomDelta = np.array([np.random.normal(0.0, derr, 1)[0] for derr in yerr])
            randomdataY = y + randomDelta
        randomfit, _ = leastsq(errfunc, p0, args=(x, randomdataY), full_output=0)
        ps.append(randomfit)
        progress_bar.update(i)
    progress_bar.finish()

    mean_pfit, err_pfit = np.mean(ps, 0), n_sigma * np.std(ps, 0)

    return mean_pfit, err_pfit


def plot_landau(source_scan_filename, tdc_hists, target_threshold, fit_range=(13000, 30000)):
    with tb.open_file(tdc_hists, 'r') as in_file_h5:
        x, count, count_error = in_file_h5.root.HistTdcCalibratedCondition_2[:]['charge'], in_file_h5.root.HistTdcCalibratedCondition_2[:]['count'], in_file_h5.root.HistTdcCalibratedCondition_2[:]['count_error']
        charge = plsr_dac_to_charge(source_scan_filename, x)
        target_threshold_charge = plsr_dac_to_charge(source_scan_filename, target_threshold)
        plt.clf()
        plt.grid()
        x_fit_range = np.logical_and(charge > fit_range[0], charge < fit_range[1])
        coeff, err = fit_landau_bootstrap(charge[x_fit_range], count[x_fit_range], p0 = (7000, np.std(charge[x_fit_range]), 150, np.amax(count[x_fit_range])), yerr=count_error[x_fit_range], n_iterations=100)
        plt.bar(charge, count, width=charge[1] - charge[0], color='blue', label='data')
        plt.plot(charge[x_fit_range], landau.langau(charge[x_fit_range], *coeff), 'r-')
        plt.plot([target_threshold_charge, target_threshold_charge], [plt.ylim()[0], plt.ylim()[1]], 'b--', linewidth=2, label='Threshold $%d$ e' % target_threshold_charge)
        plt.plot([coeff[0], coeff[0]], [plt.ylim()[0], plt.ylim()[1]], 'r--', linewidth=2, label='MPV $%d\pm%d$ e' % (coeff[0], err[0]))
        plt.title('Landau, -30 C')
        plt.legend(loc=0)
        plt.show()


if __name__ == "__main__":
    # Settings
    bias_voltage = -80
    max_iv_voltage = -100
    #   Tuning
    cref = 12
    target_threshold = 34
    target_charge = 300
    target_tot = 9

    #   TDC measurements
    plsr_dacs = [target_threshold, 40, 50, 60, 80, 100, 120, 150, 200, 250, 300, 350, 400, 500, 600, 700, 800]  # PlsrDAC range for TDC calibration, should start at threshold
    col_span = [55, 75]#[50, 78]  # pixel column range to use in TDC scans
    row_span = [125, 225]#[20, 315]  # pixel row range to use in TDC scans
    tdc_pixel = make_box_pixel_mask_from_col_row(column=[col_span[0], col_span[1]], row=[row_span[0], row_span[1]])  # edge pixel are not used in analysis

    runmngr = RunManager('configuration.yaml')

    # IV scan
    runmngr.run_run(run=IVScan, run_conf={"voltages": np.arange(-1, max_iv_voltage - 1, -1), "max_voltage": max_iv_voltage, "bias_voltage": bias_voltage, "minimum_delay": 0.5})

    # FE check and complete tuning
    runmngr.run_run(run=RegisterTest)
    runmngr.run_run(run=DigitalScan)  # digital scan with std. settings

    if runmngr.current_run.register.flavor == 'fei4a':  # FEI4 A related config changes, Deactivate noisy edge columns if FE-I4A
        runmngr.current_run.register.set_global_register_value("DisableColumnCnfg", 549755813891)  # Disable noisy columns
        runmngr.current_run.register.set_global_register_value("Cref", cref)  # Set correct cref
        runmngr.current_run.register.save_configuration(runmngr.current_run.register.configuration_file)
        runmngr.run_run(run=DigitalScan)  # repeat digital scan with specific settings

    runmngr.run_run(run=Fei4Tuning, run_conf={'target_threshold': target_threshold, 'target_tot': target_tot, 'target_charge': target_charge}, catch_exception=False)
    runmngr.run_run(run=AnalogScan, run_conf={'scan_parameters': [('PlsrDAC', target_charge)]})
    runmngr.run_run(run=FastThresholdScan)
    runmngr.run_run(run=StuckPixelScan)
    runmngr.run_run(run=NoiseOccupancyTuning, run_conf={'occupancy_limit': 1000, 'n_triggers': 10000000})  # high occupancy limit to work with strong Sr-90 source
    runmngr.run_run(run=PlsrDacScan, run_conf={"colpr_address": range(25, 39)})

    # TDC calibration
    runmngr.run_run(run=HitOrCalibration, run_conf={
                                                    'reset_rx_on_error': True,
                                                    "pixels": (np.dstack(np.where(tdc_pixel == 1))+ 1).tolist()[0],
                                                    "scan_parameters": [('column', None),
                                                                        ('row', None),
                                                                        ('PlsrDAC', plsr_dacs)]
                                                    })
    calibration_filename = runmngr.current_run.output_filename + '_calibration.h5'

    # Scintillator trigger source scan
    imon_mask = tdc_pixel ^ 1  # imon mask = not enable mask
    runmngr.current_run.register.set_pixel_register_value("Imon", imon_mask)  # remember: for the selection later index 0 == colum/row 1
    runmngr.run_run(run=ExtTriggerScan, run_conf={'comment': 'Strong Sr-90 source',
                                                  'col_span': col_span,
                                                  'row_span': row_span,
                                                  "use_enable_mask_for_imon": False,
                                                  "enable_tdc": True,
                                                  "trigger_delay": 8,
                                                  "trigger_rate_limit": 1000,
                                                  "trigger_latency": 232,
                                                  "trig_count": 0,
                                                  "scan_timeout": 45 * 60,
                                                  "no_data_timeout": 20,
                                                  'reset_rx_on_error': True,
                                                  "max_triggers": 1000000000})
    source_scan_filename = runmngr.current_run.output_filename + '.h5'

    tdc_hists = analyze_tdc(source_scan_filename, calibration_filename, col_span, row_span)
    plot_landau(source_scan_filename, tdc_hists, target_threshold)
