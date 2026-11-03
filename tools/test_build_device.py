# SPDX-License-Identifier: Apache-2.0
"""Build request safety with a fake compiler; never opens USB or loads weights."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PrivateBuildSafety(unittest.TestCase):
    def run_build(self, directory, policy=True, version='ESP-IDF v5.5.5', artifact_version=True):
        root = Path(directory).resolve()
        fake = root/'idf.py'
        fake.write_text('#!' + sys.executable + '\nimport os,sys,json\n'
            'if "--version" in sys.argv:print(os.environ["FAKE_IDF_VERSION"])\n'
            'else:open(os.environ["FAKE_BUILD_REQUEST"],"w").write(json.dumps(sys.argv[1:]))\n')
        fake.chmod(0o700)
        model = root/'hi_pikoo.tflite'; model.write_bytes(b'fixture-only-not-a-model')
        if policy: (root/'wake-policy.json').write_text('{}')
        output = root/'private-build'
        env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
            'IDF_PATH': str(root/'unused-idf'), 'FAKE_IDF_VERSION': version,
            'FAKE_BUILD_REQUEST': str(root/'request.json'), 'PIKOO_BUILD_DIR': str(output),
            'PIKOO_FIRMWARE_VERSION': '0.2.2-dev-fixture', 'PIKOO_ALLOW_TRIAL_WAKE': '0'}
        for name in ('PIKOO_WAKE_POLICY', 'PIKOO_WAKE_VETO_PACK'):
            env.pop(name, None)
        if not artifact_version: env.pop('PIKOO_FIRMWARE_VERSION', None)
        result = subprocess.run(['bash', str(Path(__file__).with_name('build-device.sh')), str(model)],
            env=env, capture_output=True, text=True, timeout=10)
        return result, root, output

    def test_private_build_uses_separate_config_and_never_flashes_or_migrates_volume(self):
        with tempfile.TemporaryDirectory() as folder:
            result, root, output = self.run_build(folder)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = json.loads((root/'request.json').read_text())
            self.assertEqual(args[args.index('-B')+1], str(output))
            self.assertIn('-DSDKCONFIG='+str(output/'sdkconfig'), args)
            self.assertIn('-DPIKOO_WAKE_POLICY='+str(root/'wake-policy.json'), args)
            self.assertIn('-DPROJECT_VER=0.2.2-dev-fixture', args)
            for flag in ('WAKE_VETO', 'AUDIO_CAPTURE_BENCHMARK', 'WAKE_BENCHMARK', 'COMMAND_BENCHMARK',
                         'VOLUME_BOOT_UPGRADE', 'WAKE_ALLOW_TRIAL'):
                self.assertIn('-DPIKOO_'+flag+'=OFF', args)
            self.assertEqual(args[-1], 'build')
            self.assertNotIn('flash', args)
            self.assertNotIn('--port', args)

    def test_hi_model_without_policy_is_rejected_before_new_build_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            result, root, output = self.run_build(folder, policy=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('matching frozen wake-policy', result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse((root/'request.json').exists())

    def test_wrong_toolchain_does_not_create_or_reconfigure_build(self):
        with tempfile.TemporaryDirectory() as folder:
            result, root, output = self.run_build(folder, version='ESP-IDF v5.4.2')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('requires ESP-IDF 5.5.5', result.stderr)
            self.assertFalse(output.exists())
            self.assertFalse((root/'request.json').exists())

    def test_default_version_keeps_bash32_compatible_build_command(self):
        with tempfile.TemporaryDirectory() as folder:
            result, root, _ = self.run_build(folder, artifact_version=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            args = json.loads((root/'request.json').read_text())
            self.assertFalse(any(s.startswith('-DPROJECT_VER=') for s in args))


if __name__ == '__main__': unittest.main()
