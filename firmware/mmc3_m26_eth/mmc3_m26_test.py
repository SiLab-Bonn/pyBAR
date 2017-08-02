# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import time

from basil.dut import Dut

cnfg_yaml = """
transfer_layer:
  - name  : ETH
    type  : SiTcp
    init:
        ip : "192.168.10.16"
        udp_port : 4660
        tcp_port : 24
        tcp_connection : True

hw_drivers:
  - name      : TRIGGER_FEI4
    type      : tlu
    interface : ETH
    base_addr : 0x8200

  - name      : CMD_FEI4
    type      : cmd_seq
    interface : ETH
    base_addr : 0x0000

  - name      : M26_RX1
    type      : m26_rx
    interface : ETH
    base_addr : 0xa000

  - name      : M26_RX2
    type      : m26_rx
    interface : ETH
    base_addr : 0xa010

  - name      : M26_RX3
    type      : m26_rx
    interface : ETH
    base_addr : 0xa020

  - name      : M26_RX4
    type      : m26_rx
    interface : ETH
    base_addr : 0xa030

  - name      : M26_RX5
    type      : m26_rx
    interface : ETH
    base_addr : 0xa040

  - name      : M26_RX6
    type      : m26_rx
    interface : ETH
    base_addr : 0xa050

  - name      : FEI4_RX
    type      : fei4_rx
    interface : ETH
    base_addr : 0x8600

  - name      : SITCP_FIFO
    type      : sitcp_fifo
    interface : ETH

  - name      : TDC_FEI4
    type      : tdc_s3
    interface : ETH
    base_addr : 0x8700
"""

dut = Dut(cnfg_yaml)
dut.init()

print 'Resetting Mimosa26 receivers'
map(lambda channel: channel.reset(), self.dut.get_modules('m26_rx'))

print 'FIFO size', dut['SITCP_FIFO'].get_FIFO_SIZE()

for channel in self.dut.get_modules('m26_rx'):
    channel["EN"] = True

time.sleep(0.01)

for channel in self.dut.get_modules('m26_rx'):
    channel["EN"] = False
    print "Lost count", channel["LOST_COUNT"], "channel name", channel.name

print 'FIFO size', dut['SITCP_FIFO'].get_FIFO_SIZE()

ret = dut['SITCP_FIFO'].get_data()
for i, r in enumerate(ret):
    if i > 1000 and i < 1100:
        print i, hex(r), 'id', (r & 0x00F00000) >>20, 'start', (r & 0x00010000) >> 16, 'data', hex(r & 0x000FFFFF)

# DATA FORMAT
# HEADER(2bit=0x20) + PLANEID(4bit) + 3'b000 + FRAME_START(1bit) + DATA(16bit)
