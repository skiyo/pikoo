import io
import json
import unittest
from urllib.error import HTTPError
from review_google_corpus import post_json


class Responses:
    def __init__(self, codes, headers=None):
        self.codes=list(codes);self.calls=0;self.headers=headers or {}

    def open(self, request, timeout):
        self.calls+=1;code=self.codes.pop(0)
        if code!=200:raise HTTPError('https://example.invalid',code,'failure',self.headers,io.BytesIO(b'{}'))
        return io.BytesIO(b'{"ok":true}')


class CapacityRetryTest(unittest.TestCase):
    def test_default_still_stops_on_first503(self):
        client=Responses([503,200])
        with self.assertRaises(HTTPError):post_json(client,None)
        self.assertEqual(client.calls,1)

    def test_explicit_budget_backs_off_and_succeeds_without_long_single_sleep(self):
        client=Responses([503,503,200]);waits=[]
        self.assertEqual(post_json(client,None,capacity_retries=3,sleep=waits.append,jitter=lambda:0),{'ok':True})
        self.assertEqual(client.calls,3)
        self.assertEqual(sum(waits),65+130)
        self.assertLessEqual(max(waits),60)

    def test_budget_exhaustion_and_auth_or_quota_errors_stop(self):
        client=Responses([503]*5)
        with self.assertRaises(HTTPError):post_json(client,None,capacity_retries=3,sleep=lambda n:None,jitter=lambda:0)
        self.assertEqual(client.calls,4)
        for code in (400,401,402,403,429,500,504):
            client=Responses([code,200])
            with self.subTest(code=code),self.assertRaises(HTTPError):
                post_json(client,None,capacity_retries=3,sleep=lambda n:None)
            self.assertEqual(client.calls,1)

    def test_retry_after_is_honored_within_bound_and_oversized_wait_is_not_ignored(self):
        client=Responses([503,200],{'Retry-After':'180'});waits=[]
        post_json(client,None,capacity_retries=1,sleep=waits.append,jitter=lambda:0)
        self.assertEqual(sum(waits),180)
        for header in ('601','-1','invalid'):
            client=Responses([503,200],{'Retry-After':header})
            with self.subTest(header=header),self.assertRaises(HTTPError):
                post_json(client,None,capacity_retries=1,sleep=lambda n:None)
            self.assertEqual(client.calls,1)


if __name__=='__main__':unittest.main()
