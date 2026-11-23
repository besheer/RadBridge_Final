#!/usr/bin/env python3
import urllib.request, json, base64, time, sys

ORTHANC_URL = "http://localhost:8042"
AUTH_USER = "admin"
AUTH_PASS = "admin"

auth_str = base64.b64encode(f"{AUTH_USER}:{AUTH_PASS}".encode()).decode("ascii")
headers = {
    "Authorization": f"Basic {auth_str}",
    "Content-Type": "application/json"
}

def get_json(endpoint):
    req = urllib.request.Request(f"{ORTHANC_URL}{endpoint}", headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def post_json(endpoint, data):
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(f"{ORTHANC_URL}{endpoint}", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def run():
    print("=== AirScan PACS Lossless Compression Utility ===")
    stats_before = get_json("/statistics")
    print(f"Total instances: {stats_before.get('CountInstances')}")
    print(f"Current disk size: {stats_before.get('TotalDiskSizeMB')} MB")
    
    studies = get_json("/studies")
    transcoded_count = 0
    already_compressed = 0

    for sid in studies:
        s_info = get_json(f"/studies/{sid}")
        desc = s_info.get("MainDicomTags", {}).get("StudyDescription", "No desc")
        pname = s_info.get("PatientMainDicomTags", {}).get("PatientName", "No name")
        series = s_info.get("Series", [])
        if not series: continue
        ser_info = get_json(f"/series/{series[0]}")
        instances = ser_info.get("Instances", [])
        if not instances: continue
        hdr = get_json(f"/instances/{instances[0]}/header?simplify")
        ts = hdr.get("TransferSyntaxUID", "")

        if ts != "1.2.840.10008.1.2.4.90":
            print(f"Transcoding study {sid} - {pname} ({desc}) to JPEG 2000 Lossless...")
            t0 = time.time()
            res = post_json(f"/studies/{sid}/modify", {
                "Transcode": "1.2.840.10008.1.2.4.90",
                "Keep": ["StudyInstanceUID", "SeriesInstanceUID", "SOPInstanceUID"],
                "KeepSource": True,
                "Force": True
            })
            el = time.time() - t0
            print(f"  -> Transcoded {res.get('InstancesCount')} instances in {el:.1f}s")
            transcoded_count += 1
        else:
            already_compressed += 1

    stats_after = get_json("/statistics")
    print("\n=== Compression Summary ===")
    print(f"Already compressed studies: {already_compressed}")
    print(f"Newly transcoded studies: {transcoded_count}")
    print(f"Final storage size: {stats_after.get('TotalDiskSizeMB')} MB")

if __name__ == "__main__":
    run()
