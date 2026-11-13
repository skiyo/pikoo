# Copyright 2026 Pikoo contributors. SPDX-License-Identifier: Apache-2.0
import importlib.util,json,unittest,subprocess,tempfile,os
from pathlib import Path
spec=importlib.util.spec_from_file_location('public_check',Path(__file__).with_name('check-public-repo.py'))
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class PublicArtifacts(unittest.TestCase):
 def test_secrets_are_reported_without_echoing_values(self):
  key='sk-proj-'+'sensitive'*8
  issues=module.check_file('src/example.py',('key="'+key+'"').encode())
  self.assertTrue(issues);self.assertNotIn(key,json.dumps(issues))
 def test_private_artifacts_are_blocked_but_approved_weights_are_allowed(self):
  for name in ['.env.local','device.nvs.bin','factory-full.bin','family.wav','private/profile.json','training/candidate.weights.h5','models/other.tflite']:
   self.assertTrue(module.check_file(name,b'fixture'),name)
  for name in module.REVIEWED_WEIGHTS:self.assertFalse(module.check_file(name,b'fixture'))
 def test_examples_require_placeholders(self):
  self.assertFalse(module.check_file('examples/config.json',b'{"api_key":"YOUR_API_KEY","network":{}}'))
  self.assertTrue(module.check_file('examples/config.json',b'{"api_key":"a-private-value"}'))
 def test_download_respects_official_origin_and_existing_proxy(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);token=root/'token';token.write_text('fixture-token');log=root/'request.json'
   hf=root/'hf';hf.write_text('#!/usr/bin/env python3\nimport json,os\njson.dump({k:os.environ.get(k) for k in ("HF_ENDPOINT","HTTPS_PROXY")},open(os.environ["AUDIT_REQUEST"],"w"))\n');hf.chmod(0o700)
   env={**os.environ,'HF_TOKEN_PATH':str(token),'HTTPS_PROXY':'http://127.0.0.1:8888','PATH':str(root)+os.pathsep+os.environ['PATH'],'AUDIT_REQUEST':str(log)};env.pop('HF_ENDPOINT',None)
   subprocess.run(['bash',str(Path(__file__).resolve().parents[1]/'training/download_childmandarin.sh'),str(root/'data')],env=env,check=True)
   result=json.loads(log.read_text());self.assertEqual(result,{'HF_ENDPOINT':'https://huggingface.co','HTTPS_PROXY':'http://127.0.0.1:8888'})
 def test_unresolved_model_blocks_public_packaging(self):
  script=Path(__file__).with_name('package-release.py')
  spec=importlib.util.spec_from_file_location('release_package',script)
  import sys
  sys.path.insert(0,str(script.parent))
  try:
   release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)
   with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);folder=root/'models/hi-pikoo';folder.mkdir(parents=True)
    model=folder/'hi_pikoo.tflite';model.write_bytes(b'fixture')
    status={'status':'pending_permission','model_sha256':release.sha(model),'clearance_evidence':[]}
    for state,evidence,digest in [('pending_permission',[],release.sha(model)),('cleared',[],release.sha(model)),('cleared',['documented-permission'],'wrong-hash')]:
     status.update(status=state,clearance_evidence=evidence,model_sha256=digest)
     (folder/'distribution-status.json').write_text(json.dumps(status))
     with self.assertRaisesRegex(ValueError,'redistribution permission is unresolved'):
      release.require_model_clearance(root)
    status.update(status='cleared',clearance_evidence=['documented-permission'],model_sha256=release.sha(model))
    (folder/'documented-permission').write_text('Fixture permission record')
    (folder/'distribution-status.json').write_text(json.dumps(status));release.require_model_clearance(root)
    status['status']='maintainer_confirmed'
    (folder/'distribution-status.json').write_text(json.dumps(status));release.require_model_clearance(root)
  finally:sys.path.pop(0)
