import os
import socket
import struct
import concurrent.futures
import threading

from packet import Packet, Flags
from file_manager import FileReader
from time import sleep

MAX_CLIENTS = 10
DATA_CHUNK_LENGTH = 32768
WINDOW_SIZE = 3
INITIAL_SOCKET_TIMEOUT = 1
MAX_ALLOWED_TIMEOUT = 5

class Server():
  def __init__(self,port, is_multi_threaded,file_path):
    self.sock = None
    self.port = port
    self.is_multi_threaded = is_multi_threaded
    self.file_path = file_path
    self.init_socket()
    self.clients = []

  def init_socket(self):
    self.sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    self.sock.bind(('',self.port))
    print('SERVER STARTED AT PORT {}...'.format(self.port))
    print('Listening to broadcast address for clients.')

  def listen(self):
    i = 0
    is_metadata = input("Would you like to send metadata? (y/n) ")
    include_metadata = is_metadata == 'y'
    if(not self.is_multi_threaded):
      while(True):
        [_,address] = self.sock.recvfrom(34828) #12 + 2048 + 32768
        self.clients.append(address)
        i+=1
        print('[!] Client ({}:{}) found'.format(address[0],address[1]))
        cont = input('[?] Listen more? (y/n) ')
        if(cont != 'y'):
          break
        if(i==MAX_CLIENTS):
          print('Maximum allowed clients reached!')
          break

      print('{} clients found:'.format(len(self.clients)))
      for idx,addr in enumerate(self.clients):
        print('{}. {}:{}'.format(idx+1,addr[0],addr[1]))

      print('Commencing file transfer')
      self.send_buffer(include_metadata)
      self.sock.close()
    else:
      port = self.port
      while(True):
        [_,address] = self.sock.recvfrom(34828) #12 + 2048 + 32768
        if(address not in self.clients):
          self.clients.append(address)
          print('[!] Client ({}:{}) found'.format(address[0],address[1]))
          port += 1
          newsocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
          newsocket.bind(('',i))
          sender = Sender(address[0],address[1],newsocket,self.file_path,include_metadata)
          t1 = threading.Thread(target=sender.start_handshake, args=())
          t1.start()

        if(i==MAX_CLIENTS):
          print('Maximum allowed clients reached!')
          break

  def send_buffer_concurrent(self, include_metadata):
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CLIENTS) as executor:
      pool = {executor.submit(Sender,addr[0],addr[1],self.sock,self.file_path,include_metadata) : addr for addr in self.clients}
      for future in concurrent.futures.as_completed(pool):
        print(future)
  
  def send_buffer(self, include_metadata):
    for addr in self.clients:
      print("Serving client ",addr[0],":",addr[1])
      sender = Sender(addr[0],addr[1],sock=self.sock, file_path=self.file_path, include_metadata=include_metadata)
      sender.start_handshake()

class Sender():
  def __init__(self,ip,port,sock: socket.SocketType, file_path, include_metadata):
    self.ip = ip
    self.port = port
    self.sock = sock
    self.curr_seq_num = 700
    self.next_seq_num = 700
    self.include_metadata = include_metadata
    self.metadata=os.path.splitext(file_path)
    self.file_reader = FileReader(file_path= file_path, step= DATA_CHUNK_LENGTH)

  def unpack(self, data):
    seq_num,ack_num,flags,_,checksum,file_name,file_extension,data  = struct.unpack("!IIBBH1024s1024s32768s", data)
    return (seq_num,ack_num,flags,_,checksum,file_name,file_extension,data )

  def send(self, seq_num, ack_num, flags, data=None):
    packet = Packet(seq_num, ack_num, flags, self.metadata, self.include_metadata)
    self.sock.sendto(packet.build(data),(self.ip, self.port))

  def close_connection(self):
    print('Closing connection...')
    self.file_reader.close()
    self.send(seq_num=self.curr_seq_num, ack_num=0, flags=Flags.FIN.value)
    i = 0
    while(True):
      try:
        seq_num,ack_num,flags,_,checksum,file_name,file_extension,data  = self.recv()
        is_FIN = flags & Flags.FIN.value == Flags.FIN.value
        if(is_FIN):
          break
        else:
          self.send(seq_num=self.curr_seq_num, ack_num=0, flags=Flags.FIN.value)
      except socket.timeout:
        i += 1
        if(i<4):
          print('retry sending FIN')
          self.send(seq_num=self.curr_seq_num, ack_num=0, flags=Flags.FIN.value)
        else:
          break

  def recv(self):
    data, _ = self.sock.recvfrom(34828)
    seq_num,ack_num,flags,_,checksum,file_name,file_extension,data = self.unpack(data)
    return seq_num,ack_num,flags,_,checksum,file_name,file_extension,data

  def start_handshake(self):  
    self.send(seq_num = self.curr_seq_num,ack_num= 0,flags= Flags.SYN.value)
    print('Segment SEQ={} Sent'.format(self.curr_seq_num))
    while True:
      try:
        seq_num,ack_num,flags,_,checksum,file_name,file_extension,data  = self.recv()

        # check SYN
        is_SYN = flags & Flags.SYN.value == Flags.SYN.value
        # check ACK
        is_ACK = flags & Flags.ACK.value == Flags.ACK.value

        if(is_SYN and is_ACK):
          if(ack_num == self.curr_seq_num + 1):
            print('Segment SEQ={} Acked'.format(self.curr_seq_num))
            self.send(seq_num = ack_num,ack_num= seq_num+1,flags= Flags.ACK.value)
            self.curr_seq_num = ack_num
            print('Segment SEQ={} Sent'.format(self.curr_seq_num))
            print("connection established")
            break
      except socket.timeout:
        print('Handshake timeout')
        break
    self.send_file()

  def go_back_n(self):
    print('Starting Go Back N Protocol with WINDOW SIZE={}'.format(WINDOW_SIZE))
    self.file_reader.go_back_n(self.next_seq_num - self.curr_seq_num)
    self.next_seq_num = self.curr_seq_num

  def send_file(self):
    print('Start sending file')
    self.curr_seq_num = 1
    self.next_seq_num = self.curr_seq_num
    timeout = INITIAL_SOCKET_TIMEOUT
    self.sock.settimeout(timeout)
    while(True):
      sleep(0.2)
      if self.next_seq_num < self.curr_seq_num + WINDOW_SIZE:
        chunk = self.file_reader.read()
        if(chunk):
          self.send(seq_num=self.next_seq_num, ack_num=0, flags= Flags.DAT.value, data=chunk)
          print('[Segment SEQ={}] Sent'.format(self.next_seq_num))
          self.next_seq_num += 1
        else:
          pass

      try:
        seq_num,ack_num,flags,_,checksum,file_name,file_extension,data = self.recv()
        # check ACK
        is_ACK = flags & Flags.ACK.value == Flags.ACK.value

        if(is_ACK):
          print('[Segment SEQ={}] Acked'.format(self.curr_seq_num))
          self.curr_seq_num = ack_num + 1
          if(self.file_reader.EOF() and self.curr_seq_num == self.next_seq_num):
            break
          else:
            timeout = INITIAL_SOCKET_TIMEOUT
            self.sock.settimeout(timeout)

      except socket.timeout:
        print('[Segment SEQ={}] NOT ACKED. SOCKET TIMEOUT or DUPLICATE ACK FOUND'.format(self.curr_seq_num))
        timeout = min(timeout * 2, MAX_ALLOWED_TIMEOUT)
        self.sock.settimeout(timeout)
        self.go_back_n()
    
    # Closing Connection
    self.close_connection()
