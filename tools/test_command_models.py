import struct
import unittest
from check_command_models import validate


def pack(include_fst=True):
    models={'mn7_cn':['mn7_data','mn7_index','vocab','_MODEL_INFO_']}
    if include_fst:models['fst']=['commands_cn.txt']
    header_size=4+sum(36+40*len(files) for files in models.values())
    output=struct.pack('<I',len(models));payload=b''
    for model,files in models.items():
        output+=struct.pack('<32sI',model.encode(),len(files))
        for name in files:
            output+=struct.pack('<32sII',name.encode(),header_size+len(payload),1);payload+=b'x'
    return output+payload


class CommandPackTest(unittest.TestCase):
    def test_missing_dictionary_is_rejected_before_hardware_startup(self):
        self.assertEqual(validate(pack())['status'],'command-model-pack-valid')
        with self.assertRaisesRegex(ValueError,'fst'):validate(pack(False))
    def test_truncated_or_out_of_bounds_pack_is_rejected(self):
        for data in [b'',pack()[:-1],b'\xff'*4]:
            with self.assertRaises(ValueError):validate(data)
        malformed=bytearray(pack());struct.pack_into('<I',malformed,72,0)
        with self.assertRaisesRegex(ValueError,'outside'):validate(malformed)


if __name__=='__main__':unittest.main()
