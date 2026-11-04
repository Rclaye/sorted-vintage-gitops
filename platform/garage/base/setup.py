"""Idempotent Garage setup (infra research R19, plan Complexity Tracking).

Applies a one-node layout if none is set, imports the S3 keys from the Terraform-created
Secrets, creates the buckets photos and backups if missing, and grants each key its bucket.
It never deletes or renames anything. Runs as an Argo CD PostSync hook on every sync.
"""
import json
import os
import time
import urllib.error
import urllib.request

ADMIN = os.environ["GARAGE_ADMIN_URL"]
TOKEN = os.environ["GARAGE_ADMIN_TOKEN"]
CAPACITY = 20 * 1024**3
GRANTS = {
    "photos": ("photos", os.environ["PHOTOS_KEY_ID"], os.environ["PHOTOS_SECRET_KEY"]),
    "backups": ("backups", os.environ["BACKUPS_KEY_ID"], os.environ["BACKUPS_SECRET_KEY"]),
}


def call(method, path, body=None, ok_missing=False):
    req = urllib.request.Request(
        ADMIN + path,
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        if ok_missing and err.code in (400, 404):
            return None
        raise SystemExit(f"{method} {path}: HTTP {err.code} {err.read().decode()[:300]}")


def wait_ready():
    for _ in range(60):
        try:
            call("GET", "/v2/GetClusterStatus")
            return
        except (urllib.error.URLError, ConnectionError, SystemExit):
            time.sleep(2)
    raise SystemExit("Garage admin API did not answer within 120 s")


def ensure_layout():
    status = call("GET", "/v2/GetClusterStatus")
    node = status["nodes"][0]
    if node.get("role"):
        print(f"layout: node {node['id'][:12]} already has a role")
        return
    call("POST", "/v2/UpdateClusterLayout",
         {"roles": [{"id": node["id"], "zone": "lab", "capacity": CAPACITY, "tags": []}]})
    version = call("GET", "/v2/GetClusterLayout")["version"]
    call("POST", "/v2/ApplyClusterLayout", {"version": version + 1})
    print(f"layout: applied version {version + 1}")


def ensure_key(name, key_id, secret):
    if call("GET", f"/v2/GetKeyInfo?id={key_id}", ok_missing=True):
        print(f"key {name}: present")
        return
    call("POST", "/v2/ImportKey", {"accessKeyId": key_id, "secretAccessKey": secret, "name": name})
    print(f"key {name}: imported")


def ensure_bucket(alias):
    info = call("GET", f"/v2/GetBucketInfo?globalAlias={alias}", ok_missing=True)
    if info:
        print(f"bucket {alias}: present")
        return info["id"]
    print(f"bucket {alias}: created")
    return call("POST", "/v2/CreateBucket", {"globalAlias": alias})["id"]


wait_ready()
ensure_layout()
for bucket, (name, key_id, secret) in GRANTS.items():
    ensure_key(name, key_id, secret)
    bucket_id = ensure_bucket(bucket)
    call("POST", "/v2/AllowBucketKey", {
        "bucketId": bucket_id,
        "accessKeyId": key_id,
        "permissions": {"read": True, "write": True, "owner": False},
    })
    print(f"grant {name} -> {bucket}: read, write")
print("garage setup complete")
