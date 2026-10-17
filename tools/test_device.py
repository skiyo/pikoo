import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import monitor_control

spec=importlib.util.spec_from_file_location('device',Path(__file__).with_name('device.py'))
device=importlib.util.module_from_spec(spec);spec.loader.exec_module(device)

def entry(label,offset,size,kind=1):
    return struct.pack('<HBBII16sI',0x50aa,kind,0,offset,size,label.encode(),0)

class DeviceSafetyTests(unittest.TestCase):
    def test_monitor_from_another_checkout_is_never_controlled(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'PIKOO_PRIVATE_DIR':tmp}):
            port='/dev/pikoo-test'
            monitor_control.registry_path(port).write_text(json.dumps({'port':port,'project':'/another/project','socket':'/tmp/another.sock'}))
            with self.assertRaisesRegex(RuntimeError,'another project'):monitor_control.registered_socket(port)

    def test_rejects_overlapping_or_out_of_flash_partitions(self):
        for raw in [entry('a',0x9000,0x10000)+entry('b',0x10000,0x20000),entry('a',0xfff000,0x2000)]:
            with self.assertRaises(ValueError):device.partitions(raw)

    def test_rejects_image_crossing_into_credentials_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            b=Path(tmp);(b/'partition_table').mkdir()
            (b/'partition_table/partition-table.bin').write_bytes(entry('nvs',0x9000,0x10000)+entry('factory',0x20000,6*1024*1024,0))
            (b/'project_description.json').write_text(json.dumps({'target':'esp32s3','project_name':'pikoo'}))
            (b/'pikoo-board.json').write_text(json.dumps({'board':'waveshare-dualeye-1.28','flash_bytes':device.FLASH_SIZE,'layout':1}))
            (b/'partition.bin').write_bytes(bytes(8192))
            (b/'flasher_args.json').write_text(json.dumps({'flash_files':{'0x8000':'partition.bin'}}))
            with self.assertRaisesRegex(ValueError,'private NVS'):device.build_files(b)
            (b/'flasher_args.json').write_text(json.dumps({'flash_files':{'0x20000':'../escape.bin'}}))
            with self.assertRaises(ValueError):device.build_files(b)

if __name__=='__main__':unittest.main()
