"""Firewall controller scoped to a single MongoDB network namespace, no Docker socket."""
import os
import secrets
import subprocess
import threading
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

IPS = {'usa': '172.29.83.11', 'france': '172.29.83.12', 'australia': '172.29.83.13'}
PEERS = [ip for r, ip in IPS.items() if r != os.environ['REGION']]
lock = threading.Lock()


def auth(x_lab_token: str = Header(default='')):
    if not secrets.compare_digest(x_lab_token, os.environ['LAB_TOKEN']):
        raise HTTPException(403)


app = FastAPI(dependencies=[Depends(auth)])


def run(*args, check=True):
    return subprocess.run(['iptables', '-w', '3', *args], check=check, capture_output=True, text=True)


def setup():
    for direction in ('INPUT', 'OUTPUT'):
        chain = f'GB_{direction}'
        run('-N', chain, check=False)
        if run('-C', direction, '-j', chain, check=False).returncode:
            run('-I', direction, '1', '-j', chain)


def status():
    return {'region': os.environ['REGION'], 'isolated':
        any('-j DROP' in run('-S', f'GB_{d}').stdout for d in ('INPUT', 'OUTPUT')),
        'rules': {d: run('-S', f'GB_{d}').stdout.splitlines() for d in ('INPUT', 'OUTPUT')}}


@app.on_event('startup')
def start():
    setup()  # Preserve an existing partition across agent restarts.


class Partition(BaseModel):
    isolated: bool


@app.get('/state')
def state():
    with lock:
        return status()


@app.post('/partition')
def partition(body: Partition):
    with lock:
        try:
            for direction, flag in [('INPUT', '-s'), ('OUTPUT', '-d')]:
                chain = f'GB_{direction}'
                run('-F', chain)
                if body.isolated:
                    for peer in PEERS:
                        run('-A', chain, flag, peer, '-j', 'DROP')
            return status()
        except subprocess.CalledProcessError as e:
            raise HTTPException(503, 'Firewall update failed; inspect state and restore all') from e
