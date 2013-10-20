''' Script to convert the raw data and to plot all histograms'''
import tables as tb
import numpy as np

import data_struct
from plotting import plotting
from RawDataConverter.data_interpreter import PyDataInterpreter
from RawDataConverter.data_histograming import PyDataHistograming

class AnalyzeRawData(object):
    """A class to analyze FE-I4 raw data"""
    def __init__(self, input_file = None, output_file = None):
        self.interpreter = PyDataInterpreter()
        self.histograming = PyDataHistograming()
        self._input_file = input_file
        self._output_file = output_file
        self.out_file_h5 = None
        self.meta_event_index = None
        self.set_standard_settings()
        
    def __enter__(self):
        return self
        
    def __exit__(self, type, value, traceback):
        del self.interpreter
        del self.histograming
    
    def set_standard_settings(self):
        self._chunk_size = 2000000
        self._filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        self.FEI4B = False
        self.create_hit_table = False
        self.create_meta_event_index = False
        self.create_occupancy_hist = True
        self.create_tot_hist = True
        self.create_rel_bcid_hist = True
        self.create_trigger_error_hist = True
        self.create_error_hist = True
        self.create_service_record_hist = True
        self.create_threshold_hists = False
        
    @property
    def chunk_size(self):
        return self._chunk_size
    @chunk_size.setter
    def chunk_size(self,value):
        self._chunk_size = value
    
    @property    
    def create_hit_table(self):
        return self._create_hit_table
    @create_hit_table.setter
    def create_hit_table(self, value):
        self._create_hit_table = value

    @property
    def create_occupancy_hist(self):
        return self._create_occupancy_hist
    @create_occupancy_hist.setter
    def create_occupancy_hist(self, value):
        self._create_occupancy_hist = value
        self.histograming.create_occupancy_hist(value)
        
    @property
    def create_tot_hist(self):
        return self._create_occupancy_hist
    @create_tot_hist.setter
    def create_tot_hist(self, value):
        self._create_tot_hist = value
        self.histograming.create_tot_hist(value)
        
    @property
    def create_rel_bcid_hist(self):
        return self._create_rel_bcid_hist
    @create_rel_bcid_hist.setter
    def create_rel_bcid_hist(self, value):
        self._create_rel_bcid_hist = value
        self.histograming.create_rel_bcid_hist(value)
        
    @property
    def create_threshold_hists(self):
        return self._create_threshold_hists
    @create_threshold_hists.setter
    def create_threshold_hists(self, value):
        self._create_threshold_hists = value
        
    @property
    def create_error_hist(self):
        return self._create_error_hist
    @create_error_hist.setter
    def create_error_hist(self, value):
        self._create_error_hist = value
        
    @property
    def create_trigger_error_hist(self):
        return self._create_trigger_error_hist
    @create_trigger_error_hist.setter
    def create_trigger_error_hist(self, value):
        self._create_trigger_error_hist = value
        
    @property
    def create_service_record_hist(self):
        return self._create_service_record_hist
    @create_service_record_hist.setter
    def create_service_record_hist(self, value):
        self._create_service_record_hist = value
    
    @property    
    def create_meta_event_index(self):
        return self._create_meta_event_index
    @create_meta_event_index.setter
    def create_meta_event_index(self, value):
        self._create_meta_event_index = value
        
    @property    
    def FEI4B(self):
        return self._FEI4B
    @FEI4B.setter
    def FEI4B(self, value):
        self._FEI4B = value
        self.interpreter.set_FEI4B(value)
        
    @property    
    def n_bcid(self):
        """Get the numbers of BCIDs (usually 16) of one event."""
        return self._n_bcid
    @n_bcid.setter
    def n_bcid(self, value):
        """Set the numbers of BCIDs (usually 16) of one event."""
        raise NotImplementedError, "Not implemented, ask David"
        self._n_bcid = value
        
    @property    
    def max_tot_value(self):
        """Get maximum TOT value that is considered to be a hit"""
        return self._max_tot_value
    @max_tot_value.setter
    def max_tot_value(self, value):
        """Set maximum TOT value that is considered to be a hit"""
        raise NotImplementedError, "Not implemented, ask David"
        self._max_tot_value = value
   
    def interpret_word_table(self, input_file = None, output_file = None, FEI4B = False):    
        if(input_file != None):
            self._input_file = input_file
            
        if(output_file != None):
            self._output_file = output_file
            
        self.FEI4B = FEI4B
        
        hits = np.empty((self._chunk_size,), dtype= 
                        [('eventNumber', np.uint32), 
                         ('triggerNumber',np.uint32),
                         ('relativeBCID',np.uint8),
                         ('LVLID',np.uint16),
                         ('column',np.uint8),
                         ('row',np.uint16),
                         ('tot',np.uint8),
                         ('BCID',np.uint16),
                         ('triggerStatus',np.uint8),
                         ('serviceRecord',np.uint32),
                         ('eventStatus',np.uint8)
                         ])
        print 'Interpreting:',
        self._filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
        with tb.openFile(self._input_file, mode = "r") as in_file_h5:
            with tb.openFile(self._output_file, mode = "w", title = "Interpreted FE-I4 raw data") as self.out_file_h5:
                if (self._create_hit_table == True):
                    hit_table = self.out_file_h5.createTable(self.out_file_h5.root, name = 'Hits', description = data_struct.HitInfoTable, title = 'hit_data', filters = self._filter_table, chunkshape=(self._chunk_size/100,))
                self.meta_data = in_file_h5.root.meta_data[:]
                try:
                    scan_parameters = in_file_h5.root.scan_parameters[:]
                    self.histograming.add_scan_parameter(scan_parameters)
                except tb.exceptions.NoSuchNodeError:
                    scan_parameters = None
                    self.histograming.set_no_scan_parameter()
            
                table_size = in_file_h5.root.raw_data.shape[0]
                meta_data_size = self.meta_data.shape[0]
                         
                self.interpreter.reset_event_variables()
                self.interpreter.reset_counters()
                self.interpreter.set_hits_array(hits)
                self.interpreter.set_meta_data(self.meta_data)                   
                  
                self.meta_event_index = np.zeros((meta_data_size,), dtype=[('metaEventIndex', np.uint32)])
                self.interpreter.set_meta_event_data(self.meta_event_index)
                
                for iWord in range(0,table_size, self._chunk_size):
                    raw_data = in_file_h5.root.raw_data.read(iWord,iWord+self._chunk_size)
                    self.interpreter.interpret_raw_data(raw_data)
                    if(iWord == range(0,table_size, self._chunk_size)[-1]): # store hits of the latest event
                        self.interpreter.store_event_hits()
                    Nhits = self.interpreter.get_n_array_hits()
                    if(scan_parameters != None):
                        nEventIndex = self.interpreter.get_n_meta_data_event()
                        self.histograming.add_meta_event_index(self.meta_event_index, nEventIndex)
                    self.histograming.add_hits(hits[:Nhits], Nhits)
                    if (self._create_hit_table == True):
                        hit_table.append(hits[:Nhits])
                    print int(float(float(iWord)/float(table_size)*100.)),
            
                if (self._create_hit_table == True):
                    hit_table.flush()  
                self._store_additional_data()
                print '100 done'
        del hits     
        
    def _store_additional_data(self):
        if (self._create_meta_event_index):
            meta_data_size = self.meta_data.shape[0]
            nEventIndex = self.interpreter.get_n_meta_data_event()  
            if (meta_data_size == nEventIndex):
                meta_data_out_table = self.out_file_h5.createTable(self.out_file_h5.root, name = 'MetaData', description = data_struct.MetaInfoOutTable, title = 'MetaData', filters = self._filter_table)
                entry = meta_data_out_table.row
                for i in range(0,nEventIndex):
                    entry['event_number'] = self.meta_event_index[i][0]   #event index
                    entry['time_stamp'] = self.meta_data[i][3]   #time stamp
                    entry['error_code'] = self.meta_data[i][4]   #error code
                    entry.append()
                meta_data_out_table.flush()
            else:
                print 'ERROR meta data analysis failed'
        
        if (self._create_service_record_hist):
            self.service_record_hist = np.zeros(32, dtype=np.uint32)    # IMPORTANT: has to be global to avoid deleting before c library is deleted 
            self.interpreter.get_service_records_counters(self.service_record_hist)
            service_record_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistServiceRecord', title = 'Service Record Histogram', atom = tb.Atom.from_dtype(self.service_record_hist.dtype), shape = self.service_record_hist.shape, filters = self._filter_table)
            service_record_hist_table[:] = self.service_record_hist
        if (self._create_error_hist):
            self.error_counter_hist = np.zeros(16, dtype=np.uint32)
            self.interpreter.get_error_counters(self.error_counter_hist)
            error_counter_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistErrorCounter', title = 'Error Counter Histogram', atom = tb.Atom.from_dtype(self.error_counter_hist.dtype), shape = self.error_counter_hist.shape, filters = self._filter_table)
            error_counter_hist_table[:] = self.error_counter_hist 
        if (self._create_trigger_error_hist):
            self.trigger_error_counter_hist = np.zeros(8, dtype=np.uint32)
            self.interpreter.get_trigger_error_counters(self.trigger_error_counter_hist)
            trigger_error_counter_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistTriggerErrorCounter', title = 'Trigger Error Counter Histogram', atom = tb.Atom.from_dtype(self.trigger_error_counter_hist.dtype), shape = self.trigger_error_counter_hist.shape, filters = self._filter_table)
            trigger_error_counter_hist_table[:] = self.trigger_error_counter_hist
        if (self._create_tot_hist):
            self.tot_hist = np.zeros(16, dtype=np.uint32)
            self.histograming.get_tot_hist(self.tot_hist)
            tot_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistTot', title = 'TOT Histogram', atom = tb.Atom.from_dtype(self.tot_hist.dtype), shape = self.tot_hist.shape, filters = self._filter_table)
            tot_hist_table[:] = self.tot_hist
        if (self._create_rel_bcid_hist):
            self.rel_bcid_hist = np.zeros(16, dtype=np.uint32)
            self.histograming.get_rel_bcid_hist(self.rel_bcid_hist)
            rel_bcid_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistRelBcid', title = 'relative BCID Histogram', atom = tb.Atom.from_dtype(self.rel_bcid_hist.dtype), shape = self.rel_bcid_hist.shape, filters = self._filter_table)
            rel_bcid_hist_table[:] = self.rel_bcid_hist
        if (self._create_occupancy_hist):
            self.occupancy = np.zeros(80*336*self.histograming.get_n_parameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
            self.histograming.get_occupancy(self.occupancy)   
            occupancy_array = np.reshape(a = self.occupancy.view(), newshape = (80,336,self.histograming.get_n_parameters()), order='F')  # make linear array to 3d array (col,row,parameter)
            occupancy_array_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistOcc', title = 'Occupancy Histogram', atom = tb.Atom.from_dtype(self.occupancy.dtype), shape = (336,80,self.histograming.get_n_parameters()), filters = self._filter_table)
            occupancy_array_table[0:336, 0:80, 0:self.histograming.get_n_parameters()] = np.swapaxes(occupancy_array, 0, 1) # swap axis col,row,parameter --> row, col,parameter
        if (self._create_threshold_hists):
            self.threshold = np.zeros(80*336, dtype=np.float64)
            self.noise = np.zeros(80*336, dtype=np.float64)
            self.histograming.calculate_threshold_scan_arrays(self.threshold, self.noise)
            threshold_hist = np.reshape(a = self.threshold.view(), newshape = (80,336), order='F')
            noise_hist = np.reshape(a = self.noise.view(), newshape = (80,336), order='F')
            threshold_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistThreshold', title = 'Threshold Histogram', atom = tb.Atom.from_dtype(threshold_hist.dtype), shape = (336,80), filters = self._filter_table)
            threshold_hist_table[0:336, 0:80] = np.swapaxes(threshold_hist,0,1)
            noise_hist_table = self.out_file_h5.createCArray(self.out_file_h5.root, name = 'HistNoise', title = 'Noise Histogram', atom = tb.Atom.from_dtype(noise_hist.dtype), shape = (336,80), filters = self._filter_table)
            noise_hist_table[0:336, 0:80] = np.swapaxes(noise_hist,0,1)
    
    def plotHistograms(self, scan_data_filename = None):
        with tb.openFile(self._output_file, mode = "r") as out_file_h5:
            if (self._create_service_record_hist):
                plotting.plot_service_records(service_record_hist = out_file_h5.root.HistServiceRecord, filename = scan_data_filename+"_serviceRecords.pdf")
            if (self._create_error_hist):
                plotting.plot_event_errors(error_hist = out_file_h5.root.HistErrorCounter, filename = scan_data_filename+"_eventErrors.pdf")
            if (self._create_trigger_error_hist):
                plotting.plot_trigger_errors(trigger_error_hist=out_file_h5.root.HistTriggerErrorCounter, filename = scan_data_filename+"_tiggerErrors.pdf") 
            if (self._create_tot_hist):
                plotting.plot_tot(tot_hist=out_file_h5.root.HistTot, filename = scan_data_filename+"_tot.pdf")
            if (self._create_rel_bcid_hist):
                plotting.plot_relative_bcid(relative_bcid_hist = out_file_h5.root.HistRelBcid, filename = scan_data_filename+"_relativeBCID.pdf")
            if (self._create_occupancy_hist and not self._create_threshold_hists):
                plotting.plotThreeWay(hist = out_file_h5.root.HistOcc[:,:,0], title = "Occupancy", label = "occupancy", filename = scan_data_filename+"_occupancy.pdf")
            if (self._create_threshold_hists):
                plotting.plotThreeWay(hist = out_file_h5.root.HistThreshold[:,:], title = "Threshold", label = "threshold", filename = scan_data_filename+"_threshold.pdf", bins = 100, minimum = 0, maximum = 100)
                plotting.plotThreeWay(hist = out_file_h5.root.HistNoise[:,:], title = "Noise", label = "noise", filename = scan_data_filename+"_noise.pdf", bins = 100, minimum = 1, maximum = 10)

if __name__ == "__main__":
    converter = AnalyzeRawData(input_file = 'K:\\test_in.h5', output_file = 'K:\\test_out.h5')
    converter.interpret_word_table()
    converter.interpreter.print_summary()