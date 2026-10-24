import json
import unittest
from review_google_corpus import file_review_request, checked_file_transcripts


class FileReviewTest(unittest.TestCase):
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
        for model, clips in [('gemini-3.8-flash', [('a' * 64, 'data')]),
                             ('gemini-3.1-flash-lite', []),
                             ('gemini-3.1-flash-lite', [('a' * 64, 'data')] * 2),
                             ('gemini-3.1-flash-lite', [('family-name', 'data')]),
                             ('gemini-3.1-flash-lite', [('a' * 64, '')])]:
            with self.subTest(model=model, clips=clips), self.assertRaises(ValueError):
                file_review_request(model, clips)


if __name__ == '__main__':
    unittest.main()
