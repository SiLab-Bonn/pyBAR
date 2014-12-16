#-------------------------------------------------------------------------
#    Title   : pySiLibUSB based on C++ SiLibUsb by HK
#    Company : SILAB, Phys. Inst Bonn
#    Authors : Tomasz Hemperek <hemperek@uni-bonn.de>, Jens Janssen <janssen@physik.uni-bonn.de>
#--------------------------------------------------------------------------------------
#    License : You are free to use this source files for your own development as long
#    as it stays in a public research context. You are not allowed to use it
#    for commercial purpose. You must put this header with
#    authors names in all development based on this library.
#--------------------------------------------------------------------------------------

r"""SiLibUSB - SILAB USB Device Application Programming Interface

Based on PyUsb [http://sourceforge.net/apps/trac/pyusb/]

HISTORY:
0.1:
- initial release
0.1.1:
- added version attribute to module
0.1.2:
- changed __init__
- added board_id, board_name and fw_version property, removed self.identifier
- added factory function from_board_id()
- added dispose() method
- removed GetBoardId() from __init__, since it leads to resource errors (when already in use)
- detach kernel driver if necessary (POSIX only)
0.1.3:
- code cleanup
- added XilinxAlreadyLoaded()
0.1.4:
- fix from_board_id() method
0.1.5:
- fix non-numerical characters
0.1.6:
- fix detaching kernel driver only in Linux (not supported in OSX)
0.1.7:
- added __repr__
0.2.0:
- buffering board ID and name to avoid freezing of some USBpix card under Windows operating system
  (reading EEPROM twice and programming the FPGA firmware will freeze the board)
- added more functionality to read out Xilinx configuration byte
0.2.1:
- reverting changes concerning reading EEPROM (fix is done in FPGA firmware)
TODO:
- add exception on misuse
"""

__version__ = '0.2.1'
__version_info__ = (tuple([int(num) for num in __version__.split('.')]), 'final', 0)

# set debugging options for pyUSB
#import os
#os.environ['PYUSB_DEBUG_LEVEL'] = 'debug'
#os.environ['PYUSB_DEBUG'] = 'debug'

import usb.core
import usb.util
import array
# import thread
from threading import Lock
# from multiprocessing import RLock
import struct
import time
import os
import platform
# import sys


class SiUSBDevice(object):

    SUR_CONTROL_PIPE = 0x01  # 0x01 write EP1
    SUR_DATA_IN_PIPE = 0x81  # 0x81 read  EP1
    SUR_DATA_OUT_PIPE = 0x01  # 0x01 write  EP1

    SUR_DATA_FASTOUT_PIPE = 0x02  # 0x02 write EP2
    SUR_DATA_FASTIN_PIPE = 0x86  # 0x86 read EP6

    SUR_EP1_RD = {'address': 0x81, 'maxTransferSize': 0xffff, 'maxPacketSize': 64}
    SUR_EP1_WR = {'address': 0x01, 'maxTransferSize': 0x8fff, 'maxPacketSize': 64}  # why? 0x8fff exactly 0xa0ff?
    SUR_EP2_WR = {'address': 0x02, 'maxTransferSize': 0xf000, 'maxPacketSize': 0xf000}
#    SUR_EP2_WR = {'address': 0x02, 'maxTransferSize': 2 ** 21, 'maxPacketSize': 2 ** 21}
    SUR_EP6_RD = {'address': 0x86, 'maxTransferSize': 0xf000, 'maxPacketSize': 0xf000}
#    SUR_EP6_RD = {'address': 0x86, 'maxTransferSize': 2 ** 21, 'maxPacketSize': 2 ** 21}

    SUR_TYPE_LOOP = {'id': 0, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_8051 = {'id': 1, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_XILINX = {'id': 2, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_EXTERNAL = {'id': 3, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_I2C = {'id': 5, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_EEPROM = {'id': 10, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_FWVER = {'id': 15, 'ep_read': SUR_EP1_RD, 'ep_write': SUR_EP1_WR}
    SUR_TYPE_GPIFBLOCK = {'id': 17, 'ep_read': SUR_EP6_RD, 'ep_write': SUR_EP2_WR}

    SUR_DIR_OUT = 0x00
    SUR_DIR_IN = 0x01

    EEPROM_OFFSET_ADDR = 0x3000
    EEPROM_MFG_ADDR = (EEPROM_OFFSET_ADDR)
    EEPROM_MFG_SIZE = 21
    EEPROM_NAME_ADDR = (EEPROM_MFG_ADDR + EEPROM_MFG_SIZE)
    EEPROM_NAME_SIZE = 21
    EEPROM_ID_ADDR = (EEPROM_NAME_ADDR + EEPROM_NAME_SIZE)
    EEPROM_ID_SIZE = 5
    EEPROM_LIAC_ADDR = (EEPROM_ID_ADDR + EEPROM_ID_SIZE)

    PORTACFG_FX = 0xE670
    IOA_FX = 0x80
    OEA_FX = 0xB2

    # Xilinx configuration
    XP_CS1_FX = 0x10  # port A, bit 4
    XP_RDWR_FX = 0x08  # port A, bit 3
    XP_BUSY_FX = 0x04  # port A, bit 2
    XP_PROG_FX = 0x02  # port A, bit 1
    XP_DONE_FX = 0x01  # port A, bit 0

    xp_cs1 = XP_CS1_FX
    xp_rdwr = XP_RDWR_FX
    xp_busy = XP_BUSY_FX
    xp_prog = XP_PROG_FX
    xp_done = XP_DONE_FX

    # compatible usb devices
    vendor_id = 0x5312
    product_id = 0x0200
    usb = 2
    
    def __init__(self, device=None):

        # import usb.backend.libusb0 as libusb0
        # backend_usb0 = libusb0.get_backend()
        # self.dev = usb.core.find( find_all=False, backend = backend_usb0, idVendor=0x5312, idProduct=0x0200)

        if device is None:
            self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.dev is None:
                raise ValueError('No device found')
        else:
            if isinstance(device, usb.core.Device):
                self.dev = device
                if self.dev.idVendor != self.vendor_id or self.dev.idProduct != self.product_id:
                    raise ValueError('Device has wrong vendor/product ID')
            else:
                raise ValueError('Device has wrong type')

        if platform.system() == 'Linux' and self.dev.is_kernel_driver_active(0) is True:
            # detach kernel driver
            self.dev.detach_kernel_driver(0)

        self.dev.set_configuration()
        #print self.dev._get_full_descriptor_str()
        #if self.dev.bcdUSB == 0x300 :
        if self.dev.bMaxPacketSize0 == 0x09 :
            self.usb = 3
            
        print self.usb
        
        self.lock = Lock()

    def __repr__(self):
        return '%s' % filter(type(self.board_id).isdigit, self.board_id)

    @classmethod
    def from_board_id(cls, board_id):
        devs = usb.core.find(find_all=True, idVendor=cls.vendor_id, idProduct=cls.product_id)
        if devs is None:
            raise ValueError('No device found')

        boards = []
        for dev in devs:
            board = cls(device=dev)
            try:
                curr_board_id = board.board_id
                if filter(type(curr_board_id).isdigit, curr_board_id) == str(board_id):
                    boards.append(board)
            except usb.core.USBError:
                pass
            board.dispose()
        if not boards:
            raise ValueError('No device found with board ID %s' % str(board_id))
        elif len(boards) > 1:
            raise ValueError('Found %d devices with board ID %s' % (len(boards), str(board_id)))
        else:
            return boards[0]

    @property
    def board_id(self):
        return self.GetBoardId()

    @property
    def board_name(self):
        return self.GetName()

    @property
    def fw_version(self):
        return self.GetFWVersion()

    def WriteExternal(self, address, data):
        if(self.usb == 3):
            self._write(self.SUR_TYPE_GPIFBLOCK, address, data)
        else:
            self._write(self.SUR_TYPE_EXTERNAL, address, data)

    def ReadExternal(self, address, size):
        if(self.usb == 3):
            return self._read(self.SUR_TYPE_GPIFBLOCK, address, size)
        else:
            return self._read(self.SUR_TYPE_EXTERNAL, address, size)

    def FastBlockWrite(self, data):
        self._write(self.SUR_TYPE_GPIFBLOCK, 0, data)

    def FastBlockRead(self, size):
        return self._read(self.SUR_TYPE_GPIFBLOCK, 0, size)

    def WriteEEPROM(self, address, data):
        return self._write(self.SUR_TYPE_EEPROM, address, data)

    def ReadEEPROM(self, address, size):
        return self._read(self.SUR_TYPE_EEPROM, address, size)

    def WriteI2C(self, address, data):
        self._write(self.SUR_TYPE_I2C, address, data)

    def ReadI2C(self, address, size):
        return self._read(self.SUR_TYPE_I2C, address, size)

    def _write(self, stype, addr, data):
        with self.lock:
            buff = array.array('B', data)
            size = buff.buffer_info()[1]

            if size > stype['ep_write']['maxTransferSize']:
                chunks = lambda l, n: [l[x: x + n] for x in xrange(0, len(l), n)]
                new_addr = addr
                for req in chunks(buff.tolist(), stype['ep_write']['maxTransferSize']):
                    self._write_single(stype, addr, array.array('B', req))  # BUG: addr should be new_addr but it does not work
                    new_addr = new_addr + len(req)
            else:
                self._write_single(stype, addr, buff)

    def _write_single(self, stype, addr, data):
        size = data.buffer_info()[1]
        if size > stype['ep_write']['maxPacketSize']:
            self._write_sur(stype, self.SUR_DIR_OUT, addr, size)
            i = 0
            chunks = lambda l, n: [l[x: x + n] for x in xrange(0, len(l), n)]
            for req in chunks(data, stype['ep_write']['maxPacketSize']):
                self.dev.write(stype['ep_write']['address'], req.tostring())
                i += 1
        else:
            self._write_sur(stype, self.SUR_DIR_OUT, addr, size)
            if( self.usb == 3):
                mod = (len(data) % 4)
                padding = 4 - mod if mod else 0
                data.extend( [0] * padding )
                
            self.dev.write(stype['ep_write']['address'], data.tostring())

    def _read(self, stype, addr, size):
        with self.lock:
            ret = array.array('B')
            if size > stype['ep_read']['maxTransferSize']:
                new_addr = addr
                new_size = stype['ep_read']['maxTransferSize']
                while new_size < size:
                    ret += self._read_single(stype, new_addr, stype['ep_read']['maxTransferSize'])
                    new_addr = addr + new_size
                    new_size = new_size + stype['ep_read']['maxTransferSize']

                ret += self._read_single(stype, new_addr - stype['ep_read']['maxTransferSize'], size + stype['ep_read']['maxTransferSize'] - new_size)

            else:
                ret += self._read_single(stype, addr, size)

        return ret

    def _read_single(self, stype, addr, size):
        if size == 0:
            return array.array('B')
        self._write_sur(stype, self.SUR_DIR_IN, addr, size)

        ret = array.array('B')

        if(self.usb == 3):
            size_padded = size if size % 4 ==0 else ((size / 4 ) +1)*4
        else:
            size_padded = size
            
        if size_padded > stype['ep_read']['maxPacketSize']:
            new_size = stype['ep_read']['maxPacketSize']
            while new_size < size_padded:
                ret += self.dev.read(stype['ep_read']['address'], stype['ep_read']['maxPacketSize'])
                new_size = new_size + stype['ep_read']['maxPacketSize']

            ret += self.dev.read(stype['ep_read']['address'],  size_padded + stype['ep_read']['maxPacketSize'] - new_size)
        else:
            ret += self.dev.read(stype['ep_read']['address'], size_padded)
                
        
        return ret[0:size]

    def _write_sur(self, stype, direction, addres, size):
        a_size = array.array('B', struct.pack('I', size))
        a_size.byteswap()
        a_addr = array.array('B', struct.pack('I', addres))
        a_addr.byteswap()
        ar = array.array('B', [stype['id'], direction]) + a_addr + a_size
        self.dev.write(self.SUR_CONTROL_PIPE, ar)

    def GetFWVersion(self):
        ret = self._read(self.SUR_TYPE_FWVER, 0, 2)
        return ret.tostring()

    def GetName(self):
        ret = self.ReadEEPROM(self.EEPROM_NAME_ADDR, self.EEPROM_NAME_SIZE)
        return ret[1:1 + ret[0]].tostring()

    def SetName(self, name):
        raise NotImplementedError()

    def GetBoardId(self):
        ret = self.ReadEEPROM(self.EEPROM_ID_ADDR, self.EEPROM_ID_SIZE)
        # return ret[1:1+ret[0]].tostring()
        return ret[1:-1].tostring()

    def SetBoardId(self, board_id):
        raise NotImplementedError()

    def _get_end_point(self, pipe):
        cfg = self.dev.get_active_configuration()
        intf = usb.util.find_descriptor(cfg, bInterfaceNumber=0, bAlternateSetting=0)
        ep = usb.util.find_descriptor(intf, bEndpointAddress=pipe)
        return ep

    def _Read8051(self, address, size):
        return self._read(self.SUR_TYPE_8051, address, size)

    def _Write8051(self, address, data):
        self._write(self.SUR_TYPE_8051, address, data)

    def _read_bit_file_section(self, f):
        letter = f.read(1)
        rlen = f.read(2)
        a = array.array('B', rlen)
        alen = a[0] * 256 + a[1]
        return letter, f.read(alen)

    def _read_bit_file(self, bit_file_name):
        # print bit_file_name
        with open(bit_file_name, "rb") as f:
            head13 = array.array('B', f.read(13))
            if head13.tolist() != [0, 9, 15, 240, 15, 240, 15, 240, 15, 240, 0, 0, 1]:
                raise ValueError('Wrong Bitstream File Header')

            ret = dict()

            ret["File Name"] = self._read_bit_file_section(f)[1]
            ret["Part Name"] = self._read_bit_file_section(f)[1]
            ret["File Creation Data"] = self._read_bit_file_section(f)[1]
            ret["File Creation Time"] = self._read_bit_file_section(f)[1]

            if f.read(1) != 'e':
                raise ValueError('Wrong Bitstream Section')

            c = array.array('B', f.read(4))
            c.byteswap()
            # bitstream_len = struct.unpack("I", c)

            # bitstream = f.read(bitstream_len[0])
            bitstream_len = c[0] * (2 ** 24) + c[1] * (2 ** 16) + c[2] * (2 ** 8) + c[3]

            bitstream = f.read(bitstream_len)

            bs = array.array('B', bitstream)
            bitstream_swap = ''
            lsbits = lambda b: (b * 0x0202020202 & 0x010884422010) % 1023
            for b in bs:
                bitstream_swap += chr(lsbits(b))

            ret["Bitstream"] = bitstream_swap
            return ret

    def InitXilinxConfPort(self):
        portreg = self._Read8051(self.PORTACFG_FX, 1)[0]
        portreg &= ~self.xp_rdwr
        portreg &= ~self.xp_busy
        portreg &= ~self.xp_prog
        portreg &= ~self.xp_done
        portreg &= ~self.xp_cs1
        self._Write8051(self.PORTACFG_FX, [portreg])

        portreg = self._Read8051(self.OEA_FX, 1)[0]
        portreg |= self.xp_rdwr  # /* write,  OE = 1 */
        portreg &= ~self.xp_busy  # /* read,  OE = 0 */
        portreg |= self.xp_prog  # /* write, OE = 1 */
        portreg &= ~self.xp_done  # /* read,  OE = 0 */
        portreg |= self.xp_cs1  # /* write, OE = 1 */
        self._Write8051(self.OEA_FX, [portreg])

    def DownloadXilinx(self, filename):
        r"""Configure FPGA.

        The filename name of the bitstream file (*.bin) or (*.bit)
        During bit generation Start-Up Clock has to be set to CCLK.
        To create *.bin file from *.bit file use impact or: "promgen -u 0 filename.bit -p bin -w"
        The possible return values are True or False.
        """

        bitstream = array.array('B')

        extension = os.path.splitext(filename)[1]
        if extension == '.bin':
            with open(filename, "rb") as f:
                fsize = os.path.getsize(filename)
                bitstream.fromfile(f, fsize)
        elif extension == '.bit':
            bitstream = array.array('B', self._read_bit_file(filename)["Bitstream"])
        else:
            raise ValueError('Wrong File Extension')

        self.InitXilinxConfPort()

        conf_reg = 0

        # /* enable write */
        conf_reg |= self.xp_cs1  # // cs_b = 1
        conf_reg &= ~self.xp_rdwr  # // write_b = 0
        conf_reg |= self.xp_prog  # // prog_b = 1
        self.SetXilinxConfByte((conf_reg,))

        # /* prog_b = 0 assert for at least 500ns */
        conf_reg |= self.xp_cs1  # // cs_b = 1
        conf_reg &= ~self.xp_rdwr  # // write_b = 0
        conf_reg &= ~self.xp_prog  # // prog_b = 0
        self.SetXilinxConfByte((conf_reg,))

        # /* prog_b = 1 */
        conf_reg |= self.xp_cs1  # // cs_b = 1
        conf_reg &= ~self.xp_rdwr  # // write_b = 0
        conf_reg |= self.xp_prog  # // prog_b = 1
        self.SetXilinxConfByte((conf_reg,))

        # /* cs_b = 0 */
        conf_reg &= ~self.xp_cs1  # // cs_b = 0
        conf_reg &= ~self.xp_rdwr  # // write_b = 0
        conf_reg |= self.xp_prog  # // prog_b = 1
        self.SetXilinxConfByte((conf_reg,))

        self._write(self.SUR_TYPE_XILINX, 0, bitstream[0:])

        self._write(self.SUR_TYPE_XILINX, 0, (0, 0, 0, 0, 0, 0, 0, 0))  # eight extra clock to enable start-up

        time.sleep(0.1)

        # /* cs_b = 1 */
        conf_reg |= self.xp_cs1  # // cs_b = 1
        conf_reg &= ~self.xp_rdwr  # // write_b = 0
        conf_reg |= self.xp_prog  # // prog_b = 1
        self.SetXilinxConfByte((conf_reg,))

        # // write_b = 1 (default condition)
        conf_reg |= self.xp_cs1  # // cs_b = 1
        conf_reg |= self.xp_rdwr  # // write_b = 1
        conf_reg |= self.xp_prog  # // prog_b = 1
        self.SetXilinxConfByte((conf_reg,))

        return self.GetXilinxConfPin(self.xp_done)

    def SetXilinxConfByte(self, reg):
        self._Write8051(self.IOA_FX, reg)

    def GetXilinxConfByte(self):
        return self._Read8051(self.IOA_FX, 1)[0]

    def SetXilinxConfPin(self, pin, value):
        reg = self.GetXilinxConfByte()
        if value:
            reg |= pin
        else:
            reg &= ~pin
        self.SetXilinxConfByte((reg,))

    def GetXilinxConfPin(self, pin):
        reg = self.GetXilinxConfByte()
        return bool(reg & pin)

    def XilinxAlreadyLoaded(self):
        self.InitXilinxConfPort()
        return self.GetXilinxConfPin(self.xp_done)

    def dispose(self):
        '''Release internal resources allocated by the object.

        Sometimes you need to provide deterministic resources
        freeing, for example to allow another application to
        talk to the device. As Python does not provide deterministic
        destruction, this function releases all internal resources
        allocated by the device, like device handle and interface
        policy.

        After calling this function, you can continue using the device
        object normally. If the resources will be necessary again, it
        will allocate them automatically.
        '''
        usb.util.dispose_resources(self.dev)

    def __del__(self):
        if os.name == 'posix':
            if self.dev is not None:
                self.dev.reset()


def GetUSBBoards():
    devs = usb.core.find(find_all=True, idVendor=0x5312, idProduct=0x0200)
    if devs is None:
        return None
    boards = [SiUSBDevice(device=dev) for dev in devs]
    return boards


def GetUSBDevices():
    devs = usb.core.find(find_all=True, idVendor=0x5312, idProduct=0x0200)
    if devs is None:
        return None
    return devs


if __name__ == "__main__":
    boards = GetUSBBoards()
    for board in boards:
        print "Name:", board.GetName()
        print "BoardId:", board.GetBoardId()
        print "FWVersion:", board.GetFWVersion()
