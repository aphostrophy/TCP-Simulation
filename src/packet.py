import struct
import random
import enum
import array

class Flags(enum.Enum):
  SYN = 0b00000010
  ACK = 0b00010000
  FIN = 0b00000001
  DAT = 0b00000000

class Packet():
    def __init__(self, seq_num, ack_num, flags, metadata, include_metadata):
        self.seq_num = seq_num
        self.ack_num = ack_num
        self.flags = flags
        self.metadata = metadata
        self.include_metadata = include_metadata

    def checksum(self, data):
        if len(data) % 2 != 0:
            data += b'\0'

        res = sum(array.array("H", data))
        res = (res >> 16) + (res & 0xffff)
        res += res >> 16

        return (~res) & 0xffff

    def build(self, data=None):
      if(data==None):
        packet = struct.pack(
            '!IIBB1024s1024s32768s',
            self.seq_num,
            self.ack_num,
            self.flags,
            0,
            b'',
            b'',
            b''
        )
      else:
        if(self.include_metadata):
          file_name = self.metadata[0].split('/')[-1]
          packet = struct.pack(
              '!IIBB1024s1024s32768s',
              self.seq_num,
              self.ack_num,
              self.flags,
              0,
              file_name.encode('utf-8'),
              self.metadata[1].encode('utf-8'),
              data
          )
        else:
          packet = struct.pack(
              '!IIBB1024s1024s32768s',
              self.seq_num,
              self.ack_num,
              self.flags,
              0,
              b'',
              b'',
              data
          )
      chksum = self.checksum(packet)
      packet = packet[:10] + struct.pack('H', chksum) + packet[10:]
      return packet