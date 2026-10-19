"""Additional disclosed development gate; never replaces legacy checks or tests."""
import math
from level_tone_scope import identity,focused
from streaming_gate import count


def assess(evaluation,expected,base_gate,protected=()):
    if any(r['split']!='validation' or r.get('preassigned_usage')!='validation'
           or r.get('source')!='Qwen3-TTS-synthetic-local' or not r.get('synthetic')
           or r.get('real_child') or r.get('reference_audio_used') or r.get('family_inputs_used')
           or not r.get('group','').startswith('qwen-generalization-development-v1:') for r in expected):
        raise ValueError('Only preassigned fictional development conditions are eligible')
    if focused(expected,protected)!=expected:raise ValueError('Unexpected additional target pronunciation')
    rows=evaluation['details']
    if identity(rows)!=identity(expected):raise ValueError('Missing or changed additional development rows')
    if evaluation['threshold']!=.9 or evaluation.get('rolling_inferences')!=5 or evaluation.get('input_context')!={'lead_seconds':1.,'background_rms':0.}:
        raise ValueError('Additional streaming contract differs')
    mapping={r['sha256']:r for r in expected};failures=[];groups={}
    if not base_gate['passed']:failures.append('original-development-gate')
    for style in ['adult','childlike']:
        selected=[r for r in rows if r.get('synthetic_style')==style]
        values=count(selected);groups[style]=values
        if values['targets']<12 or values['non_targets']<12:failures.append(style+':insufficient-content')
        if values['hits']<math.ceil(.9*values['targets']):failures.append(style+':recall')
        english=[r for r in selected if r['label'] and 'Pikoo' in mapping[r['sha256']]['text']]
        values=count(english);groups[style+':literal-English']=values
        if values['targets']<4:failures.append(style+':insufficient-English-content')
        if values['hits']<math.ceil(.9*values['targets']):failures.append(style+':English-recall')
    total=count(rows)
    if total['false_wakes']:failures.append('additional-false-wakes')
    return {'status':'passed-additional-development' if not failures else 'failed-additional-development',
            'passed':not failures,'original_gate_required':True,'failures':failures,
            'groups':groups,'streaming_development':total,
            'independent_test':False,'household_or_real_child_accepted':False}
