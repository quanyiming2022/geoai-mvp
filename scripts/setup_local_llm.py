"""Idempotent user-level macOS Ollama setup. No sudo, no GUI bypass."""
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request

VERSION='0.33.3'
SHA256='342db03df80bb9db84ff64246031bd5f70c09b59ff52fa5cc9aaae3476cc4a9d'
MODEL='qwen3:4b-instruct-2507-q4_K_M'

def run():
    if (platform.system(),platform.machine())!=('Darwin','arm64'):
        raise SystemExit('This setup supports macOS arm64 only. Configure LAN/cloud manually on other hosts.')
    home=Path.home();base=home/'.local/share/geoai/ollama';binary=base/VERSION/'ollama'
    if not binary.exists():
        if shutil.disk_usage(home).free<6*1024**3:raise SystemExit('At least 6 GB free disk space required')
        with tempfile.TemporaryDirectory(prefix='geoai-llm-') as temp:
            archive=Path(temp)/'ollama.tgz'
            url=f'https://github.com/ollama/ollama/releases/download/v{VERSION}/ollama-darwin.tgz'
            with urllib.request.urlopen(url,timeout=60) as response,archive.open('wb') as out:shutil.copyfileobj(response,out)
            if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:raise SystemExit('Official package checksum mismatch')
            binary.parent.mkdir(parents=True,exist_ok=True)
            with tarfile.open(archive) as tar:tar.extractall(binary.parent,filter='data')
    logs=home/'Library/Logs/GeoAI';logs.mkdir(parents=True,exist_ok=True)
    path=home/'Library/LaunchAgents/com.geoai.ollama.plist';path.parent.mkdir(parents=True,exist_ok=True)
    spec={'Label':'com.geoai.ollama','ProgramArguments':[str(binary),'serve'],'EnvironmentVariables':{'OLLAMA_HOST':'127.0.0.1:11434','OLLAMA_NO_CLOUD':'1','OLLAMA_MODELS':str(base/'models'),'OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1','OLLAMA_CONTEXT_LENGTH':'8192'},'RunAtLoad':True,'KeepAlive':True,'StandardOutPath':str(logs/'ollama.log'),'StandardErrorPath':str(logs/'ollama-error.log')}
    if path.exists() and plistlib.loads(path.read_bytes())!=spec:raise SystemExit('Existing LaunchAgent differs; review it before changing it')
    if not path.exists():path.write_bytes(plistlib.dumps(spec))
    label=f'gui/{os.getuid()}/com.geoai.ollama'
    if subprocess.run(['launchctl','print',label],capture_output=True).returncode:
        subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(path)],check=True)
    for attempt in range(30):
        try:
            with urllib.request.urlopen('http://127.0.0.1:11434/api/version',timeout=2) as response:
                if json.load(response).get('version'):break
        except (urllib.error.URLError,TimeoutError):pass
        time.sleep(1)
    else:raise SystemExit('User-level Ollama did not become ready; inspect ~/Library/Logs/GeoAI')
    subprocess.run([str(binary),'pull',MODEL],check=True)
    with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=10) as response:models=json.load(response)
    model=next(m for m in models['models'] if m['name']==MODEL)
    print(json.dumps({'runtime':VERSION,'model':MODEL,'digest':model['digest'],'bytes':model['size']},indent=2))

if __name__=='__main__':run()
