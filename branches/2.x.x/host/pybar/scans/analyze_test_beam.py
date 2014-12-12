"""This script does a full test beam analysis (not completed yet). As an input raw data files with a trigger number from one
run are expected.
The analysis flow is:
- Do for each DUT in parallel
  - Create a hit tables from the raw data
  - Align the hit table event number to the trigger number to be able to correlate hits in time
  - Cluster the hit table
- Create hit position correlations from the hit maps and store the arrays
- Plot the correlations as 2d heatmaps
- Take the correlation arrays and extract an offset/slope to the first DUT
- Merge the cluster tables from all DUTs to one big cluster table and reference the cluster positions to
the reference (DUT0) position.
TBD:
- Find tracks
- Align the DUT positions in z
- Fit tracks
- Create efficiency maps
"""
import logging
import re
import numpy as np
import pandas as pd
import tables as tb
from multiprocessing import Pool
from scipy.optimize import curve_fit
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import colors, cm
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

from pybar.analysis import analysis_utils
from pybar.analysis.analyze_raw_data import AnalyzeRawData
from pybar.analysis.RawDataConverter import data_struct


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
        
def align_events(input_file, output_file, chunk_size = 10000000):
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
    logging.info('Align events to trigger number in %s' % input_file)
    
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
        logging.info('Found %d inconsistencies in the event number. %d events had to be corrected.' % (jumps[jumps != 0].shape[0], n_fixed_events))

def process_dut(raw_data_file):  # called for each DUT on different CPUs in parallel
    analyze_raw_data(raw_data_file)
    align_events(raw_data_file[:-3] + '_interpreted.h5', raw_data_file[:-3] + '_aligned.h5')
    analyze_hits(raw_data_file[:-3] + '_aligned.h5', raw_data_file[:-3] + '_cluster.h5', pdf_filename=raw_data_file[:-3] + '.pdf')

def correlate_hits(hit_files, correlation_file):
    '''Histograms the hit column (row)  of two different devices on an event basis. If the hits are correlated a line should be seen.
    The correlation is done very simple. Not all hits of the first device are correlated with all hits of the second device. This is sufficient
    as long as you do not have too many hits per event.

    Parameters
    ----------
    input_file : pytables file
    correlation_file : pytables file
        Output file with the correlation data
    '''
    logging.info('Correlate the position of %d DUTs' % len(hit_files))
    with tb.open_file(correlation_file, mode="w") as out_file_h5:
        for index, hit_file in enumerate(hit_files):
            with tb.open_file(hit_file, 'r') as in_file_h5:
                hit_table = in_file_h5.root.Hits[:]
                if index == 0:
                    first_reference = pd.DataFrame({'event_number':hit_table[:]['event_number'], 'column_%d' % index:hit_table[:]['column'],'row_%d' % index:hit_table[:]['row'],'tot_%d' % index:hit_table[:]['tot']})
                else:
                    logging.info('Correlate detector %d with detector %d' % (index, 0))
                    dut = pd.DataFrame({'event_number':hit_table[:]['event_number'], 'column_1':hit_table[:]['column'],'row_1':hit_table[:]['row'],'tot_1':hit_table[:]['tot']})
                    df = first_reference.merge(dut, how='left', on='event_number')
                    df.dropna(inplace=True)
                    col_corr = analysis_utils.hist_2d_index(df['column_0'] - 1, df['column_1'] - 1, shape=(80, 80))
                    row_corr = analysis_utils.hist_2d_index(df['row_0'] - 1, df['row_1'] - 1, shape=(336, 336))
                    out = out_file_h5.createCArray(out_file_h5.root, name='CorrelationColumn_0_%d' % index, title='Column Correlation between DUT %d and %d' % (0, index), atom=tb.Atom.from_dtype(col_corr.dtype), shape=col_corr.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out_2 = out_file_h5.createCArray(out_file_h5.root, name='CorrelationRow_0_%d' % index, title='Row Correlation between DUT %d and %d' % (0, index), atom=tb.Atom.from_dtype(row_corr.dtype), shape=row_corr.shape, filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                    out.attrs.filenames = [str(hit_files[0]), str(hit_files[index])]
                    out_2.attrs.filenames = [str(hit_files[0]), str(hit_files[index])]             
                    out[:] = col_corr.T
                    out_2[:] = row_corr.T
                                       
def align_hits(correlation_file, output_pdf):
    '''Takes the correlation histograms, determines usefull ranges with valid data, fits the correlations and stores the correlation parameters. With the
    correlation parameters one can calculate the hit position of each DUT in the master reference coordinate system. The fits are
    also plotted.

    Parameters
    ----------
    correlation_file : pytables file
        The input file with the correlation histograms and also the output file for correlation data.
    output_pdf : PdfPager file object
    '''
    logging.info('Align hit coordinates')

    def gauss(x, *p):
        A, mu, sigma, offset = p
        return A*np.exp(-(x-mu)**2/(2.*sigma**2)) + offset

    with tb.open_file(correlation_file, mode="r+") as in_file_h5: 
        n_nodes = sum(1 for _ in enumerate(in_file_h5.root))  # Determine number of nodes, is there a better way?
        result = np.zeros(shape=(n_nodes, ), dtype=[('dut_x', np.uint8), ('dut_y', np.uint8), ('offset', np.float), ('offset_error', np.float), ('slope', np.float), ('slope_error', np.float), ('sigma', np.float), ('sigma_error', np.float), ('description', np.str_, 40)]) 
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
            select_no_data = np.where(np.sum(data, axis=0) == 0)[0]
            if len(select_no_data) > 0:
                select_min, select_max = select_no_data[np.gradient(select_no_data) > 1][0], select_no_data[np.gradient(select_no_data) > 1][-1]

            mean_fitted = []
            mean_error_fitted = []
            sigma_fitted = []

            # Loop over all row/row or column/column slices and fit a gaussian to the profile
            for i in range(data.shape[0]):
                if i < select_min or i > select_max:
                    mean_fitted.append(-1)
                    mean_error_fitted.append(-1)
                    sigma_fitted.append(-1)
                    continue
                p0 = [As[i], mus[i], 1., 1.]
                try:
                    coeff, var_matrix = curve_fit(gauss, x, data[i, :], p0=p0)
                    if coeff[1] - 3 * coeff[2] > select_min and coeff[1] + 3 * coeff[2] < select_max:  # Only take data of pixels that overlap
                        mean_fitted.append(coeff[1])
                        mean_error_fitted.append(np.sqrt(np.diag(var_matrix))[1])
                        sigma_fitted.append(coeff[2])
                    else:
                        mean_fitted.append(-1)
                        mean_error_fitted.append(-1)
                        sigma_fitted.append(-1)
                except RuntimeError:  # Mark failed fits by setting results to negative numbers
                    mean_fitted.append(-1)
                    mean_error_fitted.append(-1)
                    sigma_fitted.append(-1)

            # Select only good data points for fitting
            y = np.array(mean_fitted)
            y_err = np.array(mean_error_fitted)
            selected_data = np.logical_and(y >= 0., y_err < 1.)
            selected_data[np.logical_or(selected_data < select_min, selected_data > select_max)] = False
            #print selected_data.shape

            # Fit data and create fit result function
            f = lambda x, a, b: a*x + b
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

def plot_correlations(correlation_file, output_pdf):
    '''Takes the correlation histograms and plots them

    Parameters
    ----------
    correlation_file : pytables file
        The input file with the correlation histograms and also the output file for correlation data.
    output_pdf : PdfPager file object
    '''
    logging.info('Plotting Correlations')
    with tb.open_file(correlation_file, mode="r") as in_file_h5:
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
            bounds = np.linspace(start=0, stop=z_max, num=255, endpoint=True)
            im = plt.imshow(data, cmap=cmap, norm=norm, interpolation='nearest')
            divider = make_axes_locatable(plt.gca())
            plt.gca().invert_yaxis()
            plt.title(node.title)
            plt.xlabel('DUT %s' % first)
            plt.ylabel('DUT %s' % second)
            cax = divider.append_axes("right", size="5%", pad=0.1)
            plt.colorbar(im, cax=cax, ticks=np.linspace(start=0, stop=z_max, num=9, endpoint=True)) 
            output_pdf.savefig()
            

def merge_cluster_data(cluster_files, correlation_file, track_candidates_file):
    '''Takes the cluster from all cluster files and merges them into one big table. The position is
    referenced from the correlation data to the first plane. Function uses easily 8 Gb of RAM.
    If memory errors occur buy a better PC or chunk this function.

    Parameters
    ----------
    cluster_files : list of pytables files 
        Files with cluster data
    correlation_file : pytables files
        The file with the correlation data
    track_candidates_file : pytables files
    '''
    logging.info('Merge cluster to track candidates')
    with tb.open_file(correlation_file, mode="r") as in_file_h5:
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
    description.extend([('track_quality', np.uint8), ('n_tracks', np.uint8)])
  
    # Merge the cluster data from different DUTs into one table
    with tb.open_file(track_candidates_file, mode='w') as out_file_h5:
        track_candidates_table = out_file_h5.create_table(out_file_h5.root, name='TrackCandidates', description=np.zeros((1, ), dtype=description).dtype, title='Track Candidates', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        track_candidates_array = np.zeros((common_event_number.shape[0], ), dtype=description)
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
                track_candidates_array['column_dut_%d' % index][actual_cluster['mean_row'] != 0] = slopes[0] * actual_cluster['mean_column'][actual_cluster['mean_column'] != 0] + offsets[0]
                track_candidates_array['row_dut_%d' % index][actual_cluster['mean_row'] != 0] = slopes[1] * actual_cluster['mean_row'][actual_cluster['mean_column'] != 0] + offsets[1]
                track_candidates_array['charge_dut_%d' % index][actual_cluster['mean_row'] != 0] = actual_cluster['charge'][actual_cluster['mean_column'] != 0]
        track_candidates_array['event_number'] = common_event_number
        track_candidates_table.append(track_candidates_array)

if __name__ == "__main__":
    raw_data_files = ['C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_132_SCC_29_3.4_GeV_0.h5',  # the first DUT is the master reference DUT
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_213_SCC_99_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_214_SCC_146_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_201_SCC_166_3.4_GeV_0.h5', 
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_207_SCC_112_3.4_GeV_0.h5',
                      'C:\\Users\\DavidLP\\Desktop\\tb\\BOARD_ID_216_SCC_45_3.4_GeV_0.h5']

    correlation_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\Correlations.h5'
    track_candidates_file = 'C:\\Users\\DavidLP\\Desktop\\tb\\TrackCandidates.h5'
    output_pdf = PdfPages(correlation_file[:-3] + '.pdf')
    hit_files_aligned = [raw_data_file[:-3] + '_aligned.h5' for raw_data_file in raw_data_files]
    cluster_files = [raw_data_file[:-3] + '_cluster.h5' for raw_data_file in raw_data_files]

    # Do seperate DUT data processing in parallel
    pool = Pool()
    pool.map(process_dut, raw_data_files)
         
    correlate_hits(hit_files_aligned, correlation_file)    
    plot_correlations(correlation_file, output_pdf)
    align_hits(correlation_file, output_pdf)
    output_pdf.close()
    merge_cluster_data(cluster_files, correlation_file, track_candidates_file)
    