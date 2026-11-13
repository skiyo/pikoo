import copy,json,unittest
from pathlib import Path
from configure import validate
from configure import prompt_config
from unittest.mock import patch
class ConfigTest(unittest.TestCase):
 def test_prompt_language_does_not_override_agent_language(self):
  for language in ('en','zh-CN'):
   with patch('builtins.input',side_effect=['fixture-wifi','','wss://voice.fixture.test/live','fixture-live','','','https://llm.fixture.test/reason','fixture-reason']) as ask,patch('getpass.getpass',side_effect=['fixture-password','fake-live-key','fake-llm-key']):
    value=prompt_config(language)
   self.assertEqual(value['agent']['language'],'en');validate(value)
   self.assertIn('无线' if language=='zh-CN' else 'Wi-Fi',ask.call_args_list[0].args[0])
 def setUp(self):self.c=json.loads((Path(__file__).resolve().parents[1]/'examples/device.example.json').read_text())
 def test_valid(self):self.assertEqual(validate(self.c),self.c)
 def test_independent_keys_and_urls(self):
  self.c['llm'].update(protocol='openai_chat_completions',url='https://another.example:9443/custom',api_key='different-key');validate(self.c)
 def test_unknown_protocol(self):
  self.c['llm']['protocol']='guess'
  with self.assertRaises(ValueError):validate(self.c)
 def test_utf8_limit(self):
  self.c['wifi']['ssid']='网'*11
  with self.assertRaises(ValueError):validate(self.c)
 def test_url_credential(self):
  self.c['live']['url']='wss://secret@host/path'
  with self.assertRaises(ValueError):validate(self.c)
 def test_key_injection(self):
  self.c['llm']['api_key']='bad\r\nHeader:value'
  with self.assertRaises(ValueError):validate(self.c)
 def test_optional_search(self):validate(self.c)
 def test_extract_origin(self):
  self.c['search']=dict(enabled=True,protocol='tavily',url='https://search.example/search',extract_url='https://other.example/extract',api_key='fake')
  with self.assertRaises(ValueError):validate(self.c)
