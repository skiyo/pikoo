import io
import json
import tarfile
import tempfile
import unittest
import wave
from pathlib import Path

from import_childmandarin import import_archives, inventory


class ChildMandarinTest(unittest.TestCase):
    def archive(self, path, speaker, value=1, unsafe=False, text='一起玩'):
        pcm = io.BytesIO()
        with wave.open(pcm, 'wb') as w:
            w.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
            w.writeframes(value.to_bytes(2, 'little') * 8000)
        with tarfile.open(path, 'w') as tar:
            for name, data in [('sample.wav', pcm.getvalue()), ('sample.json', json.dumps(
                dict(speaker_id=speaker, age=4, text=text)).encode())]:
                info = tarfile.TarInfo(('../' if unsafe else 'data/') + name)
                info.size = len(data); tar.addfile(info, io.BytesIO(data))

    def test_import_and_preserve_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); rights = root/'rights'; rights.write_text('synthetic test fixtures')
            for n, name in enumerate(['train', 'dev', 'test']):
                self.archive(root/(name+'.tar'), str(n), value=n+1)
            report = import_archives(root, root/'out', rights)
            rows = json.loads((root/'out/manifest.json').read_text())
            self.assertEqual(report['unique_imported_clips'], 3)
            self.assertEqual({r['split'] for r in rows}, {'train', 'validation', 'test'})
            self.assertTrue(all(r['restricted'] and r['real_child'] and r['label']==0 for r in rows))

    def test_speaker_leak_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); rights = root/'rights'; rights.write_text('fixture')
            for n, name in enumerate(['train', 'dev', 'test']):
                self.archive(root/(name+'.tar'), 'same', value=n+1)
            with self.assertRaisesRegex(ValueError, 'speaker leaks'):
                import_archives(root, root/'out', rights)

    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad.tar'; self.archive(path, 'one', unsafe=True)
            with tarfile.open(path) as tar, self.assertRaisesRegex(ValueError, 'Unsafe'):
                inventory(tar, 'train')

    def test_homophone_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'data.tar'; self.archive(path, 'one', text='你好皮裤')
            with tarfile.open(path) as tar:
                rows, excluded = inventory(tar, 'train')
            self.assertEqual(rows, [])
            self.assertEqual(excluded, {'wake_phrase_or_homophone': 1})


if __name__ == '__main__':
    unittest.main()
