import sys
from client import Client

if __name__ == '__main__':
  if(len(sys.argv) > 3):
    print('Invalid arguments!')
    exit()

  port = int(sys.argv[1])
  if(len(sys.argv) == 3):
    file_path = str(sys.argv[2])
  else:
    file_path = None
  client = Client(server_port=port, file_path=file_path)
  client.broadcast()
  client.listen()