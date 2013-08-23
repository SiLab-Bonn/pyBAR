import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from mpl_toolkits.axes_grid1 import make_axes_locatable
import pandas as pd
import itertools
import tables as tb
from math import sqrt
from matplotlib import colors, cm, legend

def make_occupancy(cols, rows, max_occ = None):
    plt.clf()
    H, xedges, yedges = np.histogram2d(rows, cols, bins = (336, 80), range = [[1,336], [1,80]])
    #print xedges, yedges
    extent = [yedges[0]-0.5, yedges[-1]+0.5, xedges[-1]+0.5, xedges[0]-0.5]
    #plt.pcolor(H)
    cmap = cm.get_cmap('hot', 20)
    ceil_number = ceil_mod(H.max() if max_occ == None else max_occ, 10)
    bounds = range(0, ceil_number+1, ceil_number/10)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    plt.title('Occupancy')
    plt.xlabel('Column')
    plt.ylabel('Row')
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm, ticks = bounds)

def plot_occupancy(cols, rows = None, max_occ = None, filename = None, title = None):
    if(rows == None):
        cols = 0
        rows = 0
    make_occupancy(cols, rows, max_occ)
    if(title != 0):
        plt.title(title)
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def save_occupancy(filename, cols, rows, max_occ = None):
    make_occupancy(cols, rows, max_occ)
    plt.savefig(filename)

def ceil_mod(number, mod):
    number = int(number)
    mod = int(mod)
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
    plt.bar(range(0,16), relative_bcid_hist[:], color='r', align = 'center') #bug: https://github.com/matplotlib/matplotlib/issues/1882, log = True)
    plt.xlabel('relative BCID [25 ns]')
    plt.ylabel('#')
    plt.yscale('log')
    plt.title('Relative BCID (former LVL1ID)')
    plt.xlim((0, 16))
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
    plt.xlim((0, 15))
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
    plt.bar(range(0,len(error_hist[:])), error_hist[:], color='r', align = 'center', label="Error code")
    plt.xlabel('')
    plt.ylabel('#')
    plt.title('Event errors')
    fig = plt.figure(1)
    fig.patch.set_facecolor('white')
    plt.grid(True)
    plt.xticks(range(0,8), ('SR\noccured', 'No\ntrigger', 'LVL1ID\nnot const.', '#BCID\nwrong', 'unknown\nword', 'BCID\njump', 'trigger\nerror', 'truncated') )
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
    plt.xlim((0, 31))
    plt.xlabel('service record code')
    plt.ylabel('#')
    plt.title('Service records ('+str(sum(service_record_hist[:]))+' entries)')
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
    ceil_number = ceil_mod(H.max() if max_occ == None else max_occ, 10)
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
    H = occupancy_hist
    #print H[2, 2]
    extent = [0.5, 80.5, 336.5, 0.5]
    #     cmap = cm.get_cmap('copper_r')
    cmap = cm.get_cmap('PuBu', 10)
    if median:
        ceil_number = ceil_mod(np.median(H[H>0]*2) if max_occ == None else max_occ, 10)
    else:
        ceil_number = ceil_mod(H.max() if max_occ == None else max_occ, 10)
    #         ceil_number = ceil_mod(int(H.max()) if max_occ == None else max_occ, 255)
    
    if(ceil_number<10):
        ceil_number = 10
    bounds = range(0, ceil_number+1, ceil_number/10)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    #     if (ceil_number<255):
    #         ceil_number = 255
    #     bounds = range(0, ceil_number+1, 255/ceil_number)
    #     norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    plt.title('Occupancy ('+str(sum(sum(H)))+' entries)')
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
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plot_pixel_dac_config(dacconfig, dacname, filename = None):
    plt.clf()
    extent = [0.5, 80.5, 336.5, 0.5]
    cmap = cm.get_cmap('hot')
    ceil_number = ceil_mod(dacconfig.max(),1)
    bounds = range(0, ceil_number+1, ceil_number/255)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(dacconfig, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent)
    plt.title(dacname+" distribution")
    plt.xlabel('Column')
    plt.ylabel('Row')
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm)
    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def create_2d_pixel_hist(hist2d, title = None, x_axis_title = None, y_axis_title = None, z_max = None):
    H=np.empty(shape=(336,80),dtype=hist2d.dtype)
    H[:]=hist2d[:,:]
    extent = [0.5, 80.5, 336.5, 0.5]
    cmap = cm.get_cmap('hot', 200)
    #ceil_number = np.max(hist2d) if z_max == None else z_max
    ceil_number = ceil_mod(H.max() if z_max == None else z_max, 10)
    #ceil_number = np.max(hist2d)
    bounds = range(0, ceil_number+1, ceil_number/10)
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plt.imshow(H, interpolation='nearest', aspect="auto", cmap = cmap, norm = norm, extent=extent) # for monitoring
    if title != None:
        plt.title(title)
    if x_axis_title != None:
        plt.xlabel(x_axis_title)
    if y_axis_title != None:
        plt.ylabel(y_axis_title)
    ax = plt.subplot(311)
#     ax = plt.plot()
    divider = make_axes_locatable(ax)
#     ax = plt.plot()
    ax = plt.subplot(311)
    cax = divider.append_axes("right", size="5%", pad=0.05)
    plt.colorbar(boundaries = bounds, cmap = cmap, norm = norm, ticks = bounds, cax = cax)


def create_1d_hist(hist, title = None, x_axis_title = None, y_axis_title = None, bins = None, x_max = None):
    median = np.median(hist)
    mean = np.mean(a = hist)
    rms = 0
    for i in range(0, len(hist.ravel())):
        rms += (hist.ravel()[i]-mean)**2
    rms = sqrt(rms/len(hist.ravel()))
    
    hist,bins,_ = plt.hist(x = hist.ravel(), bins = 100 if bins == None else bins)   #rebin to 1 d hist
   
    if title != None:
        plt.title(title)
    if x_axis_title != None:
        plt.xlabel(x_axis_title)
    if y_axis_title != None:
        plt.ylabel(y_axis_title)

    bin_centres = (bins[:-1] + bins[1:])/2
    amplitude = np.amax(hist)    

    def gauss(x, *p):
        A, mu, sigma = p
        return A*np.exp(-(x-mu)**2/(2.*sigma**2))
    
    p0 = np.array([amplitude, mean, rms])# p0 is the initial guess for the fitting coefficients (A, mu and sigma above)
    ax = plt.subplot(312)
    try:
        coeff, _ = curve_fit(gauss, bin_centres, hist, p0=p0)
        hist_fit = gauss(bin_centres, *coeff)
        plt.plot(bin_centres, hist_fit, "r--", label='Gaus fit')
        chi2 = 0
        for i in range(0, len(hist)):
            chi2 += (hist[i] - gauss(bins[i], *coeff))**2
        textright = '$\mu=%.2f$\n$\sigma=%.2f$\n$\chi2=%.2f$'%(coeff[1], coeff[2], chi2)
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.85, 0.9, textright, transform=ax.transAxes, fontsize=8,
        verticalalignment='top', bbox=props)
    except RuntimeError:
        print("Fit failed, do not plot fit")
        
    plt.ylim([0, plt.ylim()[1]*1.05])
    plt.xlim([0, np.amax(bins) if x_max == None else x_max])  
    textleft = '$\mathrm{mean}=%.2f$\n$\mathrm{RMS}=%.2f$\n$\mathrm{median}=%.2f$'%(mean, rms, median)
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.1, 0.9, textleft, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)

def create_pixel_scatter_plot(hist, title = None, x_axis_title = None, y_axis_title = None, y_max = None):
    scatter_y = np.empty(shape=(336*80),dtype=hist.dtype)
    scatter_y_mean = np.zeros(shape=(80),dtype=np.float32)
    for col in range(80):
        column_mean = 0
        for row in range(336):
            scatter_y[row + col*336] = hist[row,col]
            column_mean += hist[row,col]
        scatter_y_mean[col] = column_mean/336.
    plt.scatter(range(80*336),  scatter_y, marker='o', s = 0.8)
    p1, = plt.plot(range(336/2,80*336+336/2,336), scatter_y_mean, 'o')
    plt.plot(range(336/2,80*336+336/2,336), scatter_y_mean, linewidth=2.0)
    plt.legend([p1], ["column mean"], prop={'size':6})
    plt.xlim(0,26880)
    plt.ylim(1.1*min(scatter_y) if(min(scatter_y) < 0) else 0 ,1.1*max(scatter_y) if y_max == None else y_max)
    if title != None:
        plt.title(title)
    if x_axis_title != None:
        plt.xlabel(x_axis_title)
    if y_axis_title != None:
        plt.ylabel(y_axis_title)

def plotThreeWay(hist, title, x_axis_title = None, y_axis_title = None, filename = None, label = "label not set", maximum = None, bins = None):   #the famous 3 way plot (enhanced)
    mean = np.mean(hist)
    fig = plt.figure()
    fig.patch.set_facecolor('white')
    plt.subplot(311)
    create_2d_pixel_hist(hist, title = title, x_axis_title = "column", y_axis_title = "row", z_max = 2*mean if maximum == None else maximum)
    plt.subplot(312)
    create_1d_hist(hist, bins = bins, x_axis_title = label, y_axis_title = "#", x_max = maximum)
    plt.subplot(313)
    create_pixel_scatter_plot(hist, x_axis_title = "channel = row + column*336", y_axis_title = label, y_max = maximum)
    plt.tight_layout()

    if filename is None:
        plt.show()
    else:
        plt.savefig(filename)

def plotTDACcfg(in_file_name, filename = None):
    plt.clf()
    array = []
    for line in open(in_file_name, 'r'):
        if(line[0] != "#"): #skip comments
            line = filter(None, line.split(" ")) #create array from the line and delete empty entries
            line = line[:-1] #remove new line character
            print line

if __name__ == "__main__":
    with tb.openFile('out.h5', 'r') as in_file:
        H=np.empty(shape=(336,80),dtype=in_file.root.HistOcc.dtype)
        H[:]=in_file.root.HistThreshold[:,:]
        
        #plotThreeWay(hist = in_file.root.HistOcc[:,:,70], title = "Occupancy", filename = "Occupancy.pdf", label = "noise[e]")
        plotThreeWay(hist = in_file.root.HistThreshold[:,:], title = "Threshold", filename = "Threshold.pdf", label = "noise[e]")
#     fig.patch.set_facecolor('white')
#     if filename is None:
#         plt.show()
#     else:
#         plt.savefig(filename)

# import tables as tbx
# with tb.openFile("out.h5", 'r') as in_file:
#create_pixel_scatter_plot(in_file.root.HistOcc[:,:,0])
#     plotThreeWay(in_file.root.HistOcc[:,:,0], title = "Test", x_axis_title = "occupancy", y_axis_title ="#")
# plotTDACcfg("TDAC.dat")