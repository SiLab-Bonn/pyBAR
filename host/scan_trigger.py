import threading
import itertools

from fei4.output import FEI4Record
from daq.readout import Readout

from scan.scan import ScanBase

from utils.utils import get_all_from_queue

chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'

class TriggerScan(ScanBase):
    def __init__(self, config_file, bit_file):
        super(TriggerScan, self).__init__(config_file, bit_file)


class TriggerThread(object):
    def __init__(self, register, register_utils):
        self.register = register
        self.register_utils = register_utils

        self.send_trigger_event = threading.Event()
        self.send_trigger_event.clear()

        self.worker_thread = None
        self.stop_thread_event = threading.Event()
        self.stop_thread_event.set()
        
        
        self.lvl1_command = None
    
    def start(self):
        commands = []
        commands.extend(self.register.get_commands("runmode"))
        self.register_utils.send_commands(commands)
        self.lvl1_command = self.register.get_commands("lv1")[0]
        self.register_utils.set_command(self.lvl1_command)
        
        self.send_trigger_event.clear()
        
        self.stop_thread_event.clear()
        self.worker_thread = threading.Thread(target=self.worker)
        self.worker_thread.start()
    
    def stop(self):
        self.stop_thread_event.set() # set this first, in case it is blocking
        self.send_trigger_event.set() # remove block
        
        self.worker_thread.join()
        self.worker_thread = None
        
        self.send_trigger_event.clear() # clear again after join
        
        self.lvl1_command = None
    
    def worker(self):
        number = 0
        while self.send_trigger_event.wait() and not self.stop_thread_event.is_set():#
            self.send_trigger_event.clear()

            try:
                number += 1
                self.register_utils.send_command()
                print 'sending lvl1...', number
            except Exception, msg:
                print msg
                self.stop_thread_event.set()
                continue
            
    def send_trigger(self):
        self.send_trigger_event.set()
            
        
if __name__ == "__main__":
    scan = TriggerScan(config_file, bit_file)
    
    print 'Start readout thread...'
    #readout_thread.set_filter(readout_thread.data_record_filter)
    scan.readout.start()
    print 'Done!'
    
    print 'Start trigger thread...'
    trigger_thread = TriggerThread(scan.register, scan.register_utils)
    trigger_thread.start()
    print 'Done!'
    
    
    consecutive_lvl1 = scan.register.get_global_register_value("Trig_Count")
    if consecutive_lvl1 == 0:
        consecutive_lvl1 = 16
    dh_count = 0
    unknown_count = 0
    trigger_thread.send_trigger()
    while 1:
        data_q = get_all_from_queue(scan.readout.data_queue)
        data_list = list(itertools.chain(*data_q))
        for data_word in data_list:
            record = FEI4Record(data_word, chip_flavor)
            print record
            if record == "DH":
                dh_count +=1
                if dh_count == consecutive_lvl1:
                    dh_count = 0
                    trigger_thread.send_trigger()
    #        elif record == "UNKNOWN":
    #            unknown_count += 1
    #            print 'unknown:', unknown_count
        
     

