import struct
import os
import re
from socket import *
from collections import OrderedDict as OD
from random import randint
from select import epoll, EPOLLIN, EPOLLOUT, EPOLLHUP
from base64 import b64decode as bdec
from base64 import b64encode as benc

## == References:
#  -- * https://wiki.theory.org/BitTorrentSpecification
#  -- * http://www.libtorrent.org/extension_protocol.html
#  -- * http://www.bittorrent.org/beps/bep_0003.html
#  -- * wireshark
#  -- * qtorrent
#  -- * utorrent
#  -- * rtorrent

my_peer_id = b'-pt0001-' + os.urandom(20-8)

#coreSock = socket(AF_INET, SOCK_DGRAM)
coreSock = socket()
coreSock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
coreSock.bind(('0.0.0.0', 1337))
coreSock.setblocking(0)
coreSock.listen(1)

poll = epoll()
poll.register(coreSock.fileno(), EPOLLIN)

socks = {}

## Manual bdecoder

	# def bdecode(self, data):
	# 	print('Trying to bdecode:', [data[:10]])
	# 	key = 

	# 	if data[0] == 100: # == d
	# 		dmap = {}
	# 		data = data[1:]
	# 		while 1:
	# 			split = data.find(b':')
	# 			length = int(data[:split])
	# 			if length == 0:
	# 				key = struct.pack('b', data[split+1])
	# 			else:
	# 				key = data[split+1:split+1+length]

	# 			valstart = split+1+length
	# 			value, endpos = self.bdecode(data[valstart:]) # Tailing +1 is for the `e` that ends the message
	# 			print(key, '=', value, [endpos])
	# 			dmap[key] = value
	# 			data = data[valstart+endpos:]

	# 	elif data[0] == 105: # == i
	# 		x = data.find(b'e')
	# 		return data[1:x], x+1
	# 	elif data[0] == 108: # == l
	# 		print('l - Not yet implemented')

	# 	# d 1:e i0e4:ipv44:_mzV12:complete_agoi5663e1:md11:upload_onlyi3e11:lt_donthavei7e10:ut_commenti6ee1:pi37874e4:reqqi255e1:v15:\xce\xbcTorrent 3.4.22:ypi1337e6:yourip4:.\x15fQe
	# 	# {'e': 0, 'v': '\xce\xbcTorrent 3.4.2', 'm': {'ut_comment': 6, 'lt_donthave': 7, 'upload_only': 3}, 'reqq': 255, 'yourip': '.\x16fQ', 'p': 37874, 'ipv4': '_mzV', 'complete_ago': 5663, 'yp': 1337}


class TorrentMessage():
	def __init__(self, t, data):
		self.type = t
		self.data = data

	def tokenize(self, text, match=re.compile("([idel])|(\d+):|(-?\d+)").match):
		i = 0
		while i < len(text):
			m = match(text, i)
			if m is None: break
			s = m.group(m.lastindex)
			i = m.end()
			if m.lastindex == 2:
				yield "s"
				yield text[i:i+int(s)]
				i = i + int(s)
			else:
				yield s

	def decode_item(self, gen, token):
		if token == "i":
			# integer: "i" value "e"
			data = int(next(gen))
			if next(gen) != "e":
				raise ValueError()
		elif token == "s":
			# string: "s" value (virtual tokens)
			data = next(gen)
		elif token == "l" or token == "d":
			# container: "l" (or "d") values "e"
			data = []
			tok = next(gen)
			while tok != "e":
				data.append(self.decode_item(gen, tok))
				try:
					tok = next(gen)
				except StopIteration:
					break
			if token == "d":
				data = dict(zip(data[0::2], data[1::2]))
		else:
			raise ValueError()
		return data

	def decode(self, text):
		try:
			src = self.tokenize(text)
			data = self.decode_item(src, next(src))
			for token in src: # look for more tokens
				raise SyntaxError("trailing junk")
		except (AttributeError, ValueError, StopIteration):
			raise SyntaxError("syntax error")
		return data

	def parse(self):
		if self.type == 20:
			## Extended Message
			#- src: http://www.libtorrent.org/extension_protocol.html
			#
			# The first byte indicates the type of extended message
			# 0 - being a handshake.
			if self.data[0] == 0:
				# Handshake
				# Example recieved: d1:ei0e4:ipv44:_mzV12:complete_agoi5663e1:md11:upload_onlyi3e11:lt_donthavei7e10:ut_commenti6ee1:pi37874e4:reqqi255e1:v15:\xce\xbcTorrent 3.4.22:ypi1337e6:yourip4:.\x15fQe
				return self.decode(self.data[1:].decode('utf-8')) # No way of treating <bytes> yet, need to implement logic to handle single-byte characters as key and val.
			else:
				raise ValueError('Not yet implemented')
		elif self.type == 9:
			## "Port" message
			return struct.unpack('>H', self.data)[0]
		else:
			print('Unknown message type:', self.type)
			print('Payload:',[self.data])
			print()

def parse_transfered_bytes(bstr):

	#		46.21.102.81:1337
	
	if bstr == b'\x00\x00\x00\x00':
		pass # ping
	elif bstr[0] == 19 and bstr[1:20] == b'BitTorrent protocol':
		return b'BitTorrent protocol', bstr[21:] # 21 == <digit:1><msg:20>
	else:
		msg_length = struct.unpack('>I', bstr[:4])[0]
		if len(bstr[4:]) < msg_length:
			print('Length of "' + str([bstr[4:8]]) + '..."['+str(len(bstr[4:]))+'] is not ' + str(msg_length))
			return -1

		bstr = bstr[4:msg_length+4]

		msg_type = bstr[0]
		return TorrentMessage(msg_type, bstr[1:]).parse(), None


data_queue = {}
while True:
	events = poll.poll(1)
	for fileno, event in events:
		if event and EPOLLIN:
			if fileno == coreSock.fileno():
				ns, na = coreSock.accept()
				print('accepting',na)
				socks[ns.fileno()] = ns
				poll.register(ns.fileno(), EPOLLIN)
			else:
				if fileno in data_queue:
					data = data_queue[fileno]
					data += socks[fileno].recv(8192)
				else:
					data = socks[fileno].recv(8192)
				#print([data])
				if len(data) == 0:
					# This will hang shit yo!
					#print('Length of data was 0, continuing')
					break
				print([data])

				decoded = parse_transfered_bytes(data)
				if decoded is -1:
					if not fileno in data_queue:
						data_queue[fileno] = b''
					data_queue[fileno] += data
					continue
				else:
					if fileno in data_queue:
						del(data_queue[fileno])

				decoded, rest = decoded
				if decoded == b'BitTorrent protocol':
					majorProtocol = struct.unpack('>I', rest[:4])[0]
					protocol = struct.unpack('>I', rest[3:7])[0]
					info_hash = benc(rest[7:27])
					peer_id = rest[27:48]
					trash = rest[47:]

					print('Peer ID:', [peer_id])
					print('Protocol:', [protocol])
					print('Info hash:', [info_hash])
					print('Trash?', [trash])

					response = b''
					protMsg = b'BitTorrent protocol'
					response += struct.pack('b', len(protMsg))
					response += protMsg
					response += struct.pack('>I', 0) # majorProtocol
					response += struct.pack('>I', 1048581) #\x00\x10\x00\x05 - Some undocumented shit you're supposed to respond with
					response += bdec(info_hash) # If we got it, we'll respond yes
					response += my_peer_id

					socks[fileno].send(response)
					print(' -- Responded:')
					print([response])
					print()
				else:
					print('Decoded:', [decoded])