"""Record a credential-free fingerprint of a deployed SwarmHive gate."""
import hashlib
import json
import os
from urllib.parse import urlsplit

import psycopg


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def snapshot(conn, dsn):
    target = urlsplit(dsn)
    if target.scheme not in {'postgresql', 'postgres'} or not target.hostname or not target.path:
        raise ValueError('the gate target must be an explicit PostgreSQL URI')
    database, operator = conn.execute('SELECT current_database(), session_user').fetchone()
    if database != target.path.lstrip('/'):
        raise ValueError('connected database differs from the declared target')
    schema = conn.execute("""SELECT n.nspacl::text, pg_get_userbyid(n.nspowner)
                             FROM pg_namespace n WHERE n.nspname='exp'""").fetchone()
    if not schema:
        raise ValueError('the deployed exp schema is missing')

    routines = conn.execute("""
        SELECT p.oid::regprocedure::text, pg_get_functiondef(p.oid),
               p.proacl::text, pg_get_userbyid(p.proowner)
        FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
        WHERE n.nspname='exp' ORDER BY 1
    """).fetchall()
    relations = conn.execute("""
        SELECT c.relname, c.relkind, c.relacl::text, pg_get_userbyid(c.relowner),
               c.relrowsecurity, CASE WHEN c.relkind='v' THEN pg_get_viewdef(c.oid) END
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='exp' ORDER BY 1
    """).fetchall()
    columns = conn.execute("""
        SELECT c.relname, a.attnum, a.attname, format_type(a.atttypid,a.atttypmod),
               a.attnotnull, a.attacl::text, pg_get_expr(d.adbin,d.adrelid)
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
        WHERE n.nspname='exp' AND c.relkind IN ('r','v') AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY 1, 2
    """).fetchall()
    constraints = conn.execute("""
        SELECT c.relname, co.conname, pg_get_constraintdef(co.oid)
        FROM pg_constraint co JOIN pg_class c ON c.oid=co.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='exp' ORDER BY 1, 2
    """).fetchall()
    indexes = conn.execute("""
        SELECT c.relname, pg_get_indexdef(c.oid)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='exp' AND c.relkind='i' ORDER BY 1
    """).fetchall()
    triggers = conn.execute("""
        SELECT c.relname, t.tgname, t.tgenabled, pg_get_triggerdef(t.oid)
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='exp' AND NOT t.tgisinternal ORDER BY 1, 2
    """).fetchall()
    adjudicators = conn.execute('SELECT role FROM exp.adjudicators ORDER BY role').fetchall()
    if (operator,) not in adjudicators:
        raise ValueError('connected runtime is not an adjudicator')
    if not conn.execute("""
        SELECT to_regprocedure('exp.seal_from_receipt(text,text,text,integer,text,jsonb)') IS NOT NULL
           AND to_regclass('exp.current_approvals') IS NOT NULL
           AND to_regclass('exp.advisories') IS NOT NULL
    """).fetchone()[0]:
        raise ValueError('required receipt, read-time, or advisory migration is missing')
    return {
        'target_sha256': digest([target.hostname, target.port or 5432, database, operator]),
        'gate_schema_sha256': digest([schema, routines, relations, columns, constraints, indexes, triggers, adjudicators]),
    }


def main():
    dsn = os.environ.get('HIVE_OPERATOR_DSN')
    if not dsn:
        raise ValueError('set the explicit HIVE_OPERATOR_DSN first')
    with psycopg.connect(dsn, connect_timeout=8) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        print(json.dumps(snapshot(conn, dsn), indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(f'gate preflight failed ({type(exc).__name__}, SQLSTATE {getattr(exc, "sqlstate", None)})')
