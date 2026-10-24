import io,ssl,unittest
from urllib.error import HTTPError,URLError
from review_google_corpus import post_json, checked_transcripts, content_matches


class ReviewTransportTest(unittest.TestCase):
    def test_merged_missing_and_non_string_transcripts_cannot_shift_labels(self):
        for text,count in [('[]',1),('["one"]',2),('["one",3]',2),('{"0":"one"}',1),('["unfinished"',1)]:
            with self.assertRaises(ValueError):checked_transcripts(text,count)
        self.assertEqual(checked_transcripts('["你好 Piku"]',1),['你好 Piku'])

    def test_extra_english_or_digits_are_not_erased_into_approval(self):
        self.assertTrue(content_matches('你好披哭','你好，Piku。'))
        self.assertTrue(content_matches('你好皮克','你好皮克。'))
        for text in ['Hello，你好 Piku','你好 Piku 123','你好 Pico','你好皮克']:
            self.assertFalse(content_matches('你好披哭',text))

    def opener(self,events):
        class Fake:
            def __init__(self):self.calls=0
            def open(self,request,timeout):
                item=events[self.calls];self.calls+=1
                if isinstance(item,Exception):raise item
                return io.StringIO(item)
        return Fake()

    def test_transient_faults_retry_at_low_rate_and_return_first_valid_response(self):
        opener=self.opener([TimeoutError(),URLError(ssl.SSLEOFError('EOF')),'{"ok":true}']);sleeps=[]
        self.assertEqual(post_json(opener,object(),90,2,65,sleeps.append),{'ok':True})
        self.assertEqual(opener.calls,3);self.assertEqual(sleeps,[65,65])

    def test_http_quota_auth_and_region_errors_never_retry(self):
        for code in [400,401,403,429,503]:
            opener=self.opener([HTTPError('https://example.invalid',code,'stopped',{},None)]);sleeps=[]
            with self.assertRaises(HTTPError):post_json(opener,object(),90,2,65,sleeps.append)
            self.assertEqual(opener.calls,1);self.assertEqual(sleeps,[])

    def test_certificate_and_invalid_json_fail_without_retry(self):
        for error in [ssl.SSLCertVerificationError('untrusted'),URLError(ssl.SSLCertVerificationError('untrusted'))]:
            opener=self.opener([error]);sleeps=[]
            with self.assertRaises((ssl.SSLCertVerificationError,URLError)):post_json(opener,object(),90,2,65,sleeps.append)
            self.assertEqual(opener.calls,1);self.assertEqual(sleeps,[])
        opener=self.opener(['incomplete JSON']);sleeps=[]
        with self.assertRaises(ValueError):post_json(opener,object(),90,2,65,sleeps.append)
        self.assertEqual(opener.calls,1);self.assertEqual(sleeps,[])

    def test_retry_budget_is_finite_and_unsafe_rate_bounds_are_rejected(self):
        opener=self.opener([TimeoutError(),TimeoutError()]);sleeps=[]
        with self.assertRaises(TimeoutError):post_json(opener,object(),90,1,65,sleeps.append)
        self.assertEqual(opener.calls,2);self.assertEqual(sleeps,[65])
        for timeout,retries,delay in [(0,1,65),(181,1,65),(90,4,65),(90,1,1)]:
            with self.assertRaises(ValueError):post_json(self.opener([]),object(),timeout,retries,delay)
