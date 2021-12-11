#!/usr/bin/env python3
from file_manager import FileReader, FileWriter

if __name__ == '__main__':
  reader = FileReader('./sender/milk.jpg',32768)
  writer = FileWriter('./receiver/milk.jpg')
  chunk = reader.read()
  while(chunk):
    writer.write(chunk)
    chunk = reader.read()

  print(reader.EOF())
  writer.close()
  reader.close()