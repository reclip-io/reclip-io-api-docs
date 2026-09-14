"""Reclip API client using only Python's standard library."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Client:
    def __init__(self, base=None, key=None):
        self.base = (base or os.environ.get("RECLIP_API_BASE_URL", "https://www.reclip.io/api/v1")).rstrip("/")
        self.key = key or os.environ.get("RECLIP_API_KEY")
        parsed = urllib.parse.urlsplit(self.base)
        if parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost")):
            raise ValueError("Use an HTTPS API base URL (HTTP is allowed only for local tests).")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("The API base URL must not contain credentials, query or fragment.")
        if not self.key:
            raise ValueError("Set RECLIP_API_KEY in the environment.")
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, method, path, data=None, idempotency=None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("Use an API-relative path.")
        body = json.dumps(data).encode() if data is not None else None
        headers = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json"}
        if idempotency:
            headers["Idempotency-Key"] = idempotency
        retryable = method == "GET" or idempotency is not None
        for attempt in range(3):
            req = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
            try:
                with self.opener.open(req, timeout=30) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if retryable and error.code in (429, 502, 503, 504) and attempt < 2:
                    retry_after = error.headers.get("Retry-After", "5")
                    time.sleep(min(60, max(1, int(retry_after) if retry_after.isdigit() else 5)))
                    continue
                # Return only structured Reclip error fields, not raw transport headers.
                try:
                    failure = json.loads(error.read())
                    detail = failure.get("error", {})
                    raise RuntimeError(f"API {error.code}: {detail.get('code', 'request_failed')}; request_id={failure.get('request_id', 'unknown')}") from None
                except (ValueError, AttributeError):
                    raise RuntimeError(f"API HTTP {error.code}") from None
            except (urllib.error.URLError, TimeoutError):
                if retryable and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError("Transport failed; preserve state and resume with the same idempotency key.") from None


def save_state(path, data, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, indent=2)
        return
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(data, stream, indent=2)
    os.replace(temporary, path)


def upload(client, file, tool, mime_type):
    path = Path(file)
    intent = client.request("POST", "/assets/uploads", {"tool": tool, "file_name": path.name, "mime_type": mime_type, "size_bytes": path.stat().st_size})
    # Storage uploads never receive the API Authorization header. Open file streams
    # avoid loading an entire source video into memory.
    headers = {**intent["headers"], "Content-Length": str(path.stat().st_size)}
    with path.open("rb") as stream:
        request = urllib.request.Request(intent["upload_url"], data=stream, headers=headers, method="PUT")
        with urllib.request.build_opener(NoRedirect).open(request, timeout=300) as response:
            response.read()
    client.request("POST", "/assets/" + intent["asset_id"] + "/confirm")
    return intent["asset_id"]


def run_job(client, payload, state_path, maximum_credits, timeout=1800):
    if maximum_credits < 0:
        raise ValueError("maximum_credits must be nonnegative.")
    payload = {**payload, "maximum_credits": maximum_credits}
    identity = client.request("GET", "/me")
    state_path = Path(state_path)
    if state_path.exists():
        state = json.loads(state_path.read_text())
        if state["request"] != payload or state["key_id"] != identity["key_id"] or state["workspace_id"] != identity["workspace_id"]:
            raise ValueError("State does not match this request, API key or workspace; resolve the previous run before starting another.")
    else:
        quote = client.request("POST", "/jobs/quote", payload)
        if quote["estimated_credits"] > maximum_credits or not quote["affordable"]:
            raise ValueError("Quoted job exceeds the authorized budget or available credits.")
        state = {"request": payload, "idempotency_key": str(uuid.uuid4()), "key_id": identity["key_id"], "workspace_id": identity["workspace_id"]}
        save_state(state_path, state, exclusive=True)
    if not state.get("job_id"):
        accepted = client.request("POST", "/jobs", state["request"], state["idempotency_key"])
        state["job_id"] = accepted["id"]
        save_state(state_path, state)
    deadline = time.monotonic() + timeout
    while True:
        job = client.request("GET", "/jobs/" + state["job_id"])
        if job["status"] == "succeeded":
            return job
        if job["status"] in ("failed", "canceled"):
            raise RuntimeError(f"Job {state['job_id']} is {job['status']}. No replacement was submitted.")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Job {state['job_id']} is still processing. Resume using {state_path}.")
        time.sleep(5)


def download(client, asset_id, destination):
    signed = client.request("GET", "/assets/" + asset_id + "/download")
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    # No API authorization is sent to the signed storage URL.
    with urllib.request.urlopen(signed["url"], timeout=300) as response, path.open("xb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("request", type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--maximum-credits", required=True, type=int)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    result = run_job(Client(), json.loads(args.request.read_text()), args.state, args.maximum_credits, args.timeout)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
