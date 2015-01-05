''' Script to check scans and for well known errors. A working (and biased) FE-I4 is needed. If these unit tests pass
there is a high propability that the readout system and the FE-I4 work as expected.
'''

import unittest
import os
import fnmatch
import shutil
import tables as tb
import numpy as np
from Queue import Empty

from pybar.run_manager import RunManager
from pybar.scans.scan_digital import DigitalScan
from pybar.scans.scan_analog import AnalogScan
from pybar.scans.scan_threshold_fast import FastThresholdScan
from pybar.scans.scan_threshold import ThresholdScan

_data_folder = 'test_scans//test_scans//scan_unittests'
_configuration_folder = 'test_scans/configuration.yaml'

# Cut values
_upper_noise_cut = 3.5
_upper_noise_std_cut = 0.5


def run_scan(scan, run_conf=None):
    run_manager = RunManager(_configuration_folder)
    run_manager.run_run(scan, run_conf=run_conf)
    error_msg = ''
    try:
        error_msg = str(run_manager._current_run.err_queue.get(timeout=1)[1])
    except Empty:
        pass
    return run_manager._current_run._run_status == 'FINISHED', error_msg, run_manager._current_run.output_filename, run_manager._current_run._default_run_conf, run_manager._current_run.__class__.__name__


def find(pattern, path):
    result = []
    for root, _, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(os.path.join(root, name))
    return result


def check_1d_histogram(filename, hist_name, select_mask, result, operation):
    ok = True
    error_string = hist_name + ' '
    with tb.open_file(filename, 'r') as in_file_h5:
        hist = in_file_h5.getNode(in_file_h5.root, hist_name)[:]
        for index in range(select_mask[select_mask].shape[0]):
            operation_ok = True
            if operation[select_mask][index] == '==' and not (hist[select_mask][index] == result[select_mask][index]):
                operation_ok = False
            elif operation[select_mask][index] == '<=' and not (hist[select_mask][index] <= result[select_mask][index]):
                operation_ok = False
            elif operation[select_mask][index] == '>=' and not (hist[select_mask][index] >= result[select_mask][index]):
                operation_ok = False
            elif operation[select_mask][index] == '<' and not (hist[select_mask][index] < result[select_mask][index]):
                operation_ok = False
            elif operation[select_mask][index] == '>' and not (hist[select_mask][index] > result[select_mask][index]):
                operation_ok = False
            elif operation[select_mask][index] == '!=' and not (hist[select_mask][index] != result[select_mask][index]):
                operation_ok = False
            if not operation_ok:
                error_string += ' Index %s, %s %s %s' % (index, hist[select_mask][index], operation[select_mask][index], result[select_mask][index])
                ok = False
        return ok, error_string


def check_hit_map(filename, hist_name, select_mask, result, operation):
    failing_pixels = 0
    with tb.open_file(filename, 'r') as in_file_h5:
        hist = in_file_h5.getNode(in_file_h5.root, hist_name)[:, :, 0]
        if operation == '==' and not np.all(hist[select_mask] == result[select_mask]):
            failing_pixels = np.sum(~(hist[select_mask] == result[select_mask]))
        elif operation == '<=' and not np.all(hist[select_mask] <= result[select_mask]):
            failing_pixels = np.sum(~(hist[select_mask] <= result[select_mask]))
        elif operation == '>=' and not np.all(hist[select_mask] >= result[select_mask]):
            failing_pixels = np.sum(~(hist[select_mask] >= result[select_mask]))
        elif operation == '<' and not np.all(hist[select_mask] < result[select_mask]):
            failing_pixels = np.sum(~(hist[select_mask] < result[select_mask]))
        elif operation == '>' and not np.all(hist[select_mask] > result[select_mask]):
            failing_pixels = np.sum(~(hist[select_mask] > result[select_mask]))
        elif operation == '!=' and not np.all(hist[select_mask] != result[select_mask]):
            failing_pixels = np.sum(~(hist[select_mask] != result[select_mask]))
        return failing_pixels


def check_threshold_scan(filename):
    with tb.open_file(filename, 'r') as in_file_h5:
        hist_threshold, hist_noise = in_file_h5.root.HistThresholdFitted[:], in_file_h5.root.HistNoiseFitted[:]
        threshold_mean, threshold_std = np.mean(hist_threshold[hist_threshold != 0]), np.std(hist_threshold[hist_threshold != 0])
        noise_mean, noise_std = np.mean(hist_noise[hist_noise != 0]), np.std(hist_noise[hist_noise != 0])
        return threshold_mean, threshold_std, noise_mean, noise_std


class TestScans(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree('test_scans//test_scans', ignore_errors=True)

    def test_system_status(self):  # Does a digital scan and checks the data for errors (event status, number of hits)s
        ok, error_msg, output_filename, default_cfg, _ = run_scan(DigitalScan)
        if ok:  # only analze if scan finished normal
            digital_scan_file = (output_filename + '_interpreted.h5').encode('string-escape')  # the digital interpreted data file
            #  Check event status histogram
            operation = np.array(['==', '==', '==', '==', '==', '==', '==', '==', '==', '==', '==', '==', '==', '==', '==', '=='])
            select_mask, result = np.ones(11, dtype=np.bool), np.zeros(11, dtype=np.uint32)
            select_mask[1], result[1] = True, 40 * default_cfg['mask_steps'] * default_cfg['n_injections']  # all events with no trigger word expected
            ok, error_msg = check_1d_histogram(digital_scan_file, 'HistErrorCounter', select_mask, result, operation)
            #  Check hit histogram
            result = np.ones((336, 80), np.uint32) * default_cfg['n_injections']
            select_mask = np.ones((336, 80), dtype=np.bool)
            failing_pixel = check_hit_map(digital_scan_file, 'HistOcc', select_mask, result, '==')
            if failing_pixel != 0:
                ok = False
                error_msg += ' There are %s pixels without exactly %s hits' % (failing_pixel, default_cfg['n_injections'])
        self.assertTrue(ok, msg=error_msg)

    def test_standard_scans(self):  # Check if the scans works and data integrity
        scans = [DigitalScan, AnalogScan, ThresholdScan, FastThresholdScan]  # list of scans to check
        ok = True
        error_msg = ' '
        for scan in scans:
            # Check if scan crashes
            run_conf = {'n_injections': 100, 'mask_steps': 1}  # Save time by taking less pixel
            scan_ok, scan_error_msg, output_filename, _, scan_name = run_scan(scan, run_conf=run_conf)
            if not scan_ok:
                error_msg += ' FAIL ' + str(scan_name) + ' ' + scan_error_msg

            data_file = (output_filename + '_interpreted.h5').encode('string-escape')  # the digital interpreted data file
            if 'ThresholdScan' not in scan_name:  # Check event status histogram
                operation = np.array(['==', '==', '==', '==', '==', '==', '==', '==', '>=', '>=', '>='])
                select_mask, result = np.ones(11, dtype=np.bool), np.zeros(11, dtype=np.uint32)
                select_mask[1], result[1] = True, 40 * run_conf['mask_steps'] * run_conf['n_injections']  # all events with no trigger word expected
                data_ok, data_error_msg = check_1d_histogram(data_file, 'HistErrorCounter', select_mask, result, operation)
                if not data_ok:
                    error_msg += ' ' + str(scan_name) + ': ' + data_error_msg
            else:  # Check threshold scan results
                data_ok = True
                threshold_mean, threshold_std, noise_mean, noise_std = check_threshold_scan(data_file)
                if noise_mean > _upper_noise_cut or noise_std > _upper_noise_std_cut:
                    data_ok = False
                    error_msg += ' ' + str(scan_name) + ': threshold/threshold std./noise/noise std. = %s/%s/%s/%s' % (threshold_mean, threshold_std, noise_mean, noise_std)

            ok &= (scan_ok & data_ok)
        self.assertTrue(ok, msg=error_msg)

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestScans)
    unittest.TextTestRunner(verbosity=2).run(suite)
