import io
DATA_CHUNK_LENGTH = 32768

'''
  Server Side File Writer
'''
class FileReader():
  def __init__(self,file_path, step):
    self.file_buffer = open(file=file_path,mode= 'rb')
    self.offset = 0
    self.step = step

  def read(self):
    offset = max(self.offset,0)
    self.file_buffer.seek(offset)
    self.offset += self.step
    return self.file_buffer.read(self.step)

  def EOF(self):
    offset = max(self.offset,0)
    self.file_buffer.seek(offset)
    return not self.file_buffer.read(self.step)

  def go_back_n(self,n):
    self.offset -= self.step * n

  def close(self):
    self.file_buffer.close()




'''
  Client Side File Writer
'''
class FileWriter():
  def __init__(self,file_path):
    self.file_path = file_path
    self.file_buffer = open(file=file_path,mode='ab+')

  def write(self,data):
    self.file_buffer.write(data)

  

  def close(self):
    self.file_buffer.close()
    self.file_buffer = open(file=self.file_path, mode='r+b')
    self.file_buffer.seek(-DATA_CHUNK_LENGTH, io.SEEK_END)
    last_chunk = self.file_buffer.read(DATA_CHUNK_LENGTH)
    last_chunk = last_chunk.strip(b'\0')
    self.file_buffer.seek(-DATA_CHUNK_LENGTH, io.SEEK_END)
    self.file_buffer.truncate()
    self.file_buffer.close()
    self.file_buffer = open(file=self.file_path, mode='ab+')
    self.file_buffer.write(last_chunk)
    self.file_buffer.close()