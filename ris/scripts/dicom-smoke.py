
import os, socket, sys
host=os.getenv("DICOM_HOST","127.0.0.1")
port=int(os.getenv("DICOM_PORT","4242"))
try:
    with socket.create_connection((host,port),timeout=5):
        print(f"DICOM TCP CONNECT: PASS {host}:{port}")
except Exception as e:
    print(f"DICOM TCP CONNECT: FAIL {host}:{port} {e}")
    sys.exit(1)
