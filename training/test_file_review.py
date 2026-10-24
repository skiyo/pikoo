import json
import unittest
from unittest.mock import patch
from review_google_corpus import file_review_request, checked_file_transcripts


class FileReviewTest(unittest.TestCase):
    def test_admission_refuses_multiple_files_before_opening_any_input_or_network(self):
        from review_google_corpus import main
        args=['review_google_corpus.py','--manifest','missing-manifest.json',
              '--key-file','missing-secret.env','--output','missing-cache.json',
              '--batch-size','2']
        with patch('sys.argv',args), patch('review_google_corpus.build_opener') as network:
            with self.assertRaisesRegex(ValueError,'one file per request'):
                main()
            network.assert_not_called()

    def test_independent_media_parts_are_hash_identified_without_expected_words(self):
        clips = [('a' * 64, 'firstBase64'), ('b' * 64, 'secondBase64')]
        url, request = file_review_request('gemini-3.1-flash-lite', clips)
        parts = request['contents'][0]['parts']
        self.assertEqual([part['inlineData']['data'] for part in parts if 'inlineData' in part],
                         ['firstBase64', 'secondBase64'])
        schema = request['generationConfig']['responseJsonSchema']
        self.assertEqual(schema['required'], [key for key, data in clips])
        self.assertFalse(schema['additionalProperties'])
        self.assertNotIn('Pikoo', json.dumps(request))

    def test_reversed_object_order_is_mapped_by_identity_not_position(self):
        ids = ['a' * 64, 'b' * 64]
        self.assertEqual(checked_file_transcripts(json.dumps({ids[1]: '你好皮', ids[0]: '你好皮库'}), ids),
                         ['你好皮库', '你好皮'])

    def test_missing_extra_duplicate_and_nonstring_outputs_are_rejected(self):
        key = 'a' * 64
        for text in ['{}', json.dumps({key: 'speech', 'b' * 64: 'extra'}),
                     json.dumps({key: []}), json.dumps(['speech']),
                     '{"' + key + '":"first","' + key + '":"second"}']:
            with self.subTest(text=text), self.assertRaises(ValueError):
                checked_file_transcripts(text, [key])

    def test_invalid_model_count_or_identity_never_reaches_an_api(self):
        for model, clips in [('unknown-model', [('a' * 64, 'data')]),
                             ('gemini-3.1-flash-lite', []),
                             ('gemini-3.1-flash-lite', [('a' * 64, 'data')] * 2),
                             ('gemini-3.1-flash-lite', [('family-name', 'data')]),
                             ('gemini-3.1-flash-lite', [('a' * 64, '')])]:
            with self.subTest(model=model, clips=clips), self.assertRaises(ValueError):
                file_review_request(model, clips)

    def test38_uses_stateless_interactions_and_low_thinking_with_independent_audio(self):
        clips = [('a' * 64, 'firstBase64'), ('b' * 64, 'secondBase64')]
        url, request = file_review_request('gemini-3.8-flash', clips)
        self.assertTrue(url.endswith('/interactions'))
        self.assertFalse(request['store'])
        self.assertEqual(request['generation_config']['thinking_level'], 'low')
        self.assertEqual([part['data'] for part in request['input'] if part['type'] == 'audio'],
                         ['firstBase64', 'secondBase64'])
        self.assertEqual(request['response_format']['schema']['required'], [key for key, data in clips])


if __name__ == '__main__':
    unittest.main()
