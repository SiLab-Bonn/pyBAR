from threading import Thread
#from multiprocessing import Process as Thread

import time
import logging

from pySiLibUSB.SiLibUSB import SiUSBDevice, GetUSBBoards

import scan_analog
import scan_threshold
import scan_ext_trigger

logging.basicConfig(level=logging.DEBUG, format = "%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")

chip_flavor = 'fei4a'
#config_file = r'C:\Users\silab\Dropbox\pyats\trunk\host\config\fei4default\configs\std_cfg_'+chip_flavor+'_simple.cfg'
#bit_file = r'C:\Users\silab\Dropbox\pyats\trunk\device\MultiIO\FPGA\ise\top.bit'
bit_file = r'C:\Users\silab\Dropbox\pyats\trunk\host\config\FPGA\top.bit'

devices = {dev: dev.GetBoardId() for dev in GetUSBBoards()}
logging.info("Found %d board(s) with device ID: {}".format(', '.join('\''+dev.GetBoardId()+'\'' for dev in devices)), len(devices))
threads = []
scans = []

# additional_identifier = "3.4_GeV_LOW_THR_DDL7_CNM" # "_3.4_GeV_LOW_THR_BIAS_SCAN_5V_3D_500V_DIAMOND"
# outdir = r'C:\Users\silab\Desktop\Data\ext_trigger_scan' # r'C:\Users\silab\Desktop\Data\ext_trigger_scan'

additional_identifier = "_3.4_GeV_HIGH_THR_DDL7_CNM" # "_3.4_GeV_LOW_THR_BIAS_SCAN_5V_3D_500V_DIAMOND"
#outdir = r'C:\Users\silab\Desktop\Data\threshold_scan' # r'C:\Users\silab\Desktop\Data\ext_trigger_scan'

dut_0 = {"device_identifier" : "132", "scan_identifier" : "BOARD_ID_132_SCC_29_DUT_0"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC29\cfg_RCElike\SCC29_planar.cfg"}
dut_1 = {"device_identifier" : "213", "scan_identifier" : "BOARD_ID_213_SCC_99_DUT_1"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC99\cfg_RCElike\SCC99_CNM.cfg"}
dut_2 = {"device_identifier" : "214", "scan_identifier" : "BOARD_ID_214_SCC_146_DUT_2"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC146\cfg_RCElike\SCC146_diamond.cfg"}
dut_1_HT = {"device_identifier" : "213", "scan_identifier" : "BOARD_ID_213_SCC_99_DUT_1"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC99\cfg_RCElike\SCC99_CNM_HT_2.cfg"}
dut_2_HT = {"device_identifier" : "214", "scan_identifier" : "BOARD_ID_214_SCC_146_DUT_2"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC146\cfg_RCElike\SCC146_diamond_HT.cfg"}
dut_3 = {"device_identifier" : "201", "scan_identifier" : "BOARD_ID_201_SCC_166_DUT_3"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC166\cfg_RCElike\SCC166_diamond.cfg"}
dut_4 = {"device_identifier" : "207", "scan_identifier" : "BOARD_ID_207_SCC_112_DUT_4"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC112\cfg_RCElike\SCC112_FBK.cfg"}
dut_5 = {"device_identifier" : "216", "scan_identifier" : "BOARD_ID_216_SCC_45_DUT_5"+additional_identifier, "config_file" : r"C:\Users\silab\Dropbox\pyats\trunk\host\config\Testbeam\SCC45\cfg_RCElike\SCC45_planar.cfg"}

device_config = {
                 "132" : dut_0,
                 "207" : dut_1_HT,
                 "214" : dut_2_HT,
                 #"201" : dut_3,
                 #"213" : dut_4,
                 "%5%" : dut_5 # alias 216
}

threshold_devices = ["207", "214", "201", "213"]

vthin_altcoarse_range = [1, 2]#range(10,13)
vthin_altfine_range = [0, 64, 128, 192]


for dev in devices.iterkeys():
    logging.info('Programming FPGA of board %s ...', devices[dev])
    logging.info('FPGA bit file: %s', bit_file)
    dev.DownloadXilinx(bit_file)
    logging.info('Done!')
time.sleep(1)

for vthin_altcoarse in vthin_altcoarse_range:
    for vthin_altfine in vthin_altfine_range:
        # Threshold Scan
    #     outdir = r'C:\Users\silab\Desktop\Data\threshold_scan_last_day'
    #     logging.info('Starting multi-board scan...')
    #     init_number = 0
    #     for dev in devices.iterkeys():
    #         #device_id = dev.GetBoardId()
    #         device_id = devices[dev]
    #         
    #         if device_id in threshold_devices:
    #             init_number += 1
    #             config_file = device_config[device_id]["config_file"]
    #             dev.device_identifier = device_config[device_id]["device_identifier"]
    #             scan_identifier = device_config[device_id]["scan_identifier"]+"_Vthin_AltCoarse_"+str(vthin_altcoarse)+"_Vthin_AltFine_"+str(vthin_altfine)
    #         
    #             logging.info("Initialize board number %d with ID %s (device identifier: %s, scan identifier: %s)", init_number, device_id, dev.identifier, scan_identifier)
    # 
    #             #Threshold scan
    #             scan = scan_threshold.ThresholdScan(config_file = config_file, bit_file = None, device = dev, scan_identifier = scan_identifier, outdir = outdir)
    #             # set scan variable
#                 if device_id in threshold_devices:
#                     scan.register.set_global_register_value("Vthin_AltCoarse", vthin_altcoarse)
#                     scan.register.set_global_register_value("Vthin_AltFine", vthin_altfine)
    #             scan.configure()
    #             # start scan here
    #             thread = Thread(name = scan_identifier, target = scan.start, kwargs = {"configure" : False})
    #             
    #             threads.append(thread)
    #             scans.append(scan)
    #         else:
    #             logging.info("Board with ID %s not initialized.", device_id)
    #     
    #     logging.info('%d board(s) initialized. Starting scan...', init_number)
    #     for thread in threads:
    #         #thread.setDaemon(True)
    #         thread.start()
    #     
    #     stop_threads = False    
    #     while 1:
    #         if stop_threads == True:
    #             break
    #         for number, thread in enumerate(threads):
    #             if not thread.is_alive():
    #                 stop_threads = True
    #                 scan = scans[number]
    #                 logging.info("%s has stopped.", scan.scan_identifier)
    #                 break
    #         time.sleep(1)
    #     
    #     for number, thread in enumerate(threads):
    #         if thread.is_alive():
    #             scan = scans[number]
    #             scan.stop_thread_event.set()
    #             logging.info("Stopping scan thread(s) %s...", scan.scan_identifier)
    #     
    #     for thread in threads:
    #         thread.join()
    #         
    #     threads = []
    #     scans = []
        
        # Ext Trigger Scan
        outdir = r'C:\Users\silab\Desktop\Data\ext_trigger_scan_last_day'
        logging.info('Starting multi-board scan...')
        init_number = 0
        for dev in devices.iterkeys():
            #device_id = dev.GetBoardId()
            device_id = devices[dev]
            
            if device_id in device_config.iterkeys():
                init_number += 1
                config_file = device_config[device_id]["config_file"]
                dev.device_identifier = device_config[device_id]["device_identifier"]
                scan_identifier = device_config[device_id]["scan_identifier"]+"_Vthin_AltCoarse_"+str(vthin_altcoarse)+"_Vthin_AltFine_"+str(vthin_altfine)
            
                logging.info("Initialize board number %d with ID %s (device identifier: %s, scan identifier: %s)", init_number, device_id, dev.identifier, scan_identifier)
                
                # ext trigger scan
                scan = scan_ext_trigger.ExtTriggerScan(config_file = config_file, bit_file = None, device = dev, scan_identifier = scan_identifier, outdir = outdir)
                # set scan variable
                if device_id in threshold_devices:
                    scan.register.set_global_register_value("Vthin_AltCoarse", vthin_altcoarse)
                    scan.register.set_global_register_value("Vthin_AltFine", vthin_altfine)
                scan.configure()
                # start scan here
                thread = Thread(name = scan_identifier, target = scan.start, kwargs = {"configure" : False})
                
                threads.append(thread)
                scans.append(scan)
            else:
                logging.info("Board with ID %s not initialized.", device_id)
        
        logging.info('%d board(s) initialized. Starting scan...', init_number)
        for thread in threads:
            #thread.setDaemon(True)
            thread.start()
        
        stop_threads = False
        while 1:
            if stop_threads == True:
                break
            for number, thread in enumerate(threads):
                if not thread.is_alive():
                    stop_threads = True
                    scan = scans[number]
                    logging.info("%s has stopped.", scan.scan_identifier)
                    break
            time.sleep(1)
        
        for number, thread in enumerate(threads):
            if thread.is_alive():
                scan = scans[number]
                scan.stop_thread_event.set()
                logging.info("Stopping scan thread(s) %s...", scan.scan_identifier)
        
        for thread in threads:
            thread.join()
            
        threads = []
        scans = []
    
logging.info('Done!')
