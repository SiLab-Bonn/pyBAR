''' Script to convert the raw data and to plot all histograms'''
from RawDataConverter import converter #Bug?: has to be imported first, no reason obvious
import tables as tb
from plotting import plotting

def analyze_raw_data(rawdata_filename, output_filename, plot_base_name = "Plot_", Fe_indicator = "_FE4"):   
    # converter options
    print "Analysing raw data...",
    raw_data_converter = converter.Converter()
    raw_data_converter.setMaxTot(13)
    raw_data_converter.setNbCIDs(16)
    raw_data_converter.setFEi4B(True)
    raw_data_converter.setOutFileName(output_filename)
    raw_data_converter.setWarningOutput(True)
    raw_data_converter.createHitsTable(False)
    raw_data_converter.createErrorHist()
    raw_data_converter.createServiceRecordHist()
    raw_data_converter.createTriggerErrorHist()
    raw_data_converter.createOccupancyHist()
    raw_data_converter.createRelBcidHist()
    raw_data_converter.createTotHist()
    raw_data_converter.convertTable(rawdata_filename); # convert raw data file
    
    # plot the data
    with tb.openFile(output_filename, 'r') as in_file:
        plotting.plotOccupancy(in_file.root.HistOcc, filename=rawdata_filename[:-3]+plot_base_name+"Occupancy.pdf")
        plotting.plot_relative_bcid(in_file.root.HistRelBCID, filename=rawdata_filename[:-3]+plot_base_name+"RelBCID.pdf")
        plotting.plot_tot(in_file.root.HistTot, filename=rawdata_filename[:-3]+plot_base_name+"Tot.pdf")
        plotting.plot_event_errors(in_file.root.HistErrors_FE4, filename=rawdata_filename[:-3]+plot_base_name+"EventErrors.pdf")
        plotting.plot_trigger_errors(in_file.root.HistTrgError_FE4, filename=rawdata_filename[:-3]+plot_base_name+"TriggerErrors.pdf")
        plotting.plot_service_records(in_file.root.HistServiceRecords_FE4, filename=rawdata_filename[:-3]+plot_base_name+"ServiceRecords.pdf")
    
    print "done!"

if __name__ == "__main__":
    rawdata_filename = "C:\\data\\analog_scan_1.h5"
    output_filename = "C:\\data\\analog_scan_out.h5"
    analyze_raw_data(rawdata_filename = rawdata_filename, output_filename = output_filename)