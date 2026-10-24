import unittest
import tempfile
from pathlib import Path
import wave
import numpy as np
from clean_corpus import clean, signal_issue


def sample(digest='original', **changes):
    return dict(sha256=digest, path=digest+'.wav', split='train', label=1,
                group='fictional-train', source='Qwen3-TTS-synthetic-local',
                synthetic=True, text='你好披哭', **changes)


def review(digest='original', transcript='你好皮裤', model='Qwen3-ASR'):
    return dict(sha256=digest, transcript=transcript, model=model)


class CleanCorpusTest(unittest.TestCase):
    def test_disagreement_quarantines_all_recursive_derivatives_without_relabeling(self):
        original=sample()
        variant={**sample('variant'), 'augmentation': {'parent_sha256':'original'}}
        prefix={**sample('prefix'), 'label':0, 'text':'你好皮',
                'source':'TTS-matched-incomplete-prefix', 'parent_sha256':'variant'}
        rows=[original, variant, prefix]
        approved, report=clean(rows,[review(),review(transcript='你好皮克',model='gemini-2.5-flash'),
                                    review('prefix','你好皮')])
        self.assertEqual(approved,[])
        self.assertEqual(report['quarantined_rows'],3)
        self.assertEqual(report['labels_changed'],0)
        self.assertEqual(rows,[original,variant,prefix])
        self.assertTrue(any('quarantined-ancestor' in r for r in report['quarantine'][2]['reasons']))

    def test_latin_positive_needs_two_recognizer_families_not_two_reruns(self):
        row={**sample(), 'text':'你好Pikoo'}
        a,_=clean([row],[review(),review(model='Qwen3-ASR-new')])
        self.assertFalse(a)
        a,_=clean([row],[review(),review(model='gemini-2.5-flash')])
        self.assertEqual(a,[row])
        a,_=clean([row],[review(),review(transcript='你好皮',model='gemini-2.5-flash')])
        self.assertFalse(a)

    def test_all_evidence_including_prior_rejection_is_preserved(self):
        row=sample()
        a,_=clean([row],[{**review(),'prior_approved':False}])
        self.assertFalse(a)
        with self.assertRaises(ValueError):clean([row],[{**review(),'label':0}])
        with self.assertRaises(ValueError):clean([row],[{**review(),'model':''}])

    def test_prefix_requires_own_review_and_missing_parent_never_inherits_trust(self):
        prefix={**sample('prefix'),'source':'TTS-matched-incomplete-prefix',
                'label':0,'text':'你好皮','parent_sha256':'original'}
        a,r=clean([sample(),prefix],[review()])
        self.assertEqual(len(a),1)
        self.assertIn('missing-content-review',r['quarantine'][0]['reasons'])
        a,r=clean([prefix],[review('prefix','你好皮')])
        self.assertFalse(a)
        self.assertIn('missing-parent-provenance',r['quarantine'][0]['reasons'])
        a,_=clean([prefix],[review(),review('prefix','你好皮')],catalog=[sample()])
        self.assertEqual(a,[prefix])

    def test_guard_blocks_test_and_household_metadata_and_protected_ancestors(self):
        for changes in [{'evaluation_only':True},{'frozen_holdout':True},{'split':'test'},
                        {'source':'private-family'},{'family_inputs_used':True},
                        {'reference_audio_used':True},{'parent_sha256':'sealed'},
                        {'augmentation':{'parent_sha256':'sealed'}},
                        {'ancestry_parents':['sealed']}]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                clean([{**sample(),**changes}],[review()],protected={'sealed'})
        with self.assertRaises(ValueError):clean([sample()],[review()],protected={'original'})
        with self.assertRaises(ValueError):clean([sample()],[review('sealed')],protected={'sealed'})

    def test_cycles_conflicting_labels_and_split_leaks_are_fatal(self):
        with self.assertRaises(ValueError):clean([sample(),{**sample(),'label':0}],[])
        with self.assertRaises(ValueError):clean([sample(),{**sample('b'),'split':'validation'}],[])
        with self.assertRaises(ValueError):clean([{**sample(),'parent_sha256':'b'},
            {**sample('b'),'parent_sha256':'original'}],[])
        with self.assertRaises(ValueError):clean([sample(),{**sample('b'),
            'group':'validation','split':'validation','parent_sha256':'original'}],[])

    def test_public_child_background_kept_but_legacy_synthesis_quarantined(self):
        public={**sample(),'source':'ChildMandarin','synthetic':False,'real_child':True,'label':0}
        legacy={**sample('old'),'source':'macOS-aligned-v2','label':0}
        a,r=clean([public,legacy],[])
        self.assertEqual(a,[public])
        self.assertEqual(r['quarantined_rows'],1)
        with self.assertRaises(ValueError):clean([{**public,'label':1}],[])

    def test_signal_corruption_propagates_to_augmented_descendants(self):
        variant={**sample('variant'),'source':'pitch-tempo-augmented-Qwen3-TTS',
                 'augmentation':{'parent_sha256':'original'}}
        a,r=clean([sample(),variant],[review()],signal_findings=[
            {'sha256':'original','reason':'severe-digital-clipping'}])
        self.assertFalse(a)
        self.assertEqual(r['quarantined_rows'],2)
        with self.assertRaises(ValueError):clean([sample()],[review()],signal_findings=[
            {'sha256':'original','reason':'low-model-score'}])
        with self.assertRaises(ValueError):clean([sample(),{**variant,'label':0}],[review()])

    def test_pcm_checks_flag_corruption_not_normal_low_volume_speech(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'clip.wav'
            def write(pcm,rate=16000):
                with wave.open(str(path),'wb') as audio:
                    audio.setparams((1,2,rate,0,'NONE','not compressed'))
                    audio.writeframes(np.array(pcm,dtype='<i2').tobytes())
            write([0]*100)
            self.assertEqual(signal_issue(path),'empty-or-nearly-silent')
            write([32767,-32768]*100)
            self.assertEqual(signal_issue(path),'severe-digital-clipping')
            write([10,-10]*100)
            self.assertIsNone(signal_issue(path))
            write([10,-10]*100,8000)
            self.assertEqual(signal_issue(path),'invalid-pcm-format')
            path.write_bytes(b'not a wave')
            self.assertEqual(signal_issue(path),'malformed-waveform')

    def test_pitch_variant_tracks_immediate_parent_and_retains_older_ancestry(self):
        old={**sample('old'),'text':'你好皮酷'}
        retuned={**sample('retuned'),'source':'Google-TTS-level-tone-synthetic',
                 'parent_sha256':'old','augmentation':{'method':'tone-transform'}}
        variant={**sample('variant'),'source':'pitch-tempo-augmented-Google-level-tone',
                 'parent_sha256':'old','augmentation':{'parent_sha256':'retuned'}}
        a,_=clean([old,retuned,variant],[review('old'),review('retuned')])
        self.assertEqual(len(a),3)
        a,r=clean([old,retuned,variant],[review('old')])
        self.assertEqual(a,[old])
        self.assertEqual(r['quarantined_rows'],2)
