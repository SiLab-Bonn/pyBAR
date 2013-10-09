import tables as tb
import numpy as np
import time
from data_interpreter import PyDataInterpreter

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

chunk = 3000000

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

with tb.openFile("K:\\test_in.h5", mode = "r", title = "test file") as in_file_h5:
    filter_hit_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
    with tb.openFile("K:\\test_out.h5", mode = "w", title = "test file") as out_file_h5:
        hit_table = out_file_h5.createTable(out_file_h5.root, name = 'Hits', description = HitInfoTable, title = 'hit_data', filters = filter_hit_table, chunkshape=(chunk/100,))
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
        
        for iWord in range(0,table_size, chunk):
            raw_data = in_file_h5.root.raw_data.read(iWord,iWord+chunk)
            myInterpreter.interpret_raw_data(raw_data)
            if (save_hits == True):
                Nhits = myInterpreter.get_hits(hits)
                hit_table.append(hits[:Nhits])

        hit_table.flush()
        
        meta_event_index = np.zeros((meta_data_size,), dtype=[('metaEventIndex', np.uint32)])
        nEventIndex = myInterpreter.get_meta_event_index(meta_event_index)
        
        if (meta_data_size == nEventIndex): 
            meta_data_output = np.empty((meta_data_size,), dtype=[('metaEventIndex', np.uint32)])        
            filter_meta_data_out_table = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
            meta_data_out_table = out_file_h5.createTable(out_file_h5.root, name = 'MetaData', description = MetaInfoOutTable, title = 'MetaData', filters = filter_meta_data_out_table)
            entry = meta_data_out_table.row
            for i in range(0,nEventIndex):
                entry['event_number'] = meta_event_index[i][0]   #event index
                entry['time_stamp'] = meta_data[i][3]   #time stamp
                entry['error_code'] = meta_data[i][4]   #error code
                entry.append()
                #print meta_event_index[i]
            meta_data_out_table.flush()
        else:
            print 'ERROR meta data analysis failed'        
        
    #     hits[0] = (1,2,3,4,5,6,7,8,9,10,11)
    #     hits[1] = (12,13,15,16,17,18,19,20,21,22,23)
    
        
    #     print 'hits[0].itemsize', hits[0].itemsize
        print "##########################################"
        myInterpreter.print_summary()
    
print 'It took ',time.time() - start   
    #     myInterpreter.print_status()
    
    #     print type(meta_data), meta_data.dtype, type(meta_data.data), len(meta_data)
    #     myInterpreter.print_status()
#     print meta_data.__array_interface__
#     print raw_data.shape, raw_data.dtype
#     print 'size:',raw_data.shape[0]*4
#     print raw_data[:10]
