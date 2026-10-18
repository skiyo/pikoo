import base64
import json
import unittest
from command_probe import Probe, fnv1a


class Transport:
    def __init__(self, corrupt=False):
        self.pending=[];self.audio=bytearray();self.corrupt=corrupt
    def write(self,line):
        parts=line.strip().split(b' ')
        if not parts[0]:return
        if parts[0]==b'R':result={'kind':'ready','value':512}
        elif parts[0]==b'B':
            self.identifier,self.label,self.samples=map(int,parts[1:]);self.audio.clear()
            result={'kind':'begin','value':self.identifier}
        elif parts[0]==b'F':
            self.audio.extend(base64.b64decode(parts[2],validate=True));result={'kind':'frame','value':int(parts[1])}
        else:
            result={'kind':'result','id':self.identifier,'label':self.label,'samples':self.samples,
                    'checksum':fnv1a(self.audio)+self.corrupt,'top_id':1,'top_probability':.8}
        self.pending.append(b'PROBE '+json.dumps(result).encode()+b'\n')
    def flush(self):pass
    def readline(self):return self.pending.pop(0)


class Tests(unittest.TestCase):
    def test_known_checksum(self):
        self.assertEqual(fnv1a(b'hello'),0x4f9f2cab)
    def test_chunked_replay_including_partial_block(self):
        serial=Transport();pcm=bytes(range(256))*5+b'\x00\x00'
        result=Probe(serial).replay(12,1,pcm)
        self.assertEqual(bytes(serial.audio),pcm)
        self.assertEqual(result['samples'],641)
    def test_checksum_mismatch_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,'checksum'):
            Probe(Transport(corrupt=True)).replay(1,0,b'\x00\x00')
    def test_reset_discards_only_stale_protocol_records(self):
        serial=Transport();serial.pending=[b'PROBE {"kind":"error","value":4}\n',b'PROBE {"kind":"frame","value":2}\n']
        probe=Probe(serial);probe.reset()
        self.assertEqual(probe.replay(3,0,b'\x00\x00')['id'],3)
    def test_partial_serial_read_is_retained_until_newline(self):
        serial=Transport();serial.pending=[b'PROBE {"kind":',b'"frame","value":0}',b'\n']
        self.assertEqual(Probe(serial).receive('frame',0)['value'],0)
    def test_device_transport_error_fails_closed(self):
        serial=Transport();serial.pending=[b'PROBE {"kind":"error","value":5}\n']
        with self.assertRaisesRegex(RuntimeError,'transport'):
            Probe(serial).receive('result')
    def test_reordered_ack_is_rejected(self):
        serial=Transport();serial.pending=[b'PROBE {"kind":"frame","value":2}\n']
        with self.assertRaisesRegex(RuntimeError,'acknowledgement'):
            Probe(serial).receive('frame',1)
    def test_device_panic_fails_immediately(self):
        serial=Transport();serial.pending=[b'Guru Meditation Error: test\n']
        with self.assertRaisesRegex(RuntimeError,'runtime failed'):
            Probe(serial).receive('frame',0)
    def test_invalid_input_never_sends(self):
        serial=Transport()
        for pcm in [b'',b'\x01',b'\x00'*320002]:
            with self.assertRaises(ValueError):Probe(serial).replay(1,0,pcm)
        self.assertEqual(serial.pending,[])


if __name__=='__main__':unittest.main()
