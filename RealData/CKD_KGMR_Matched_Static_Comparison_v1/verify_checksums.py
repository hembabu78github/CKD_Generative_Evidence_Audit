from pathlib import Path
import hashlib,sys
base=Path(__file__).resolve().parent/'results'
failed=[]
for line in (base/'SHA256SUMS.txt').read_text().splitlines():
    digest,name=line.split('  ',1)
    path=base/name
    actual=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'MISSING'
    if actual!=digest:failed.append(name)
print('PASS' if not failed else 'FAIL', 'result-file checksums;',len(failed),'mismatches')
sys.exit(bool(failed))
