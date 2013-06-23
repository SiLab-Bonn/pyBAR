import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import itertools
from matplotlib import colors, cm, legend

def make_occupancy(cols, rows, max_occ = None):
    plt.clf()
    H, xedges, yedges = np.histogram2d(rows, cols, bins = (336, 80), range = [[1,336], [1,80]])
    #print xedges, yedges
    extent = [yedges[0]-0.5, yedges[-1]+0.5, xedges[-1]+0.5, xedges[0]-0.5]
    #plt.pcolor(H)
    cmap = cm.get_cmap('hot', 20)
    ceil_number = ceil_mod(int(H.max()) if max_occ == None else max_occ, 10) 
    bounds = range(0, ceil_number+1, ceil_number/10)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    plt.title('Occupancy')
    plt.xlabel('Column')
    plt.ylabel('Row')
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm, ticks = bounds)

def plot_occupancy(cols, rows, max_occ = None, filename = None):
    make_occupancy(cols, rows, max_occ)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
    
def save_occupancy(filename, cols, rows, max_occ = None):
    make_occupancy(cols, rows, max_occ)
    plt.savefig(filename)
    
def ceil_mod(number, mod):
    #print number
    while True:
        if number%mod == 0:
            break
        number+=1
    #print number
    return number

def plot_threshold(threshold_hist, v_cal = 53, plot_range = (1500,2500), filename = None):
    plt.clf()
    H=np.empty(shape=(336,80),dtype=threshold_hist.dtype)
    H[:]=threshold_hist[:,:]
    H=H*v_cal
    A = np.reshape(H, -1)
    n, _, _ = plt.hist(A, 200, range = plot_range, facecolor='green', alpha=0.75)
    plt.xlabel('threshold [e]')
    plt.ylabel('#')
    plt.title('Threshold (S-curve mu)')
    plt.axis([plot_range[0], plot_range[1], 0, max(n)+10])
    plt.grid(True)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_noise(noise_hist, v_cal = 53, plot_range = (1500,2500), filename = None):
    plt.clf()
    H=np.empty(shape=(336,80),dtype=noise_hist.dtype)
    H[:]=noise_hist[:,:]
    H=H*v_cal
    A = np.reshape(H, -1)
    n, _, _ = plt.hist(A, 200, range = plot_range, facecolor='green', alpha=0.75)
    plt.xlabel('noise [e]')
    plt.ylabel('#')
    plt.title(r'Noise (S-curve sigma)')
    plt.axis([plot_range[0], plot_range[1], 0, max(n)+10])
    plt.grid(True)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_relative_bcid(relative_bcid_hist, filename = None):
    plt.clf()
    plt.bar(range(10,16), relative_bcid_hist[:], color='r', align = 'center') #bug: https://github.com/matplotlib/matplotlib/issues/1882, log = True)
    plt.xlabel('relative BCID [25 ns]')
    plt.ylabel('#')
    plt.yscale('log')
    plt.title('Relative BCID (former LVL1ID)')
    fig = plt.figure(1)  
    fig.patch.set_facecolor('white')
    plt.grid(True)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_tot(tot_hist, filename = None):
    plt.clf()
    plt.bar(range(0,16), tot_hist[:], color='b', align = 'center')
    plt.xlabel('TOT [25 ns]')
    plt.ylabel('#')
    plt.title('Time over threshold distribution (TOT code)')
    fig = plt.figure(1)  
    fig.patch.set_facecolor('white')
    plt.grid(True)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_event_errors(error_hist, filename = None):
    plt.clf()
    plt.bar(range(0,8), error_hist[:], color='r', align = 'center', label="Error code")
    plt.xlabel('')
    plt.ylabel('#')
    plt.title('Event errors')
    fig = plt.figure(1)  
    fig.patch.set_facecolor('white')
    plt.grid(True)
    plt.xticks(range(0,8), ('SR\noccured', 'No\ntrigger', 'LVL1ID\nnot const.', '#BCID\nwrong', 'unknown\nword', 'BCID\njump', 'trigger\nerror', 'not\nused') )
    #plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_trigger_errors(trigger_error_hist, filename = None):
    plt.clf()
    plt.bar(range(0,8), trigger_error_hist[:], color='r', align = 'center', label="Error code")
    plt.xlabel('')
    plt.ylabel('#')
    plt.title('Trigger errors')
    fig = plt.figure(1)  
    fig.patch.set_facecolor('white')
    plt.grid(True)
    plt.xticks(range(0,8), ('increase\nerror', 'more than\none trg.', 'TLU\naccept', 'TLU\ntime out', 'not\nused', 'not\nused', 'not\nused', 'not\nused') )
    #plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_service_records(service_record_hist, filename = None):
    plt.clf()
    plt.bar(range(0,32), service_record_hist[:], color='r', align = 'center', label="Error code")
    plt.xlabel('service record code')
    plt.ylabel('#')
    plt.title('Service records')
    fig = plt.figure(1)  
    fig.patch.set_facecolor('white')
    plt.grid(True)
    #plt.legend(bbox_to_anchor=(1.05, 1), loc=2, borderaxespad=0.)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_threshold_2d(threshold_hist, v_cal = 53, plot_range = (1500,2500),  max_occ = None, filename = None):
    plt.clf()
    H=np.empty(shape=(336,80),dtype=threshold_hist.dtype)
    H[:]=threshold_hist[:,:]
    H=H*v_cal
    extent = [0.5, 80.5, 336.5, 0.5]
    cmap = cm.get_cmap('hot', 200)
    ceil_number = ceil_mod(int(H.max()) if max_occ == None else max_occ, 10) 
    bounds = range(0, ceil_number+1, ceil_number/10)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    plt.title('Threshold')
    plt.xlabel('Column')
    plt.ylabel('Row')
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm, ticks = bounds)
    plt.show()

def plot_correlations(filenames, limit = None):
    plt.clf()
    DataFrame = pd.DataFrame();
    index = 0
    for fileName in filenames:
        print 'open ', fileName
        with pd.get_store(fileName, 'r') as store:
            tempDataFrame = pd.DataFrame({'Event':store.Hits.Event[:15000], 'Row'+str(index):store.Hits.Row[:15000]})
            tempDataFrame = tempDataFrame.set_index('Event')
            DataFrame = tempDataFrame.join(DataFrame)
            DataFrame = DataFrame.dropna()
            index += 1
            del tempDataFrame
    DataFrame["index"] = DataFrame.index
    DataFrame.drop_duplicates(take_last=True, inplace=True)
    del DataFrame["index"]
    print DataFrame.head(10)
    correlationNames = ('Row')
    index = 0
    for corName in correlationNames:
        for colName in itertools.permutations(DataFrame.filter(regex=corName),2):
            if(corName == 'Col'):
                heatmap, xedges, yedges = np.histogram2d(DataFrame[colName[0]],DataFrame[colName[1]], bins = (80, 80), range = [[1,80], [1,80]])
            else:
                heatmap, xedges, yedges = np.histogram2d(DataFrame[colName[0]],DataFrame[colName[1]], bins = (336, 336), range = [[1,336], [1,336]])
            extent = [yedges[0]-0.5, yedges[-1]+0.5, xedges[-1]+0.5, xedges[0]-0.5]
#             extent = [xedges[0], xedges[-1], yedges[0], yedges[-1]]
            plt.clf()
            cmap = cm.get_cmap('hot', 40)
            plt.imshow(heatmap, extent=extent, cmap = cmap, interpolation='nearest')
            plt.gca().invert_yaxis()
            plt.xlabel(colName[0])
            plt.ylabel(colName[1])
            plt.title('Correlation plot('+corName+')')
            plt.savefig(colName[0]+'_'+colName[1]+'.pdf')
#             print 'store as ', fileNames[int(index/2)]
            index+=1
            
def plotOccupancy(occupancy_hist, median = False, max_occ = None, filename = None):
    plt.clf()
    H=np.empty(shape=(336,80),dtype=occupancy_hist.dtype)
    H[:]=occupancy_hist[:,:,0]
    #print H[2, 2]
    extent = [0.5, 80.5, 336.5, 0.5]
    cmap = cm.get_cmap('hot')    
    if median:
        ceil_number = ceil_mod(int(np.median(H[H>0])*2) if max_occ == None else max_occ, 255)
    else:
        ceil_number = ceil_mod(int(H.max()) if max_occ == None else max_occ, 255)
    bounds = range(0, ceil_number+1, ceil_number/255)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    plt.title('Occupancy')
    plt.xlabel('Column')
    plt.ylabel('Row')
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_pixel_mask(mask, maskname, filename = None):
    plt.clf()
    extent = [0.5, 80.5, 336.5, 0.5]
    plt.imshow(mask, interpolation='nearest', aspect="auto", extent=extent) # for monitoring
    plt.title(maskname+" mask")
    plt.xlabel('Column')
    plt.ylabel('Row')
    #plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)
        
def plot_pixel_dac_config(dacconfig, dacname, filename = None):
    plt.clf()
    extent = [0.5, 80.5, 336.5, 0.5]
    cmap = cm.get_cmap('hot')
    ceil_number = ceil_mod(int(dacconfig.max()),1)
    bounds = range(0, ceil_number+1, ceil_number/255)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(dacconfig, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent)
    plt.title(dacname+" distribution")
    plt.xlabel('Column')
    plt.ylabel('Row')
    #plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)