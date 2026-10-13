import unittest
from configure import validate
class ConfigTest(unittest.TestCase):
 def setUp(self):self.c=dict(ssid='测试网络',password='example-pass',endpoint='wss://203.0.113.10/api/realtime',token='example-device-token')
 def test_valid(self):self.assertEqual(validate(self.c),self.c)
 def test_utf8_limit(self):
  with self.assertRaises(ValueError):validate({**self.c,'ssid':'网'*11})
 def test_url_credential(self):
  with self.assertRaises(ValueError):validate({**self.c,'endpoint':'wss://secret@host/api/realtime'})
 def test_token_injection(self):
  with self.assertRaises(ValueError):validate({**self.c,'token':'abc\r\nHeader:value'})
if __name__=='__main__':unittest.main()
