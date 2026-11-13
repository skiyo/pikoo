#!/usr/bin/env python3
"""Loopback-only silent service/TLS/CONNECT tests with fake credentials."""
import argparse,base64,contextlib,hashlib,json,os,select,socket,socketserver,ssl,struct,subprocess,tempfile,threading,time
from pathlib import Path
from urllib.parse import urlsplit

def read_exact(stream, n):
    data = bytearray()
    while len(data) < n:
        chunk = stream.recv(n - len(data))
        if not chunk:
            raise EOFError("peer closed")
        data.extend(chunk)
    return bytes(data)


def header(stream):
    data = bytearray()
    while len(data) < 8192:
        data += read_exact(stream, 1)
        if data.endswith(b"\r\n\r\n"):
            return bytes(data)
    raise ValueError("oversize header")


def frame(stream, data, masked=False, opcode=0x81):
    mask = os.urandom(4) if masked else b""
    bit = 128 if masked else 0
    length = bytes([len(data) | bit]) if len(data) < 126 else bytes([126 | bit]) + struct.pack("!H", len(data))
    payload = bytes(x ^ mask[i % 4] for i, x in enumerate(data)) if masked else data
    stream.sendall(bytes([opcode]) + length + mask + payload)


def read_frame(stream, masked=False):
    opcode, length = read_exact(stream, 2)
    assert bool(length & 128) == masked
    length &= 127
    if length == 126:
        length = struct.unpack("!H", read_exact(stream, 2))[0]
    assert length < 32768
    mask = read_exact(stream, 4) if masked else b""
    payload = read_exact(stream, length)
    return opcode, bytes(x ^ mask[i % 4] for i, x in enumerate(payload)) if masked else payload


def certificate(directory, name):
    key, cert = (directory / f"{name}.{ext}" for ext in ("key", "pem"))
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                    "-subj", f"/CN={name}", "-addext", f"subjectAltName=DNS:{name}", "-keyout", str(key), "-out", str(cert)],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert, key)
    return context, cert, key


class NestedTLS:
    def __init__(self, proxy, context, hostname):
        self.proxy = proxy
        self.incoming, self.outgoing = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.ssl = context.wrap_bio(self.incoming, self.outgoing, server_hostname=hostname)
        self.call(self.ssl.do_handshake)

    def flush(self):
        while self.outgoing.pending:
            self.proxy.sendall(self.outgoing.read())

    def call(self, operation, *args):
        while True:
            try:
                result = operation(*args)
                self.flush()
                return result
            except ssl.SSLWantWriteError:
                self.flush()
            except ssl.SSLWantReadError:
                self.flush()
                data = self.proxy.recv(16384)
                if not data:
                    raise EOFError("tunnel closed")
                self.incoming.write(data)

    def recv(self, n):
        return self.call(self.ssl.read, n)

    def sendall(self, data):
        while data:
            data = data[self.call(self.ssl.write, data):]


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@contextlib.contextmanager
def serve(handler):
    with Server(("127.0.0.1", 0), handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_address[1]
        finally:
            server.shutdown()
            thread.join()


VOICE='voice.fixture.test'
REASON='reason.fixture.test'
SEARCH='search.fixture.test'
PROXY='proxy.fixture.test'
PROXY_AUTH=b'Basic '+base64.b64encode(b'fixture:proxy-only')
KEYS={VOICE:b'Bearer fake-voice-key',REASON:b'Bearer fake-reason-key',SEARCH:b'Bearer fake-search-key'}
PCM=base64.b64encode(struct.pack('<640h',*([31]*640))).decode()
errors=[];seen={VOICE:[],REASON:[],SEARCH:[],PROXY:[]}

class Core:
    def __init__(self,binary):self.p=subprocess.Popen([binary],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    def call(self,op,**kw):
        self.p.stdin.write(json.dumps(dict(op=op,**kw))+'\n');self.p.stdin.flush()
        line=self.p.stdout.readline()
        if not line:raise AssertionError('native core exited')
        return json.loads(line)
    def close(self):
        self.p.stdin.close();self.p.stdout.close();assert self.p.wait(timeout=10)==0

def fields(raw):return {k.lower():v.strip() for k,v in (line.split(b':',1) for line in raw.split(b'\r\n')[1:] if b':' in line)}
def send_response(stream,status,body,chunked=False):
    data=json.dumps(body).encode()
    if chunked:
        chunks=b''.join(f'{len(data[i:i+31]):x}\r\n'.encode()+data[i:i+31]+b'\r\n' for i in range(0,len(data),31))+b'0\r\n\r\n'
        raw=f'HTTP/1.1 {status} Fixture\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n'.encode()+chunks
    else:raw=f'HTTP/1.1 {status} Fixture\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n'.encode()+data
    stream.sendall(raw)

def fixture(name,tls):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                self.request.settimeout(5);self.request.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
                with tls.wrap_socket(self.request,server_side=True) as stream:self.session(stream)
            except (EOFError,ssl.SSLError,ConnectionError,OSError):pass
            except Exception as e:errors.append(type(e).__name__+': '+str(e))
        def session(self,stream):
            raw=header(stream);f=fields(raw);auth=f.get(b'authorization');seen[name].append(auth)
            assert b'proxy-authorization' not in f
            if auth!=KEYS[name]:send_response(stream,429 if auth==b'Bearer rate-fixture' else 401,{});return
            line=raw.split(b'\r\n')[0]
            if name==VOICE:
                assert line==b'GET /custom/live HTTP/1.1'
                accept=base64.b64encode(hashlib.sha1(f[b'sec-websocket-key']+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                stream.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\n\r\n')
                _,payload=read_frame(stream,True);session=json.loads(payload)['session'];assert session['model']=='fixture-live' and session['delegation']['type']=='client'
                events=[dict(type='session.started',session=dict(audio=dict(format=dict(type='audio/pcm',rate=16000)))),
                        dict(type='session.output_audio.delta',delta=PCM),
                        dict(type='session.input_transcript.delta',event_id='input',delta='加入测试条目，然后搜索天气'),
                        dict(type='decision.event',source_event_id='input',source_event_type='session.input_transcript.delta',event=dict(type='decision.completed',decision=dict(answers=[dict(name='interaction',choice='addressed')]))),
                        dict(type='session.delegation.created',delegation=dict(id='network-task',target='client'))]
                for e in events:frame(stream,json.dumps(e).encode())
                read_frame(stream,True) # Keep voice TLS alive during backend HTTP work.
                return
            assert line.startswith(b'POST /custom/')
            data=json.loads(read_exact(stream,int(f[b'content-length'])))
            if name==SEARCH:
                if b'/tavily ' in line:body=dict(results=[dict(title='Fixture weather',url='https://source.fixture.test/weather',content='sunny')])
                elif b'/extract ' in line:body=dict(results=[dict(url='https://source.fixture.test/weather',raw_content='public page')])
                else:body=dict(status='completed',output=[dict(content=[dict(type='output_text',text='sunny',annotations=[dict(type='url_citation',url='https://source.fixture.test/weather',title='Weather')])])])
            else:
                chat=b'/chat ' in line
                continued=any(x.get('role')=='tool' for x in data.get('messages',[])) if chat else any(x.get('type')=='function_call_output' for x in data.get('input',[]))
                if continued:
                    assert 'source.fixture.test' in json.dumps(data)
                    body=dict(choices=[dict(finish_reason='stop',message=dict(role='assistant',content='Completed from actual tool results.'))]) if chat else dict(status='completed',output=[dict(type='message',role='assistant',content=[dict(type='output_text',text='Completed from actual tool results.')])])
                else:
                    functions=[dict(name='family_list',arguments=json.dumps(dict(group='shopping',operation='add',entry='fixture item'))),dict(name='web_search',arguments=json.dumps(dict(query='weather')))]
                    calls=[dict(type='function',id='call-'+str(i),function=f) for i,f in enumerate(functions)] if chat else [dict(type='function_call',call_id='call-'+str(i),**f) for i,f in enumerate(functions)]
                    body=dict(choices=[dict(finish_reason='tool_calls',message=dict(role='assistant',content=None,tool_calls=calls))]) if chat else dict(status='completed',output=calls)
            send_response(stream,200,body,chunked=True)
    return Handler

def proxy_fixture(tls,ports):
    class Handler(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                self.request.settimeout(5)
                with tls.wrap_socket(self.request,server_side=True) as client:
                    raw=header(client);f=fields(raw);seen[PROXY].append(f.get(b'proxy-authorization'));assert b'authorization' not in f
                    if f.get(b'proxy-authorization')!=PROXY_AUTH:client.sendall(b'HTTP/1.1 407 Proxy Authentication Required\r\nContent-Length: 0\r\n\r\n');return
                    target=raw.split(b' ')[1].decode();host,port=target.rsplit(':',1)
                    if host not in ports or int(port)!=ports[host]:client.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n');return
                    with socket.create_connection(('127.0.0.1',ports[host]),timeout=5) as upstream:
                        client.sendall(b'HTTP/1.1 200 Connection established\r\n\r\n');tail=b''
                        while True:
                            ready=[client] if client.pending() else select.select([client,upstream],[],[],5)[0]
                            if not ready:return
                            for src in ready:
                                data=src.recv(16384)
                                if not data:return
                                if src is client:
                                    assert not any(key.split(b' ',1)[1] in tail+data for key in KEYS.values());tail=(tail+data)[-32:]
                                (upstream if src is client else client).sendall(data)
            except (EOFError,ssl.SSLError,ConnectionError,OSError):pass
            except Exception as e:errors.append(type(e).__name__+': '+str(e))
    return Handler

@contextlib.contextmanager
def connect(host,ports,contexts,proxy_port=None,proxy_auth=PROXY_AUTH,wrong_certificate=False,wrong_inner=False,metrics=None):
    started=time.perf_counter();outer_host=PROXY if proxy_port else host
    ca=ssl.create_default_context(cafile=str(contexts[outer_host][1]))
    if wrong_certificate:ca=ssl.create_default_context(cafile=str(contexts[SEARCH if host!=SEARCH else VOICE][1]))
    with socket.create_connection(('127.0.0.1',proxy_port or ports[host]),timeout=5) as raw:
        raw.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
        with ca.wrap_socket(raw,server_hostname=outer_host) as stream:
            outer=time.perf_counter();connected=outer
            if proxy_port:
                stream.sendall(f'CONNECT {host}:{ports.get(host,443)} HTTP/1.1\r\nHost: {host}\r\nProxy-Authorization: '.encode()+proxy_auth+b'\r\n\r\n')
                status=int(header(stream).split(b' ')[1]);connected=time.perf_counter()
                if status!=200:yield status,None;return
                inner=ssl.create_default_context(cafile=str(contexts[SEARCH if wrong_inner else host][1]));tunnel=NestedTLS(stream,inner,host)
            else:tunnel=stream
            if metrics is not None:metrics.append([(outer-started)*1000,(connected-outer)*1000,(time.perf_counter()-connected)*1000])
            yield 200,tunnel

def upgrade(stream,port,key=b'Bearer fake-voice-key'):
    nonce=base64.b64encode(os.urandom(16))
    stream.sendall(f'GET /custom/live HTTP/1.1\r\nHost: {VOICE}:{port}\r\nAuthorization: '.encode()+key+b'\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\nSec-WebSocket-Key: '+nonce+b'\r\n\r\n')
    raw=header(stream);status=int(raw.split(b' ')[1])
    if status==101:assert base64.b64encode(hashlib.sha1(nonce+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest()) in raw
    return status

def http_call(core,r,ports,contexts,proxy_port):
    u=urlsplit(r['url'])
    with connect(u.hostname,ports,contexts,proxy_port) as (status,stream):
        assert status==200;data=r['body'].encode()
        stream.sendall(f'POST {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nAuthorization: {r["authorization"]}\r\nContent-Length: {len(data)}\r\nConnection: close\r\n\r\n'.encode()+data)
        core.call('http_begin')
        while True:
            chunk=stream.recv(127)
            out=core.call('http_feed',data=chunk.decode('ascii'),eof=not chunk)
            assert out['ok']
            if out['done']:break
        return core.call('complete',token=r['token'],status=out['status'],body=out['body'],now=120)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('services');ap.add_argument('--cycles',type=int,default=100,choices=range(1,1001));args=ap.parse_args()
    metrics=[];started=time.perf_counter();cycles=0
    with tempfile.TemporaryDirectory(prefix='pikoo-service-network-') as temp,contextlib.ExitStack() as stack:
        directory=Path(temp);contexts={name:certificate(directory,name) for name in (VOICE,REASON,SEARCH,PROXY)}
        ports={name:stack.enter_context(serve(fixture(name,contexts[name][0]))) for name in (VOICE,REASON,SEARCH)}
        proxy_port=stack.enter_context(serve(proxy_fixture(contexts[PROXY][0],ports)))
        core=Core(args.services)
        try:
            for i in range(args.cycles):
                proxied=i%2==1;chat=(i//2)%2==1;hosted=(i//4)%2==1
                c=json.loads((Path(__file__).resolve().parents[1]/'examples/device.example.json').read_text())
                c['live'].update(url=f'wss://{VOICE}:{ports[VOICE]}/custom/live',api_key='fake-voice-key',model='fixture-live')
                c['llm'].update(protocol='openai_chat_completions' if chat else 'openai_responses',url=f'https://{REASON}:{ports[REASON]}/custom/'+('chat' if chat else 'responses'),api_key='fake-reason-key',model='fixture-reason')
                c['search']=dict(enabled=True,protocol='openai_responses' if hosted else 'tavily',url=f'https://{SEARCH}:{ports[SEARCH]}/custom/'+('responses' if hosted else 'tavily'),api_key='fake-search-key',model='fixture-search')
                assert core.call('configure',config=c)['valid']
                with connect(VOICE,ports,contexts,proxy_port if proxied else None,metrics=metrics) as (status,stream):
                    assert status==200 and upgrade(stream,ports[VOICE])==101
                    out=core.call('live_start',now=100);frame(stream,out['send'][0].encode(),True)
                    request=None
                    for _ in range(5):
                        _,payload=read_frame(stream);out=core.call('receive',message=json.loads(payload),now=110)
                        if out['requests']:request=out['requests'][0]
                    assert request
                    for _ in range(4):
                        out=http_call(core,request,ports,contexts,proxy_port if proxied else None)
                        if out['replies']:break
                        request=out['requests'][0]
                    assert out['replies'] and not out['busy']
                    assert json.loads(out['snapshot'])['shopping']==['fixture item']
                    frame(stream,out['send'][0].encode(),True)
                cycles+=1
            for key,expected in [(b'Bearer wrong-key',401),(b'Bearer rate-fixture',429)]:
                with connect(VOICE,ports,contexts,proxy_port) as (_,stream):assert upgrade(stream,ports[VOICE],key)==expected
            with connect(VOICE,ports,contexts,proxy_port,proxy_auth=b'Basic wrong') as (status,_):assert status==407
            with connect('blocked.fixture.test',ports,contexts,proxy_port) as (status,_):assert status==403
            try:
                with connect(VOICE,ports,contexts,wrong_certificate=True):raise AssertionError('certificate accepted')
            except ssl.SSLCertVerificationError:pass
            try:
                with connect(VOICE,ports,contexts,proxy_port,wrong_inner=True):raise AssertionError('inner certificate accepted')
            except ssl.SSLCertVerificationError:pass
            # Actual reasoning HTTP 401/429 must not run a supplied tool batch.
            for auth in ['Bearer wrong-key','Bearer rate-fixture']:
                r=core.call('start',id='http-fault',history=[],now=100)['requests'][0];r['authorization']=auth
                out=http_call(core,r,ports,contexts,proxy_port)
                assert out['replies'] and not out['requests']
            # Close a tunnel mid-frame and establish a fresh connection.
            with connect(VOICE,ports,contexts,proxy_port) as (_,stream):assert upgrade(stream,ports[VOICE])==101
            with connect(VOICE,ports,contexts,proxy_port) as (_,stream):assert upgrade(stream,ports[VOICE])==101
        finally:core.close()
    assert not errors,errors
    assert all(v for v in seen.values())
    result=dict(cycles_passed=cycles,independent_service_credentials=True,direct_and_https_connect=True,llm_protocols=2,search_protocols=2,certificate_auth_and_disconnect_faults=True,wall_seconds=round(time.perf_counter()-started,3))
    for index,name in enumerate(('outer_tls_ms','connect_ms','inner_tls_ms')):
        values=sorted(x[index] for x in metrics);result[name]={'p50':round(values[(len(values)-1)//2],3),'p95':round(values[int((len(values)-1)*.95)],3)}
    print(json.dumps(result))
if __name__=='__main__':main()
