"""This class provides often needed analysis functions, for analysis that is done with python.
"""

import logging
import pandas as pd
import numpy as np
import tables as tb
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


class AnalysisUtils(object):
    """A class to analyze FE-I4 data with Python"""
    def __init__(self, raw_data_file=None, analyzed_data_file=None):
        self.set_standard_settings()

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    def set_standard_settings(self):
        pass

    # @profile
    def correlate_events(self, data_frame_fe_1, data_frame_fe_2):
        '''Correlates events from different Fe by the event number

        Parameters
        ----------
        data_frame_fe_1 : pandas.dataframe
        data_frame_fe_2 : pandas.dataframe

        Returns
        -------
        Merged pandas dataframe.
        '''
        logging.info("Correlating events")
        return data_frame_fe_1.merge(data_frame_fe_2, how='left', on='event_number')  # join in the events that the triggered fe sees, only these are interessting

    def remove_duplicate_hits(self, data_frame):
        '''Removes duplicate hits, possible due to Fe error or Tot = 14 hits.

        Parameters
        ----------
        data_frame : pandas.dataframe

        Returns
        -------
        pandas dataframe.
        '''
        # remove duplicate hits from TOT = 14 hits or FE data error and count how many have been removed
        df_length = len(data_frame.index)
        data_frame = data_frame.drop_duplicates(cols=['event_number', 'col', 'row'])
        logging.info("Removed %d duplicates in trigger FE data" % (df_length - len(data_frame.index)))
        return data_frame

    # @profile
    def get_hits_with_n_cluster_per_event(self, hits_table, cluster_table, n_cluster=1):
        '''Selects the hits with a certain number of cluster.

        Parameters
        ----------
        hits_table : pytables.table
        cluster_table : pytables.table

        Returns
        -------
        pandas.DataFrame
        '''
        logging.info("Calculate hits with %d clusters" % n_cluster)
        data_frame_hits = pd.DataFrame({'event_number': hits_table[:]['event_number'], 'column': hits_table[:]['column'], 'row': hits_table[:]['row']})
        data_frame_hits = data_frame_hits.set_index(keys='event_number')
        n_cluster_in_events = self.get_n_cluster_in_events(cluster_table)
        events_with_n_cluster = n_cluster_in_events[n_cluster_in_events[:, 1] == n_cluster, 0]
        data_frame_hits = data_frame_hits.reset_index()
        return data_frame_hits.loc[events_with_n_cluster]

    # @profile
    def get_n_cluster_in_events(self, cluster_table):
        '''Calculates the number of cluster in every event.

        Parameters
        ----------
        cluster_table : pytables.table

        Returns
        -------
        numpy.Array
            First dimension is the event number
            Second dimension is the number of cluster of the event
        '''
        logging.info("Calculate the number of cluster in every event")
        event_number_array = cluster_table[:]['event_number']
        cluster_in_event = np.bincount(event_number_array)  # for one cluster one event number is given, counts how many different event_numbers are there for each event number from 0 to max event number
        event_number = np.nonzero(cluster_in_event)[0]
        return np.vstack((event_number, cluster_in_event[event_number])).T

    # @profile
    def get_n_cluster_per_event_hist(self, cluster_table):
        '''Calculates the number of cluster in every event.

        Parameters
        ----------
        cluster_table : pytables.table

        Returns
        -------
        numpy.Histogram
        '''
        logging.info("Histogram number of cluster per event")
        cluster_in_events = self.get_n_cluster_in_events(cluster_table)[:, 1]  # get the number of cluster for every event
        return np.histogram(cluster_in_events, bins=range(0, np.max(cluster_in_events) + 2))  # histogram the occurrence of n cluster per event

    # @profile
    def histogram_correlation(self, data_frame_combined):
        '''Takes a dataframe with combined hit data from two Fe and correlates for each event each hit from one Fe to each hit of the other Fe. 

        Parameters
        ----------
        data_frame_combined : pandas.DataFrame

        Returns
        -------
        [numpy.Histogram, numpy.Histogram]
        '''
        logging.info("Histograming correlations")
        corr_row = np.histogram2d(data_frame_combined['row_fe0'], data_frame_combined['row_fe1'], bins=(336, 336), range=[[1, 336], [1, 336]])
        corr_col = np.histogram2d(data_frame_combined['column_fe0'], data_frame_combined['column_fe1'], bins=(80, 80), range=[[1, 80], [1, 80]])
        return corr_col, corr_row

    def histogram_tot(self, array, label='tot'):
        '''Takes the numpy hit/cluster array and histograms the tot values

        Parameters
        ----------
        hit_array : numpy.ndarray

        Returns
        -------
        numpy.Histogram
        '''
        logging.info("Histograming tot values")
        return np.histogram(a=array[label], bins=16, range=(0,16))


if __name__ == "__main__":
    pass
