# test the converter class
import converter
print "Creating converter object... ",
Converter = converter.Converter()
print "successfull"
# Try calling some methods
print "Testing conversion methods... ",
Converter.setWarningOutput(False);
Converter.setDebugOutput(False)
Converter.setInfoOutput(False)
Converter.setMaxTot(13)
Converter.setNbCIDs(16)
Converter.setFEi4B(False)
Converter.setOutFileName('out.h5')
Converter.createHitsTable(False)
Converter.createMetaData(True)
Converter.createErrorHist(True)
Converter.createServiceRecordHist(True)
Converter.createOccupancyHist(True)
Converter.createRelBcidHist(True);
Converter.createTotHist(True);
Converter.createThresholdHists(False)
Converter.createParameterData(False)
#Converter.printOptions()
print "successfull"
print "Testing conversion... ",
if(Converter.convertTable('in.h5')):
    print "successfull"
    #Converter.printSummary()
else:
    print "failed"
raw_input("Press Enter to continue...")

