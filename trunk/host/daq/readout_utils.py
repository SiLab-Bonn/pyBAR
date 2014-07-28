import logging
import numpy as np
import readout

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] (%(threadName)-10s) %(message)s")


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
    index_value = np.where(readout.is_address_record(data))[0] + 1  # assume value record follows address record
    index_value = index_value[readout.is_value_record(data[index_value])]  # delete all non value records
    index_address = index_value - 1  # calculate address record indices that are followed by an value record

    # create the pixel address/value arrays
    address = readout.get_address_record_address(data[index_address])
    value = readout.get_value_record(data[index_address + 1])

    # split array for each bit in pixel data, split is done on decreasing address values
    address_split = np.array_split(address, np.where(np.diff(address.astype(np.int32)) < 0)[0] + 1)
    value_split = np.array_split(value, np.where(np.diff(address.astype(np.int32)) < 0)[0] + 1)

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
