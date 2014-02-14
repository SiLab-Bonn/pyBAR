"""This script takes the data of a source scan and determines the number of events, the beam spot and the number of particles per event as a function of time.
"""
import logging
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages
from analysis import analysis

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


analysis_configuration = {
    'scan_base': ['data//SCC_50//SCC_50_ext_trigger_scan_21', ],
    'combine_n_readouts': 1000,
    'time_line_absolute': True,
    'output_pdf': PdfPages('data//SCC_50//SCC_50_ext_trigger_scan_21_beam_analysis.pdf')
}

if __name__ == "__main__":
    start_time = datetime.now()
    analysis.analyze_beam_spot(**analysis_configuration)
    analysis.analyze_event_rate(**analysis_configuration)
    analysis.analyse_n_cluster_per_event(**analysis_configuration)
    analysis_configuration['output_pdf'].close()
    logging.info('Script runtime %.1f seconds' % (datetime.now() - start_time).total_seconds())
