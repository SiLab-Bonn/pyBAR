# file: TestPythonModule.py
# Test various properties of classes defined in separate modules

print "Testing the %import directive"
import Converter
print "Creating converter object"
Converter = Converter.Converter()
# Try calling some methods
print "Testing some methods"
print "",
Converter.setWarningOutput(False);
Converter.setDebugOutput(False)
Converter.setInfoOutput(False)
Converter.loadHDF5file('in.h5')
Converter.setNbCIDs(16)
Converter.setFEi4B(False)
Converter.setOutFileName('out.h5')
Converter.createHitsTable(False)
Converter.createMetaData(True)
Converter.createParameterData(False)
Converter.createErrorHist(True)
Converter.createServiceRecordHist(True)
Converter.createOccupancyHists(True)
Converter.createThresholdHists(False)
#Converter.printOptions()
Converter.convertTable()
Converter.printSummary()


