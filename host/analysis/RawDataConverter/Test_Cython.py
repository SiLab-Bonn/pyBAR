import tables as tb
import numpy as np
import time
import sys
from data_interpreter import PyDataInterpreter
from data_histograming import PyDataHistograming

class HitInfoTable(tb.IsDescription):
    event_number = tb.UInt32Col(pos=0)
    trigger_number = tb.UInt32Col(pos=1)
    relative_BCID = tb.UInt8Col(pos=2)
    LVLID = tb.UInt16Col(pos=3)
    column = tb.UInt8Col(pos=4)
    row = tb.UInt16Col(pos=5)
    tot = tb.UInt8Col(pos=6)
    BCID = tb.UInt16Col(pos=7)
    trigger_status = tb.UInt8Col(pos=8)
    service_record = tb.UInt32Col(pos=9)
    event_status = tb.UInt8Col(pos=10)
    
class MetaInfoOutTable(tb.IsDescription):
    event_number = tb.UInt32Col(pos=0)
    time_stamp = tb.Float64Col(pos=1)
    error_code = tb.UInt32Col(pos=2)

chunk = 2000000

save_hits = False

start = time.time()

MAXARRAYSIZE = chunk
hits = np.empty((MAXARRAYSIZE,), dtype= 
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

filter_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
with tb.openFile("K:\\test_in.h5", mode = "r", title = "test file") as in_file_h5:
    with tb.openFile("K:\\test_out.h5", mode = "w", title = "test file") as out_file_h5:
        hit_table = out_file_h5.createTable(out_file_h5.root, name = 'Hits', description = HitInfoTable, title = 'hit_data', filters = filter_table, chunkshape=(chunk/100,))
        meta_data = in_file_h5.root.meta_data[:]

        table_size = in_file_h5.root.raw_data.shape[0]
        meta_data_size = meta_data.shape[0]
        
        myInterpreter = PyDataInterpreter()
        myInterpreter.set_debug_output(False)
        myInterpreter.set_warning_output(False)
        myInterpreter.set_FEI4B(False)
#         
        myInterpreter.reset_event_variables()
        myInterpreter.reset_counters()
        myInterpreter.set_meta_word_index(meta_data)
        
        myHistograming = PyDataHistograming()
        myHistograming.set_debug_output(False)
        myHistograming.set_warning_output(True)
        myHistograming.create_occupancy_hist(True)
        myHistograming.create_tot_hist(True)
        myHistograming.create_rel_bcid_hist(True)
        
        try:
            scan_parameters = in_file_h5.root.scan_parameters[:]
            myHistograming.add_scan_parameter(scan_parameters)
        except tb.exceptions.NoSuchNodeError:
            scan_parameters = None
            myHistograming.set_no_scan_parameter()           
            
        meta_event_index = np.zeros((meta_data_size,), dtype=[('metaEventIndex', np.uint32)])
        
        for iWord in range(0,table_size, chunk):
            raw_data = in_file_h5.root.raw_data.read(iWord,iWord+chunk)
            myInterpreter.interpret_raw_data(raw_data)
            Nhits = myInterpreter.get_hits(hits)
            if(scan_parameters != None):
                nEventIndex = myInterpreter.get_meta_event_index(meta_event_index)
                myHistograming.add_meta_event_index(meta_event_index, nEventIndex)
            myHistograming.add_hits(hits, Nhits)
            if (save_hits == True):
                hit_table.append(hits[:Nhits])
            print int(float(float(iWord)/float(table_size)*100.)),

        hit_table.flush()
        
        # create service record array
        service_record_hist = np.zeros(32, dtype=np.uint32)
        myInterpreter.get_service_records_counters(service_record_hist)
        service_record_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistServiceRecord', title = 'Service Record Histogram', atom = tb.Atom.from_dtype(service_record_hist.dtype), shape = service_record_hist.shape, filters = filter_table)
        service_record_hist_table[:] = service_record_hist
        
        # create error counter array
        error_counter_hist = np.zeros(16, dtype=np.uint32)
        myInterpreter.get_error_counters(error_counter_hist)
        error_counter_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistErrorCounter', title = 'Error Counter Histogram', atom = tb.Atom.from_dtype(error_counter_hist.dtype), shape = error_counter_hist.shape, filters = filter_table)
        error_counter_hist_table[:] = error_counter_hist
        
        # create trigger error counter array
        trigger_error_counter_hist = np.zeros(8, dtype=np.uint32)
        myInterpreter.get_trigger_error_counters(trigger_error_counter_hist)
        trigger_error_counter_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistTriggerErrorCounter', title = 'Trigger Error Counter Histogram', atom = tb.Atom.from_dtype(trigger_error_counter_hist.dtype), shape = trigger_error_counter_hist.shape, filters = filter_table)
        trigger_error_counter_hist_table[:] = trigger_error_counter_hist
        
        # create TOT array
        tot_hist = np.zeros(16, dtype=np.uint32)
        myHistograming.get_tot_hist(tot_hist)
        tot_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistTot', title = 'TOT Histogram', atom = tb.Atom.from_dtype(tot_hist.dtype), shape = tot_hist.shape, filters = filter_table)
        tot_hist_table[:] = tot_hist
        
        # create relative BCID array
        rel_bcid_hist = np.zeros(16, dtype=np.uint32)
        myHistograming.get_rel_bcid_hist(rel_bcid_hist)
        rel_bcid_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistRelBcid', title = 'relative BCID Histogram', atom = tb.Atom.from_dtype(rel_bcid_hist.dtype), shape = rel_bcid_hist.shape, filters = filter_table)
        rel_bcid_hist_table[:] = rel_bcid_hist
        
        # create occupancy array
        occupancy = np.zeros(80*336*myHistograming.get_nparameters(), dtype=np.uint32)  # create linear array as it is created in histogram class
        myHistograming.get_occupancy(occupancy)   
        occupancy_array = np.reshape(a = occupancy.view(), newshape = (80,336,myHistograming.get_nparameters()), order='F')  # make linear array to 3d array (col,row,parameter)
        occupancy_array_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistOcc', title = 'Occupancy Histogram', atom = tb.Atom.from_dtype(occupancy.dtype), shape = (336,80,myHistograming.get_nparameters()), filters = filter_table)
        occupancy_array_table[0:336, 0:80, 0:myHistograming.get_nparameters()] = np.swapaxes(occupancy_array, 0, 1) # swap axis col,row,parameter --> row, col,parameter
        
        # create threshold scan arrays
        threshold = np.zeros(80*336, dtype=np.float64)
        noise = np.zeros(80*336, dtype=np.float64)
        myHistograming.calculate_threshold_scan_arrays(threshold, noise)
        threshold_hist = np.reshape(a = threshold.view(), newshape = (80,336), order='F')
        noise_hist = np.reshape(a = noise.view(), newshape = (80,336), order='F')
        threshold_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistThreshold', title = 'Threshold Histogram', atom = tb.Atom.from_dtype(threshold_hist.dtype), shape = (336,80), filters = filter_table)
        threshold_hist_table[0:336, 0:80] = np.swapaxes(threshold_hist,0,1)
        noise_hist_table = out_file_h5.create_carray(out_file_h5.root, name = 'HistNoise', title = 'Noise Histogram', atom = tb.Atom.from_dtype(noise_hist.dtype), shape = (336,80), filters = filter_table)
        noise_hist_table[0:336, 0:80] = np.swapaxes(noise_hist,0,1)
                
        # create meta data table
        nEventIndex = myInterpreter.get_meta_event_index(meta_event_index)  
        if (meta_data_size == nEventIndex): 
            meta_data_output = np.empty((meta_data_size,), dtype=[('metaEventIndex', np.uint32)])
            meta_data_out_table = out_file_h5.createTable(out_file_h5.root, name = 'MetaData', description = MetaInfoOutTable, title = 'MetaData', filters = filter_table)
            entry = meta_data_out_table.row
            for i in range(0,nEventIndex):
                entry['event_number'] = meta_event_index[i][0]   #event index
                entry['time_stamp'] = meta_data[i][3]   #time stamp
                entry['error_code'] = meta_data[i][4]   #error code
                entry.append()
            meta_data_out_table.flush()
        else:
            print 'ERROR meta data analysis failed'        
        
        print '100 done'
        
        # print summary
        print "##########################################"
        myInterpreter.print_summary()

del hits
del tot_hist
del rel_bcid_hist
print 'Conversion took ',time.time() - start,'seconds'
