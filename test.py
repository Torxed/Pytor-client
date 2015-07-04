from socket import *
from threading import *
from time import sleep
import struct

class worker(Thread):
    def __init__(self, sock):
        Thread.__init__(self)
        self.sock = sock
        self.alive = 1
        self.start()

    def run(self):
        while self.alive:
            print('<<',self.sock.recv(8192))

        self.sock.close()

s = socket()
s.connect(('95.109.122.86', 37874))
w = worker(s)

# Handshake
print('Sending handshake [3]')
s.send(b'\x13BitTorrent protocol\x00\x00\x00\x00\x00\x10\x00\x05L\xcdn\x08\xbc \xf3\t1\xa2\x83"\x0bL\xf9l,M\xab\xf2-UT3220-v\x8bv-\xef\'\x10y\x9aV\xe0\x91')
sleep(3)

## Send extended message
print('Sending extended message [5]')
s.send(b'\x00\x00\x00\xa5\x14\x00d1:ei0e4:ipv44:_mzV12:complete_agoi12889e1:md11:upload_onlyi3e11:lt_donthavei7e10:ut_commenti6ee1:pi1337e4:reqqi255e1:v15:\xce\xbcTorrent 3.2.22:ypi37874e6:yourip4:.\x15fQe\x00\x00\x00\x01\x0f')
sleep(5)

print('Sending ping')
s.send(b'\x00\x00\x00\x00') # Ping
sleep(2)

print('Sending interested message')
s.send(b'\x00\x00\x00\x01' + b'\x02') # Interested (pack the length of 1 instead)
sleep(3)

print('Sending request package')
        #   type         index               begining offset           length
request = b'\x06' + b'\x00\x00\x00\x00' + b'\x00\x00\x00\x00' + b'\x00\x00\x00\x07'
s.send(struct.pack('>I', len(request)) + request) # Interested (pack the length of 1 instead)
sleep(5)

# c -> s: handshake
# s -> c: handshake (identical if torrent exists)
# c -> s: Extended message (20)
# s -> c: Extended (response Parts:[20, 5, 4])
# c -> s: PING (0000)
# c -> s: [00 00 00 01][02] Interested message
# s -> c: [00 00 00 01][01] Unchoke (meaning we can now request shit)
# c -> s: [LE NG TH 00][06] Request [IN DE X0 00][ST AR TI ND][LE NG TH 00]
# s -> c: [LE NG TH 00][07] Piece [Index-4][Offset start-4] [9:length]