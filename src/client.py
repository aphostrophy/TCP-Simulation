import os
import socket
import array
import struct
import errno
from packet import Packet, Flags

from file_manager import FileWriter


class Client():
  def __init__(self,server_port, file_path) -> None:
      self.curr_seq_num = 200
      self.next_seq_num = 200
      self.server_ip = None
      self.server_port = server_port
      self.file_path = file_path
      self.sock = None
      self.file_writer = None
      self.init_socket()

  def init_socket(self):
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    self.init_socket_port(10000)

  def init_socket_port(self,port):
    while(True):
      try:
        self.sock.bind(('',port))
        break
      except socket.error as err:
        if err.errno == errno.EADDRINUSE:
          print('Port {} is already in use'.format(port))
          port+=1
        else:
          print('Unhandled error')

  def calc_checksum(self, data):
    if len(data) % 2 == 1:
        data += "\0"
    s = sum(array.array("H", data))
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return (((s>>8)&0xff)|s<<8) & 0xffff

  def unpack(self, data):
    seq_num,ack_num,flags,_,checksum,file_name,file_extension,data = struct.unpack("!IIBBH1024s1024s32768s", data)
    return (seq_num,ack_num,flags,_,checksum,file_name,file_extension,data)
  
  def send(self, seq_num, ack_num, flags):
    packet = Packet(seq_num, ack_num, flags, None, False)
    self.sock.sendto(packet.build(),(self.server_ip,self.server_port))

  def recv(self):
    data, addr = self.sock.recvfrom(34828)
    packet = data[:10] + data[12:]

    self.server_ip = addr[0]
    self.server_port = addr[1]

    seq_num,ack_num,flags,_,checksum,file_name,file_extension,data = self.unpack(data)
    return seq_num,ack_num,flags,_,checksum,file_name,file_extension,data,packet

  def handle_handshake_request(self):
    while True:
      try:
        seq_num,ack_num,flags,_,checksum,file_name,file_extension,data,packet = self.recv()

        # check SYN
        is_SYN = flags & Flags.SYN.value == Flags.SYN.value
        # check ACK
        is_ACK = flags & Flags.ACK.value == Flags.ACK.value

        if(is_SYN):
          self.send(seq_num = self.curr_seq_num,ack_num= seq_num + 1, flags= Flags.SYN.value + Flags.ACK.value)
          print('Segment SEQ={} Sent SYN+ACK'.format(self.curr_seq_num))
        elif(is_ACK):
          if(ack_num == self.curr_seq_num + 1):
            print('Segment SEQ={} Acked'.format(self.curr_seq_num))
            self.curr_seq_num = ack_num
            print("connection established!!")
            break
      except socket.timeout:
        print('Socket timeout')
        self.close_connection()

  def close_connection(self):
    print('Closing connection...')
    self.send(seq_num=0 ,ack_num=self.next_seq_num,flags = Flags.FIN.value)
    self.file_writer.close()
    self.sock.close()
    print('Connection closed')

  def listen(self):
    print('Waiting for file transfer...')
    self.curr_seq_num = 1
    self.next_seq_num = self.curr_seq_num
    print_metadata = False
    while(True):
      seq_num,ack_num,flags,_,checksum,file_name,file_extension,data,packet = self.recv()
      file_name = file_name.decode('utf-8').replace("\0","")
      file_extension = file_extension.decode('utf-8').replace("\0","")
      port = self.sock.getsockname()[1]
      cwd = os.getcwd()

      if(self.file_path == None):
        if(file_name != '' and not(print_metadata)):
          # setting up file writer
          folder = "{}/{}".format(cwd, port)
          file_path = "{}/{}/{}{}".format(cwd, port, file_name, file_extension)
          if(not(os.path.isdir(folder))):
            os.mkdir(folder)
          self.file_writer = FileWriter(file_path)
          print("File Name: {}".format(file_name))
          print("File Extension: {}".format(file_extension))
          print_metadata = True
      else:
        self.file_writer = FileWriter(self.file_path)

      is_FIN = flags & Flags.FIN.value == Flags.FIN.value

      if is_FIN:
        self.close_connection()
        break
      else:
        if(seq_num == self.next_seq_num and (checksum + self.calc_checksum(packet) == 0xffff)): # AND IF VALID
          self.send(seq_num=0 ,ack_num=self.next_seq_num,flags = Flags.ACK.value)
          self.file_writer.write(data)
          print('[SEGMENT SEQ={}] Received, Ack sent'.format(self.next_seq_num))
          self.next_seq_num += 1
        else:
          print('[SEGMENT SEQ={}] Segment damaged. Ack prev sequence number.'.format(self.next_seq_num))
          self.send(seq_num=0, ack_num=self.next_seq_num - 1, flags= Flags.ACK.value)

  def broadcast(self):
    self.sock.sendto(b'', ('255.255.255.255',self.server_port))
    self.handle_handshake_request()
  