'Simple example how to draw hit maps from a raw data file with data from multiple chips. No event builing is done, thus no feedback about FE status!'
import os.path

from matplotlib.backends.backend_pdf import PdfPages
import tables as tb
import numpy as np

from pybar.daq import readout_utils
from pybar.analysis.plotting import plotting


def draw_hit_map_from_raw_data(raw_data_file, front_ends):
    with PdfPages(os.path.splitext(raw_data_file)[0] + '.pdf') as output_pdf:
        with tb.open_file(raw_data_file, 'r') as in_file_h5:
            raw_data = in_file_h5.root.raw_data[:]
            for front_end in range(front_ends):
                print 'Create occupancy hist of front end %d' % front_end
                occupancy_array, _, _ = np.histogram2d(*readout_utils.convert_data_array(raw_data,
                                                                                         filter_func=readout_utils.logical_and(readout_utils.is_data_record, readout_utils.is_data_from_channel(4 - front_end)),
                                                                                         converter_func=readout_utils.get_col_row_array_from_data_record_array), bins=(80, 336), range=[[1, 80], [1, 336]])
                plotting.plot_three_way(hist=occupancy_array.T, title="Occupancy of chip %d" % front_end, x_axis_title="Occupancy", filename=output_pdf)

if __name__ == "__main__":
    draw_hit_map_from_raw_data('/home/davidlp/Downloads/digital_analog/21_module_test_analog_scan.h5', 4)
