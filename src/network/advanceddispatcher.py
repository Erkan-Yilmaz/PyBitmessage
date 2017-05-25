import Queue
import time

import asyncore_pollchoose as asyncore
from bmconfigparser import BMConfigParser

class AdvancedDispatcher(asyncore.dispatcher):
    _buf_len = 2097152 # 2MB

    def __init__(self, sock=None):
        if not hasattr(self, '_map'):
            asyncore.dispatcher.__init__(self, sock)
        self.read_buf = b""
        self.write_buf = b""
        self.writeQueue = Queue.Queue()
        self.receiveQueue = Queue.Queue()
        self.state = "init"
        self.lastTx = time.time()
        self.sentBytes = 0
        self.receivedBytes = 0

    def slice_write_buf(self, length=0):
        if length > 0:
            self.write_buf = self.write_buf[length:]

    def slice_read_buf(self, length=0):
        if length > 0:
            self.read_buf = self.read_buf[length:]

    def read_buf_sufficient(self, length=0):
        if len(self.read_buf) < length:
            return False
        else:
            return True

    def process(self):
        if self.state not in ["init", "tls_handshake"] and len(self.read_buf) == 0:
            return
        while True:
            try:
#                print "Trying to handle state \"%s\"" % (self.state)
                if getattr(self, "state_" + str(self.state))() is False:
                    break
            except AttributeError:
                # missing state
                raise

    def set_state(self, state, length=0):
        self.slice_read_buf(length)
        self.state = state

    def writable(self):
        return self.connecting or len(self.write_buf) > 0 or not self.writeQueue.empty()

    def readable(self):
        return self.connecting or len(self.read_buf) < AdvancedDispatcher._buf_len

    def handle_read(self):
        self.lastTx = time.time()
        if asyncore.maxDownloadRate > 0:
            newData = self.recv(asyncore.downloadChunk)
            asyncore.downloadBucket -= len(newData)
        else:
            newData = self.recv(AdvancedDispatcher._buf_len)
        self.receivedBytes += len(newData)
        asyncore.updateReceived(len(newData))
        self.read_buf += newData
        self.process()

    def handle_write(self):
        self.lastTx = time.time()
        if asyncore.maxUploadRate > 0:
            bufSize = asyncore.uploadChunk
        else:
            bufSize = self._buf_len
        while len(self.write_buf) < bufSize:
            try:
                self.write_buf += self.writeQueue.get(False)
            except Queue.Empty:
                break
        if len(self.write_buf) > 0:
            written = self.send(self.write_buf[0:bufSize])
            asyncore.uploadBucket -= written
            asyncore.updateSent(written)
            self.sentBytes += written
            self.slice_write_buf(written)

    def handle_connect(self):
        self.lastTx = time.time()
        self.process()

    def state_close(self):
        pass

    def close(self):
        self.read_buf = b""
        self.write_buf = b""
        self.state = "shutdown"
        asyncore.dispatcher.close(self)
