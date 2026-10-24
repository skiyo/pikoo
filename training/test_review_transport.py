import io,ssl,unittest
from urllib.error import HTTPError,URLError
from review_google_corpus import post_json, checked_transcripts, content_matches, review_request, review_text, validated_cache, write_cache, validate


class ReviewTransportTest(unittest.TestCase):
    def test_original_level_tts_is_opt_in_and_protected_audio_never_uploads(self):
        import hashlib,tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'clip.wav').write_bytes(b'fictional-test-audio')
            digest=hashlib.sha256((root/'clip.wav').read_bytes()).hexdigest()
            row=dict(source='Google-TTS-level-tone-synthetic',source_terms='https://ai.google.dev/gemini-api/terms',
                     synthetic=True,path='clip.wav',sha256=digest)
            validate([row],root,set(),True)
            with self.assertRaises(ValueError):validate([row],root,set(),False)
            with self.assertRaises(ValueError):validate([row],root,{digest},True)
            for lineage in [{'parent_sha256':'protected-parent'},
                            {'augmentation':{'parent_sha256':'protected-parent'}}]:
                with self.assertRaises(ValueError):validate([{**row,**lineage}],root,{'protected-parent'},True)
            for flag in ['evaluation_only','frozen_holdout','real_child','reference_audio_used','family_inputs_used']:
                with self.assertRaises(ValueError):validate([{**row,flag:True,'path':'must-not-read.wav'}],root,set(),True)
            with self.assertRaises(ValueError):validate([{**row,'source_terms':''}],root,set(),True)
            with self.assertRaises(ValueError):validate([{**row,'path':'../outside.wav'}],root,set(),True)

    def test_resume_preserves_later_reviews_and_rejects_mixed_model_cache(self):
        import json,tempfile
        from pathlib import Path
        rows=[{'sha256':str(i),'label':i%2} for i in range(3)]
        review=lambda i:dict(rows[i],model='gemini-3.1-flash-lite',transcript='fixture',approved=True)
        cached=validated_cache(rows,[review(2)],'gemini-3.1-flash-lite')
        cached['0']=review(0)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'review.json'
            write_cache(path,rows,cached)
            self.assertEqual([x['sha256'] for x in json.loads(path.read_text())],['0','2'])
            self.assertFalse(path.with_name('review.json.tmp').exists())
        for bad in [[review(0),review(0)], [dict(review(0),model='gemini-2.5-flash')],
                    [dict(review(0),label=1)], [dict(review(0),sha256='unknown')]]:
            with self.assertRaises(ValueError):validated_cache(rows,bad,'gemini-3.1-flash-lite')

    def test_audio_requests_use_the_selected_model_protocol_without_transcript_hint(self):
        url,body=review_request('gemini-3.8-flash','fixture-base64',2)
        self.assertTrue(url.endswith('/interactions'))
        self.assertFalse(body['store'])
        content=body['input'][0]['content']
        self.assertEqual(content[1],{'type':'audio','data':'fixture-base64','mime_type':'audio/wav'})
        self.assertNotIn('Pikoo',content[0]['text'])
        self.assertEqual(body['response_format']['schema']['minItems'],2)
        self.assertEqual(body['response_format']['schema']['maxItems'],2)
        self.assertNotIn('temperature',body['generation_config'])
        url,body=review_request('gemini-2.5-flash','fixture-base64',1)
        self.assertTrue(url.endswith('/models/gemini-2.5-flash:generateContent'))
        self.assertEqual(body['generationConfig']['thinkingConfig'],{'thinkingBudget':0})
        url,body=review_request('gemini-3.1-flash-lite','fixture-base64',1)
        self.assertTrue(url.endswith('/models/gemini-3.1-flash-lite:generateContent'))
        self.assertEqual(body['generationConfig']['thinkingConfig'],{'thinkingLevel':'minimal'})
        self.assertEqual(body['generationConfig']['responseJsonSchema']['minItems'],1)
        self.assertNotIn('temperature',body['generationConfig'])
        with self.assertRaises(ValueError):review_request('other-model','data',1)

    def test_only_completed_model_text_can_supply_transcript_labels(self):
        response={'status':'completed','steps':[
            {'type':'thought','content':[{'type':'text','text':'not a transcript'}]},
            {'type':'model_output','content':[{'type':'text','text':'["你好"'},{'type':'text','text':']'}]}]}
        self.assertEqual(checked_transcripts(review_text('gemini-3.8-flash',response),1),['你好'])
        for value in [{'status':'in_progress','steps':response['steps']},{'status':'completed','steps':[]}]:
            with self.assertRaises(ValueError):review_text('gemini-3.8-flash',value)
        with self.assertRaises(ValueError):review_text('gemini-2.5-flash',{'candidates':[{'finishReason':'MAX_TOKENS'}]})
        legacy={'candidates':[{'finishReason':'STOP','content':{'parts':[{'thought':True,'text':'hidden'},{'text':'["你好"]'}]}}]}
        self.assertEqual(review_text('gemini-2.5-flash',legacy),'["你好"]')
        self.assertEqual(review_text('gemini-3.1-flash-lite',legacy),'["你好"]')

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
