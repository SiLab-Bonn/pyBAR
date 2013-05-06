from threading import Thread
#from multiprocessing import Process as Thread

import time
import logging

from SiLibUSB import SiUSBDevice, GetUSBBoards

import scan_analog


logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-10s) %(message)s')

chip_flavor = 'fei4a'
config_file = 'C:\Users\Jens\Desktop\Python\python_projects\etherpixcontrol\std_cfg_'+chip_flavor+'.cfg'
bit_file = r'C:\Users\Jens\Desktop\ModularReadoutSystem\device\trunk\MIO\FPGA\FEI4\ise\top.bit'

devices = GetUSBBoards()

threads = []

for dev in devices:
    scan = scan_analog.AnalogScan(config_file = config_file, bit_file = bit_file, device = dev)
    thread = Thread(name = dev.GetBoardId, target = scan.start)
    #thread.setDaemon(True)
    thread.start()
    threads.append(thread)
    
for thread in threads:
    thread.join()
    
logging.debug('finished')

