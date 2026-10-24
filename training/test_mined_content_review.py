import hashlib
import tempfile
import unittest
from pathlib import Path
from review_local_corpus import validate, content_approved


class MinedContentReviewTest(unittest.TestCase):
    def row(self, root):
        data=b'fictional-synthetic-prefix'
        (root/'prefix.wav').write_bytes(data)
        return dict(path='prefix.wav',sha256=hashlib.sha256(data).hexdigest(),
                    split='train',label=0,source='pitch-tempo-augmented-Qwen3-TTS',
                    synthetic=True,mined_training_prefix=True,causal_end_sample=16000,
                    parent_sha256='declared-train-parent',text='你好皮球')

    def test_augmented_prefix_needs_explicit_opt_in_and_keeps_content_rule(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);row=self.row(root)
            with self.assertRaises(ValueError):validate([row],root,set())
            validate([row],root,set(),True)
            self.assertTrue(content_approved(row,'你好皮球'))
            self.assertFalse(content_approved(row,'你好皮'))
            self.assertFalse(content_approved(row,'你好皮酷'))

    def test_private_test_positive_and_ambiguous_ancestry_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);row=self.row(root)
            for changes in [{'split':'validation'},{'label':1},{'real_child':True},
                            {'family_inputs_used':True},{'frozen_holdout':True},
                            {'mined_training_prefix':False},{'causal_end_sample':0},
                            {'parent_sha256':row['sha256']}]:
                with self.subTest(changes=changes),self.assertRaises(ValueError):
                    validate([{**row,**changes}],root,set(),True)
            with self.assertRaises(ValueError):validate([row],root,{'declared-train-parent'},True)
            with self.assertRaises(ValueError):
                validate([{**row,'ancestry_parents':['sealed']}],root,{'sealed'},True)


if __name__=='__main__':unittest.main()
