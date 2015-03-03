import serial
import time
import sys

Units = {
    'Voltage':
    {'mV': 0.001,
     'V': 1.0
     },
    'Current':
    {'nA': 0.000000001,
     'uA': 0.000001,
     'mA': 0.001,
     'A': 1.0}
}

Modi = {
    'Source':
    {'V': 'VOLT',
     'v': 'VOLT',
          'A': 'CURR',
     'a': 'CURR'
     },
    'Sample':
    {'V': 'VOLT',
          'v': 'VOLT',
          'A': 'CURR',
     'a': 'CURR'}
}

##################################################
##################################################
# Class definitions
##################################################
##################################################

# class SourceError(Exception):
#     def __init__(self, value):
#         self.value = value
#     def __str__(self):
#         return repr(self.value)

# User defined data point with errors


class DataPoint:

    def __init__(self, x_value, y_value, x_error, y_error):
        self.x = x_value
        self.y = y_value
        self.x_err = x_error
        self.y_err = y_error

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_x_error(self):
        return self.x_err

    def get_y_error(self):
        return self.y_err


# Class for the Keithley SMU 2400/2410 series
class Keithley24xx:
    ser = None

    def __init__(self, conf):
        self.configuration_file = conf
        self.set_device_configuration()

    def open_device_interface(self):
        self._ser.open()
        print "Device Ready at Port %s" % (self.configuration_file["Device"]["Configuration"]["Port"])

    def enable_output(self, en=False):
        if(en == True):
            self._ser.write(':OUTPUT ON\r\n')
            print "Output On"
        if(en == False):
            self._ser.write(':OUTPUT OFF\r\n')
            print "Output Off"

    def close_device_interface(self):
        self._ser.close()
        print "Device Closed at Port %s" % (self.configuration_file["Device"]["Configuration"]["Port"])

    def set_device_configuration(self):
        # Initialization of the Serial interface
        self._ser = serial.Serial(
            port=self.configuration_file["Device"]["Configuration"]["Port"],
            baudrate=self.configuration_file["Device"]["Configuration"]["Baudrate"],
            timeout=2
        )
        print "Device at Port %s Configured" % (self.configuration_file["Device"]["Configuration"]["Port"])

        self._source = Modi['Source'][self.configuration_file["Device"]["Configuration"]["Source"]]
        self._sample = Modi['Sample'][self.configuration_file["Device"]["Configuration"]["Sample"]]
        self._compliance = self.configuration_file["Device"]["Configuration"]["Compliance"]
        self._triggerCount = self.configuration_file["Device"]["Configuration"]["TriggerCount"]
        self._triggerDelay = self.configuration_file["Device"]["Configuration"]["TriggerDelay"]
        self._sampleAutoRange = self.configuration_file["Device"]["Configuration"]["SampleAutoRange"]
        self._sourceAutoRange = self.configuration_file["Device"]["Configuration"]["SourceAutoRange"]

        # Setup the source
        self._ser.write('*RST\r\n')

        self._ser.write(':SYST:BEEP:STAT ON\r\n')

        self._ser.write(':SOUR:CLEar:IMMediate\r\n')
        self._ser.write(':SOUR:FUNC:MODE %s\r\n' % (self._source))
        # self._ser.write(':SOUR:CLEar:IMMediate\r\n')
        self._ser.write(':SOUR:%s:MODE FIX\r\n' % (self._source))
        self._ser.write(':SOUR:%s:RANG:AUTO %s\r\n' % (self._source, self._sourceAutoRange))

        # Setup the sensing
        self._ser.write(':SENS:FUNC \"%s\"\r\n' % (self._sample))
        self._ser.write(':SENSE:%s:PROT:LEV %s\r\n' % (self._sample, self._compliance))
        self._ser.write(':SENSE:%s:RANG:AUTO %s\r\n' % (self._sample, self._sampleAutoRange))

        # Setup the buffer
        self._ser.write(':TRAC:FEED:CONT NEVer\r\n')
        self._ser.write(':TRAC:FEED SENSE\r\n')
        self._ser.write(':TRAC:POIN %s\r\n' % (self._triggerCount))
        self._ser.write(':TRAC:CLEar\r\n')
        self._ser.write(':TRAC:FEED:CONT NEXT\r\n')

        # Setup the data format
        self._ser.write(':FORMat:DATA ASCii\r\n')
        self._ser.write(':FORMat:ELEM VOLTage, CURRent\r\n')

# Setup the trigger
        self._ser.write(':TRIG:COUN %s\r\n' % (self._triggerCount))
        self._ser.write(':TRIG:DEL %s\r\n' % (self._triggerDelay))

    def reset(self):
        self._ser.write('*RST\r\n')

    def set_value(self, source_value):
        self._ser.write(':SOUR:%s:LEVel %s\r\n' % (self._source, source_value))
        time.sleep(self.configuration_file["Device"]["Configuration"]["SettlingTime"])

    def set_voltage(self, voltage_value=0, unit='mV'):
        val = voltage_value * Units['Voltage'][unit]
        self._ser.write(':SOUR:%s:LEVel %s\r\n' % (self._source, val))
        time.sleep(self.configuration_file["Device"]["Configuration"]["SettlingTime"])

    def set_source_upper_range(self, senseUpperRange):
        self._ser.write(':SENSE:%s:RANG:UPP %s\r\n' % (self._source, senseUpperRange))

    def sample(self):
        self._ser.write(':TRAC:FEED:CONT NEVer\r\n')
        self._ser.write(':TRACe:CLEar\r\n')
        self._ser.write(':TRAC:FEED:CONT NEXT\r\n')
        self._ser.write(':INIT\r\n')

    def get_raw_values(self):
        self._ser.write(':TRACe:DATA?\r\n')

    def get_mean(self):
        self._ser.write(':CALC3:FORM MEAN\r\n')
        self._ser.write(':CALC3:DATA?\r\n')

    def get_std(self):
        self._ser.write(':CALC3:FORM SDEV\r\n')
        self._ser.write(':CALC3:DATA?\r\n')

    def read(self, time_to_wait):
        while (self._ser.inWaiting() <= 2):
            pass
        time.sleep(time_to_wait)
        data = self._ser.read(self._ser.inWaiting())
        return data

    def get_value(self, with_error=False):
        self.sample()
        self.get_mean()
        dmean = eval(self.read(self.configuration_file["Device"]["Configuration"]["WaitRead"]))
        if(with_error == True):
            self.get_std()
            dstd = eval(self.read(self.configuration_file["Device"]["Configuration"]["WaitRead"]))
            return dmean, dstd
        else:
            return dmean

    def get_voltage(self, unit, with_error=False):
        self.sample()
        self.get_mean()
        d = eval(self.read(self.configuration_file["Device"]["Configuration"]["WaitRead"]))
        if(with_error == True):
            self.get_std()
            derr = eval(self.read(self.configuration_file["Device"]["Configuration"]["WaitRead"]))
            return d[0] / Units['Voltage'][unit], derr[0] / Units['Voltage'][unit]
        else:
            return d[0] / Units['Voltage'][unit]

    def get_current(self, unit, with_error=False):
        self.sample()
        self.get_mean()
        d = eval(self.read(self.configuration_file["Device"]["Configuration"]["WaitRead"]))
        if(with_error == True):
            self.get_std()
            derr = eval(self.read(self.configuration_file["Device"]["Configuration"]["WaitRead"]))
            return d[1] / Units['Current'][unit], derr[1] / Units['Current'][unit]
        else:
            return d[1] / Units['Current'][unit]

    def sweep(self, sampleDev):
        sampleDev._ser.write(':SENSE:%s:RANG:UPP %s\r\n' % (self._sample, self.configuration_file["Device"]["Sweep"]["UpperRangeOfExpectedSamplingValue"]))
        counter = 0
        data = []
        for i in range(0, self.configuration_file["Device"]["Sweep"]["NumberOfSamplingPoints"] + 1):
            low = self.configuration_file["Device"]["Sweep"]["LowValue"]
            high = self.configuration_file["Device"]["Sweep"]["HighValue"]
            val = low + i * (high - low) / self.configuration_file["Device"]["Sweep"]["NumberOfSamplingPoints"]
            # if(self._source == 'VOLT'):
            self.set_voltage(val, unit='V')
            # if(self._source == 'CURR'):
            # 	self.set_current(val, unit = 'A')
            # else:
            # 	print "ERR: No Voltage or Current sweep selected"
            # 	break
            sampleDev.sample()
            sampleDev.get_mean()
            sampledData = sampleDev.read(self.configuration_file["Device"]["Configuration"]["WaitRead"])
            mean = eval(sampledData)
            sampleDev.get_std()
            sampledData = sampleDev.read(self.configuration_file["Device"]["Configuration"]["WaitRead"])
            std = eval(sampledData)
            data.append([mean[0], std[0], mean[1], std[1]])
            # counter += 1
        return data, counter
