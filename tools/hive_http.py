"""Minimal SQL-over-HTTPS client for the swarm test Hive (Neon).

A bot calls query(sql, params). The connection string is NEVER an argument the
bot supplies: it comes from the environment (local testing) or is attached by
the cloud proxy as the Neon-Connection-String header (bot environments), so a
bot cannot pick another identity. Test Hive only; no personal data.
"""
import json
import os
import sys
import urllib.request
from urllib.parse import urlparse

HIVE_HOST = os.environ.get("HIVE_HOST", "ep-summer-paper-bbe7uhtw.c-15.us-east-1.aws.neon.tech")


def query(sql, params=None, conn=None):
    conn = conn if conn is not None else os.environ.get("HIVE_CONN", "")
    host = urlparse(conn).hostname if conn else HIVE_HOST
    req = urllib.request.Request(
        f"https://{host}/sql",
        data=json.dumps({"query": sql, "params": params or []}).encode(),
        headers={"Content-Type": "application/json", "Neon-Raw-Text-Output": "true",
                 **({"Neon-Connection-String": conn} if conn else {})},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            return {"error": json.loads(body), "http_status": e.code}
        except ValueError:
            return {"error": body, "http_status": e.code}


if __name__ == "__main__":
    sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT * FROM hive_whoami"
    print(json.dumps(query(sql), indent=1)[:3000])
