"""Upload a video, extract MP3, resume safely and download the result."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/reclip/scripts"))
from reclip import Client, upload, run_job, download, save_state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--maximum-credits", required=True, type=int)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    client = Client()
    with args.video.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    upload_state = args.state.with_suffix(".upload.json")
    identity = client.request("GET", "/me")
    if upload_state.exists():
        saved = json.loads(upload_state.read_text())
        if saved["sha256"] != digest or saved["workspace_id"] != identity["workspace_id"]:
            raise ValueError("Upload state belongs to a different file or workspace.")
        asset = saved["asset_id"]
    else:
        asset = upload(client, args.video, "mp4_to_mp3", "video/mp4")
        save_state(upload_state, {"sha256": digest, "asset_id": asset, "workspace_id": identity["workspace_id"]})
    payload = {"tool": "mp4_to_mp3", "input": {"asset_id": asset, "file_name": args.video.name, "operation": "extract_mp3"}}
    result = run_job(client, payload, args.state, args.maximum_credits, args.timeout)
    print("Job", result["id"], result["status"])
    outputs = result.get("outputs", [])
    if not outputs:
        raise RuntimeError("Job returned no downloadable output.")
    target = Path("output") / (outputs[0]["asset_id"] + ".mp3")
    print(download(client, outputs[0]["asset_id"], target))


if __name__ == "__main__":
    main()
