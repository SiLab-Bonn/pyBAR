import logging
import time

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import tables as tb

from pybar.fei4_run_base import Fei4RunBase
from pybar.run_manager import RunManager
from pybar.analysis import analysis_utils


class TluTuning(Fei4RunBase):
    '''TLU Tuning

    This script tries to find a delay value for the TLU module that the error rate in the trigger number transfer is 0.
    An error is detected when the trigger number does not increase by one.

    Note:
    The TLU has to be started with internal trigger generation (TLUControl -t 1).
    '''
    _default_run_conf = {
        "broadcast_commands": True,
        "threaded_scan": True,
        "scan_parameters": [('TRIGGER_DATA_DELAY', range(0, 2**4))],  # TRIGGER_DATA_DELAY has 4-bit
        "sleep": 2  # Time to record the trigger words per delay setting in seconds
    }

    def configure(self):
        self.dut['TLU']['TRIGGER_COUNTER'] = 0

    def scan(self):
        curr_data_format = self.dut['TLU']['DATA_FORMAT']
        self.dut['TLU']['DATA_FORMAT'] = 0
        for value in self.scan_parameters.TRIGGER_DATA_DELAY:
            if self.abort_run.is_set():
                break
            self.dut['TLU']['TRIGGER_DATA_DELAY'] = value
            time.sleep(0.1)

            with self.readout(TRIGGER_DATA_DELAY=value):
                self.dut['TLU']['TRIGGER_ENABLE'] = True
                time.sleep(self.sleep)
                self.dut['TLU']['TRIGGER_ENABLE'] = False
                if self.dut['TLU']['TRIGGER_COUNTER'] == 0:
                    raise RuntimeError('No triggers collected. Check if TLU is on and the IO is set correctly.')
        self.dut['TLU']['DATA_FORMAT'] = curr_data_format

    def analyze(self):
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            scan_parameters = in_file_h5.root.scan_parameters[:]  # Table with the scan parameter value for every readout
            meta_data = in_file_h5.root.meta_data[:]
            data_words = in_file_h5.root.raw_data[:]
            if data_words.shape[0] == 0:
                raise RuntimeError('No trigger words recorded')
            readout_indices = [i[1] for i in analysis_utils.get_meta_data_index_at_scan_parameter(scan_parameters, 'TRIGGER_DATA_DELAY')]  # Readout indices where the scan parameter changed
            with tb.open_file(self.output_filename + '_interpreted.h5', 'w') as out_file_h5:
                with PdfPages(self.output_filename + '_interpreted.pdf') as output_pdf:
                    description = [('TRIGGER_DATA_DELAY', np.uint8), ('error_rate', np.float)]  # Output data table description
                    data_array = np.zeros((len(readout_indices),), dtype=description)
                    data_table = out_file_h5.create_table(out_file_h5.root, name='error_rate', description=np.zeros((1,), dtype=description).dtype, title='Trigger number error rate for different data delay values')
                    for index, (index_low, index_high) in enumerate(analysis_utils.get_ranges_from_array(readout_indices)):  # Loop over the scan parameter data
                        data_array['TRIGGER_DATA_DELAY'][index] = scan_parameters['TRIGGER_DATA_DELAY'][index_low]
                        word_index_start = meta_data[index_low]['index_start']
                        word_index_stop = meta_data[index_high]['index_start'] if index_high is not None else meta_data[-1]['index_stop']
                        actual_raw_data = data_words[word_index_start:word_index_stop]
                        selection = np.bitwise_and(actual_raw_data, 0x80000000) == 0x80000000
                        trigger_words = np.bitwise_and(actual_raw_data[selection], 0x7FFFFFFF)  # Get the trigger values
                        if selection.shape[0] != word_index_stop - word_index_start:
                            logging.warning('There are not only trigger words in the data stream')
                        actual_errors = np.count_nonzero(np.diff(trigger_words[trigger_words != 0x7FFFFFFF]) != 1)
                        data_array['error_rate'][index] = float(actual_errors) / selection.shape[0]

                        # Plot trigger number
                        fig = Figure()
                        FigureCanvas(fig)
                        ax = fig.add_subplot(111)
                        ax.plot(range(trigger_words.shape[0]), trigger_words, '-', label='data')
                        ax.set_title('Trigger words for delay setting index %d' % index)
                        ax.set_xlabel('Trigger word index')
                        ax.set_ylabel('Trigger word')
                        ax.grid(True)
                        ax.legend(loc=0)
                        output_pdf.savefig(fig)

                    data_table.append(data_array)  # Store valid data
                    if np.all(data_array['error_rate'] != 0.0):
                        logging.warning('There is no delay setting without errors')
                    logging.info('ERRORS: %s', str(data_array['error_rate']))

                    # Determine best delay setting (center of working delay settings)
                    good_indices = np.where(np.logical_and(data_array['error_rate'][:-1] == 0, np.diff(data_array['error_rate']) == 0))[0]
                    best_index = good_indices[good_indices.shape[0] / 2]
                    best_delay_setting = data_array['TRIGGER_DATA_DELAY'][best_index]
                    logging.info('The best delay setting for this setup is %d', best_delay_setting)

                    # Plot error rate plot
                    fig = Figure()
                    FigureCanvas(fig)
                    ax = fig.add_subplot(111)
                    ax.plot(data_array['TRIGGER_DATA_DELAY'], data_array['error_rate'], '.-', label='data')
                    ax.plot([best_delay_setting, best_delay_setting], [0, 1], '--', label='best delay setting')
                    ax.set_title('Trigger word error rate for different data delays')
                    ax.set_xlabel('TRIGGER_DATA_DELAY')
                    ax.set_ylabel('Error rate')
                    ax.grid(True)
                    ax.legend(loc=0)
                    output_pdf.savefig(fig)


if __name__ == "__main__":
    with RunManager('configuration.yaml') as runmngr:
        runmngr.run_run(TluTuning)
