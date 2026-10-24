"""Experimental content-comparator boundary fix; not the live default.

ASCII token boundaries permit a known English nickname immediately after
Chinese, while retaining unexpected English words/digits. This changes no
label, target pronunciation or recognizer observation. Integrate only through
a versioned corpus review after existing source-fingerprinted jobs finish.
"""
import re
from review_google_corpus import normalize
from review_local_corpus import content_approved as original_content_approved


def content_approved(row, transcript):
    if not row.get('english_phonetic_surface'):
        return original_content_approved(row, transcript)
    if (row.get('label') != 1 or row.get('expected_spoken_transcript') != '你好皮酷'
            or row.get('text') not in {'Ni hao, pee coo.', 'Ni hao! Pee koo!'}):
        return False
    text = re.sub(r'(?<![A-Za-z0-9])(?:ni[\s-]*hao|knee[\s-]*how)(?![A-Za-z0-9])',
                  '你好', transcript, flags=re.I)
    text = re.sub(r'(?<![A-Za-z0-9])(?:pee[\s-]*(?:coo|koo)|pikoo|piku|peekoo)(?![A-Za-z0-9])',
                  '皮酷', text, flags=re.I)
    unexpected = any(char.isalnum() and not '\u4e00' <= char <= '\u9fff' for char in text)
    return not unexpected and normalize(text) == '你好皮酷'
