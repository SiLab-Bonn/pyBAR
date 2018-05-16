from collections import OrderedDict

from basil.utils.BitLogic import BitLogic

from pybar.daq.readout_utils import is_data_header, is_address_record, is_value_record, is_service_record, is_data_record

flavors = ('fei4a', 'fei4b')


class FEI4Record(object):
    """Record Object

    """
    def __init__(self, data_word, chip_flavor, tdc_trig_dist=False, trigger_data_mode=0):
        self.record_rawdata = int(data_word)
        self.record_word = BitLogic.from_value(value=self.record_rawdata, size=32)
        self.record_dict = OrderedDict()
        if self.record_rawdata & 0x80000000:
            self.record_type = "TW"
            if trigger_data_mode == 0:
                self.record_dict.update([('trigger number', self.record_word[30:0].tovalue())])
            elif trigger_data_mode == 1:
                self.record_dict.update([('trigger timestamp', self.record_word[30:0].tovalue())])
            elif trigger_data_mode == 2:
                self.record_dict.update([('trigger timestamp', self.record_word[30:16].tovalue()), ('trigger number', self.record_word[15:0].tovalue())])
            else:
                raise ValueError("Unknown trigger data mode %d" % trigger_data_mode)
        elif self.record_rawdata & 0xF0000000 == 0x40000000:
            self.record_type = "TDC"
            if tdc_trig_dist:
                self.record_dict.update([('tdc distance', self.record_word[27:20].tovalue()), ('tdc counter', self.record_word[19:12].tovalue()), ('tdc value', self.record_word[11:0].tovalue())])
            else:
                self.record_dict.update([('tdc counter', self.record_word[27:12].tovalue()), ('tdc value', self.record_word[11:0].tovalue())])
        elif not self.record_rawdata & 0xF0000000:  # FE data
            self.record_dict.update([('channel', (self.record_rawdata & 0x0F000000) >> 24)])
            self.chip_flavor = chip_flavor
            if self.chip_flavor not in flavors:
                raise KeyError('Chip flavor is not of type {}'.format(', '.join('\'' + flav + '\'' for flav in self.chip_flavors)))
            if is_data_header(self.record_rawdata):
                self.record_type = "DH"
                if self.chip_flavor == "fei4a":
                    self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('flag', self.record_word[15:15].tovalue()), ('lvl1id', self.record_word[14:8].tovalue()), ('bcid', self.record_word[7:0].tovalue())])
                elif self.chip_flavor == "fei4b":
                    self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('flag', self.record_word[15:15].tovalue()), ('lvl1id', self.record_word[14:10].tovalue()), ('bcid', self.record_word[9:0].tovalue())])
            elif is_address_record(self.record_rawdata):
                self.record_type = "AR"
                self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('type', self.record_word[15:15].tovalue()), ('address', self.record_word[14:0].tovalue())])
            elif is_value_record(self.record_rawdata):
                self.record_type = "VR"
                self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('value', self.record_word[15:0].tovalue())])
            elif is_service_record(self.record_rawdata):
                self.record_type = "SR"
                if self.chip_flavor == "fei4a":
                    self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('counter', self.record_word[9:0].tovalue())])
                elif self.chip_flavor == "fei4b":
                    if self.record_word[15:10].tovalue() == 14:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('lvl1id[11:5]', self.record_word[9:3].tovalue()), ('bcid[12:10]', self.record_word[2:0].tovalue())])
                    elif self.record_word[15:10].tovalue() == 15:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('skipped', self.record_word[9:0].tovalue())])
                    elif self.record_word[15:10].tovalue() == 16:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('truncation flag', self.record_word[9:9].tovalue()), ('truncation counter', self.record_word[8:4].tovalue()), ('l1req', self.record_word[3:0].tovalue())])
                    else:
                        self.record_dict.update([('start', self.record_word[23:19].tovalue()), ('header', self.record_word[18:16].tovalue()), ('code', self.record_word[15:10].tovalue()), ('counter', self.record_word[9:0].tovalue())])
            elif is_data_record(self.record_rawdata):
                self.record_type = "DR"
                self.record_dict.update([('column', self.record_word[23:17].tovalue()), ('row', self.record_word[16:8].tovalue()), ('tot1', self.record_word[7:4].tovalue()), ('tot2', self.record_word[3:0].tovalue())])
            else:
                self.record_type = "UNKNOWN FE WORD"
                self.record_dict.update([('word', self.record_word.tovalue())])
    #             raise ValueError('Unknown data word: ' + str(self.record_word.tovalue()))
        else:
            self.record_type = "UNKNOWN WORD"
            self.record_dict.update([('unknown', self.record_word[31:0].tovalue())])

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
        except Exception:
            try:
                return self.record_type == other.record_type
            except Exception:
                return False

    def __str__(self):
        return self.record_type + ' {}'.format(' '.join(key + ':' + str(val) for key, val in self.record_dict.iteritems()))

    def __repr__(self):
        return repr(self.__str__())
