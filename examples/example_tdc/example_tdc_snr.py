# Example how to use pyBar to take TDC data and analyze the TDC SN in one small script.
import matplotlib.pyplot as plt
import numpy as np
import tables as tb

from pybar.run_manager import RunManager  # importing run manager
from pybar.scans.scan_threshold_fast import FastThresholdScan
from pybar.scans.calibrate_hit_or import HitOrCalibration


def get_signal_to_noise(filename):  # extracts the SN from the data file
    with tb.open_file(filename + '_calibration.h5', 'r') as in_file_h5:
        charge_calibration = in_file_h5.root.HitOrCalibration[:]
        plsr_dacs = in_file_h5.root.HitOrCalibration._v_attrs.scan_parameter_values
        valid_pixel = np.where(charge_calibration.sum(axis=(2, 3)) > 0)  # valid pixel have data and a calibration (that is any charge(TDC) calibration != 0)

        mean_signal_to_noise = np.zeros(len(plsr_dacs))
        for (column, row) in np.column_stack(valid_pixel):
            if np.all(np.isfinite(charge_calibration[column, row, :, 1])) and np.all(np.isfinite(charge_calibration[column, row, :, 3])):
                mean_signal_to_noise += (charge_calibration[column, row, :, 1] / charge_calibration[column, row, :, 3])
        mean_signal_to_noise /= valid_pixel[0].shape[0]

        return mean_signal_to_noise


if __name__ == "__main__":
    plsr_dacs = [40, 50, 60, 80, 130, 180, 230, 280, 340, 440, 540, 640, 740]  # PlsrDAC setting for hit OR calibration scan

    runmngr = RunManager(r'../../pybar/configuration.yaml')
    runmngr.run_run(run=FastThresholdScan)  # initial threshold check
    actual_vthin_alt_fine = runmngr.current_run.register.get_global_register_value("Vthin_AltFine")
    sns = []  # SN values

    # Take data
    for dis_vbn in [40, ]:  # analog discriminator bias loop
        for vthin_alt_fine in range(actual_vthin_alt_fine, 256, 100):  # threshold loop
            for prmp_vbpf in range(0, 256, 32):  # feedback current loop
                runmngr.current_run.register.set_global_register_value("PrmpVbpf", prmp_vbpf)
                runmngr.current_run.register.set_global_register_value("Vthin_AltFine", vthin_alt_fine)
                runmngr.current_run.register.set_global_register_value("DisVbn", dis_vbn)
                runmngr.run_run(run=HitOrCalibration, run_conf={  # run the hit or calibration scan
                    'reset_rx_on_error': True,
                    "pixels": ((10, 10), (30, 100), (50, 200), (70, 300)),
                    "scan_parameters": [('column', None),
                                        ('row', None),
                                        ('PlsrDAC', plsr_dacs)]
                })

                sns.append((dis_vbn, vthin_alt_fine, prmp_vbpf, get_signal_to_noise(runmngr.current_run.output_filename)))

    # Plot data
    plt.clf()
    line_styles = ['o', '-', '--']
    for index, (dis_vbn, vthin_alt_fine, prmp_vbpf, sn) in enumerate(sns):
        print dis_vbn, vthin_alt_fine, prmp_vbpf, sn
        plt.plot(np.array(plsr_dacs) * 55.0, sn, line_styles[index % 3], label='Dis_Vbn:%d, Vthin_AF:%d, PrmpVbpf:%d' % (dis_vbn, vthin_alt_fine, prmp_vbpf))
    plt.grid(True)
    plt.xlabel('Charge')
    plt.ylabel('Signal to noise')
    plt.legend(loc=0)
    plt.show()
