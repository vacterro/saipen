from pathlib import Path
import argparse, hashlib, json, os, shutil, subprocess, sys, tempfile
parser=argparse.ArgumentParser()
parser.add_argument('--subject',required=True)
args=parser.parse_args()
EVIDENCE=Path(__file__).resolve().parent
ROOT=Path(args.subject).resolve()
FILES=json.loads((EVIDENCE/'paths.json').read_text())
VERIFIER='tools/test_t1633_process_tree.py'
COMMAND=[sys.executable,'-B','-m','unittest','test_t1633_process_tree']
def fingerprint(root):
    digest=hashlib.sha256()
    for name in FILES:
        if name==VERIFIER: continue
        path=root/name
        digest.update(name.encode()+b'\0')
        digest.update(path.read_bytes() if path.is_file() else b'MISSING')
    return digest.hexdigest()[:16]
def run(root,label):
    env={k:v for k,v in os.environ.items() if not k.startswith('SAIPEN_')}
    env['CLAUDE_CONFIG_DIR']=''
    result=subprocess.run(COMMAND,cwd=root/'tools',env=env,stdin=subprocess.DEVNULL,
                          capture_output=True,timeout=180)
    (EVIDENCE/(label+'.out.txt')).write_bytes(result.stdout+result.stderr)
    return result.returncode
verifier=hashlib.sha256((ROOT/VERIFIER).read_bytes()).hexdigest()[:16]
post=fingerprint(ROOT)
with tempfile.TemporaryDirectory(prefix='saipen-t1633-pair-') as temporary:
    subject=Path(temporary)/'project'
    sys.path.insert(0,str(ROOT/'tools'))
    from saipen_engine.test_runner import _ignore_copy
    def ignore(directory,names):
        return _ignore_copy(directory,names) | {name for name in names if name in {'.saipen','.git'}}
    shutil.copytree(ROOT,subject,symlinks=True,ignore=ignore)
    control=run(subject,'control')
    if control: raise SystemExit('known-good clone failed; see control.out.txt')
    for name in FILES:
        if name==VERIFIER: continue
        saved=EVIDENCE/'pre'/name
        target=subject/name
        if saved.is_file(): shutil.copyfile(saved,target)
        elif target.exists(): target.unlink()
    pre=fingerprint(subject)
    red=run(subject,'red')
    held=hashlib.sha256((subject/VERIFIER).read_bytes()).hexdigest()[:16]==verifier
green=run(ROOT,'green')
record={'verifier':verifier,'pre_subject':pre,'post_subject':post,'pre_rc':red,
        'post_rc':green,'control_rc':control,'held':held,
        'command':'python -B -m unittest test_t1633_process_tree'}
(EVIDENCE/'pair.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
raise SystemExit(0 if red and not green and held else 1)
