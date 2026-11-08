#!/usr/bin/env python3
"""Create/recreate distributor-side SHA-256 list of the package content."""
import json,pathlib
from audit_utils import file_manifest,utc
root=pathlib.Path(__file__).resolve().parent
out=root/'PACKAGE_FILES_SHA256.json'
files=[x for x in file_manifest(root,out) if not x['path'].startswith('results/grok_') and not x['path'].endswith('.pyc')]
out.write_text(json.dumps({'generated_utc':utc(),'purpose':'Source/input integrity manifest, not a trusted timestamp or API-execution attestation','files':files},indent=2),encoding='utf-8')
print('Indexed',len(files),'files')
