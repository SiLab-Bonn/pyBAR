"""This script takes the data of a source scan and determines the number of events, the beam spot and the number of particles per event as a function of time.
"""
import logging
import pprint
from datetime import datetime

from matplotlib.backends.backend_pdf import PdfPages

from analysis import analysis
from analysis import analysis_utils


analysis_configuration = {
    'scan_base': ['data//SCC_99//20V//SCC_99_ext_trigger_gdac_scan_432'],
    'scan_parameter': False,#'GDAC',  # if set the scan_bases represent multiple files with this scan parameter changing, otherwise False
    'combine_n_readouts': 1,
    'time_line_absolute': False,
    'plot_occupancy_hists': False,
    'plot_n_cluster_hists': False,
    'include_no_cluster': False,
    'output_file': 'data//SCC_99//20V//beam_analysis_rate.h5',  # if set the data is stored into an hdf5 file with this file name, otherwise False
    'output_pdf': None#PdfPages('data//SCC_99//20V//beam_analysis.pdf')
}

if __name__ == "__main__":
    start_time = datetime.now()

    logging.info('Use the following files')
    logging.info(pprint.pformat(analysis_configuration['scan_base']))

    analysis.analyze_beam_spot(**analysis_configuration)
    analysis.analyze_event_rate(**analysis_configuration)
    analysis.analyse_n_cluster_per_event(**analysis_configuration)

    if analysis_configuration['output_pdf'] is not None:
        analysis_configuration['output_pdf'].close()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
