"""Conservative first-trigger replay gate for a local phonetic veto experiment.

Rejecting the first trigger cannot prove a negative clip safe if that clip extends
past the declared rearm guard. Such inputs require a full causal replay instead.
No household or sealed test material may select this development candidate.
"""
import copy
import math
from streaming_gate import assess


def combine(primary, prepared, results, policy):
    if primary['threshold'] != policy['primary_threshold']:
        raise ValueError('Primary threshold mismatch')
    if primary['models']['candidate'] != policy['primary_model_sha256']:
        raise ValueError('Primary model mismatch')
    rows=primary['details']
    if len(prepared)!=len(rows) or len({r['id'] for r in prepared})!=len(rows):
        raise ValueError('Incomplete or duplicated prepared corpus')
    if len({r['id'] for r in results})!=len(results):
        raise ValueError('Duplicate command replay')
    by_id={r['id']:r for r in prepared};commands={r['id']:r for r in results}
    candidates={r['id'] for r in prepared if r['stage1_trigger_sample'] is not None}
    if set(commands)!=candidates:
        raise ValueError('Every primary trigger requires a complete replay')
    combined=copy.deepcopy(primary)
    for index,row in enumerate(combined['details']):
        replay=by_id[index];trigger=replay['stage1_trigger_sample']
        if row['sha256']!=replay['sha256'] or row['label']!=replay['label']:
            raise ValueError('Replay identity mismatch')
        if row.get('evaluation_only') or row.get('frozen_holdout') or str(row['source']).startswith('private-'):
            raise ValueError('Protected recordings cannot select a candidate')
        if bool(trigger is not None)!=bool(row['detected']['candidate']):
            raise ValueError('Causal primary trigger differs from full primary evaluation')
        if bool(row['scores']['candidate']>=primary['threshold'])!=bool(row['detected']['candidate']):
            raise ValueError('Inconsistent primary score and decision')
        accepted=trigger is not None
        if accepted:
            result=commands[index]
            if not isinstance(result['top_id'],int) or not 0<=result['top_id']<=10 or not math.isfinite(result['top_probability']) or not 0<=result['top_probability']<=1:
                raise ValueError('Invalid verifier score')
            if result['top_id']==0 and result['top_probability']!=0:
                raise ValueError('Unknown command cannot have a detection probability')
            if result['label']!=row['label'] or result['sha256']!=row['sha256']:
                raise ValueError('Command replay provenance mismatch')
            if result['samples']!=policy['pre_roll_samples']+policy['lookahead_samples']+policy['trailing_silence_samples']:
                raise ValueError('Replay window mismatch')
            veto=result['top_id'] in policy['veto_command_ids'] and result['top_probability']>=policy['veto_probability']
            accepted=not veto
            # All other negative clips had no primary trigger at all. For a
            # rejected negative, prove rearming cannot happen inside this clip.
            end_sample=round((row['seconds']+2)*16000)
            rearm_sample=trigger+round(policy['rearm_guard_ms']*16)
            if not row['label'] and veto and end_sample>rearm_sample:
                raise ValueError('Negative extends beyond rearm; full causal replay required')
            row['phonetic_veto']={'top_id':result['top_id'],'probability':result['top_probability'],'rejected':veto}
        row['detected']['candidate']=accepted
    combined['pipeline']='primary streaming KWS plus fixed local phonetic veto'
    return combined


def gate(primary,prepared,results,policy,quality_policy,legacy_hashes,primary_bytes):
    evaluation=combine(primary,prepared,results,policy)
    report=assess(evaluation,quality_policy,legacy_hashes,primary_bytes)
    report.update(pipeline=evaluation['pipeline'],policy=policy,household_used_for_selection=False,
                  inference_and_human_acceptance='pending; offline replay is not microphone acceptance')
    return report,evaluation
