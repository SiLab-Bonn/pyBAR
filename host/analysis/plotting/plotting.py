import numpy as np
import matplotlib.pyplot as plt
from matplotlib import colors, cm


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