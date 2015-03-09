"""This script does a full test beam analysis. As an input raw data files with a trigger number from one
run are expected. This script does in-RAM calculations on multiple cores in parallel. 12 Gb of free RAM and 8 cores are recommended.
The analysis flow is (also mentioned again in the main section):
- Do for each DUT in parallel
  - Create a hit tables from the raw data
  - Align the hit table event number to the trigger number to be able to correlate hits in time
  - Cluster the hit table
- Create hit position correlations from the hit maps and store the arrays
- Plot the correlations as 2d heatmaps (optional)
- Take the correlation arrays and extract an offset/slope aligned to the first DUT
- Merge the cluster tables from all DUTs to one big cluster table and reference the cluster positions to the reference (DUT0) position
- Find tracks
- Align the DUT positions in z (optional)
- Fit tracks
- Plot event tracks (optional)
- Calculate residuals
- Create efficiency / distance maps
"""

# from __future__ import print_function
import logging
import progressbar
import re
import numpy as np
from math import sqrt, ceil
import pandas as pd
import tables as tb
from multiprocessing import Pool, cpu_count
from scipy.optimize import curve_fit, minimize_scalar

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib import colors, cm
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
from mpl_toolkits.mplot3d import Axes3D  # needed for 3d plotting
# from numba import jit, numpy_support, types

from pybar.analysis import analysis_utils
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.RawDataConverter import data_struct


def _create_2d_pixel_hist(fig, ax, hist2d, title=None, x_axis_title=None, y_axis_title=None, z_min=0, z_max=None):
    extent = [0.5, 80.5, 336.5, 0.5]
    if z_max is None:
        if hist2d.all() is np.ma.masked:  # check if masked array is fully masked
            z_max = 1
        else:
            z_max = 2 * ceil(hist2d.max())
    bounds = np.linspace(start=z_min, stop=z_max, num=255, endpoint=True)
    cmap = cm.get_cmap('jet')
    cmap.set_bad('w')
    norm = colors.BoundaryNorm(bounds, cmap.N)
    im = ax.imshow(hist2d, interpolation='nearest', aspect="auto", cmap=cmap, norm=norm, extent=extent)
    if title is not None:
        ax.set_title(title)
    if x_axis_title is not None:
        ax.set_xlabel(x_axis_title)
    if y_axis_title is not None:
        ax.set_ylabel(y_axis_title)
    divider = make_axes_locatable(ax)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    fig.colorbar(im, boundaries=bounds, cmap=cmap, norm=norm, ticks=np.linspace(start=z_min, stop=z_max, num=9, endpoint=True), cax=cax)


# FE-I4 data analysis
def analyze_raw_data(input_file):
    '''Std. raw data analysis of FE-I4 data. A hit table is ceated for further analysis.

    Parameters
    ----------
    input_file : pytables file
    output_file_hits : pytables file
    '''
    with AnalyzeRawData(raw_data_file=input_file, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.use_trigger_number = False
        analyze_raw_data.interpreter.use_tdc_word(False)
        analyze_raw_data.create_hit_table = True
        analyze_raw_data.create_meta_event_index = True
        analyze_raw_data.create_trigger_error_hist = True
        analyze_raw_data.create_rel_bcid_hist = True
        analyze_raw_data.create_error_hist = True
        analyze_raw_data.create_service_record_hist = True
        analyze_raw_data.create_occupancy_hist = False
        analyze_raw_data.create_tot_hist = False
        analyze_raw_data.n_bcid = 16
        analyze_raw_data.n_injections = 100
        analyze_raw_data.max_tot_value = 13
        analyze_raw_data.interpreter.set_debug_output(False)
        analyze_raw_data.interpreter.set_info_output(False)
        analyze_raw_data.interpreter.set_warning_output(False)
        analyze_raw_data.clusterizer.set_warning_output(False)
        analyze_raw_data.interpret_word_table()
        analyze_raw_data.interpreter.print_summary()
        analyze_raw_data.plot_histograms()


def analyze_hits(input_file, output_file_hits_analyzed, pdf_filename):
    '''Std. analysis of a hit table. Clusters are created.

    Parameters
    ----------
    input_file : pytables file
    output_file_hits_analyzed : pytables file
    output_pdf : PdfPager file object
    '''
    with AnalyzeRawData(raw_data_file=None, analyzed_data_file=input_file, create_pdf=True) as analyze_raw_data:
        analyze_raw_data.create_source_scan_hist = True
        analyze_raw_data.create_cluster_table = True
        analyze_raw_data.create_cluster_size_hist = True
        analyze_raw_data.create_cluster_tot_hist = True
        analyze_raw_data.analyze_hit_table(analyzed_data_out_file=output_file_hits_analyzed)
        analyze_raw_data.plot_histograms(pdf_filename=pdf_filename, analyzed_data_file=output_file_hits_analyzed)


# Common test beam analysis functions to be called in consecutive order
def process_dut(raw_data_file):
    ''' Process the raw data and create cluster. This is different for all devices '''
    analyze_raw_data(raw_data_file)
    align_events(raw_data_file[:-3] + '_interpreted.h5', raw_data_file[:-3] + '_aligned.h5')
    analyze_hits(raw_data_file[:-3] + '_aligned.h5', raw_data_file[:-3] + '_cluster.h5', pdf_filename=raw_data_file[:-3] + '.pdf')


def align_events(input_file, output_file, chunk_size=10000000):
    ''' Selects only hits from good events and checks the distance between event number and trigger number for each hit.
    If the FE data allowed a successfull event recognizion the distance is always constant (besides the fact that the trigger number overflows).
    Otherwise the event number is corrected by the trigger number. How often an inconstistency occurs is counted as well as the number of events that had to be corrected.
    Remark: Only one event analyzed wrong shifts all event numbers leading to no correlation! But usually data does not have to be corrected.

    Parameters
    ----------
    input_file : pytables file
    output_file : pytables file
    chunk_size :  int
        How many events are read at once into RAM for correction.
    '''
    logging.info('Align events to trigger number in %s', input_file)

    with tb.open_file(input_file, 'r+') as in_file_h5:
        hit_table = in_file_h5.root.Hits
        jumps = []  # variable to determine the jumps in the event-number to trigger-number offset
        n_fixed_events = 0  # events that were fixed
        with tb.open_file(output_file, 'w') as out_file_h5:
            hit_table_description = data_struct.HitInfoTable().columns.copy()
            hit_table_out = out_file_h5.createTable(out_file_h5.root, name='Hits', description=hit_table_description, title='Selected hits for test beam analysis', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False), chunkshape=(chunk_size,))
            # Correct hit event number
            for hits, _ in analysis_utils.data_aligned_at_events(hit_table, chunk_size=chunk_size):
                selected_hits = hits[(hits['event_status'] & 0b0000011111111111) == 0b0000000000000000]  # no error at all
                selector = np.array((np.mod(selected_hits['event_number'], 32768) - selected_hits['trigger_number']), dtype=np.int32)
                jumps.extend(np.unique(selector).tolist())
                n_fixed_events += np.count_nonzero(selector)
                selected_hits['event_number'] = np.divide(selected_hits['event_number'], 32768) * 32768 + selected_hits['trigger_number']
                hit_table_out.append(selected_hits)

        jumps = np.unique(np.array(jumps))
        logging.info('Found %d inconsistencies in the event number. %d events had to be corrected.', jumps[jumps != 0].shape[0], n_fixed_events)


def correlate_hits(hit_files, alignment_file, max_column, max_row):
    '''Histograms the hit column (row)  of two different devices on an event basis. If the hits are correlated a line should be seen.
    The correlation is done very simple. Not all hits of the first device are correlated with all hits of the second device. This is sufficient
    as long as you do not have too many hits per event.

    Parameters
    ----------
    input_file : pytables file
    alignment_file : pytables file
        Output file with the correlation data
    '''
    logging.info('Correlate the position of %d DUTs', len(hit_files))
    with tb.open_file(alignment_file, mode="w") as out_file_h5:
        for index, hit_file in enumerate(hit_files):
            with tb.open_file(hit_file, 'r') as in_file_h5:
                hit_table = in_file_h5.root.Hits[:]
                if index == 0:
                    first_reference = pd.DataFrame({'event_number': hit_table[:]['event_number'], 'column_%d' % index: hit_table[:]['column'], 'row_%d' % index: hit_table[:]['row'], 'tot_%d' % index: hit_table[:]['tot']})
                else:
                    logging.info('Correlate detector %d with detector %d', index, 0)
                    dut = pd.DataFrame({'event_number': hit_table[:]['event_number'], 'column_1': hit_table[:]['column'], 'row_1': hit_table[:]['row'], 'tot_1': hit_table[:]['tot']})
                    df = first_reference.merge(dut, how='left', on='event_number')
                    df.dropna(inplace=True)
                    col_corr = analysis_utils.hist_2d_index(df['column_0'] - 1, df['column_1'] - 1, shape=(max_column, max_column))
                    row_corr = analysis_utils.hist_2d_index(df['row_0'] - 1, df['row_1'] - 1, shape=(max_row, max_row))
                    out = out_file_h5.createCArray(out_file_h5.root, name='CorrelationColumn_0_%d' % index, title='Column Correlation between DUT %d and %d' % (0, index), atom=tb.Atom.from_dtype(col_corr.dtype), shape=col_corr.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out_2 = out_file_h5.createCArray(out_file_h5.root, name='CorrelationRow_0_%d' % index, title='Row Correlation between DUT %d and %d' % (0, index), atom=tb.Atom.from_dtype(row_corr.dtype), shape=row_corr.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out.attrs.filenames = [str(hit_files[0]), str(hit_files[index])]
                    out_2.attrs.filenames = [str(hit_files[0]), str(hit_files[index])]
                    out[:] = col_corr.T
                    out_2[:] = row_corr.T


def align_hits(alignment_file, output_pdf):
    '''Takes the correlation histograms, determines usefull ranges with valid data, fits the correlations and stores the correlation parameters. With the
    correlation parameters one can calculate the hit position of each DUT in the master reference coordinate system. The fits are
    also plotted.

    Parameters
    ----------
    alignment_file : pytables file
        The input file with the correlation histograms and also the output file for correlation data.
    output_pdf : PdfPager file object
    '''
    logging.info('Align hit coordinates')

    def gauss(x, *p):
        A, mu, sigma, offset = p
        return A * np.exp(-(x - mu) ** 2 / (2. * sigma ** 2)) + offset

    with tb.open_file(alignment_file, mode="r+") as in_file_h5:
        n_nodes = sum(1 for _ in enumerate(in_file_h5.root))  # Determine number of nodes, is there a better way?
        result = np.zeros(shape=(n_nodes,), dtype=[('dut_x', np.uint8), ('dut_y', np.uint8), ('offset', np.float), ('offset_error', np.float), ('slope', np.float), ('slope_error', np.float), ('sigma', np.float), ('sigma_error', np.float), ('description', np.str_, 40)])
        for node_index, node in enumerate(in_file_h5.root):
            try:
                result[node_index]['dut_x'], result[node_index]['dut_y'] = int(re.search(r'\d+', node.name).group()), node.name[-1:]
            except AttributeError:
                continue

            data = node[:]
            x = np.arange(data.shape[0])  # The column/row index

            # Start values for fitting
            mus = np.argmax(data, axis=1)
            As = np.max(data, axis=1)

            # Determine boundaries of pixels that do not overlap at all
            select_min, select_max = 0, np.amax(x)
            # FIXME: does not work with diamond data
#             select_no_data = np.where(np.sum(data, axis=0) < 0.5 * np.mean(np.sum(data, axis=0)))[0]
#
#             if len(select_no_data) > 1:
#                 try:
#                     select_min, select_max = select_no_data[np.gradient(select_no_data) > 1][0], select_no_data[np.gradient(select_no_data) > 1][-1]
#                 except IndexError:
#                     pass

            # Fit result arrays have -1 for bad fit
            mean_fitted = np.array([-1. for _ in x])
            mean_error_fitted = np.array([-1. for _ in x])
            sigma_fitted = np.array([-1. for _ in x])

            # Loop over all row/row or column/column slices and fit a gaussian to the profile
            for index in range(select_min, select_max + 1):
                p0 = [As[index], mus[index], 1., 1.]
                try:
                    coeff, var_matrix = curve_fit(gauss, x, data[index, :], p0=p0)
                    if coeff[1] - 3 * coeff[2] > select_min and coeff[1] + 3 * coeff[2] < select_max:  # Only take data of pixels that overlap
                        mean_fitted[index] = coeff[1]
                        mean_error_fitted[index] = np.sqrt(np.diag(var_matrix))[1]
                        sigma_fitted[index] = coeff[2]
                        # Plot example fit
                        if index == (select_max - select_min) / 2:
                            plt.clf()
                            gauss_fit_legend_entry = 'gaus fit: \nA=$%.1f\pm%.1f$\nmu=$%.1f\pm%.1f$\nsigma=$%.1f\pm%.1f$' % (coeff[0], np.absolute(var_matrix[0][0] ** 0.5), coeff[1], np.absolute(var_matrix[1][1] ** 0.5), coeff[2], np.absolute(var_matrix[2][2] ** 0.5))
                            plt.plot(x, data[index, :], 'o', label='data')
                            plt.plot(np.arange(np.amin(x), np.amax(x), 0.1), gauss(np.arange(np.amin(x), np.amax(x), 0.1), *coeff), '-', label=gauss_fit_legend_entry)
                            plt.plot([select_min, select_min], [np.amax(data[index, :]), np.amax(data[index, :])], "-")
                            plt.plot([select_max, select_max], [np.amax(data[index, :]), np.amax(data[index, :])], "-")
                            plt.legend(loc=0)
                            plt.title(node.title)
                            plt.xlabel('DUT %s at DUT0 = %d' % (result[node_index]['dut_x'], index))
                            plt.ylabel('#')
                            plt.grid()
                            output_pdf.savefig()
                except RuntimeError:
                    pass

            # Select only good data points for fitting
            y = mean_fitted
            y_err = mean_error_fitted
            selected_data = np.logical_and(y >= 0., y_err < 1.)

            # Fit data and create fit result function
            f = lambda x, a, b: a * x + b

            line_fit, pcov = curve_fit(f, x[selected_data], y[selected_data], sigma=y_err[selected_data], absolute_sigma=True)
            fit_fn = np.poly1d(line_fit)

            # Calculate mean sigma (is somwhat a residual) and store the actual data in result array
            mean_sigma = np.mean(np.array(sigma_fitted)[selected_data])
            mean_sigma_error = np.std(np.array(sigma_fitted)[selected_data]) / np.sqrt(x[selected_data].shape[0])
            result[node_index]['offset'], result[node_index]['offset_error'] = line_fit[1], np.absolute(pcov[1][1]) ** 0.5
            result[node_index]['slope'], result[node_index]['slope_error'] = line_fit[0], np.absolute(pcov[0][0]) ** 0.5
            result[node_index]['sigma'], result[node_index]['sigma_error'] = mean_sigma, mean_sigma_error
            result[node_index]['description'] = node.title

            # Plot selected data with fit
            plt.clf()
            plt.errorbar(x[selected_data], y[selected_data], y_err[selected_data], fmt='.')
            line_fit_legend_entry = 'line fit: ax + b\na=$%.3f\pm%.3f$\nb=$%.3f\pm%.3f$' % (line_fit[0], np.absolute(pcov[0][0]) ** 0.5, line_fit[1], np.absolute(pcov[1][1]) ** 0.5)
            plt.plot(x[selected_data], fit_fn(x[selected_data]), '-', label=line_fit_legend_entry)
            plt.legend(loc=0)
            plt.title(node.title)
            plt.xlabel('DUT %s' % result[node_index]['dut_x'])
            plt.ylabel('DUT %s' % result[node_index]['dut_y'])
            plt.grid()
            output_pdf.savefig()

        try:
            result_table = in_file_h5.create_table(in_file_h5.root, name='Correlation', description=result.dtype, title='Correlation data', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            result_table.append(result)
        except tb.exceptions.NodeError:
            logging.info('Correlation table exists already. Do not create new.')


def plot_correlations(alignment_file, output_pdf):
    '''Takes the correlation histograms and plots them

    Parameters
    ----------
    alignment_file : pytables file
        The input file with the correlation histograms and also the output file for correlation data.
    output_pdf : PdfPager file object
    '''
    logging.info('Plotting Correlations')
    with tb.open_file(alignment_file, mode="r") as in_file_h5:
        for node in in_file_h5.root:
            try:
                first, second = int(re.search(r'\d+', node.name).group()), node.name[-1:]
            except AttributeError:
                continue
            data = node[:]
            plt.clf()
            cmap = cm.get_cmap('jet', 200)
            cmap.set_bad('w')
            norm = colors.LogNorm()
            z_max = np.amax(data)
            im = plt.imshow(data, cmap=cmap, norm=norm, interpolation='nearest')
            divider = make_axes_locatable(plt.gca())
            plt.gca().invert_yaxis()
            plt.title(node.title)
            plt.xlabel('DUT %s' % first)
            plt.ylabel('DUT %s' % second)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True))
            output_pdf.savefig()


def merge_cluster_data(cluster_files, alignment_file, tracklets_file):
    '''Takes the cluster from all cluster files and merges them into one big table onto the event number.
    Empty entries are signalled with charge = 0. The position is referenced from the correlation data to the first plane.
    Function uses easily several Gb of RAM. If memory errors occur buy a better PC or chunk this function.

    Parameters
    ----------
    cluster_files : list of pytables files
        Files with cluster data
    alignment_file : pytables files
        The file with the correlation data
    track_candidates_file : pytables files
    '''
    logging.info('Merge cluster to tracklets')
    with tb.open_file(alignment_file, mode="r") as in_file_h5:
        correlation = in_file_h5.root.Correlation[:]

    # Calculate a event number index to map the cluster of all files to
    common_event_number = None
    for cluster_file in cluster_files:
        with tb.open_file(cluster_file, mode='r') as in_file_h5:
            common_event_number = in_file_h5.root.Cluster[:]['event_number'] if common_event_number is None else analysis_utils.get_max_events_in_both_arrays(common_event_number, in_file_h5.root.Cluster[:]['event_number'])

    # Create result array description, depends on the number of DUTs
    description = [('event_number', np.int64)]
    for index, _ in enumerate(cluster_files):
        description.append(('column_dut_%d' % index, np.float))
    for index, _ in enumerate(cluster_files):
        description.append(('row_dut_%d' % index, np.float))
    for index, _ in enumerate(cluster_files):
        description.append(('charge_dut_%d' % index, np.float))
    description.extend([('track_quality', np.uint32), ('n_tracks', np.uint8)])

    # Merge the cluster data from different DUTs into one table
    with tb.open_file(tracklets_file, mode='w') as out_file_h5:
        tracklets_table = out_file_h5.create_table(out_file_h5.root, name='Tracklets', description=np.zeros((1,), dtype=description).dtype, title='Tracklets', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        tracklets_array = np.zeros((common_event_number.shape[0],), dtype=description)
        for index, cluster_file in enumerate(cluster_files):
            logging.info('Add cluster file ' + str(cluster_file))
            with tb.open_file(cluster_file, mode='r') as in_file_h5:
                actual_cluster = analysis_utils.map_cluster(common_event_number, in_file_h5.root.Cluster[:])
                if index == 0:  # Position corrections are normalized to the first reference
                    offsets = np.array([0, 0])
                    slopes = np.array([1., 1.])
                else:
                    offsets = correlation[correlation['dut_y'] == index]['offset']
                    slopes = correlation[correlation['dut_y'] == index]['slope']
                tracklets_array['column_dut_%d' % index][actual_cluster['mean_row'] != 0] = slopes[0] * actual_cluster['mean_column'][actual_cluster['mean_column'] != 0] + offsets[0]
                tracklets_array['row_dut_%d' % index][actual_cluster['mean_row'] != 0] = slopes[1] * actual_cluster['mean_row'][actual_cluster['mean_column'] != 0] + offsets[1]
                tracklets_array['charge_dut_%d' % index][actual_cluster['mean_row'] != 0] = actual_cluster['charge'][actual_cluster['mean_column'] != 0]
        tracklets_array['event_number'] = common_event_number
        tracklets_table.append(tracklets_array)


def find_tracks(tracklets_file, alignment_file, track_candidates_file):
    '''Takes first DUT track hit and tries to find matching hits in subsequent DUTs.
    The output is the same array with resorted hits into tracks. A track quality is given to
    be able to cut on good tracks.
    This function is slow since the main loop happens in Python (< 1e5 tracks / second) but does the track finding
    loop on all cores in parallel (_find_tracks_loop()).

    Parameters
    ----------
    tracklets_file : string
        Input file name with merged cluster hit table from all DUTs
    alignment_file : string
        File containing the alignment information
    track_candidates_file : string
        Output file name for track candidate array
    '''
    logging.info('Build tracks from tracklets')

    with tb.open_file(alignment_file, mode='r') as in_file_h5:
        correlations = in_file_h5.root.Correlation[:]
        column_sigma = np.zeros(shape=(correlations.shape[0] / 2) + 1)
        row_sigma = np.zeros(shape=(correlations.shape[0] / 2) + 1)
        column_sigma[0], row_sigma[0] = 0, 0  # DUT0 has no correlation error
        for index in range(1, correlations.shape[0] / 2 + 1):
            column_sigma[index] = correlations['sigma'][np.where(correlations['dut_y'] == index)[0][0]]
            row_sigma[index] = correlations['sigma'][np.where(correlations['dut_y'] == index)[0][1]]

    with tb.open_file(tracklets_file, mode='r') as in_file_h5:
        tracklets = in_file_h5.root.Tracklets
        n_duts = sum(['column' in col for col in tracklets.dtype.names])
        n_slices = cpu_count() - 1
        n_tracks = tracklets.nrows
        slice_length = n_tracks / n_slices
        slices = [tracklets[i:i + slice_length] for i in range(0, n_tracks, slice_length)]

        pool = Pool(n_slices)  # let all cores work the array
        arg = [(one_slice, correlations, n_duts, column_sigma, row_sigma) for one_slice in slices]  # FIXME: slices are not aligned at event numbers, up to n_slices * 2 tracks are found wrong
        results = pool.map(_function_wrapper_find_tracks_loop, arg)
        result = np.concatenate(results)

#         _find_tracks_loop_compiled = jit((numpy_support.from_dtype(tracklets.dtype)[:], types.int32, types.float64, types.float64), nopython=True)(_find_tracks_loop)
#         _find_tracks_loop(tracklets, correlations, n_duts, column_sigma, row_sigma)
#         result = tracklets

        with tb.open_file(track_candidates_file, mode='w') as out_file_h5:
            track_candidates = out_file_h5.create_table(out_file_h5.root, name='TrackCandidates', description=in_file_h5.root.Tracklets.description, title='Track candidates', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
            track_candidates.append(result)


def align_z(track_candidates_file, alignment_file, output_pdf, z_positions=None, track_quality=1):
    '''Minimizes the squared distance between track hit and measured hit by changing the z position.
    In a perfect measurement the function should be minimal at the real DUT position. The tracks is given
    by the first and last reference hit. A track quality cut is applied to all cuts first.

    Parameters
    ----------
    track_candidates_file : pytables file
    alignment_file : pytables file
    output_pdf : PdfPager file object
    track_quality : int
        0: All tracks with hits in DUT and references are taken
        1: The track hits in DUT and reference are within 5-sigma of the correlation
        2: The track hits in DUT and reference are within 2-sigma of the correlation
    '''
    logging.info('Find relative z-position')

    def pos_error(z, dut, first_reference, last_reference):
        return np.mean(np.square(z * (last_reference - first_reference) + first_reference - dut))

    with tb.open_file(track_candidates_file, mode='r') as in_file_h5:
        n_duts = sum(['column' in col for col in in_file_h5.root.TrackCandidates.dtype.names])
        track_candidates = in_file_h5.root.TrackCandidates[::10]  # take only every 10th track

        results = np.zeros((n_duts - 2,), dtype=[('DUT', np.uint8), ('z_position_column', np.float32), ('z_position_row', np.float32)])

        for dut_index in range(1, n_duts - 1):
            logging.info('Find best z-position for DUT %d', dut_index)
            dut_selection = (1 << (n_duts - 1)) | 1 | ((1 << (n_duts - 1)) >> dut_index)
            good_track_selection = np.logical_and((track_candidates['track_quality'] & (dut_selection << (track_quality * 8))) == (dut_selection << (track_quality * 8)), track_candidates['n_tracks'] == 1)
            good_track_candidates = track_candidates[good_track_selection]

            first_reference_row, last_reference_row = good_track_candidates['row_dut_0'], good_track_candidates['row_dut_%d' % (n_duts - 1)]
            first_reference_col, last_reference_col = good_track_candidates['column_dut_0'], good_track_candidates['column_dut_%d' % (n_duts - 1)]

            z = np.arange(0, 1., 0.01)
            dut_row = good_track_candidates['row_dut_%d' % dut_index]
            dut_col = good_track_candidates['column_dut_%d' % dut_index]
            dut_z_col = minimize_scalar(pos_error, args=(dut_col, first_reference_col, last_reference_col), bounds=(0., 1.), method='bounded')
            dut_z_row = minimize_scalar(pos_error, args=(dut_row, first_reference_row, last_reference_row), bounds=(0., 1.), method='bounded')
            dut_z_col_pos_errors, dut_z_row_pos_errors = [pos_error(i, dut_col, first_reference_col, last_reference_col) for i in z], [pos_error(i, dut_row, first_reference_row, last_reference_row) for i in z]
            results[dut_index - 1]['DUT'] = dut_index
            results[dut_index - 1]['z_position_column'] = dut_z_col.x
            results[dut_index - 1]['z_position_row'] = dut_z_row.x

            # Plot actual DUT data
            plt.clf()
            plt.plot([dut_z_col.x, dut_z_col.x], [0., 1.], "--", label="DUT%d, col, z=%1.4f" % (dut_index, dut_z_col.x))
            plt.plot([dut_z_row.x, dut_z_row.x], [0., 1.], "--", label="DUT%d, row, z=%1.4f" % (dut_index, dut_z_row.x))
            plt.plot(z, dut_z_col_pos_errors / np.amax(dut_z_col_pos_errors), "-", label="DUT%d, column" % dut_index)
            plt.plot(z, dut_z_row_pos_errors / np.amax(dut_z_row_pos_errors), "-", label="DUT%d, row" % dut_index)
            plt.grid()
            plt.legend(loc=1)
            plt.ylim((np.amin(dut_z_col_pos_errors / np.amax(dut_z_col_pos_errors)), 1.))
            plt.xlabel('Relative z-position')
            plt.ylabel('Mean squared offset [a.u.]')
            plt.gca().set_yscale('log')
            plt.gca().get_yaxis().set_ticks([])
            output_pdf.savefig()

    with tb.open_file(alignment_file, mode='r+') as out_file_h5:
        z_table_out = out_file_h5.createTable(out_file_h5.root, name='Zposition', description=results.dtype, title='Relative z positions of the DUTs without references', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        z_table_out.append(results)

    z_positions_rec = [0.] + results[:]['z_position_row'].tolist() + [1.]

    if z_positions is not None:  # check reconstructed z against measured z
        z_positions_rec_abs = [i * z_positions[-1] for i in z_positions_rec]
        z_differences = [abs(i - j) for i, j in zip(z_positions, z_positions_rec_abs)]
        failing_duts = [j for (i, j) in zip(z_differences, range(5)) if i >= warn_at]
        if failing_duts:
            logging.warning('The reconstructed z postions is more than 1 cm off for DUTS %s', str(failing_duts))
        else:
            logging.info('Absoulte reconstructed z-positions %s', str(z_positions_rec_abs))
            logging.info('Difference between measured and reconstructed z-positions %s', str(z_differences))

    return z_positions_rec_abs if z_positions is not None else z_positions_rec


def event_display(track_file, z_positions, event_range, pixel_size=(250, 50), dut=None, output_pdf=None):
    '''Plots the tracks (or track candidates) of the events in the given event range.

    Parameters
    ----------
    track_file : pytables file with tracks
    z_positions : iterable
    event_range : iterable:
        (start event number, stop event number(
    pixel_size : iterable:
        (column size, row size) in um
    output_pdf : PdfPager file object or None
    '''
    with tb.open_file(track_file, "r") as in_file_h5:
        fitted_tracks = False
        try:  # data has track candidates
            table = in_file_h5.root.TrackCandidates
        except tb.NoSuchNodeError:  # data has fitted tracks
            table = in_file_h5.getNode(in_file_h5.root, name='Tracks_DUT_%d' % dut)
            fitted_tracks = True

        n_duts = sum(['column' in col for col in table.dtype.names])
        array = table[:]
        tracks = analysis_utils.get_data_in_event_range(array, event_range[0], event_range[-1])
        mpl.rcParams['legend.fontsize'] = 10
        fig = plt.figure()
        ax = fig.gca(projection='3d')
        for track in tracks:
            x, y, z = [], [], []
            for dut_index in range(0, n_duts):
                if track['row_dut_%d' % dut_index] != 0:  # No hit has row = 0
                    x.append(track['column_dut_%d' % dut_index] * pixel_size[0] * 1e-3)
                    y.append(track['row_dut_%d' % dut_index] * pixel_size[1] * 1e-3)
                    z.append(z_positions[dut_index])
            if fitted_tracks:
                scale = np.array((pixel_size[0] * 1e-3, pixel_size[1] * 1e-3, 1))
                offset = np.array((track['offset_0'], track['offset_1'], track['offset_2'])) * scale
                slope = np.array((track['slope_0'], track['slope_1'], track['slope_2'])) * scale
                linepts = offset + slope * np.mgrid[-10:10:2j][:, np.newaxis]

            n_hits = bin(track['track_quality'] & 0xFF).count('1')
            n_very_good_hits = bin(track['track_quality'] & 0xFF0000).count('1')

            if n_hits > 2:  # only plot tracks with more than 2 hits
                if fitted_tracks:
                    ax.plot(x, y, z, '.' if n_hits == n_very_good_hits else 'o')
                    ax.plot3D(*linepts.T)
                else:
                    ax.plot(x, y, z, '.-' if n_hits == n_very_good_hits else '.--')

        ax.set_xlim(0, 20)
        ax.set_ylim(0, 20)
        ax.set_zlim(z_positions[0], z_positions[-1])
        ax.set_xlabel('x [mm]')
        ax.set_ylabel('y [mm]')
        ax.set_zlabel('z [cm]')
        plt.title('Events %d - %d' % (event_range[0], event_range[-1] - 1))
        if output_pdf is not None:
            output_pdf.savefig()
        else:
            plt.show()


def fit_tracks(track_candidates_file, tracks_file, z_positions, fit_duts=None, ignore_duts=None, include_duts=[-5, -4, -3, -2, -1, 1, 2, 3, 4, 5], max_tracks=1, track_quality=1, pixel_size=(250, 50), output_pdf=None):
    '''Fits a line through selected DUT hits for selected DUTs. The selection criterion for the track candidates to fit is the track quality and the maximum number of hits per event.
    The fit is done for specified DUTs only (fit_duts). This DUT is then not included in the fit (include_duts). Bad DUTs can be always ignored in the fit (ignore_duts).

    Parameters
    ----------
    track_candidates_file : string
        file name with the track candidates table
    tracks_file : string
        file name of the created track file having the track table
    z_position : iterable
        the positions of the devices in z in cm
    fit_duts : iterable
        the duts to fit tracks for. If None all duts are used
    ignore_duts : iterable
        the duts that are not taken in a fit. Needed to exclude bad planes from track fit.
    include_duts : iterable
        the relative dut positions of dut to use in the track fit. The position is relative to the actual dut the tracks are fitted for
        e.g. actual track fit dut = 2, include_duts = [-3, -2, -1, 1] means that duts 0, 1, 3 are used for the track fit
    output_pdf : PdfPager file object
        if None plots are printed to screen
    max_tracks : int
        only events with tracks <= max tracks are taken
    pixel_size : iterable, (x dimensions, y dimension)
        the size in um of the pixels
    track_quality : int
        0: All tracks with hits in DUT and references are taken
        1: The track hits in DUT and reference are within 5-sigma of the correlation
        2: The track hits in DUT and reference are within 2-sigma of the correlation
    '''

    def create_results_array(good_track_candidates, slopes, offsets, chi2s, n_duts):
        description = [('event_number', np.int64)]
        for index in range(n_duts):
            description.append(('column_dut_%d' % index, np.float))
        for index in range(n_duts):
            description.append(('row_dut_%d' % index, np.float))
        for index in range(n_duts):
            description.append(('charge_dut_%d' % index, np.float))
        for dimension in range(3):
            description.append(('offset_%d' % dimension, np.float))
        for dimension in range(3):
            description.append(('slope_%d' % dimension, np.float))
        description.extend([('track_chi2', np.uint32), ('track_quality', np.uint32), ('n_tracks', np.uint8)])

        tracks_array = np.zeros((n_tracks,), dtype=description)
        tracks_array['event_number'] = good_track_candidates['event_number']
        tracks_array['track_quality'] = good_track_candidates['track_quality']
        tracks_array['n_tracks'] = good_track_candidates['n_tracks']
        for index in range(n_duts):
            tracks_array['column_dut_%d' % index] = good_track_candidates['column_dut_%d' % index]
            tracks_array['row_dut_%d' % index] = good_track_candidates['row_dut_%d' % index]
            tracks_array['charge_dut_%d' % index] = good_track_candidates['charge_dut_%d' % index]
        for dimension in range(3):
            tracks_array['offset_%d' % dimension] = offsets[:, dimension]
            tracks_array['slope_%d' % dimension] = slopes[:, dimension]
        tracks_array['track_chi2'] = chi2s

        return tracks_array

    with tb.open_file(track_candidates_file, mode='r') as in_file_h5:
        with tb.open_file(tracks_file, mode='w') as out_file_h5:
            n_duts = sum(['column' in col for col in in_file_h5.root.TrackCandidates.dtype.names])
            track_candidates = in_file_h5.root.TrackCandidates[:]
            fit_duts = fit_duts if fit_duts else range(n_duts)
            for fit_dut in fit_duts:  # loop over the duts to fit the tracks for
                logging.info('Fit tracks for DUT %d' % fit_dut)

                # Select track candidates
                dut_selection = 0
                for include_dut in include_duts:  # calculate mask to select DUT hits for fitting
                    if fit_dut + include_dut < 0 or (ignore_duts and fit_dut + include_dut in ignore_duts):
                        continue
                    if include_dut >= 0:
                        dut_selection |= ((1 << (n_duts - 1)) >> fit_dut) >> include_dut
                    else:
                        dut_selection |= ((1 << (n_duts - 1)) >> fit_dut) << abs(include_dut)

                if bin(dut_selection).count("1") < 2:
                    logging.warning('Insufficient track hits to do fit (< 2). Omit DUT %d' % fit_dut)
                    continue
                good_track_selection = np.logical_and((track_candidates['track_quality'] & (dut_selection << (track_quality * 8))) == (dut_selection << (track_quality * 8)), track_candidates['n_tracks'] <= max_tracks)
                good_track_candidates = track_candidates[good_track_selection]

                # Prepare track hits array to be fitted
                n_fit_duts = n_duts - len(ignore_duts) - 1 if ignore_duts else n_duts - 1
                n_fit_duts += 1 if ignore_duts and fit_dut in ignore_duts else 0
                n_fit_duts += 1 if 0 in include_duts else 0
                tmp_dut_index, n_tracks = 0, good_track_candidates['event_number'].shape[0]
                track_hits = np.zeros((n_tracks, n_fit_duts, 3))
                for dut_index in range(0, n_duts):
                    if (ignore_duts and dut_index in ignore_duts) or (0 not in include_duts and dut_index == fit_dut):
                        continue
                    xyz = np.column_stack((good_track_candidates['column_dut_%s' % dut_index], good_track_candidates['row_dut_%s' % dut_index], np.repeat(z_positions[dut_index], n_tracks)))
                    track_hits[:, tmp_dut_index, :] = xyz
                    tmp_dut_index += 1

                # Split data and fit on all available cores
                n_slices = cpu_count() - 1
                slice_length = n_tracks / n_slices
                slices = [track_hits[i:i + slice_length] for i in range(0, n_tracks, slice_length)]
                pool = Pool(n_slices)
                arg = [(one_slice, pixel_size) for one_slice in slices]  # FIXME: slices are not aligned at event numbers, up to n_slices * 2 tracks are found wrong
                results = pool.map(_function_wrapper_fit_tracks_loop, arg)
                del track_hits

                # Store results
                offsets = np.concatenate([i[0] for i in results])  # merge offsets from all cores in results
                slopes = np.concatenate([i[1] for i in results])  # merge slopes from all cores in results
                chi2s = np.concatenate([i[2] for i in results])  # merge slopes from all cores in results
                tracks_array = create_results_array(good_track_candidates, slopes, offsets, chi2s, n_duts)
                tracklets_table = out_file_h5.create_table(out_file_h5.root, name='Tracks_DUT_%d' % fit_dut, description=np.zeros((1,), dtype=tracks_array.dtype).dtype, title='Tracks fitted for DUT_%d' % fit_dut, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                tracklets_table.append(tracks_array)

                # Plot track chi2 and angular distribution
                plt.clf()
                plot_range = (0, 40000)
                plt.hist(chi2s, bins=200, range=plot_range)
                plt.grid()
                plt.xlim(plot_range)
                plt.xlabel('Track Chi2 [um*um]')
                plt.ylabel('#')
                plt.title('Track Chi2 for DUT %d tracks' % fit_dut)
                plt.gca().set_yscale('log')
                if output_pdf:
                    output_pdf.savefig()
                else:
                    plt.show()


def calculate_residuals(tracks_file, z_positions, output_pdf=None, use_duts=None, track_quality=1):
    '''Takes the tracks and calculates residuals for selected DUTs in col, row direction.
    Parameters
    ----------
    tracks_file : string
        file name with the tracks table
    z_position : iterable
        the positions of the devices in z in cm
    use_duts : iterable
        the duts to calculate residuals for. If None all duts are used
    output_pdf : PdfPager file object
        if None plots are printed to screen
    track_quality : int
        0: All tracks with hits in DUT and references are taken
        1: The track hits in DUT and reference are within 5-sigma of the correlation
        2: The track hits in DUT and reference are within 2-sigma of the correlation
    '''
    logging.info('Calculate residuals')
    with tb.open_file(tracks_file, mode='r') as in_file_h5:
        for node in in_file_h5.root:
            actual_dut = int(node.name[-1:])
            if use_duts and actual_dut not in use_duts:
                continue
            logging.info('Calculate residuals for DUT %d' % actual_dut)

            track_array = node[:]
            track_array = track_array[track_array['charge_dut_%d' % actual_dut] != 0]  # take only tracks where actual dut has a hit, otherwise residual wrong
            hits, offset, slope = np.column_stack((track_array['column_dut_%d' % actual_dut], track_array['row_dut_%d' % actual_dut], np.repeat(z_positions[actual_dut], track_array.shape[0]))), np.column_stack((track_array['offset_0'], track_array['offset_1'], track_array['offset_2'])), np.column_stack((track_array['slope_0'], track_array['slope_1'], track_array['slope_2']))
            intersection = offset + slope / slope[:, 2, np.newaxis] * (z_positions[actual_dut] - offset[:, 2, np.newaxis])  # intersection track with DUT plane
            difference = intersection - hits
            difference = difference[np.logical_and(np.logical_and(np.logical_and(intersection[:, 0] >= 0, intersection[:, 0] <= 80), intersection[:, 1] >= 0), intersection[:, 0] <= 336)]

            for i in range(2):  # col / row
                for plot_log in [False, True]:  # plot with log y or not
                    plt.clf()
                    plot_range = (-i - 1.5, i + 1.5)
                    plt.xlim(plot_range)
                    plt.grid()
                    plt.title('Residuals for DUT %d' % actual_dut)
                    plt.xlabel('Residual [Column]' if i == 0 else 'Residual [Row]')
                    plt.ylabel('#')
                    plt.hist(difference[:, 0], range=plot_range, bins=200, log=plot_log)
                    if output_pdf is not None:
                        output_pdf.savefig()
                    else:
                        plt.show()


def plot_track_density(tracks_file, output_pdf, use_duts=None, max_chi2=None):
    '''Takes the tracks and calculates the track density projected on selected DUTs.
    Parameters
    ----------
    tracks_file : string
        file name with the tracks table
    use_duts : iterable
        the duts to calculate residuals for. If None all duts are used
    output_pdf : PdfPager file object
    max_chi2 : int
        only use track with a chi2 <= max_chi2
    '''
    logging.info('Plot track density')
    with tb.open_file(tracks_file, mode='r') as in_file_h5:
        for node in in_file_h5.root:
            actual_dut = int(node.name[-1:])
            if use_duts and actual_dut not in use_duts:
                continue
            logging.info('Plot track density for DUT %d' % actual_dut)

            track_array = node[:]
            offset, slope = np.column_stack((track_array['offset_0'], track_array['offset_1'], track_array['offset_2'])), np.column_stack((track_array['slope_0'], track_array['slope_1'], track_array['slope_2']))
            intersection = offset + slope / slope[:, 2, np.newaxis] * (z_positions[actual_dut] - offset[:, 2, np.newaxis])  # intersection track with DUT plane
            if max_chi2:
                intersection = intersection[track_array['track_chi2'] <= max_chi2]

            heatmap, _, _ = np.histogram2d(intersection[:, 0], intersection[:, 1], bins=(80, 336), range=[[1, 80], [1, 336]])

            fig = Figure()
            fig.patch.set_facecolor('white')
            ax = fig.add_subplot(111)
            _create_2d_pixel_hist(fig, ax, heatmap.T, title='Track densitiy for DUT %d tracks' % actual_dut, x_axis_title="column", y_axis_title="row")
            fig.tight_layout()
            output_pdf.savefig(fig)


def calculate_efficiency(tracks_file, output_pdf, use_duts=None, max_chi2=None):
    '''Takes the tracks and calculates the hit efficiency and hit/track hit distance for selected DUTs.
    Parameters
    ----------
    tracks_file : string
        file name with the tracks table
    use_duts : iterable
        the duts to calculate residuals for. If None all duts are used
    output_pdf : PdfPager file object
    max_chi2 : int
        only use track with a chi2 <= max_chi2
    '''
    logging.info('Calculate efficiency')
    with tb.open_file(tracks_file, mode='r') as in_file_h5:
        for node in in_file_h5.root:
            actual_dut = int(node.name[-1:])
            if use_duts and actual_dut not in use_duts:
                continue
            logging.info('Calculate efficiency for DUT %d' % actual_dut)

            track_array = node[:]
            if max_chi2:
                track_array = track_array[track_array['track_chi2'] <= max_chi2]
            hits, charge, offset, slope = np.column_stack((track_array['column_dut_%d' % actual_dut], track_array['row_dut_%d' % actual_dut], np.repeat(z_positions[actual_dut], track_array.shape[0]))), track_array['charge_dut_%d' % actual_dut], np.column_stack((track_array['offset_0'], track_array['offset_1'], track_array['offset_2'])), np.column_stack((track_array['slope_0'], track_array['slope_1'], track_array['slope_2']))
            intersection = offset + slope / slope[:, 2, np.newaxis] * (z_positions[actual_dut] - offset[:, 2, np.newaxis])  # intersection track with DUT plane

            # Calculate distance between track hit and DUT hit
            scale = np.square(np.array((250, 50, 0)))
            distance = np.sqrt(np.dot(np.square(intersection - hits), scale))
            col_row_distance = np.column_stack((hits[:, 0], hits[:, 1], distance))
            distance_array = np.histogramdd(col_row_distance, bins=(80, 336, 500), range=[[1, 80], [1, 336], [0, 500]])[0]
            hh, _, _ = np.histogram2d(hits[:, 0], hits[:, 1], bins=(80, 336), range=[[1, 80], [1, 336]])
            distance_mean_array = np.average(distance_array, axis=2, weights=range(0, 500)) * sum(range(0, 500)) / hh.astype(np.float)
            distance_mean_array = np.ma.masked_invalid(distance_mean_array)
            fig = Figure()
            fig.patch.set_facecolor('white')
            ax = fig.add_subplot(111)
            _create_2d_pixel_hist(fig, ax, distance_mean_array.T, title='Distance for DUT %d' % actual_dut, x_axis_title="column", y_axis_title="row", z_min=0, z_max=150)
            fig.tight_layout()
            output_pdf.savefig(fig)

            # Calculate efficiency
            track_density, _, _ = np.histogram2d(intersection[:, 0], intersection[:, 1], bins=(80, 336), range=[[1, 80], [1, 336]])
            track_density_with_DUT_hit, _, _ = np.histogram2d(intersection[charge != 0][:, 0], intersection[charge != 0][:, 1], bins=(80, 336), range=[[1, 80], [1, 336]])
            fig = Figure()
            fig.patch.set_facecolor('white')
            ax = fig.add_subplot(111)
            efficiency = track_density_with_DUT_hit.astype(np.float) / track_density.astype(np.float) * 100.
            efficiency = np.ma.array(efficiency, mask=track_density < 10)
            _create_2d_pixel_hist(fig, ax, efficiency.T, title='Efficiency for DUT %d' % actual_dut, x_axis_title="column", y_axis_title="row", z_min=94., z_max=100.)
            fig.tight_layout()
            output_pdf.savefig(fig)
            plt.clf()
            plt.grid()
            plt.title('Efficiency per pixel')
            plt.xlabel('Efficiency [%]')
            plt.ylabel('#')
            plt.yscale('log')
            plt.title('Efficiency for DUT %d' % actual_dut)
            plt.hist(efficiency.ravel(), bins=100, range=(94, 104))
            output_pdf.savefig()


# Helper functions that are not ment to be called during analysis
def _find_tracks_loop(tracklets, correlations, n_duts, column_sigma, row_sigma):
    ''' Complex loop to resort the tracklets array inplace to form track candidates. Each track candidate
    is given a quality identifier. Not ment to be called stand alone.
    Optimizations included to make it easily compile with numba in the future. Can be called from
    several real threads if they work on different areas of the array'''

    actual_event_number = tracklets[0]['event_number']
    n_tracks = tracklets.shape[0]
    # Numba does not understand python scopes, define all used variables here
    n_actual_tracks = 0
    track_index = 0
    column, row = 0., 0.
    actual_track_column, actual_track_row = 0., 0.
    column_distance, row_distance = 0., 0.
    hit_distance = 0.
    tmp_column, tmp_row = 0., 0.
    best_hit_distance = 0.

    progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.AdaptiveETA()], maxval=n_tracks, term_width=80)
    progress_bar.start()

    for track_index, actual_track in enumerate(tracklets):
        progress_bar.update(track_index)

        if actual_track['event_number'] != actual_event_number:
            actual_event_number = actual_track['event_number']
            for i in range(n_actual_tracks):
                tracklets[track_index - 1 - i]['n_tracks'] = n_actual_tracks
            n_actual_tracks = 0

        n_actual_tracks += 1
        first_hit_set = False

        for dut_index in xrange(n_duts):
            actual_column_sigma, actual_row_sigma = column_sigma[dut_index], row_sigma[dut_index]
            if not first_hit_set and actual_track['row_dut_%d' % dut_index] != 0:
                actual_track_column, actual_track_row = actual_track['column_dut_%d' % dut_index], actual_track['row_dut_%d' % dut_index]
                first_hit_set = True
                actual_track['track_quality'] |= (65793 << (n_duts - dut_index - 1))  # first track hit has best quality by definition
            else:
                # Find best (closest) DUT hit
                close_hit_found = False
                for hit_index in xrange(track_index, tracklets.shape[0]):  # loop over all not sorted hits of actual DUT
                    if tracklets[hit_index]['event_number'] != actual_event_number:
                        break
                    column, row = tracklets[hit_index]['column_dut_%d' % dut_index], tracklets[hit_index]['row_dut_%d' % dut_index]
                    column_distance, row_distance = abs(column - actual_track_column), abs(row - actual_track_row)
                    hit_distance = sqrt((column_distance * 5) * (column_distance * 5) + row_distance * row_distance)

                    if row != 0:  # Track hit found
                        actual_track['track_quality'] |= (1 << (n_duts - dut_index - 1))

                    if row != 0 and not close_hit_found and column_distance < 5 * actual_column_sigma and row_distance < 5 * actual_row_sigma:  # good track hit (5 sigma search region)
                        tmp_column, tmp_row = tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index]
                        tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index] = column, row
                        tracklets[hit_index]['column_dut_%d' % dut_index], tracklets[hit_index]['row_dut_%d' % dut_index] = tmp_column, tmp_row
                        best_hit_distance = hit_distance
                        close_hit_found = True
                    elif row != 0 and close_hit_found and hit_distance < best_hit_distance:  # found better track hit
                        tmp_column, tmp_row = tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index]
                        tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index] = column, row
                        tracklets[hit_index]['column_dut_%d' % dut_index], tracklets[hit_index]['row_dut_%d' % dut_index] = tmp_column, tmp_row
                        best_hit_distance = hit_distance
                    elif row == 0 and not close_hit_found:  # take no hit if no good hit is found
                        tmp_column, tmp_row = tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index]
                        tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index] = column, row
                        tracklets[hit_index]['column_dut_%d' % dut_index], tracklets[hit_index]['row_dut_%d' % dut_index] = tmp_column, tmp_row

                # Set track quality of actual DUT from closest DUT hit
                column, row = tracklets[track_index]['column_dut_%d' % dut_index], tracklets[track_index]['row_dut_%d' % dut_index]
                column_distance, row_distance = abs(column - actual_track_column), abs(row - actual_track_row)
                if column_distance < 2 * actual_column_sigma and row_distance < 2 * actual_row_sigma:  # high quality track hits
                    actual_track['track_quality'] |= (65793 << (n_duts - dut_index - 1))
                elif column_distance < 5 * actual_column_sigma and row_distance < 5 * actual_row_sigma:  # low quality track hits
                    actual_track['track_quality'] |= (257 << (n_duts - dut_index - 1))
    else:
        for i in range(n_actual_tracks):
            tracklets[track_index - i]['n_tracks'] = n_actual_tracks

    progress_bar.finish()
    return tracklets


def _fit_tracks_loop(track_hits, pixel_dimension):
    ''' Do 3d line fit and calculate chi2 for each fit. '''
    def line_fit_3d(data, scale):
        datamean = data.mean(axis=0)
        offset, slope = datamean, np.linalg.svd(data - datamean)[2][0]  # http://stackoverflow.com/questions/2298390/fitting-a-line-in-3d
        intersections = offset + slope / slope[2] * (data.T[2][:, np.newaxis] - offset[2])  # fitted line and dut plane intersections (here: points)
        chi2 = np.sum(np.dot(np.square(data - intersections), scale), dtype=np.uint32)  # chi2 of the fit in pixel dimension units
        return datamean, slope, chi2

    slope = np.zeros((track_hits.shape[0], 3, ))
    offset = np.zeros((track_hits.shape[0], 3, ))
    chi2 = np.zeros((track_hits.shape[0], ))

    scale = np.square(np.array((pixel_dimension[0], pixel_dimension[-1], 0)))

    for index, actual_hits in enumerate(track_hits):  # loop over selected track candidate hits and fit
        offset[index], slope[index], chi2[index] = line_fit_3d(actual_hits, scale)
#         if chi2[index] < 1e1:
#             print chi2[index]
#             ax = m3d.Axes3D(plt.figure())
#             ax.set_xlim(0, 80)
#             ax.set_ylim(0, 336)
#             ax.set_zlim(0, 13)
#             plot_hits = np.column_stack(actual_hits)
#             ax.plot3D(plot_hits[0], plot_hits[1], plot_hits[2], 'o')
#             linepts = offset[index] + slope[index] * np.mgrid[-10:10:2j][:, np.newaxis]
#             ax.plot3D(*linepts.T)
#             plt.show()

    return offset, slope, chi2


def _function_wrapper_find_tracks_loop(args):  # needed for multiprocessing call with arguments
    return _find_tracks_loop(*args)


def _function_wrapper_fit_tracks_loop(args):  # needed for multiprocessing call with arguments
    return _fit_tracks_loop(*args)


if __name__ == "__main__":
    # Input file names
    raw_data_files = ['C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_132_SCC_29_3.4_GeV_0.h5',  # the first DUT is the master reference DUT
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_213_SCC_99_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_214_SCC_146_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_201_SCC_166_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_207_SCC_112_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_216_SCC_45_3.4_GeV_0.h5']  # the last DUT is the second reference DUT

    # Output file names
    alignment_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\Alignment.h5'
    tracklets_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\Tracklets.h5'
    track_candidates_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\TrackCandidates.h5'
    tracks_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\Tracks.h5'
    pdf_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\Plots_2.pdf'

    # Measured z positions (optional)
    z_positions = [0., 1.95, 5.05, 7.2, 10.88, 12.83]  # in cm
    warn_at = 1.  # difference in cm between measure / reconstructed z position

    hit_files_aligned = [raw_data_file[:-3] + '_aligned.h5' for raw_data_file in raw_data_files]
    cluster_files = [raw_data_file[:-3] + '_cluster.h5' for raw_data_file in raw_data_files]

    # The following shows a complete test beam analysis by calling the seperate function in correct order
    with PdfPages(pdf_file) as output_pdf:
        # Do seperate DUT data processing in parallel. The output is a cluster table.
        pool = Pool()
        pool.map(process_dut, raw_data_files)
        # Correlate the row/col of each DUT
        correlate_hits(hit_files_aligned, alignment_file, max_column=80, max_row=336)
        plot_correlations(alignment_file, output_pdf)
        # Create alignment data for the DUT positions to the first DUT from the correlation data
        align_hits(alignment_file, output_pdf)
        # Correct all DUT hits via alignment information and merge the cluster tables to one tracklets table aligned at the event number
        merge_cluster_data(cluster_files, alignment_file, tracklets_file)
        # Find tracks from the tracklets and stores the with quality indicator into track candidates table
        find_tracks(tracklets_file, alignment_file, track_candidates_file)
        # optional: try to deduce the devices z positions. Difficult for parallel tracks / bad resolution
        align_z(track_candidates_file, alignment_file, output_pdf, z_positions, track_quality=1)
        # Fit the track candidates and create new track table
        fit_tracks(track_candidates_file, tracks_file, z_positions, fit_duts=None, ignore_duts=[2, 3], max_tracks=1, track_quality=1, pixel_size=(250, 50), output_pdf=output_pdf)
        # optional: plot some tracks (or track candidates) of selected events
        event_display(tracks_file, z_positions, event_range=(0, 10), pixel_size=(250, 50), dut=1, output_pdf=output_pdf)
        # Calculate the residuals to check the alignment
        calculate_residuals(tracks_file, z_positions, use_duts=None, output_pdf=output_pdf)
        # Plot the track density on selected DUT planes
        plot_track_density(tracks_file, output_pdf=output_pdf, use_duts=None, max_chi2=200000)
        # Calculate the efficiency and mean hit/track hit distance
        calculate_efficiency(tracks_file, output_pdf=output_pdf, use_duts=None, max_chi2=200000)
