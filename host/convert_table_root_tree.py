"""This script has different methods to convert the hdf5 hit table from pyBAR into a CERN ROOT Ttree.
"""
import tables as tb
import numpy as np
import ctypes
import progressbar
from ROOT import TFile, TTree
from ROOT import gROOT, AddressOf


def init_hit_struct():
    gROOT.ProcessLine(\
    "struct HitInfo{\
      ULong64_t event_number;\
      UInt_t trigger_number;\
      UChar_t relative_BCID;\
      UShort_t LVL1ID;\
      UChar_t column;\
      UShort_t row;\
      UChar_t tot;\
      UShort_t BCID;\
      UShort_t TDC;\
      UChar_t trigger_status;\
      UInt_t service_record;\
      UShort_t event_status;\
    };");
    from ROOT import HitInfo
    return HitInfo()


def get_root_type_descriptor(numpy_type_descriptor):
    ''' Converts the numpy type descriptor to the ROOT type descriptor.
    Parameters
    ----------
    numpy_type_descriptor: np.dtype
    '''
    return{
        'int64': 'L',
        'uint64': 'l',
        'int32': 'I',
        'uint32': 'i',
        'int16': 'S',
        'uint16': 's',
        'int8': 'B',
        'uint8': 'b',
    }[str(numpy_type_descriptor)]


def init_tree_from_table(table, chunk_size=1, tree_entry=None):
    ''' Initializes a ROOT tree from a HDF5 table.
    Takes the HDF5 table column names and types and creates corresponding branches. If a chunk size is specified the branches will have the length of the chunk size and
    an additional parameter is returned to change the chunk size at a later stage.
    If a tree_entry is defined (a ROOT c-struct) the new tree has the branches set to the corresponding tree entry address.

    Parameters
    ----------
    numpy_type_descriptor: np.dtype
    '''
    if(chunk_size > 1 and tree_entry is not None):
        raise NotImplementedError()

    tree = TTree('Table', 'Converted HDF5 table')
    chunk_size_tree = None
    if chunk_size > 1:
        chunk_size_tree = ctypes.c_int(chunk_size) if chunk_size > 1 else 1
        tree.Branch('chunk_size_tree', ctypes.addressof(chunk_size_tree), 'chunk_size_tree/I')  # needs to be added, otherwise one cannot access chunk_size_tree

    for column_name in table.dtype.names:
        tree.Branch(column_name, 'NULL' if tree_entry is None else AddressOf(tree_entry, column_name), column_name + '[chunk_size_tree]/' + get_root_type_descriptor(table.dtype[column_name]) if chunk_size > 1 else column_name + '/' + get_root_type_descriptor(table.dtype[column_name]))

    return tree, chunk_size_tree


def convert_hit_table(input_filename, output_filename):
    ''' Creates a ROOT Tree by looping over all entries of the table.
    In each iteration all entries are type casting to int and appended to the ROOT Tree. This is straight forward but rather slow (45 kHz Hits).
    The ROOT Tree has its addresses pointing to a hit struct members. The struct is defined in ROOT.

    Parameters
    ----------
    input_filename: string
        The file name of the hdf5 hit table.

    output_filename: string
        The filename of the created ROOT file

    '''
    with tb.open_file(input_filename, 'r') as in_file_h5:
        hits = in_file_h5.root.Hits

        myHit = init_hit_struct()
        out_file_root = TFile(output_filename, 'RECREATE')
        tree, _ = init_tree_from_table(hits, 1, myHit)

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.ETA()], maxval=hits.shape[0])
        progress_bar.start()

        update_progressbar_index = hits.shape[0] / 1000

        for index, hit in enumerate(hits):
            myHit.event_number = int(hit['event_number'])
            myHit.trigger_number = int(hit['trigger_number'])
            myHit.relative_BCID = int(hit['relative_BCID'])
            myHit.LVL1ID = int(hit['LVL1ID'])
            myHit.column = int(hit['column'])
            myHit.row = int(hit['row'])
            myHit.tot = int(hit['tot'])
            myHit.BCID = int(hit['BCID'])
            myHit.TDC = int(hit['TDC'])
            myHit.trigger_status = int(hit['trigger_status'])
            myHit.service_record = int(hit['service_record'])
            myHit.event_status = int(hit['event_status'])
            tree.Fill()
            if (index % update_progressbar_index == 0):  # increase the progress bar update speed, otherwise progress_bar.update(index) is called too often
                progress_bar.update(index)
        progress_bar.finish()

        out_file_root.Write()
        out_file_root.Close()


def convert_hit_table_fast(input_filename, output_filename):
    ''' Creates a ROOT Tree by looping over chunks of the hdf5 table. Some pointer magic is used to increase the conversion speed. Is 40x faster than convert_hit_table.

    Parameters
    ----------
    input_filename: string
        The file name of the hdf5 hit table.

    output_filename: string
        The filename of the created ROOT file

    '''

    with tb.open_file(input_filename, 'r') as in_file_h5:
        hits_table = in_file_h5.root.Hits

        out_file_root = TFile(output_filename, 'RECREATE')

        tree, chunk_size_tree = init_tree_from_table(hits_table, chunk_size)

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.ETA()], maxval=hits_table.shape[0])
        progress_bar.start()

        for index in range(0, hits_table.shape[0], chunk_size):
            hits = hits_table.read(start=index, stop=index + chunk_size)

            column_data = {}  # columns have to be in an additional python data container to prevent the carbage collector from deleting

            for branch in tree.GetListOfBranches():  # loop over the branches
                if branch.GetName() != 'chunk_size_tree':
                    column_data[branch.GetName()] = hits[branch.GetName()].view(np.recarray).copy()  # a copy has to be made to get the correct memory alignement
                    branch.SetAddress(column_data[branch.GetName()].data)  # get the column data pointer by name and tell its address to the tree

            if index + chunk_size > hits_table.shape[0]:  # decrease tree leave size for the last chunk
                chunk_size_tree.value = hits_table.shape[0] - index

            tree.Fill()
            progress_bar.update(index)

        out_file_root.Write()
        out_file_root.Close()


if __name__ == "__main__":
    chunk_size = 50000  # chose this parameter as big as possible to increase speed, but not too big otherwise program crashed
    convert_hit_table('test.h5', 'output.root')
    convert_hit_table_fast('test.h5', 'output_fast.root')
