import sys
from server import Server

if __name__ == '__main__':
  port = int(sys.argv[1])
  file_path = sys.argv[2]
  is_multi_threaded = int(sys.argv[3])

  server = Server(port, is_multi_threaded, file_path)
  server.listen()