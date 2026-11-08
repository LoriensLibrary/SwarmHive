"""Record model dispatch inputs and seal outputs from trusted runtime state.

The caller resolves inputs from the authoritative store and binds the actor from
the authenticated execution context. This module observes the request constructed
by the harness. It cannot infer what the model relied on internally.
"""
from dataclasses import dataclass
import hashlib
import json


def _json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


@dataclass(frozen=True)
class ArtifactInput:
    artifact_id: str
    version: int
    body: str

    def __post_init__(self):
        if not isinstance(self.artifact_id, str) or not self.artifact_id:
            raise ValueError('artifact id must be a nonempty string')
        if type(self.version) is not int or self.version < 1:
            raise ValueError('artifact version must be a positive integer')
        if not isinstance(self.body, str):
            raise ValueError('artifact body must be text')


@dataclass(frozen=True)
class DispatchRecord:
    actor: str
    request_json: bytes
    # Immutable (id, version, content SHA-256) triples.
    artifacts: tuple[tuple[str, int, str], ...]

    @property
    def request_sha256(self):
        return hashlib.sha256(self.request_json).hexdigest()

    def dependencies(self):
        return [{'id': artifact, 'ver': version} for artifact, version, _ in self.artifacts]

    def trace_metadata(self):
        return {
            'actor': self.actor,
            'request_sha256': self.request_sha256,
            'delivered_artifacts': [
                {'id': artifact, 'ver': version, 'content_sha256': digest}
                for artifact, version, digest in self.artifacts
            ],
        }


def dispatch_stage(send, *, actor, model, instructions, task, inputs, corrections, max_tokens,
                   history_metadata=None, thinking=None, output_schema=None):
    """Call a trusted send(**request) adapter and return its response and receipt.

    corrections is runtime-authenticated notice metadata. If a stage reads an
    artifact body, include that body in inputs, even when it is stale. The sender
    must transmit this request without adding unseen documents or tool results.
    """
    if not isinstance(actor, str) or not actor:
        raise ValueError('authenticated actor is required')
    bodies = {}
    for artifact in inputs:
        key = (artifact.artifact_id, artifact.version)
        previous = bodies.setdefault(key, artifact.body)
        if previous != artifact.body:
            raise ValueError('conflicting bodies for one immutable artifact version')

    user_content = {
        'task': task,
        'corrections': corrections,
        'artifacts': [{'id': aid, 'ver': ver, 'body': body} for (aid, ver), body in bodies.items()],
    }
    if history_metadata is not None:
        user_content['history_metadata'] = history_metadata
    request = {
        'model': model,
        'system': instructions,
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': _json_bytes(user_content).decode('utf-8')}],
    }
    if thinking is not None:
        request['thinking'] = thinking
    if output_schema is not None:
        request['output_config'] = {'format': {'type': 'json_schema', 'schema': output_schema}}
    receipt = DispatchRecord(actor, _json_bytes(request), tuple(
        (aid, ver, hashlib.sha256(body.encode('utf-8')).hexdigest())
        for (aid, ver), body in bodies.items()
    ))
    response = send(**json.loads(receipt.request_json))
    return response, receipt


def seal_stage_output(seal, receipt, *, artifact_id, version, body):
    """Invoke the operator's seal API using the dispatch receipt's inputs only."""
    return seal(receipt.actor, artifact_id, version, body, receipt.dependencies())
