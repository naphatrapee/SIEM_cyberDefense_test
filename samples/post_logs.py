"""Send sample JSON events to POST /api/ingest.  Usage: python post_logs.py [base_url] [token]"""
import glob, json, os, sys
import requests

base = sys.argv[1] if len(sys.argv) > 1 else "https://localhost"
token = sys.argv[2] if len(sys.argv) > 2 else ""
headers = {"Authorization": f"Bearer {token}"} if token else {}
here = os.path.dirname(__file__)
for path in sorted(glob.glob(os.path.join(here, "sample_*.json"))):
    with open(path) as f:
        event = json.load(f)
    r = requests.post(f"{base}/api/ingest", json=event, headers=headers, verify=False)
    print(os.path.basename(path), r.status_code)
