import zlib
import numpy as np
import tables as tb
import progressbar
from matplotlib import pyplot as plt
from scipy.optimize import curve_fit, leastsq

import visa
import time
import os

from basil.dut import Dut
#from pyLandau import landau

from pybar import *

if __name__ == "__main__":   
    
#     os.chdir('/media/niko/data/IBL_irrad_samples/pcb-test')
    target_threshold = 55  # in PlsrDAC (assuming 1 PlsrDAC = 55 electrons)
    target_charge = 280  # in PlsrDAC (assuming 1 PlsrDAC = 55 electrons)
    target_tot = 9
    mask = 3
    gdac_mask = [3]
    delta_tot = 1
  
    runmngr = RunManager('../configuration_multi.yaml')
    runmngr.run_run(InitScan, run_conf={"broadcast_commands": False,"threaded_scan": True})  # to be able to set global register values
 
    # FE check and tuning
#     runmngr.run_run(RegisterTest, run_conf={"broadcast_commands": False,"threaded_scan": False})
    runmngr.run_run(DigitalScan, run_conf={'mask_steps' : mask, "broadcast_commands": True,"threaded_scan": True})
    runmngr.run_run(run=AnalogScan, run_conf={'mask_steps' : mask, 'scan_parameters' : [('PlsrDAC', target_charge)],
                                              "broadcast_commands": True,"threaded_scan": True})  # heat up the Fe a little bit for PlsrDAC scan
                            
    runmngr.run_run(run=Fei4Tuning, run_conf={'target_threshold': target_threshold,
                                              "broadcast_commands": False,"threaded_scan": True,
                                              'target_tot': target_tot,
                                              'target_charge': target_charge,
                                              'mask_steps' : mask,
                                              'gdac_lower_limit' : 30,
#                                               "max_delta_tot": delta_tot,
#                                               'enable_mask_steps_gdac' : gdac_mask,
                                              'same_mask_for_all_dc' : True},
                    catch_exception=False)
    runmngr.run_run(run=AnalogScan, run_conf={'scan_parameters': [('PlsrDAC', target_charge)],'mask_steps' : mask,"broadcast_commands": True,"threaded_scan": True})
#     runmngr.run_run(run=FastThresholdScan, run_conf={"ignore_columns":(), 'mask_steps' : mask,"broadcast_commands": False,"threaded_scan": True})
    runmngr.run_run(run=ThresholdScan, run_conf={ 'mask_steps' : mask,"broadcast_commands": True, "threaded_scan": True})
    runmngr.run_run(run=StuckPixelScan, run_conf={"broadcast_commands": False,"threaded_scan": False,})
    runmngr.run_run(run=NoiseOccupancyTuning, run_conf={'n_triggers': 1000000}) #'occupancy_limit': 0,
    runmngr.run_run(run=Fei4SelfTriggerScan, run_conf = {"broadcast_commands": True, "threaded_scan": True,"scan_timeout": 60})
    
#     hit_file = '/home/niko/git/pyBAR/pybar/test_93_07_04/module_0/9_module_0_fei4_self_trigger_scan_interpreted.h5'
#     with tb.open_file(hit_file) as in_file:
#         hits = in_file.root.HistOcc[:]
#         print np.count_nonzero(hits==0)/(80.*336.)
    