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

class DigitalScan(ScanBase):
    def __init__(self, config_file, definition_file = None, bit_file = None, device = None, scan_identifier = "digital_scan", outdir = None):
        super(DigitalScan, self).__init__(config_file, definition_file, bit_file, device, scan_identifier, outdir)
        
    def start(self, configure = True):
        super(DigitalScan, self).start(configure)
        
        print 'Start readout thread...'
        self.readout.set_filter(self.readout.data_record_filter)
        self.readout.start()
        print 'Done!'
        
        #import cProfile
        #pr = cProfile.Profile()
        repeat = 100
        cal_lvl1_command = self.register.get_commands("cal")[0]+BitVector.BitVector(size = 35)+self.register.get_commands("lv1")[0]+BitVector.BitVector(size = 1000)
        #pr.enable()
        self.scan_utils.base_scan(cal_lvl1_command, repeat = repeat, mask = 6, dcs = [], same_mask_for_all_dc = True, hardware_repeat = True, enable_c_high = False, enable_c_low = False, digital_injection = True, read_function = None)#self.readout.read_once)
        #pr.disable()
        #pr.print_stats('cumulative')
        
        q_size = -1
        while self.readout.data_queue.qsize() != q_size:
            time.sleep(0.5)
            q_size = self.readout.data_queue.qsize()
        print 'Items in queue:', q_size
              
        def get_cols_rows(data_words):
            for item in data_words:
                yield ((item & 0xFE0000)>>17), ((item & 0x1FF00)>>8)
                
        def get_rows_cols(data_words):
            for item in data_words:
                yield ((item & 0x1FF00)>>8), ((item & 0xFE0000)>>17)
        
        data_q = get_all_from_queue(self.readout.data_queue)
        data_words = itertools.chain(*(data_dict['raw_data'] for data_dict in data_q))
        print 'got all from queue'
        
    #    with open('raw_data_digital_self.raw', 'w') as f:
    #        f.writelines([str(word)+'\n' for word in data_words])
        
        print 'Stopping readout thread...'
        self.readout.stop()
        print 'Done!'
         
        print 'Data remaining in memory:', self.readout.get_fifo_size()
        print 'Lost data count:', self.readout.get_lost_data_count()
        
        plot_occupancy(*zip(*get_cols_rows(data_words)), max_occ = repeat*2)
    
    #    set nan to special value
    #    masked_array = np.ma.array (a, mask=np.isnan(a))
    #    cmap = matplotlib.cm.jet
    #    cmap.set_bad('w',1.)
    #    ax.imshow(masked_array, interpolation='nearest', cmap=cmap)


if __name__ == "__main__":
    chip_flavor = 'fei4a'
    config_file = r'C:\Users\silab\Dropbox\pyats\trunk\host\config\fei4default\configs\std_cfg_'+chip_flavor+'_simple.cfg'
    bit_file = r'C:\Users\silab\Dropbox\pyats\trunk\device\MultiIO\FPGA\ise\top.bit'
    scan_identifier = "analog_scan"
    outdir = r"C:\Users\silab\Desktop\Data\analog_scan"
    
    scan = DigitalScan(config_file = config_file, bit_file = bit_file)
    
    scan.start()
    
    