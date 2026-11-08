"""Local, tamper-evident (not independently timestamped or cryptographically signed) audit trail."""
import datetime,hashlib,json,os,pathlib,platform,subprocess,sys,uuid

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')
def sha_bytes(raw):return hashlib.sha256(raw).hexdigest()
def sha(path):return sha_bytes(pathlib.Path(path).read_bytes())
def canonical(o):return json.dumps(o,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
def append_event(path,kind,**data):
    p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    previous='0'*64;seq=1
    if p.exists():
        with p.open(encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    prior=json.loads(line);previous=prior['entry_sha256'];seq=prior['seq']+1
    row={'seq':seq,'timestamp_utc':utc(),'event':kind,'previous_entry_sha256':previous,**data}
    row['entry_sha256']=sha_bytes(canonical(row))
    with p.open('a',encoding='utf-8') as f:
        f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
    return row

def verify_events(path):
    p=pathlib.Path(path);prev='0'*64;count=0
    if not p.exists():return {'valid':False,'error':'missing audit file'}
    try:
        for line in p.read_text(encoding='utf-8').splitlines():
            if not line.strip():continue
            d=json.loads(line);h=d.pop('entry_sha256');count+=1
            if d['seq']!=count or d['previous_entry_sha256']!=prev or sha_bytes(canonical(d))!=h:raise ValueError('broken audit chain at line '+str(count))
            prev=h
        return {'valid':True,'events':count,'head_sha256':prev}
    except Exception as e:return {'valid':False,'events_checked':count,'error':str(e)}

def environment():
    return {'python':sys.version,'platform':platform.platform(),'machine':platform.machine(),
            'python_executable':sys.executable,'timezone':str(datetime.datetime.now().astimezone().tzinfo),
            'utc_clock':utc(),'environment_note':'Local clock is not externally attested; API response IDs independently checkable with provider.'}

def file_manifest(root,output=None):
    root=pathlib.Path(root);files=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and (output is None or p.resolve()!=pathlib.Path(output).resolve()):
            if '__pycache__' in p.parts:continue
            files.append({'path':p.relative_to(root).as_posix(),'size_bytes':p.stat().st_size,'sha256':sha(p)})
    return files
