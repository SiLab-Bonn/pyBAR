from RawDataConverter import converter #Bug?: has to be imported first, no reason obvious
import tables as tb
from plotting import plotting

''' Script to convert the raw data and to plot all histograms'''

rawdata_filename = r"RawDataConverter\in.h5"
output_filename = "out.h5"

plot_base_name = "Test_"

# convert raw data file
converter = converter.Converter()
converter.setMaxTot(13)
converter.setNbCIDs(16)
converter.setFEi4B(False)
converter.setOutFileName(output_filename)
converter.setWarningOutput(True)
converter.createOccupancyHist()
converter.createErrorHist()
converter.createServiceRecordHist()
#converter.createTriggerErrorHist()
#converter.createRelBcidHist()
converter.createTotHist()

converter.convertTable(rawdata_filename);

# plot the data
with tb.openFile(output_filename, 'r') as in_file:
    plotting.plotOccupancy(in_file.root.HistOcc, filename=plot_base_name+"Occupancy.pdf")
    #plot_relative_bcid(in_file.root.HistRelBCID, filename=plot_base_name+"Occupancy.pdf")
    plotting.plot_tot(in_file.root.HistTot, filename=plot_base_name+"Tot.pdf")
    plotting.plot_event_errors(in_file.root.HistErrors, filename=plot_base_name+"EventErrors.pdf")
    #plotting.plot_trigger_errors(in_file.root.HistTrgError, filename=plot_base_name+"Occupancy.pdf")
    plotting.plot_service_records(in_file.root.HistServiceRecords, filename=plot_base_name+"ServiceRecords.pdf")


