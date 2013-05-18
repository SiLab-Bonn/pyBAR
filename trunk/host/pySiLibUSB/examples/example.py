
import SiLibUSB

sidev = SiLibUSB.SiUSBDevice()

#boards = SiLibUSB.GetUSBBoards()
#for b in boards:
#    print "BoardId: " +str(b.GetBoardId())
#sidev = boards[0]

print '   This is test!'
print "FWVersion: " + str(sidev.GetFWVersion())
#print "Name: " + str(sidev.GetName())
#print "BoardId: " +str(sidev.GetBoardId())


#

#sidev.WriteExternal(0x0000, [0x66])
#sidev.WriteExternal(0x0001, [0x64])
#sidev.WriteExternal(0x1000, [4])
#sidev.WriteExternal(0x8100, [8])
#sidev.WriteExternal(0x8200, [16])

sidev.WriteExternal(0x0000, [0xa0])
sidev.WriteExternal(0x8000-1, [0xb0])

sidev.WriteExternal(0x8000, [0xa1])
sidev.WriteExternal(0x8100-1, [0xb1])

sidev.WriteExternal(0x8100, [0xa2])
sidev.WriteExternal(0x8200-1, [0xb2])

sidev.WriteExternal(0x8200, [0xa3])
sidev.WriteExternal(0x8300-1, [0xb3])


sidev.WriteExternal(0x0003, [150])
sidev.WriteExternal(0x0008, range(16))
sidev.WriteExternal(0x0008, [0xaa,0x55,0xaa,0x55,0xff])
sidev.WriteExternal(0x0001, [0]) #start

print sidev.ReadExternal(0x0000, 16)
