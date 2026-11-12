import unittest
from configure import validate
class ConfigTest(unittest.TestCase):
 def setUp(self):self.c=dict(ssid='测试网络',password='example-pass',endpoint='wss://203.0.113.10/api/realtime',token='example-device-token')
 def test_valid(self):self.assertEqual(validate(self.c),self.c)
 def test_local_without_gateway(self):
  c=dict(mode='local',ssid='测试网络',password='example-pass')
  self.assertEqual(validate(c),c)
 def test_local_rejects_secret_image(self):
  with self.assertRaises(ValueError):validate(dict(mode='local',ssid='家',password='',api_key='fake-key'))
 def test_unknown_mode(self):
  with self.assertRaises(ValueError):validate({**self.c,'mode':'other'})
 def test_local_validates_optional_legacy_credentials(self):
  with self.assertRaises(ValueError):validate({**self.c,'mode':'local','token':'bad\nheader'})
 def test_utf8_limit(self):
  with self.assertRaises(ValueError):validate({**self.c,'ssid':'网'*11})
 def test_url_credential(self):
  with self.assertRaises(ValueError):validate({**self.c,'endpoint':'wss://secret@host/api/realtime'})
 def test_token_injection(self):
  with self.assertRaises(ValueError):validate({**self.c,'token':'abc\r\nHeader:value'})
if __name__=='__main__':unittest.main()
