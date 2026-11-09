"""Independent acceptance probes for SwarmHive's b7260e7 PostgreSQL API.

Requires psycopg 3, four real logins, and a disposable test database/branch.
Writes uniquely named fixtures and retains them as evidence. Never truncates.
No provider API calls. See README for setup and API compatibility limits.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import hashlib
import json
import os
import time
import uuid


def run(args):
    import psycopg

    names = {
        'operator': 'SWARM_TEST_OPERATOR_DSN',
        'researcher': 'SWARM_TEST_RESEARCHER_DSN',
        'writer': 'SWARM_TEST_WRITER_DSN',
        'intruder': 'SWARM_TEST_INTRUDER_DSN',
    }
    if any(not os.environ.get(key) for key in names.values()):
        raise RuntimeError('Set the four SWARM_TEST_*_DSN variables for a disposable target')

    prefix = 'lorien_' + uuid.uuid4().hex[:16]
    results = []

    def record(case, passed, **details):
        row = dict(case=case, passed=bool(passed), **details)
        results.append(row)
        print(json.dumps(row), flush=True)

    def one(conn, sql, params=()):
        return conn.execute(sql, params).fetchone()[0]

    def attempt(conn, sql, params=()):
        try:
            cursor = conn.execute(sql, params)
            value = cursor.fetchone()[0] if cursor.description else cursor.rowcount
            return {'value': value}
        except psycopg.Error as exc:
            # Do not print credentials, DSNs, or raw connection errors.
            return {'sqlstate': exc.sqlstate,
                    'message': exc.diag.message_primary if exc.sqlstate else None}

    def denied(outcome):
        return str(outcome.get('value', '')).startswith('rejected:')

    def stamp(*ids):
        return json.dumps([dict(id=i, ver=1, acked_epoch=0) for i in ids])

    publish_sql = 'SELECT exp.publish_decision(%s, %s, %s::jsonb)'
    withdraw_sql = "SELECT exp.invalidate(%s, %s, 'withdrawn')"

    with ExitStack() as stack:
        conns = {}
        identity = {}
        for purpose in (*names, 'observer'):
            key = names['operator' if purpose == 'observer' else purpose]
            c = stack.enter_context(psycopg.connect(os.environ[key], autocommit=True,
                                                    connect_timeout=8))
            db, role = c.execute('SELECT current_database(), session_user').fetchone()
            if db != args.disposable_database:
                raise RuntimeError('Connected database name does not match the declared disposable target')
            identity[purpose] = role
            c.execute("SET statement_timeout = '12s'")
            c.execute("SET lock_timeout = '8s'")
            c.execute("SET idle_in_transaction_session_timeout = '20s'")
            conns[purpose] = c
        if len({identity[purpose] for purpose in names}) != len(names):
            raise RuntimeError('Tests require four distinct authenticated login roles')
        op, researcher, writer, intruder, observer = (conns[k] for k in (
            'operator', 'researcher', 'writer', 'intruder', 'observer'))
        if not one(op, 'SELECT EXISTS(SELECT 1 FROM exp.adjudicators WHERE role=session_user)'):
            raise RuntimeError('Operator must be listed as an adjudicator in the scratch schema')
        fingerprint = one(op, "SELECT md5(pg_get_functiondef('exp.publish_decision(text,int,jsonb)'::regprocedure))")
        print(json.dumps({'fixture_prefix': prefix, 'live_publish_function_md5': fingerprint,
                          'creation_api': args.creation_api, 'cases': args.cases}), flush=True)

        def add(c, aid, body, ver=1):
            return add_with_dependencies(c, aid, body, ver, [])

        def add_with_dependencies(c, aid, body, ver, dependencies):
            if args.creation_api == 'sealed':
                author = one(c, 'SELECT session_user')
                kind = one(op, 'SELECT exp.seal_artifact(%s,%s,%s,%s,%s::jsonb)',
                           (author, aid, ver, body, json.dumps(dependencies)))
                row = op.execute('SELECT author_role, kind FROM exp.artifacts '
                                 'WHERE artifact_id=%s AND version=%s', (aid, ver)).fetchone()
                expected_kind = 'derivative' if dependencies else 'root'
                if row != (author, expected_kind) or kind != expected_kind:
                    raise RuntimeError('Sealed fixture identity or kind mismatch')
                return
            bound = one(c, 'INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash) '
                           'VALUES (%s,%s,session_user,%s,%s) RETURNING author_role',
                        (aid, ver, body, hashlib.sha256(body.encode()).hexdigest()))
            if bound != one(c, 'SELECT session_user'):
                raise RuntimeError('Unexpected identity binding in fixture creation')
            for dependency in dependencies:
                op.execute('INSERT INTO exp.provenance(derived_id,derived_ver,source_id,source_ver) '
                           'VALUES (%s,%s,%s,%s)',
                           (aid, ver, dependency['id'], dependency['ver']))

        def fixture(case):
            source, draft = (f'{prefix}_{case}_{suffix}' for suffix in ('source', 'draft'))
            add(researcher, source, 'synthetic source')
            add_with_dependencies(writer, draft, 'synthetic derivative', 1, [dict(id=source, ver=1)])
            return source, draft

        def approvals(artifact, ver=1):
            return one(observer, "SELECT count(*) FROM exp.approvals WHERE artifact_id=%s "
                       "AND version=%s AND decision='approved'", (artifact, ver))

        def wait_block_or_finish(future, worker_pid, blocker_pid):
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if future.done():
                    return 'finished_before_first_commit'
                if one(observer, 'SELECT %s = ANY(pg_blocking_pids(%s))', (blocker_pid, worker_pid)):
                    return 'waiting_for_first_transaction'
                time.sleep(0.025)
            return 'not_observed'

        if args.cases == 'dispatch':
            from delivery_recorder import ArtifactInput, dispatch_stage, seal_stage_output

            source, draft = prefix + '_dispatch_source', prefix + '_dispatch_draft'
            add(researcher, source, 'Authorized count: 12')

            def simulated_writer(**request):
                # Deliberately omit the source and assert a forged author.
                return {'body': 'Prepare 12 units', 'inputs': [], 'author': identity['intruder']}

            def seal(author, artifact, version, body, dependencies):
                return one(op, 'SELECT exp.seal_artifact(%s,%s,%s,%s,%s::jsonb)',
                           (author, artifact, version, body, json.dumps(dependencies)))

            def deliver_and_seal(source_version, send, notices):
                source_body = one(op, 'SELECT body FROM exp.artifacts WHERE artifact_id=%s AND version=%s',
                                  (source, source_version))
                reply, receipt = dispatch_stage(
                    send, actor=identity['writer'], model='simulated-writer',
                    instructions='Summarize the authorized count.', task='Prepare a draft.',
                    inputs=[ArtifactInput(source, source_version, source_body)],
                    corrections=notices, max_tokens=64,
                )
                kind = seal_stage_output(seal, receipt, artifact_id=draft, version=source_version,
                                         body=reply['body'])
                return kind, receipt.trace_metadata()

            kind, delivery = deliver_and_seal(1, simulated_writer, [])
            stored_author = one(observer, 'SELECT author_role FROM exp.artifacts WHERE artifact_id=%s AND version=1', (draft,))
            edges = observer.execute('SELECT source_id, source_ver FROM exp.provenance '
                                     'WHERE derived_id=%s AND derived_ver=1', (draft,)).fetchall()
            record('dispatch seals real delivered input despite agent omission',
                   kind == 'derivative' and stored_author == identity['writer'] and edges == [(source, 1)],
                   stored_author=stored_author, edges=edges, delivery=delivery)

            one(researcher, withdraw_sql, (source, 1))
            result = attempt(op, publish_sql, (draft, 1, stamp(source)))
            record('withdrawal blocks the draft despite agent omission', denied(result) and approvals(draft) == 0,
                   gate=result, approvals=approvals(draft))

            add(researcher, source, 'Authorized count: 9', ver=2)
            _, delivery = deliver_and_seal(2, lambda **request: {'body': 'Prepare 9 units'},
                                           [{'id': source, 'ver': 1, 'status': 'withdrawn'}])
            result = attempt(op, publish_sql, (draft, 2, json.dumps([dict(id=source, ver=2, acked_epoch=0)])))
            record('clean revalidation can publish corrected draft',
                   result.get('value') == 'approved' and approvals(draft, 2) == 1,
                   gate=result, approvals=approvals(draft, 2), delivery=delivery)

        if args.cases == 'seal-inputs':
            source = prefix + '_valid_source'
            add(researcher, source, 'valid source for malformed-input probes')
            probes = [
                ('SQL NULL dependency list rejected', None),
                ('dependency missing identity rejected', json.dumps([{'ver': 1}])),
                ('duplicate dependency aborts atomically', json.dumps([
                    {'id': source, 'ver': 1}, {'id': source, 'ver': 1}])),
            ]
            for index, (label, dependencies) in enumerate(probes):
                artifact = f'{prefix}_invalid_input_{index}'
                result = attempt(op, 'SELECT exp.seal_artifact(%s,%s,1,%s,%s::jsonb)',
                                 (identity['writer'], artifact, 'malformed input test', dependencies))
                stored = one(observer, 'SELECT count(*) FROM exp.artifacts WHERE artifact_id=%s', (artifact,))
                links = one(observer, 'SELECT count(*) FROM exp.provenance WHERE derived_id=%s', (artifact,))
                record(label, result.get('sqlstate') in {'22023', '23502', '23505', 'P0001'}
                       and stored == 0 and links == 0,
                       seal=result, artifacts=stored, edges=links)

        if args.cases == 'intake':
            source = prefix + '_intake_source'
            add(researcher, source, 'intake test source')
            forged = prefix + '_forged_seal'
            result = attempt(intruder, 'SELECT exp.seal_artifact(%s,%s,1,%s,%s::jsonb)',
                             (identity['researcher'], forged, 'forged root', '[]'))
            stored = one(observer, 'SELECT count(*) FROM exp.artifacts WHERE artifact_id=%s', (forged,))
            record('intruder cannot seal a root as someone else',
                   result.get('sqlstate') == '42501' and stored == 0,
                   seal=result, artifacts=stored)

            payload = json.dumps({'author': identity['researcher'], 'body': 'untrusted claim',
                                  'probe': prefix + '_explicit'})
            result = attempt(intruder, 'INSERT INTO exp.proposals(proposer,payload) '
                             'VALUES (%s,%s::jsonb)',
                             (identity['researcher'], payload))
            owners = observer.execute('SELECT proposer FROM exp.proposals WHERE payload=%s::jsonb',
                                      (payload,)).fetchall()
            record('explicit proposer override denied or bound to login',
                   (result.get('sqlstate') == '42501' and not owners) or
                   (result.get('value') == 1 and owners == [(identity['intruder'],)]),
                   intake=result, stored_proposers=[row[0] for row in owners])

            payload = json.dumps({'author': identity['researcher'], 'body': 'untrusted claim',
                                  'probe': prefix + '_ordinary'})
            result = attempt(intruder, 'INSERT INTO exp.proposals(payload) '
                             'VALUES (%s::jsonb)', (payload,))
            owners = observer.execute('SELECT proposer FROM exp.proposals WHERE payload=%s::jsonb',
                                      (payload,)).fetchall()
            record('ordinary proposal attributed to authenticated login',
                   result.get('value') == 1 and owners == [(identity['intruder'],)],
                   intake=result, stored_proposers=[row[0] for row in owners])

            result = attempt(intruder, 'SELECT exp._enter_fence()')
            record('intruder cannot directly acquire internal fence',
                   result.get('sqlstate') == '42501', fence=result)

        if args.cases in ('sequential', 'all'):
            missing = prefix + '_missing'
            result = attempt(op, publish_sql, (missing, 1, '[]'))
            count = approvals(missing)
            record('missing artifact denied', count == 0 and (denied(result) or result.get('sqlstate') in {'23503', 'P0002'}),
                   gate=result, approvals=count)

            source, draft = fixture('target_withdrawn')
            one(writer, withdraw_sql, (draft, 1))
            result = attempt(op, publish_sql, (draft, 1, stamp(source)))
            count = approvals(draft)
            record('withdrawn target denied', count == 0 and denied(result), gate=result, approvals=count)

            source, draft = fixture('transitive')
            report = prefix + '_report'
            add_with_dependencies(writer, report, 'report derived via draft', 1, [dict(id=draft, ver=1)])
            one(researcher, withdraw_sql, (source, 1))
            result = attempt(op, publish_sql, (report, 1, stamp(source, draft)))
            count = approvals(report)
            record('withdrawn transitive source denied', count == 0 and denied(result), gate=result, approvals=count)

            source, draft = fixture('foreign_edge')
            bogus = prefix + '_bogus'
            add(researcher, bogus, 'unrelated evidence')
            result = attempt(intruder, 'INSERT INTO exp.provenance(derived_id,derived_ver,source_id,source_ver) '
                             'VALUES (%s,1,%s,1) RETURNING source_id', (draft, bogus))
            observed = one(observer, 'SELECT count(*) FROM exp.provenance WHERE derived_id=%s AND source_id=%s', (draft, bogus))
            record('intruder cannot poison foreign edge', result.get('sqlstate') == '42501' and observed == 0,
                   insert=result, inserted_edges=observed)

            unknown = prefix + '_no_lineage'
            # Intentionally bypass the honest runner, as the attacker can use raw SQL.
            submission = attempt(writer, 'INSERT INTO exp.artifacts(artifact_id,version,author_role,body,content_hash) '
                                 'VALUES (%s,1,session_user,%s,%s) RETURNING artifact_id',
                                 (unknown, 'copied source with provenance omitted', hashlib.sha256(b'copied source with provenance omitted').hexdigest()))
            result = attempt(op, publish_sql, (unknown, 1, '[]')) if 'value' in submission else None
            count = approvals(unknown)
            record('omitting recorded lineage cannot create an eligible root', count == 0 and
                   (submission.get('sqlstate') == '42501' or (result is not None and denied(result))),
                   submission=submission, gate=result, approvals=count)

            source, draft = fixture('recover')
            before = one(op, publish_sql, (draft, 1, stamp(source)))
            one(researcher, withdraw_sql, (source, 1))
            add(researcher, source, 'corrected source', ver=2)
            add_with_dependencies(writer, draft, 'draft with corrected source', 2, [dict(id=source, ver=2)])
            after = one(op, publish_sql, (draft, 2, json.dumps([dict(id=source, ver=2, acked_epoch=0)])))
            record('D7 corrected versions recover and prior approval remains recorded',
                   before == after == 'approved' and approvals(draft, 1) == approvals(draft, 2) == 1,
                   first_decision=before, corrected_decision=after)

        if args.cases in ('race', 'all'):
            # Connection enters transaction before worker runs; only the worker
            # touches its connection until the future completes.
            pub_pid = one(op, 'SELECT pg_backend_pid()')
            rev_pid = one(researcher, 'SELECT pg_backend_pid()')
            with ThreadPoolExecutor(max_workers=1) as executor:
                source, draft = fixture('approval_first')
                op.execute('BEGIN ISOLATION LEVEL READ COMMITTED')
                try:
                    p = one(op, publish_sql, (draft, 1, stamp(source)))
                    f = executor.submit(attempt, researcher, withdraw_sql, (source, 1))
                    ordering = wait_block_or_finish(f, rev_pid, pub_pid)
                    op.execute('COMMIT')
                    w = f.result(timeout=14)
                    count = approvals(draft)
                    record('D6 approval holds withdrawal until commit',
                           p == 'approved' and ordering == 'waiting_for_first_transaction' and isinstance(w.get('value'), int) and count == 1,
                           order=ordering, withdrawal=w, approvals=count)
                finally:
                    op.execute('ROLLBACK')

                source, draft = fixture('withdrawal_first')
                researcher.execute('BEGIN ISOLATION LEVEL READ COMMITTED')
                try:
                    one(researcher, withdraw_sql, (source, 1))
                    f = executor.submit(attempt, op, publish_sql, (draft, 1, stamp(source)))
                    ordering = wait_block_or_finish(f, pub_pid, rev_pid)
                    researcher.execute('COMMIT')
                    p = f.result(timeout=14)
                    count = approvals(draft)
                    record('D6 withdrawal holds approval; post-lock read rejects',
                           ordering == 'waiting_for_first_transaction' and denied(p) and count == 0,
                           order=ordering, gate=p, approvals=count)
                finally:
                    researcher.execute('ROLLBACK')

            source, draft = fixture('stale_snapshot')
            op.execute('BEGIN ISOLATION LEVEL REPEATABLE READ')
            try:
                one(op, 'SELECT count(*) FROM exp.invalidations WHERE artifact_id=%s', (source,))
                one(researcher, withdraw_sql, (source, 1))
                result = attempt(op, publish_sql, (draft, 1, stamp(source)))
                # Commit on the disposable target to distinguish a real bypass
                # from a gate whose surrounding transaction cannot commit.
                op.execute('ROLLBACK' if 'sqlstate' in result else 'COMMIT')
                count = approvals(draft)
                record('D6 old repeatable-read snapshot cannot publish after withdrawal',
                       count == 0 and (denied(result) or result.get('sqlstate') in {'40001', '25001', '0A000'}),
                       gate=result, approvals=count)
            finally:
                op.execute('ROLLBACK')

    print(json.dumps(dict(passed=sum(r['passed'] for r in results), total=len(results), fixture_prefix=prefix)))
    return 0 if all(r['passed'] for r in results) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-database', required=True, help='database name on an explicitly disposable target')
    parser.add_argument('--cases', choices=('all', 'sequential', 'race', 'intake', 'seal-inputs', 'dispatch'),
                        default='all')
    parser.add_argument('--creation-api', choices=('legacy', 'sealed'), default='legacy',
                        help='fixture creation API, retain legacy for historical revisions')
    args = parser.parse_args()
    try:
        return run(args)
    except ImportError:
        parser.exit(2, 'psycopg 3 is required for live checks.\n')
    except Exception as exc:
        # Connection exceptions can embed DSNs. Report their type and SQLSTATE only.
        parser.exit(2, f'Live checks aborted: {type(exc).__name__} (SQLSTATE {getattr(exc, "sqlstate", None)}).\n')


if __name__ == '__main__':
    raise SystemExit(main())
