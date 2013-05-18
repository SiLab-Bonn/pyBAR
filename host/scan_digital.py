from analysis.plotting.plotting import plot_occupancy
import pprint
import time
import struct
import itertools

import BitVector

from fei4.output import FEI4Record
from daq.readout import Readout

from utils.utils import get_all_from_queue

from scan.scan import ScanBase


chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'

class DigitalScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None):
        super(DigitalScan, self).__init__(config_file, definition_file, bit_file, device)
        
if __name__ == "__main__":
    scan = DigitalScan(config_file, bit_file)

    print 'Start readout thread...'
    scan.readout.set_filter(scan.readout.data_record_filter)
    scan.readout.start()
    print 'Done!'
    
    import cProfile
    pr = cProfile.Profile()
    repeat = 100
    cal_lvl1_command = scan.register.get_commands("cal")[0]+BitVector.BitVector(size = 35)+scan.register.get_commands("lv1")[0]+BitVector.BitVector(size = 1000)
    pr.enable()
    scan.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = 6, dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, digital_injection = True, read_function = None)#scan.readout.read_once)
    pr.disable()
    pr.print_stats('cumulative')
    
    q_size = -1
    while scan.readout.data_queue.qsize() != q_size:
        time.sleep(0.5)
        q_size = scan.readout.data_queue.qsize()
    print 'Items in queue:', q_size
          
    def get_cols_rows(data_words):
        for item in data_words:
            yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
            
    def get_rows_cols(data_words):
        for item in data_words:
            yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
    
    data_q = get_all_from_queue(scan.readout.data_queue)
    data_words = itertools.chain(*(data_dict['raw_data'] for data_dict in data_q))
    print 'got all from queue'
    
#    with open('raw_data_digital_scan.raw', 'w') as f:
#        f.writelines([str(word)+'\n' for word in data_words])
    
    print 'Stopping readout thread...'
    scan.readout.stop()
    print 'Done!'
     
    print 'Data remaining in memory:', scan.readout.get_fifo_size()
    print 'Lost data count:', scan.readout.get_lost_data_count()
    
    plot_occupancy(*zip(*get_cols_rows(data_words)), max_occ = repeat*2)

#    set nan to special value
#    masked_array = np.ma.array (a, mask=np.isnan(a))
#    cmap = matplotlib.cm.jet
#    cmap.set_bad('w',1.)
#    ax.imshow(masked_array, interpolation='nearest', cmap=cmap)
#    