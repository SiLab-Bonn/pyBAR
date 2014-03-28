"""This is a slow and ugly script to convert the hdf5 hit table from pyBAR to a CERN ROOT Ttree.
The speed is only about 45 kHz Hits.
"""
import tables as tb
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

def convert_hit_table(input_filename, output_filename):
    with tb.open_file(input_filename, 'r') as in_file_h5:
        hits = in_file_h5.root.Hits

        myHit = init_hit_struct()
        out_file_root = TFile(output_filename, 'RECREATE')
        tree = TTree('Hits', 'Hits from PyBAR')

        tree.Branch('event_number', AddressOf(myHit, 'event_number'), 'event_number/L')
        tree.Branch('trigger_number', AddressOf(myHit, 'trigger_number'), 'trigger_number/i')
        tree.Branch('relative_BCID', AddressOf(myHit, 'relative_BCID'), 'relative_BCID/b')
        tree.Branch('LVL1ID', AddressOf(myHit, 'LVL1ID'), 'LVL1ID/s')
        tree.Branch('column', AddressOf(myHit, 'column'), 'column/b')
        tree.Branch('row', AddressOf(myHit, 'row'), 'row/s')
        tree.Branch('tot', AddressOf(myHit, 'tot'), 'tot/b')
        tree.Branch('BCID', AddressOf(myHit, 'BCID'), 'BCID/s')
        tree.Branch('TDC', AddressOf(myHit, 'TDC'), 'TDC/s')
        tree.Branch('trigger_status', AddressOf(myHit, 'trigger_status'), 'trigger_status/b')
        tree.Branch('service_record', AddressOf(myHit, 'service_record'), 'service_record/i')
        tree.Branch('event_status', AddressOf(myHit, 'event_status'), 'event_status/s')

        progress_bar = progressbar.ProgressBar(widgets=['', progressbar.Percentage(), ' ', progressbar.Bar(marker='*', left='|', right='|'), ' ', progressbar.ETA()], maxval=hits.shape[0])
        progress_bar.start()

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
            progress_bar.update(index)
        progress_bar.finish()

        out_file_root.Write()
        out_file_root.Close()


if __name__ == "__main__":
    convert_hit_table('test.h5', 'output.root')
