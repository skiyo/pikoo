import csv, tempfile, unittest, wave
from pathlib import Path
from import_children import import_data
class ChildImportTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        with wave.open(str(self.root/'a.wav'),'wb') as w:
            w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(bytes(16000))
        self.rights=self.root/'rights.txt';self.rights.write_text('Test fixture, not a real child recording')
        self.row=dict(path='a.wav',speaker='p1',age='4',language='zh-CN',recording_session='s1',split='train',label='0',text='我要玩游戏')
    def tearDown(self):self.tmp.cleanup()
    def run_rows(self,rows):
        index=self.root/'index.csv'
        with index.open('w') as f:
            w=csv.DictWriter(f,fieldnames=self.row);w.writeheader();w.writerows(rows)
        return import_data(self.root,index,self.root/'out','fixture',self.rights)
    def test_private_metadata(self):
        r=self.run_rows([self.row])[0];self.assertTrue(r['real_child']);self.assertNotEqual(r['speaker'],'p1');self.assertTrue(r['restricted'])
    def test_speaker_leak(self):
        with self.assertRaisesRegex(ValueError,'leakage'):self.run_rows([self.row,{**self.row,'split':'test'}])
    def test_homophone(self):
        with self.assertRaisesRegex(ValueError,'homophone'):self.run_rows([{**self.row,'text':'你好皮裤'}])
    def test_path_escape(self):
        with self.assertRaisesRegex(ValueError,'inside'):self.run_rows([{**self.row,'path':'../outside.wav'}])
    def test_language(self):
        with self.assertRaisesRegex(ValueError,'Mandarin'):self.run_rows([{**self.row,'language':'en'}])
if __name__=='__main__':unittest.main()
