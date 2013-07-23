#import numpy as np
from bitstring import BitArray#, BitStream

class FEI4Record(object):
    """Record Object
    
    """
    
    def __init__(self, rawdata, chip_flavor):
        self.record_rawdata = int(rawdata) & 0x00FFFFFF
        self.chip_flavor = str(chip_flavor).lower()
        self.chip_flavors = ['fei4a', 'fei4b']
        if self.chip_flavor not in self.chip_flavors:
            raise KeyError('Chip flavor is not of type {}'.format(', '.join('\''+flav+'\'' for flav in self.chip_flavors)))
        self.record_word = BitArray(uint=self.record_rawdata, length = 24)
        self.record_dict = None
        if self.record_word[0:8].uint == int("11101001", 2):
            self.record_type = "DH"
            if self.chip_flavor == "fei4a":
                self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'flag':self.record_word[8:9].uint, 'lvl1id':self.record_word[9:16].uint, 'bcid':self.record_word[16:24].uint}
            elif self.chip_flavor == "fei4b":
                self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'flag':self.record_word[8:9].uint, 'lvl1id':self.record_word[9:14].uint, 'bcid':self.record_word[14:24].uint}
        elif self.record_word[0:8].uint == int("11101010", 2):
            self.record_type = "AR"
            self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'type':self.record_word[8:9].uint, 'address':self.record_word[9:24].uint}
        elif self.record_word[0:8].uint == int("11101100", 2):
            self.record_type = "VR"
            self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'value':self.record_word[8:24].uint}
        elif self.record_word[0:8].uint == int("11101111", 2):
            self.record_type = "SR"
            if self.chip_flavor == "fei4a":
                self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'code':self.record_word[8:14].uint, 'counter':self.record_word[14:24].uint}
            elif self.chip_flavor == "fei4b":
                if self.record_word[8:14].uint == 14:
                    self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'code':self.record_word[8:14].uint, 'lvl1id':self.record_word[14:21].uint, 'bcid':self.record_word[21:24].uint}
                elif self.record_word[8:14].uint == 15:
                    self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'code':self.record_word[8:14].uint, 'skipped':self.record_word[14:24].uint}
                elif self.record_word[8:14].uint == 16:
                    self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'code':self.record_word[8:14].uint, 'truncation flag':self.record_word[14:15].uint, 'truncation counter':self.record_word[15:20].uint, 'l1req':self.record_word[20:24].uint}
                else:  
                    self.record_dict = {'start':self.record_word[0:5].uint, 'header':self.record_word[5:8].uint, 'code':self.record_word[8:14].uint, 'counter':self.record_word[14:24].uint}
        elif self.record_word[0:7].uint >= int("0000001", 2) and self.record_word[0:7].uint <= int("1010000", 2) and self.record_word[7:16].uint >= int("000000001", 2) and self.record_word[7:16].uint <= int("101010000", 2):
            self.record_type = "DR"
            self.record_dict = {'column':self.record_word[0:7].uint, 'row':self.record_word[7:16].uint, 'tot1':self.record_word[16:20].uint, 'tot2':self.record_word[20:24].uint}
        else:
            self.record_type = "UNKNOWN"
            self.record_dict = {'unknown':self.record_word.uint}
            raise ValueError('Unknown data word: '+str(self.record_word.uint))
        
    def __len__(self):
        return len(self.record_dict)
    
    def __getitem__(self, key):
        if not (isinstance(key, (int, long)) or isinstance(key, basestring)):
            raise TypeError()
        try:
            return self.record_dict[key.lower()]
        except TypeError:
            return self.record_dict[self.record_dict.iterkeys()[int(key)]]
    
    def next(self):
        return self.record_dict.iteritems().next()
    
    def __iter__(self):
        return self.record_dict.iteritems()
    
    def __eq__(self, other):
        try:
            return self.record_type.lower() == other.lower()
        except:
            try:
                return self.record_type == other.record_type
            except:
                return False
            
    def __str__(self):
        return self.record_type + ' {}'.format(' '.join(key+':'+str(val) for key,val in self.record_dict.iteritems()))
        
    def __repr__(self):
        return repr(self.__str__())

class FEI4RecordSequence:
    """Sequence of Data Record Objects
    
    """
    
    def __init__(self):
        pass