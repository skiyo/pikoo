import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave


@unittest.skipUnless(importlib.util.find_spec('numpy'), 'Optional training runtime is not installed')
class PrepareGoogleTest(unittest.TestCase):
    def test_empty_optional_corpus_does_not_require_a_review_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['previous','google','negatives']:(root/(name+'.json')).write_text('[]')
            (root/'protected.json').write_text('{"audio_sha256":{}}')
            result=self.run_prepare(root)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads((root/'result/manifest.json').read_text()),[])
    def test_duplicate_waveform_preserves_mining_weight_and_rejects_conflicting_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'fixture.wav').write_bytes(b'fixture')
            row=dict(path='fixture.wav',source='Qwen3-TTS-synthetic-local',synthetic=True,label=0,split='train',group='train')
            for name in ['google','review','negatives']:(root/(name+'.json')).write_text('[]')
            (root/'protected.json').write_text('{"audio_sha256":{}}')
            (root/'previous.json').write_text(json.dumps([row,{**row,'hard_negative':True,'mining_model_sha256':'mining-fixture'}]))
            result=self.run_prepare(root)
            self.assertEqual(result.returncode,0,result.stderr)
            merged=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual(len(merged),1)
            self.assertTrue(merged[0]['hard_negative'])
            (root/'previous.json').write_text(json.dumps([row,{**row,'label':1}]))
            result=self.run_prepare(root)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('conflicting labels',result.stderr)
    def test_ambiguous_training_contrast_cannot_remove_legacy_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[]
            for split in ('train','validation'):
                path=root/(split+'.wav');path.write_bytes(split.encode())
                rows.append(dict(path=path.name,source='Qwen3-TTS-synthetic-local',synthetic=True,label=0,split=split,group=split,text='你好比酷'))
            (root/'previous.json').write_text(json.dumps(rows))
            for name in ('google','review','negatives'):(root/(name+'.json')).write_text('[]')
            (root/'protected.json').write_text('{"audio_sha256":{}}')
            result=self.run_prepare(root,['--quarantine-training-negatives','你好比酷'])
            self.assertEqual(result.returncode,0,result.stderr)
            output=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual([r['split'] for r in output],['validation'])
    def test_short_context_never_discards_long_validation_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[]
            for name,split,seconds,amplitude in [('long-train','train',3,1),('short-train','train',1,2),('long-val','validation',3,3)]:
                path=root/(name+'.wav')
                with wave.open(str(path),'wb') as w:
                    w.setparams((1,2,16000,0,'NONE','not compressed'));w.writeframes(amplitude.to_bytes(2,'little')*16000*seconds)
                rows.append(dict(path=path.name,source='Google-Gemini-TTS-synthetic',label=1,split=split,group=name))
            (root/'previous.json').write_text(json.dumps(rows))
            for name in ('google','review','negatives'):(root/(name+'.json')).write_text('[]')
            (root/'protected.json').write_text('{"audio_sha256":{}}')
            result=self.run_prepare(root,['--context-frames','300'])
            self.assertEqual(result.returncode,0,result.stderr)
            output=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual({r['group'] for r in output},{'short-train','long-val'})
    def run_prepare(self, root, extra=()):
        return subprocess.run([sys.executable, str(Path(__file__).with_name('prepare_google_iteration.py')),
            '--previous', str(root / 'previous.json'), '--google', str(root / 'google.json'),
            '--real-negatives', str(root / 'negatives.json'),
            '--excluded-audio-hashes', str(root / 'protected.json'), '--output', str(root / 'result'),*extra],
            capture_output=True, text=True)

    def test_renamed_protected_waveform_cannot_enter_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = b'protected recording fixture'
            (root / 'renamed.wav').write_bytes(audio)
            (root / 'protected.json').write_text(json.dumps({'audio_sha256': {
                'original.wav': hashlib.sha256(audio).hexdigest()}}))
            (root / 'previous.json').write_text(json.dumps([{
                'path': 'renamed.wav', 'source': 'authorized-speech', 'split': 'train',
                'label': 0, 'group': 'test-speaker'}]))
            result = self.run_prepare(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Protected human recording', result.stderr)
            self.assertFalse((root / 'result/manifest.json').exists())

    def test_auxiliary_synthesis_training_rows_are_never_a_validation_challenge(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('previous','negatives','google','review'):(root/(name+'.json')).write_text('[]')
            (root/'protected.json').write_text('{"audio_sha256":{}}')
            folder=root/'challenge';folder.mkdir();rows=[];reviews=[]
            for split in ('train','validation'):
                audio=split.encode();(folder/(split+'.wav')).write_bytes(audio);digest=hashlib.sha256(audio).hexdigest()
                rows.append(dict(path=split+'.wav',sha256=digest,label=1,split=split,group=split,text='你好皮酷',source='Qwen3-TTS-synthetic-local',synthetic=True))
                reviews.append(dict(sha256=digest,transcript='你好皮酷',approved=True))
            (folder/'manifest.json').write_text(json.dumps(rows));(folder/'review.json').write_text(json.dumps(reviews))
            result=self.run_prepare(root,['--drop-historical-positives','--validation-challenge',str(folder/'manifest.json')])
            self.assertEqual(result.returncode,0,result.stderr)
            output=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual(len(output),1);self.assertEqual(output[0]['split'],'validation')

    def test_one_misaligned_transcript_rejects_entire_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('previous', 'negatives'):
                (root / (name + '.json')).write_text('[]')
            (root / 'protected.json').write_text('{"audio_sha256": {}}')
            rows = []
            review = []
            for label, expected, heard in [(1, '你好皮酷', '你好皮酷'), (0, '你好皮球', '你好皮酷')]:
                blob = bytes([label])
                path = root / f'{label}.wav'
                path.write_bytes(blob)
                digest = hashlib.sha256(blob).hexdigest()
                rows.append(dict(path=path.name, sha256=digest, batch_id='same-batch',
                                 source='Google-Gemini-TTS-synthetic',synthetic=True,
                                 text=expected, label=label, split='train', group='one-voice'))
                review.append(dict(sha256=digest, transcript=heard))
            (root / 'google.json').write_text(json.dumps(rows, ensure_ascii=False))
            (root / 'review.json').write_text(json.dumps(review, ensure_ascii=False))
            result = self.run_prepare(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((root / 'result/manifest.json').read_text()), [])
            self.assertEqual(json.loads((root / 'result/preparation-report.json').read_text())['rejected_google_rows'], 2)

    def test_prefix_review_cannot_label_complete_wake_as_negative(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('previous','negatives','google','review'):(root/(name+'.json')).write_text('[]')
            (root/'protected.json').write_text('{"audio_sha256":{}}')
            folder=root/'prefixes';folder.mkdir();rows=[];reviews=[]
            for index,heard in enumerate(('你好皮','你好皮裤')):
                audio=str(index).encode();digest=hashlib.sha256(audio).hexdigest()
                (folder/f'{index}.wav').write_bytes(audio)
                rows.append(dict(path=f'{index}.wav',sha256=digest,label=0,split='train',group='one-voice',source='Google-TTS-incomplete-prefix',synthetic=True))
                reviews.append(dict(sha256=digest,transcript=heard,approved=True))
            (folder/'manifest.json').write_text(json.dumps(rows));(folder/'review.json').write_text(json.dumps(reviews))
            result=self.run_prepare(root,['--reviewed-prefixes',str(folder/'manifest.json')])
            self.assertEqual(result.returncode,0,result.stderr)
            output=json.loads((root/'result/manifest.json').read_text())
            self.assertEqual(len(output),1);self.assertTrue(output[0]['hard_negative'])


if __name__ == '__main__':
    unittest.main()
