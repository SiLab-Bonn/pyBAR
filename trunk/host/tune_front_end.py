""" Script to tune the the hole front end
"""
from datetime import datetime
import configuration

from scan_digital import DigitalScan
from scan_analog import AnalogScan
from scan_threshold import ThresholdScan

from tune_gdac import GdacTune
from tune_feedback import FeedbackTune
from tune_tdac import TdacTune
from tune_fdac import FdacTune

from fei4 import register

from analysis.plotting.plotting import plotThreeWay

target_threshold = 40 #in PlsrDAC
target_charge = 250 #in PlsrDAC
target_tot = 5
global_iterations = 0 #set 1..5, 0 is global threshold tuning only
local_iterations = 1 #set 1..5, 0 is local threshold tuning only

cfg_name = "test"
#cfg_name = str(target_threshold)+"PlsrDac_"+str(target_tot)+"TOTat"+str(target_charge)+"PlsrDac"
      
if __name__ == "__main__":
    startTime = datetime.now()
    GdacTuneScan = GdacTune(config_file = configuration.config_file, bit_file = configuration.bit_file, scan_data_path = configuration.scan_data_path)
    GdacTuneScan.setTargetThreshold(target_threshold) 
    FeedbackTuneScan = FeedbackTune(config_file = configuration.config_file, bit_file = None, scan_data_path = configuration.scan_data_path, device = GdacTuneScan.device)
    FeedbackTuneScan.setTargetCharge(target_charge)
    FeedbackTuneScan.setTargetTot(target_tot)
    FeedbackTuneScan.register = GdacTuneScan.register
    
    difference_bit = int(8/(global_iterations if global_iterations > 0 else 1))
#     print difference_bit
    
    PrmpVbpf = 0 
    Vthin_AC = 0
    Vthin_AF = 0
    
    for iteration in range(0,global_iterations):    #tune iterativly with decreasing range to save time
        start_bit = 7-difference_bit*iteration
#         print "!! Global Iteration Start_bit:",iteration, start_bit
        GdacTuneScan.setGdacTuneBits(range(start_bit,-1,-1))
        FeedbackTuneScan.setFeedbackTuneBits(range(start_bit,-1,-1))
        Vthin_AC, Vthin_AF = GdacTuneScan.start(configure = True if iteration == 0 else False)
        PrmpVbpf = FeedbackTuneScan.start(configure = False)
      
    Vthin_AC, Vthin_AF = GdacTuneScan.start(configure = True if global_iterations == 0 else False) # always stop with threshold tuning, it is more important
    print "Results: PrmpVbpf/Vthin_AltCoarse, Vthin_AltFine",PrmpVbpf,Vthin_AC,Vthin_AF
    
    config_file = GdacTuneScan.register.save_configuration(name = cfg_name)
       
    tdac_tune_scan = TdacTune(config_file = config_file, bit_file = None, outdir = configuration.outdir, device = GdacTuneScan.device)
    tdac_tune_scan = TdacTune(config_file = new_config, bit_file = None, scan_data_path = configuration.scan_data_path, device = GdacTuneScan.device)
    tdac_tune_scan.setTargetThreshold(target_threshold)
    fdac_tune_scan = FdacTune(config_file = new_config, bit_file = None, scan_data_path = configuration.scan_data_path, device = GdacTuneScan.device)

    tdac_tune_scan.register = GdacTuneScan.register
    fdac_tune_scan = FdacTune(config_file = config_file, bit_file = None, outdir = configuration.outdir, device = GdacTuneScan.device)
    fdac_tune_scan.register = GdacTuneScan.register
<<<<<<< .mine
=======>>>>>>> .theirs    fdac_tune_scan.setTargetCharge(target_charge)
    fdac_tune_scan.setTargetTot(target_tot)
    
    difference_bit = int(5/(local_iterations if local_iterations > 0 else 1))
    fdac_mean_tot = []
    
    for iteration in range(0,local_iterations):    #tune iterativly with decreasing range to save time
        start_bit = 4#-difference_bit*iteration
#         print "!! Local Iteration Start_bit:",iteration, start_bit
        tdac_tune_scan.setTdacTuneBits(range(start_bit,-1,-1))
        fdac_tune_scan.setFdacTuneBits(range(start_bit-1,-1,-1))
        tdac_tune_scan.start(configure = False)
        fdac_mean_tot = fdac_tune_scan.start(configure = False)
    
    tdac_occ = tdac_tune_scan.start(configure = False) # always stop with threshold tuning, it is more important

    #save final cfg
#     tdac_tune_scan.register.set_pixel_register_value("FDAC", fdac_tune_scan.register.get_pixel_register_value("FDAC"))
    GdacTuneScan.register.save_configuration(name = cfg_name)
    
<<<<<<< .mine    plotThreeWay(hist = GdacTuneScan.register.get_pixel_register_value("TDAC").transpose(), title = "TDAC distribution final", label = 'TDAC', filename = configuration.outdir+"\TDAC_map.pdf")
    plotThreeWay(hist = tdac_occ.transpose(), title = "Occupancy final", label = 'Occupancy', filename = configuration.outdir+"\occupancy_map.pdf")
=======    plotThreeWay(hist = tdac_tune_scan.register.get_pixel_register_value("TDAC").transpose(), title = "TDAC distribution final", label = 'TDAC', filename = configuration.scan_data_path+"\TDAC_map.pdf")
    plotThreeWay(hist = tdac_occ.transpose(), title = "Occupancy final", label = 'Occupancy', filename = configuration.scan_data_path+"\occupancy_map.pdf")
>>>>>>> .theirs
    if(iterations > 0):
    if(local_iterations > 0):
        plotThreeWay(hist = fdac_tune_scan.register.get_pixel_register_value("FDAC").transpose(), title = "FDAC distribution final", label = 'FDAC', filename = configuration.scan_data_path+"\FDAC_map.pdf")
<<<<<<< .mine        plotThreeWay(hist = GdacTuneScan.register.get_pixel_register_value("FDAC").transpose(), title = "FDAC distribution final", label = 'FDAC', filename = configuration.outdir+"\FDAC_map.pdf")
=======        plotThreeWay(hist = fdac_mean_tot.transpose(), title = "TOT mean final", label = 'mean TOT', filename = configuration.scan_data_path+"\mean_tot_map.pdf")
>>>>>>> .theirs        plotThreeWay(hist = fdac_mean_tot.transpose(), title = "TOT mean final", label = 'mean TOT', filename = configuration.outdir+"\mean_tot_map.pdf")
    
    print(datetime.now()-startTime)
