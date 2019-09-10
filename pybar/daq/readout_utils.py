import logging
import os

import numpy as np
import tables as tb


class NameValue(tb.IsDescription):
    name = tb.StringCol(256, pos=0)
    value = tb.StringCol(4 * 1024, pos=1)


def save_configuration_dict(h5_file, configuation_name, configuration, **kwargs):
        '''Stores any configuration dictionary to HDF5 file.

        Parameters
        ----------
        h5_file : string, file
            Filename of the HDF5 configuration file or file object.
        configuation_name : str
            Configuration name. Will be used for table name.
        configuration : dict
            Configuration dictionary.
        '''
        def save_conf():
            try:
                h5_file.remove_node(h5_file.root.configuration, name=configuation_name)
            except tb.NodeError:
                pass
            try:
                configuration_group = h5_file.create_group(h5_file.root, "configuration")
            except tb.NodeError:
                configuration_group = h5_file.root.configuration

            scan_param_table = h5_file.create_table(configuration_group, name=configuation_name, description=NameValue, title=configuation_name)
            row_scan_param = scan_param_table.row
            for key, value in dict.iteritems(configuration):
                row_scan_param['name'] = key
                row_scan_param['value'] = str(value)
                row_scan_param.append()
            scan_param_table.flush()

        if isinstance(h5_file, tb.file.File):
            save_conf()
        else:
            if os.path.splitext(h5_file)[1].strip().lower() != ".h5":
                h5_file = os.path.splitext(h5_file)[0] + ".h5"
            with tb.open_file(h5_file, mode="a", title='', **kwargs) as h5_file:
                save_conf()


def convert_data_array(array, filter_func=None, converter_func=None):  # TODO: add copy parameter, otherwise in-place
    '''Filter and convert raw data numpy array (numpy.ndarray)

    Parameters
    ----------
    array : numpy.array
        Raw data array.
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.

    Returns
    -------
    data_array : numpy.array
        Data numpy array of specified dimension (converter_func) and content (filter_func)
    '''
#     if filter_func != None:
#         if not hasattr(filter_func, '__call__'):
#             raise ValueError('Filter is not callable')
    if filter_func:
        array = array[filter_func(array)]
#     if converter_func != None:
#         if not hasattr(converter_func, '__call__'):
#             raise ValueError('Converter is not callable')
    if converter_func:
        array = converter_func(array)
    return array


def convert_data_iterable(data_iterable, filter_func=None, converter_func=None):  # TODO: add concatenate parameter
    '''Convert raw data in data iterable.

    Parameters
    ----------
    data_iterable : iterable
        Iterable where each element is a tuple with following content: (raw data, timestamp_start, timestamp_stop, status).
    filter_func : function
        Function that takes array and returns true or false for each item in array.
    converter_func : function
        Function that takes array and returns an array or tuple of arrays.

    Returns
    -------
    data_list : list
        Data list of the form [(converted data, timestamp_start, timestamp_stop, status), (...), ...]
    '''
    data_list = []
    for item in data_iterable:
        data_list.append((convert_data_array(item[0], filter_func=filter_func, converter_func=converter_func), item[1], item[2], item[3]))
    return data_list


def data_array_from_data_iterable(data_iterable):
    '''Convert data iterable to raw data numpy array.

    Parameters
    ----------
    data_iterable : iterable
        Iterable where each element is a tuple with following content: (raw data, timestamp_start, timestamp_stop, status).

    Returns
    -------
    data_array : numpy.array
        concatenated data array
    '''
    try:
        data_array = np.concatenate([item[0] for item in data_iterable])
    except ValueError:  # length is 0
        data_array = np.empty(0, dtype=np.uint32)
    return data_array


def is_tdc_from_channel(channel=4):  # function factory
    if channel >= 1 and channel < 8:
        def f(value):
            return np.equal(np.right_shift(np.bitwise_and(value, 0xF0000000), 28), channel)
        f.__name__ = "is_tdc_from_channel_" + str(channel)  # or use inspect module: inspect.stack()[0][3]
        return f
    else:
        raise ValueError('Invalid channel number')


def is_data_from_channel(channel=4):  # function factory
    '''Select data from channel

    Parameters:
    channel : int
        Channel number (4 is default channel on Single Chip Card)

    Returns:
    Function

    Usage:
    # 1
    is_data_from_channel_4 = is_data_from_channel(4)
    data_from_channel_4 = data_array[is_data_from_channel_4(data_array)]
    # 2
    filter_func = logical_and(is_data_record, is_data_from_channel(3))
    data_record_from_channel_3 = data_array[filter_func(data_array)]
    # 3
    is_raw_data_from_channel_3 = is_data_from_channel(3)(raw_data)

    Similar to:
    f_ch3 = functoools.partial(is_data_from_channel, channel=3)
    l_ch4 = lambda x: is_data_from_channel(x, channel=4)

    Note:
    Trigger data not included
    '''
    if channel >= 0 and channel < 16:
        def f(value):
            return np.equal(np.right_shift(np.bitwise_and(value, 0xFF000000), 24), channel)
        f.__name__ = "is_data_from_channel_" + str(channel)  # or use inspect module: inspect.stack()[0][3]
        return f
    else:
        raise ValueError('Invalid channel number')


def logical_and(f1, f2):  # function factory
    '''Logical and from functions.

    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.

    Returns
    -------
    Function

    Examples
    --------
    filter_func=logical_and(is_data_record, is_data_from_channel(4))  # new filter function
    filter_func(array) # array that has Data Records from channel 4
    '''
    def f(value):
        return np.logical_and(f1(value), f2(value))
    f.__name__ = "(" + f1.__name__ + "_and_" + f2.__name__ + ")"
    return f


def logical_or(f1, f2):  # function factory
    '''Logical or from functions.

    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.

    Returns
    -------
    Function
    '''
    def f(value):
        return np.logical_or(f1(value), f2(value))
    f.__name__ = "(" + f1.__name__ + "_or_" + f2.__name__ + ")"
    return f


def logical_not(f):  # function factory
    '''Logical not from functions.

    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.

    Returns
    -------
    Function
    '''
    def f(value):
        return np.logical_not(f(value))
    f.__name__ = "not_" + f.__name__
    return f


def logical_xor(f1, f2):  # function factory
    '''Logical xor from functions.

    Parameters
    ----------
    f1, f2 : function
        Function that takes array and returns true or false for each item in array.

    Returns
    -------
    Function
    '''
    def f(value):
        return np.logical_xor(f1(value), f2(value))
    f.__name__ = "(" + f1.__name__ + "_xor_" + f2.__name__ + ")"
    return f


def is_trigger_word(value):
    return np.equal(np.bitwise_and(value, 0x80000000), 0x80000000)


def is_tdc_word(value):
    return np.equal(np.bitwise_and(value, 0xC0000000), 0x40000000)


def is_fe_word(value):
    return np.equal(np.bitwise_and(value, 0xF0000000), 0)


def is_data_header(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111010010000000000000000)


def is_address_record(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111010100000000000000000)


def is_value_record(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111011000000000000000000)


def is_service_record(value):
    return np.equal(np.bitwise_and(value, 0x00FF0000), 0b111011110000000000000000)


def is_data_record(value):
    return np.logical_and(np.logical_and(np.less_equal(np.bitwise_and(value, 0x00FE0000), 0x00A00000), np.less_equal(np.bitwise_and(value, 0x0001FF00), 0x00015000)), np.logical_and(np.not_equal(np.bitwise_and(value, 0x00FE0000), 0x00000000), np.not_equal(np.bitwise_and(value, 0x0001FF00), 0x00000000)))


def get_trigger_data(value, mode=0):
    '''Returns 31bit trigger counter (mode=0), 31bit timestamp (mode=1), 15bit timestamp and 16bit trigger counter (mode=2)
    '''
    if mode == 2:
        return np.right_shift(np.bitwise_and(value, 0x7FFF0000), 16), np.bitwise_and(value, 0x0000FFFF)
    else:
        return np.bitwise_and(value, 0x7FFFFFFF)


def get_address_record_address(value):
    '''Returns the address in the address record
    '''
    return np.bitwise_and(value, 0x0000EFFF)


def get_address_record_type(value):
    '''Returns the type in the address record
    '''
    return np.right_shift(np.bitwise_and(value, 0x00008000), 14)


def get_value_record(value):
    '''Returns the value in the value record
    '''
    return np.bitwise_and(value, 0x0000FFFF)


def get_col_row_tot_array_from_data_record_array(array):  # TODO: max ToT
    '''Convert raw data array to column, row, and ToT array

    Parameters
    ----------
    array : numpy.array
        Raw data array.

    Returns
    -------
    Tuple of arrays.
    '''
    def get_col_row_tot_1_array_from_data_record_array(value):
        return np.right_shift(np.bitwise_and(value, 0x00FE0000), 17), np.right_shift(np.bitwise_and(value, 0x0001FF00), 8), np.right_shift(np.bitwise_and(value, 0x000000F0), 4)
#         return (value & 0xFE0000)>>17, (value & 0x1FF00)>>8, (value & 0x0000F0)>>4 # numpy.vectorize()

    def get_col_row_tot_2_array_from_data_record_array(value):
        return np.right_shift(np.bitwise_and(value, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(value, 0x0001FF00), 8), 1), np.bitwise_and(value, 0x0000000F)
#         return (value & 0xFE0000)>>17, ((value & 0x1FF00)>>8)+1, (value & 0x0000F) # numpy.vectorize()

    col_row_tot_1_array = np.column_stack(get_col_row_tot_1_array_from_data_record_array(array))
    col_row_tot_2_array = np.column_stack(get_col_row_tot_2_array_from_data_record_array(array))
#     print col_row_tot_1_array, col_row_tot_1_array.shape, col_row_tot_1_array.dtype
#     print col_row_tot_2_array, col_row_tot_2_array.shape, col_row_tot_2_array.dtype
    # interweave array here
    col_row_tot_array = np.vstack((col_row_tot_1_array.T, col_row_tot_2_array.T)).reshape((3, -1), order='F').T  # http://stackoverflow.com/questions/5347065/interweaving-two-numpy-arrays
#     print col_row_tot_array, col_row_tot_array.shape, col_row_tot_array.dtype
    # remove ToT > 14 (late hit, no hit) from array, remove row > 336 in case we saw hit in row 336 (no double hit possible)
    try:
        col_row_tot_array_filtered = col_row_tot_array[col_row_tot_array[:, 2] < 14]  # [np.logical_and(col_row_tot_array[:,2]<14, col_row_tot_array[:,1]<=336)]
#         print col_row_tot_array_filtered, col_row_tot_array_filtered.shape, col_row_tot_array_filtered.dtype
    except IndexError:
        # logging.warning('Array is empty')
        return np.array([], dtype=np.dtype('>u4')), np.array([], dtype=np.dtype('>u4')), np.array([], dtype=np.dtype('>u4'))
    return col_row_tot_array_filtered[:, 0], col_row_tot_array_filtered[:, 1], col_row_tot_array_filtered[:, 2]  # column, row, ToT


def get_col_row_array_from_data_record_array(array):
    col, row, _ = get_col_row_tot_array_from_data_record_array(array)
    return col, row


def get_row_col_array_from_data_record_array(array):
    col, row, _ = get_col_row_tot_array_from_data_record_array(array)
    return row, col


def get_tot_array_from_data_record_array(array):
    _, _, tot = get_col_row_tot_array_from_data_record_array(array)
    return tot


def get_occupancy_mask_from_data_record_array(array, occupancy):
    pass  # TODO:


def get_col_row_iterator_from_data_records(array):  # generator
    for item in np.nditer(array):  # , flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.right_shift(np.bitwise_and(item, 0x0001FF00), 8)
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1)


def get_row_col_iterator_from_data_records(array):  # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), np.right_shift(np.bitwise_and(item, 0x00FE0000), 17)
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1), np.right_shift(np.bitwise_and(item, 0x00FE0000), 17)


def get_col_row_tot_iterator_from_data_records(array):  # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), np.right_shift(np.bitwise_and(item, 0x000000F0), 4)  # col, row, ToT1
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.right_shift(np.bitwise_and(item, 0x00FE0000), 17), np.add(np.right_shift(np.bitwise_and(item, 0x0001FF00), 8), 1), np.bitwise_and(item, 0x0000000F)  # col, row+1, ToT2


def get_tot_iterator_from_data_records(array):  # generator
    for item in np.nditer(array, flags=['multi_index']):
        yield np.right_shift(np.bitwise_and(item, 0x000000F0), 4)  # ToT1
        if np.not_equal(np.bitwise_and(item, 0x0000000F), 15):
            yield np.bitwise_and(item, 0x0000000F)  # ToT2


def build_events_from_raw_data(array):
    idx = np.where(is_trigger_word(array))[-1]
    if idx.shape[0] == 0:
        return [array]
    else:
        return np.split(array, idx)


def interpret_pixel_data(data, dc, pixel_array, invert=True):
    '''Takes the pixel raw data and interprets them. This includes consistency checks and pixel/data matching.
    The data has to come from one double column only but can have more than one pixel bit (e.g. TDAC = 5 bit)

    Parameters
    ----------
    data : numpy.ndarray
        The raw data words
    dc : int
        The double column where the data is from.
    pixel_array : numpy.ma.ndarray
        The masked numpy.ndarrays to be filled. The masked is set to zero for pixels with valid data.
    invert : boolean
        Invert the read pixel data.
    '''

    # data validity cut, VR has to follow an AR
    index_value = np.where(is_address_record(data))[0] + 1  # assume value record follows address record
    index_value = index_value[is_value_record(data[index_value])]  # delete all non value records
    index_address = index_value - 1  # calculate address record indices that are followed by an value record

    # create the pixel address/value arrays
    address = get_address_record_address(data[index_address])
    value = get_value_record(data[index_address + 1])

    # split array for each bit in pixel data, split is done on decreasing address values
    address_split = np.array_split(address, np.where(np.diff(address.astype(np.int32)) < 0)[0] + 1)
    value_split = np.array_split(value, np.where(np.diff(address.astype(np.int32)) < 0)[0] + 1)

    if len(address_split) > 5:
        raise NotImplementedError('Only the data from one double column can be interpreted at once!')

    mask = np.empty_like(pixel_array.data)  # BUG in numpy: pixel_array is de-masked if not .data is used
    mask[:] = len(address_split)

    for bit, (bit_address, bit_value) in enumerate(zip(address_split, value_split)):  # loop over all bits of the pixel data
        # error output, pixel data is often corrupt for FE-I4A
        if len(bit_address) == 0:
            logging.warning('No pixel data')
            continue
        if len(bit_address) != 42:
            logging.warning('Some pixel data missing')
        if (np.any(bit_address > 672)):
            RuntimeError('Pixel data corrupt')
        # set pixel that occurred in the data stream
        pixel = []
        for i in bit_address:
            pixel.extend(range(i - 15, i + 1))
        pixel = np.array(pixel)

        # create bit set array
        value_new = bit_value.view(np.uint8)  # interpret 32 bit numpy array as uint8 to be able to use bit unpacking; byte unpacking is not supported yet
        if invert:
            value_new = np.invert(value_new)  # read back values are inverted
        value_new = np.insert(value_new[::4], np.arange(len(value_new[1::4])), value_new[1::4])  # delete 0 padding
        value_bit = np.unpackbits(value_new, axis=0)

        if len(address_split) == 5:  # detect TDAC data, here the bit order is flipped
            bit_set = len(address_split) - bit - 1
        else:
            bit_set = bit

        pixel_array.data[dc * 2, pixel[pixel >= 336] - 336] = np.bitwise_or(pixel_array.data[dc * 2, pixel[pixel >= 336] - 336], np.left_shift(value_bit[pixel >= 336], bit_set))
        pixel_array.data[dc * 2 + 1, pixel[pixel < 336]] = np.bitwise_or(pixel_array.data[dc * 2 + 1, pixel[pixel < 336]], np.left_shift(value_bit[pixel < 336], bit_set)[::-1])

        mask[dc * 2, pixel[pixel >= 336] - 336] = mask[dc * 2, pixel[pixel >= 336] - 336] - 1
        mask[dc * 2 + 1, pixel[pixel < 336]] = mask[dc * 2 + 1, pixel[pixel < 336]] - 1

    pixel_array.mask[np.equal(mask, 0)] = False
