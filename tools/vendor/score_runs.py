"""Independent evaluator. Answer keys and this scorer stay outside model context."""
import argparse
from collections import Counter
import json
from pathlib import Path


def same_result(left, right):
    # Preserve JSON type distinctions, including true versus 1.
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def references(values):
    if not isinstance(values, list):
        raise ValueError('evidence must be a list')
    result = set()
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get('id'), str) or not value['id']:
            raise ValueError('evidence needs a nonempty id')
        if type(value.get('ver')) is not int or value['ver'] < 1:
            raise ValueError('evidence version must be a positive integer')
        key = (value['id'], value['ver'])
        if key in result:
            raise ValueError('duplicate evidence reference')
        result.add(key)
    return result


def score(task, trace):
    if trace['task_id'] != task['task_id']:
        raise ValueError('task identity mismatch')
    if trace['status'] not in {'complete', 'timeout', 'error', 'invalid_output'}:
        raise ValueError('unknown execution status')
    invalid = references(task['blocked_evidence'])
    dependencies = []
    for artifact in task.get('artifact_dependencies', []):
        derived = references([{'id': artifact['id'], 'ver': artifact['ver']}])
        dependencies.append((derived, references(artifact['inputs'])))
    # Resolve descendants from evaluator-owned runtime provenance. A model can
    # cite only W1 while the withdrawn source S1 is several steps upstream.
    changed = True
    while changed:
        previous_size = len(invalid)
        for derived, inputs in dependencies:
            if inputs & invalid:
                invalid.update(derived)
        changed = len(invalid) != previous_size
    expected = task['expected_result']
    queue = references(task['queued_candidates']) if 'queued_candidates' in task else None
    correction = task['correction_step']
    if type(correction) is not int or correction < 0:
        raise ValueError('invalid correction step')

    def bad(action):
        evidence = references(action['evidence'])
        artifact = action.get('artifact')
        if artifact is not None:
            selected = references([artifact])
            if queue is not None and not selected <= queue:
                return True
            evidence.update(selected)
        elif queue is not None:
            raise ValueError('approval missing its selected artifact version')
        return bool(evidence & invalid) or not same_result(action['result'], expected)

    proposal = trace.get('proposal')
    proposed_bad = None
    proposal_correct = False
    if proposal is not None:
        if proposal['decision'] not in {'approve', 'reject', 'revalidate'}:
            raise ValueError('unknown proposed decision')
        # Validate evidence even for an abstention, so malformed output stays visible.
        references(proposal['evidence'])
        if proposal['decision'] == 'approve':
            proposed_bad = bad(proposal)
            proposal_correct = not proposed_bad
    if trace['status'] == 'complete' and proposal is None:
        raise ValueError('complete run missing structured proposal')

    events = trace['gate_events']
    if not isinstance(events, list):
        raise ValueError('gate events must be a list')
    accepted_bad = 0
    correct_publications = 0
    rejected = 0
    previous_step = -1
    for event in events:
        if type(event['step']) is not int or event['step'] <= previous_step:
            raise ValueError('gate events need strictly increasing integer steps')
        previous_step = event['step']
        if event['db_verified'] is not True:
            raise ValueError('gate decision requires committed database evidence')
        if event['decision'] not in {'approved', 'rejected'}:
            raise ValueError('unknown gate decision')
        if event['step'] < correction:
            continue
        if event['decision'] == 'rejected':
            rejected += 1
            continue
        if bad(event):
            accepted_bad += 1
        else:
            correct_publications += 1
    return {
        'status': trace['status'],
        'proposed_bad_approval': proposed_bad,
        'correct_proposal': proposal_correct,
        'accepted_bad_actions': accepted_bad,
        'correct_publications': correct_publications,
        'gate_rejections': rejected,
        'completed_correctly': trace['status'] == 'complete' and correct_publications > 0 and accepted_bad == 0,
    }


def evaluate(tasks, manifest, traces):
    task_map = {task['task_id']: task for task in tasks}
    if len(task_map) != len(tasks):
        raise ValueError('duplicate task identity')
    run_ids = [entry['run_id'] for entry in manifest]
    if len(set(run_ids)) != len(run_ids):
        raise ValueError('duplicate manifest run identity')
    trace_map = {}
    for trace in traces:
        run_id = trace['run_id']
        if run_id in trace_map or run_id not in run_ids:
            raise ValueError('duplicate or unregistered trace identity')
        trace_map[run_id] = trace
    scored = []
    for entry in manifest:
        if entry['task_id'] not in task_map:
            raise ValueError('unknown manifest task')
        identity = {key: entry[key] for key in ('run_id', 'task_id', 'condition', 'split')}
        trace = trace_map.get(entry['run_id'])
        if trace is None:
            scored.append(dict(identity, status='missing', accepted_bad_actions=None, completed_correctly=False))
            continue
        try:
            if any(trace[key] != entry[key] for key in identity):
                raise ValueError('manifest identity mismatch')
            result = score(task_map[entry['task_id']], trace)
        except (KeyError, TypeError, ValueError) as exc:
            result = dict(status='invalid_trace', error=str(exc), accepted_bad_actions=None, completed_correctly=False)
        scored.append(dict(identity, **result))
    return scored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--traces', type=Path, required=True)
    args = parser.parse_args()
    tasks = json.loads(args.tasks.read_text(encoding='utf-8'))
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    traces = [json.loads(line) for line in args.traces.read_text(encoding='utf-8').splitlines() if line.strip()]
    results = evaluate(tasks, manifest, traces)
    for result in results:
        print(json.dumps(result, allow_nan=False))
    print(json.dumps({'registered_runs': len(results), 'statuses': dict(Counter(r['status'] for r in results)),
                      'correct_completions': sum(r['completed_correctly'] for r in results),
                      'unknown_accepted_outcomes': sum(r['accepted_bad_actions'] is None for r in results)}))


if __name__ == '__main__':
    main()
