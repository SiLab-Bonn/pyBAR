import numpy as np
import tables as tb
from scipy.interpolate import interp1d
import matplotlib.pyplot as plt
from analysis.plotting.plotting import plot_scurves, plotThreeWay

from scipy.interpolate import interp1d

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def central_difference(x, y):  
    if (len(x) != len(y)):
        raise ValueError("x, y must have the same length")
    z1 = np.hstack((y[0], y[:-1]))
    z2 = np.hstack((y[1:], y[-1]))
    dx1 = np.hstack((0, np.diff(x)))
    dx2 = np.hstack((np.diff(x), 0))
    return (z2 - z1) / (dx2 + dx1)


def get_mean_threshold(gdac, mean_threshold_calibration):
    interpolation = interp1d(mean_threshold_calibration['gdac'], mean_threshold_calibration['mean_threshold'], kind='slinear')
    return interpolation(gdac)


def get_pixel_threshold(column, row, gdac, threshold_calibration):
    pixel_gdacs = threshold_calibration[np.logical_and(threshold_calibration['column'] == column, threshold_calibration['row'] == row)]['gdac']
    pixel_thresholds = threshold_calibration[np.logical_and(threshold_calibration['column'] == column, threshold_calibration['row'] == row)]['threshold']
#     print pixel_gdacs, pixel_thresholds
    interpolation = interp1d(x=pixel_gdacs, y=pixel_thresholds, kind='slinear', bounds_error=True)
    return interpolation(gdac)

if __name__ == "__main__":
    scan_name = 'scan_fei4_trigger_141'
    chip_flavor = 'fei4a'
    input_file_hits = 'data/' + scan_name + "_interpreted.h5"
    input_file_calibration = 'data/calibrate_threshold_gdac.h5'
    scan_parameters = range(100, 5001, 15)
    pixel_row = 200
    pixel_column = 35

    with tb.openFile(input_file_calibration, mode="r") as in_file_calibration_h5:  # read calibration file from calibrate_threshold_gdac scan
        with tb.openFile(input_file_hits, mode="r") as in_file_hits_h5:  # read scan data file from scan_fei4_trigger_gdac scan
            hits = in_file_hits_h5.root.HistOcc[:]
            mean_threshold_calibration = in_file_calibration_h5.root.MeanThresholdCalibration[:]
            threshold_calibration = in_file_calibration_h5.root.ThresholdCalibration[:]
    
    #         print get_pixel_threshold(pixel_column, pixel_row, scan_parameters, threshold_calibration=threshold_calibration)
        #     print hits[200:201, 35:36, :]
        #     print np.gradient(hits[200, 35, :], 15)
    
    
            x = get_mean_threshold(scan_parameters, mean_threshold_calibration)
            y = hits[190:220, 32:37, :]
    # 
    # #         plot_scurves(y, max_occ = 300, scan_paramter_name='GDAC', scan_parameters=scan_parameters)
#             plot_scurves(y, max_occ = 300, scan_paramter_name='Threshold [e]', scan_parameters=x * 55)
    # #         plt.close()
    #         
    # #         y = 
    # #         
    #         print x,y
    
    #         pixel_gdacs = threshold_calibration[np.logical_and(threshold_calibration['column'] == pixel_column, threshold_calibration['row'] == pixel_row)]['gdac']
    #         pixel_thresholds = threshold_calibration[np.logical_and(threshold_calibration['column'] == pixel_column, threshold_calibration['row'] == pixel_row)]['threshold']
    
            x = get_pixel_threshold(pixel_column, pixel_row, scan_parameters, threshold_calibration=threshold_calibration)
#             x_2 = get_mean_threshold(scan_parameters, mean_threshold_calibration=mean_threshold_calibration)
            y = hits[pixel_row, pixel_column, :]
            
#             x = np.arange(0,3.1*3,0.1)
#             y = np.sin(x)
    #         x = x/30.
    #         plt.plot(x, np.sin(x), x, central_difference(x, np.sin(x)))
        
            plt.plot(x * 55, y, 'o')
    #         plt.plot(x, y, 'o', x, central_difference(x, y))
    #         plt.plot(scan_parameters, y, 'o', scan_parameters, )
            plt.show()


