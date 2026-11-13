#!/usr/bin/env python3
"""Silent behavioral tests for the shared C++ Agent and provider adapters."""
import copy,json,subprocess,sys,unittest
from pathlib import Path
from configure import validate
BINARY=sys.argv.pop(1)

def config():
    c=json.loads((Path(__file__).resolve().parents[1]/'examples/device.example.json').read_text())
    c['live'].update(url='wss://voice.fixture.test:9443/custom/live',api_key='fake-voice-key',model='fixture-live')
    c['llm'].update(url='https://reason.fixture.test/custom/reason',api_key='fake-reason-key',model='fixture-reason')
    c['search']=dict(enabled=True,protocol='tavily',url='https://search.fixture.test/custom/search',api_key='fake-search-key',extract_url='https://search.fixture.test/custom/extract')
    return c

class Core:
    def __init__(self):self.p=subprocess.Popen([BINARY],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    def call(self,op,**kw):
        self.p.stdin.write(json.dumps(dict(op=op,**kw))+'\n');self.p.stdin.flush();line=self.p.stdout.readline()
        if not line:raise AssertionError('native driver exited')
        return json.loads(line)
    def close(self):
        self.p.stdin.close();self.p.stdout.close();assert self.p.wait(timeout=10)==0

def history():return [dict(type='message',role='user',content=[dict(type='input_text',text='请把测试条目加入购物清单，然后搜索天气')])]
def tool(protocol,name,args,call='call-one'):
    f=dict(name=name,arguments=json.dumps(args,ensure_ascii=False))
    return dict(type='function_call',call_id=call,**f) if protocol=='openai_responses' else dict(type='function',id=call,function=f)
def response(protocol,tools=None,answer='已根据实际结果完成。'):
    if protocol=='openai_responses':return dict(status='completed',output=tools or [dict(type='message',role='assistant',content=[dict(type='output_text',text=answer)])])
    return dict(choices=[dict(finish_reason='tool_calls' if tools else 'stop',message=dict(role='assistant',content=None if tools else answer,**(dict(tool_calls=tools) if tools else {})))])

class Services(unittest.TestCase):
    def setUp(self):self.core=Core()
    def tearDown(self):self.core.close()
    def complete(self,r,value,status=200,now=101):return self.core.call('complete',token=r['token'],status=status,body=json.dumps(value),now=now)
    def start(self,c=None):
        c=c or config();self.assertTrue(self.core.call('configure',config=c)['valid'])
        return self.core.call('start',id='delegation-one',history=history(),now=100)['requests'][0]
    def test_independent_providers_and_tool_loop(self):
        for protocol in ['openai_responses','openai_chat_completions']:
            for search in ['tavily','openai_responses']:
                with self.subTest(protocol=protocol,search=search):
                    c=config();c['llm']['protocol']=protocol;c['search']['protocol']=search
                    if search=='openai_responses':c['search'].pop('extract_url');c['search']['model']='fixture-search'
                    r=self.start(c);self.assertEqual(r['authorization'],'Bearer fake-reason-key');self.assertEqual(r['url'],c['llm']['url'])
                    tools=[tool(protocol,'family_list',dict(group='shopping',operation='add',entry='测试条目')),
                           tool(protocol,'web_search',dict(query='天气'),call='search-one')]
                    result=self.complete(r,response(protocol,tools));request=result['requests'][0]
                    self.assertEqual(request['url'],c['search']['url']);self.assertEqual(request['authorization'],'Bearer fake-search-key')
                    self.assertNotIn('fake-voice-key',json.dumps(request));self.assertNotIn('fake-reason-key',json.dumps(request))
                    self.assertEqual(json.loads(result['snapshot'])['shopping'],['测试条目'])
                    data=dict(results=[dict(title='天气',url='https://source.fixture.test/news',content='晴')]) if search=='tavily' else dict(output=[dict(content=[dict(type='output_text',text='晴',annotations=[dict(type='url_citation',url='https://source.fixture.test/news',title='天气')])])])
                    next_request=self.complete(request,data)['requests'][0];self.assertIn('source.fixture.test',next_request['body'])
                    final=self.complete(next_request,response(protocol));self.assertEqual(len(final['replies']),1);self.assertFalse(final['busy'])
    def test_cancellation_drops_late_write_and_reply(self):
        r=self.start();self.core.call('cancel');out=self.complete(r,response('openai_responses',[tool('openai_responses','family_memory',dict(group='memory',operation='add',entry='不应写入'))]))
        self.assertEqual(json.loads(out['snapshot'])['memory'],[]);self.assertEqual(out['replies'],[])
    def test_new_task_supersedes_previous(self):
        old=self.start();new=self.core.call('start',id='new-task',history=history(),now=101)['requests'][0]
        self.assertFalse(self.complete(old,response('openai_responses'))['replies']);self.assertTrue(self.complete(new,response('openai_responses'))['replies'])
    def test_error_status_never_runs_pending_tools(self):
        for status in (0,401,429,500):
            r=self.start();out=self.complete(r,{'private':'not-for-output'},status)
            self.assertFalse(out['requests']);self.assertTrue(out['replies']);self.assertNotIn('not-for-output',str(out['replies']))
    def test_timeout_and_four_round_limit(self):
        r=self.start();out=self.core.call('tick',now=30100);self.assertTrue(out['replies']);self.assertFalse(self.complete(r,response('openai_responses'))['replies'])
        r=self.start()
        for i in range(4):
            out=self.complete(r,response('openai_responses',[tool('openai_responses','family_list',dict(group='shopping',operation='list'),call='list-'+str(i))]))
            if i<3:r=out['requests'][0]
        self.assertFalse(out['requests']);self.assertTrue(out['replies']);self.assertFalse(out['busy'])
    def test_search_disabled_does_not_request_search(self):
        c=config();c['search']=dict(enabled=False);r=self.start(c);self.assertNotIn('web_search',r['body'])
        out=self.complete(r,response('openai_responses',[tool('openai_responses','web_search',dict(query='天气'))]));self.assertEqual(out['requests'][0]['url'],c['llm']['url']);self.assertIn('unknown_tool',out['requests'][0]['body'])
    def test_extract_is_capability_gated(self):
        r=self.start();out=self.complete(r,response('openai_responses',[tool('openai_responses','read_webpage',dict(url='https://public.fixture.test/page'))]));r=out['requests'][0]
        self.assertEqual(r['url'],config()['search']['extract_url']);out=self.complete(r,dict(results=[dict(url='https://public.fixture.test/page',raw_content='原文')]))
        self.assertIn('原文',out['requests'][0]['body'])
    def test_search_failure_returns_tool_error_then_reasoning(self):
        r=self.start();r=self.complete(r,response('openai_responses',[tool('openai_responses','web_search',dict(query='天气'))]))['requests'][0]
        out=self.complete(r,{},429);self.assertIn('search_unavailable',out['requests'][0]['body'])
    def test_incomplete_or_oversized_response_cannot_write(self):
        r=self.start();out=self.complete(r,dict(status='incomplete',output=[tool('openai_responses','family_memory',dict(group='memory',operation='add',entry='不保存'))]));self.assertFalse(json.loads(out['snapshot'])['memory'])
        r=self.start();out=self.core.call('complete',token=r['token'],status=200,body='x'*65537,now=101);self.assertTrue(out['replies']);self.assertFalse(out['requests'])
    def test_duplicate_call_and_restart_persistence(self):
        r=self.start();call=tool('openai_responses','family_list',dict(group='todo',operation='add',entry='测试待办'))
        out=self.complete(r,response('openai_responses',[call,call]));snapshot=out['snapshot'];self.assertEqual(json.loads(snapshot)['todo'],['测试待办'])
        self.assertTrue(self.core.call('snapshot_load',snapshot=snapshot)['loaded']);self.assertFalse(self.core.call('snapshot_load',snapshot=snapshot+'garbage')['loaded'])
        r=self.start();out=self.complete(r,response('openai_responses',[call]));self.assertIn('already_applied',out['requests'][0]['body'])
    def test_live_client_delegation_uses_classified_context(self):
        self.core.call('configure',config=config());out=self.core.call('live_start',now=100)
        session=json.loads(out['send'][0])['session'];self.assertEqual(session['delegation']['type'],'client');self.assertEqual(session['model'],'fixture-live');self.assertNotIn('fixture-reason',str(session))
        self.core.call('receive',message=dict(type='session.started',session=dict(audio=dict(format=dict(type='audio/pcm',rate=16000)))),now=101)
        self.core.call('receive',message=dict(type='session.input_transcript.delta',event_id='input',delta='查询购物清单'),now=110)
        out=self.core.call('receive',message=dict(type='session.delegation.created',delegation=dict(id='client-job',target='client')),now=111);self.assertFalse(out['requests'])
        out=self.core.call('receive',message=dict(type='decision.event',source_event_id='input',source_event_type='session.input_transcript.delta',event=dict(type='decision.completed',decision=dict(answers=[dict(name='interaction',choice='addressed')]))),now=112)
        r=out['requests'][0];self.assertIn('查询购物清单',r['body']);out=self.complete(r,response('openai_responses'),now=113)
        event=json.loads(out['send'][0]);self.assertEqual(event['type'],'session.commentary.append');self.assertEqual(event['delegation_id'],'client-job')
    def test_live_interrupt_invalidates_pending_mutation(self):
        self.core.call('configure',config=config());self.core.call('live_start',now=100)
        self.core.call('receive',message=dict(type='session.started',session=dict(audio=dict(format=dict(type='audio/pcm',rate=16000)))),now=101)
        def speech(event,text,choice,now):
            self.core.call('receive',message=dict(type='session.input_transcript.delta',event_id=event,delta=text),now=now)
            return self.core.call('receive',message=dict(type='decision.event',source_event_id=event,source_event_type='session.input_transcript.delta',event=dict(type='decision.completed',decision=dict(answers=[dict(name='interaction',choice=choice)]))),now=now+1)
        speech('question','请记住测试内容','addressed',110)
        r=self.core.call('receive',message=dict(type='session.delegation.created',delegation=dict(id='cancelled',target='client')),now=112)['requests'][0]
        speech('stop','停一下','interrupt',120)
        out=self.complete(r,response('openai_responses',[tool('openai_responses','family_memory',dict(group='memory',operation='add',entry='不应保存'))]),now=123)
        self.assertEqual(json.loads(out['snapshot'])['memory'],[]);self.assertFalse(out['replies']);self.assertFalse(out['requests'])
    def test_many_live_tasks_and_ignored_speech_do_not_replay_old_context(self):
        self.core.call('configure',config=config());self.core.call('live_start',now=100)
        self.core.call('receive',message=dict(type='session.started',session=dict(audio=dict(format=dict(type='audio/pcm',rate=16000)))),now=101)
        for i in range(40):
            now=200+i*50;event='q-'+str(i)
            self.core.call('receive',message=dict(type='session.input_transcript.delta',event_id=event,delta='明确的查询'),now=now)
            self.core.call('receive',message=dict(type='decision.event',source_event_id=event,source_event_type='session.input_transcript.delta',event=dict(type='decision.completed',decision=dict(answers=[dict(name='interaction',choice='addressed')]))),now=now+1)
            out=self.core.call('receive',message=dict(type='session.delegation.created',delegation=dict(id='job-'+str(i),target='client')),now=now+2)
            self.assertEqual(len(out['requests']),1);self.complete(out['requests'][0],response('openai_responses'),now=now+3)
        self.core.call('receive',message=dict(type='session.input_transcript.delta',event_id='tv',delta='电视对白'),now=2300)
        self.core.call('receive',message=dict(type='decision.event',source_event_id='tv',source_event_type='session.input_transcript.delta',event=dict(type='decision.completed',decision=dict(answers=[dict(name='interaction',choice='ignore')]))),now=2301)
        out=self.core.call('receive',message=dict(type='session.delegation.created',delegation=dict(id='ignored-tv',target='client')),now=2302)
        self.assertFalse(out['requests']);self.assertNotIn('电视对白',out['snapshot'])
    def test_farewell_cancels_pending_write_and_new_question_can_resume(self):
        self.core.call('configure',config=config());self.core.call('live_start',now=100)
        self.core.call('receive',message=dict(type='session.started',session=dict(audio=dict(format=dict(type='audio/pcm',rate=16000)))),now=101)
        def speech(event,text,choice,now):
            self.core.call('receive',message=dict(type='session.input_transcript.delta',event_id=event,delta=text),now=now)
            return self.core.call('receive',message=dict(type='decision.event',source_event_id=event,source_event_type='session.input_transcript.delta',event=dict(type='decision.completed',decision=dict(answers=[dict(name='interaction',choice=choice)]))),now=now+1)
        speech('first','保存测试内容','addressed',110)
        r=self.core.call('receive',message=dict(type='session.delegation.created',delegation=dict(id='before-bye',target='client')),now=112)['requests'][0]
        speech('bye','Pikoo 再见','farewell',120)
        out=self.complete(r,response('openai_responses',[tool('openai_responses','family_memory',dict(group='memory',operation='add',entry='迟到写入'))]),now=123)
        self.assertFalse(out['replies']);self.assertEqual(json.loads(out['snapshot'])['memory'],[])
        speech('again','还有一个问题','addressed',130)
        out=self.core.call('receive',message=dict(type='session.delegation.created',delegation=dict(id='after-bye',target='client')),now=132)
        self.assertEqual(len(out['requests']),1)
    def test_http_fragmentation_chunking_bounds_and_truncation(self):
        for wire in ['HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\n{"x":1}', 'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n3\r\n{"x\r\n4\r\n":1}\r\n0\r\n\r\n']:
            self.core.call('http_begin')
            for i in range(0,len(wire),2):out=self.core.call('http_feed',data=wire[i:i+2])
            self.assertTrue(out['done']);self.assertTrue(out['ok']);self.assertEqual(out['body'],'{"x":1}')
        for wire in ['HTTP/1.1 200 OK\r\nContent-Length: 70000\r\n\r\n','HTTP/1.1 200 OK\r\nContent-Length: 1\r\nTransfer-Encoding: chunked\r\n\r\n','HTTP/1.1 200 OK\r\nContent-Length: 7\r\n\r\n{']:
            self.core.call('http_begin');out=self.core.call('http_feed',data=wire,eof=True);self.assertFalse(out['ok'])
    def test_python_and_firmware_config_validation_agree(self):
        cases=[config()]
        for path,value in [('live.protocol','unknown'),('llm.url','http://not-tls.test'),('live.url','wss://key@host/path'),('llm.api_key','bad\r\nHeader:value'),('live.audio_rate',48000),('wifi.ssid','网'*11),('wifi.password','short'),('version',2),('search.protocol','unknown'),('search.extract_url','https://other.test/extract'),('network.proxy_url','https://proxy.test/path')]:
            c=config();keys=path.split('.');node=c
            for key in keys[:-1]:node=node[key]
            node[keys[-1]]=value;cases.append(c)
        for c in cases:
            try:validate(c);valid=True
            except (ValueError,TypeError):valid=False
            self.assertEqual(self.core.call('validate',config=c)['valid'],valid)

if __name__=='__main__':unittest.main()
