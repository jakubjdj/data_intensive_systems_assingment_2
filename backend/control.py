import asyncio
from collections import deque
from contextlib import asynccontextmanager
from uuid import uuid4
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pymongo.errors import PyMongoError
from common import REGIONS, HOSTS, TOKEN, direct, client, now, public, seed

events = deque(maxlen=100)
previous = {}
admin_lock = asyncio.Lock()
condition = asyncio.Condition()
maintenance = False
active = 0
local_clients = {r: direct(r) for r in REGIONS}
cluster = client()


def event(message):
    events.appendleft({'id': str(uuid4()), 'timestamp': now().isoformat(), 'message': message})


@asynccontextmanager
async def lifespan(app):
    event('Control station online. Node roles and balances are observed from MongoDB.')
    yield
    for c in local_clients.values():
        c.close()
    cluster.close()


app = FastAPI(lifespan=lifespan)


@app.middleware('http')
async def local_control(request: Request, call_next):
    # The only published listener is loopback. Custom headers block cross-site form writes.
    if request.method not in ('GET', 'HEAD'):
        origin = request.headers.get('origin')
        if request.headers.get('x-lab-control') != '1' or (origin and origin != f'{request.url.scheme}://{request.headers.get("host")}'):
            return JSONResponse(status_code=403, content={'detail': 'Use the local lab interface'})
    return await call_next(request)


def valid(region):
    if region not in REGIONS:
        raise HTTPException(404, 'Unknown region')


async def internal(region, port, path, method='GET', body=None):
    async with httpx.AsyncClient(timeout=15) as h:
        try:
            response = await h.request(method, f'http://{HOSTS[region]}:{port}{path}',
                headers={'X-Lab-Token': TOKEN}, json=body)
        except httpx.HTTPError as e:
            raise HTTPException(503, f'{region} service unreachable; submitted writes may need reconciliation') from e
    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(503, f'{region} service returned an invalid response')
    if response.status_code >= 400:
        raise HTTPException(response.status_code, payload.get('detail', 'Regional service failed'))
    return payload


async def agent_states():
    values = await asyncio.gather(*(internal(r, 8002, '/state') for r in REGIONS), return_exceptions=True)
    return {r: v if not isinstance(v, Exception) else {'region': r, 'isolated': None, 'error': str(v)}
            for r, v in zip(REGIONS, values)}


def component(region, states):
    if any(s['isolated'] is None for s in states.values()):
        raise HTTPException(503, 'Cannot verify firewall state; banking paused until controls recover')
    if states[region]['isolated']:
        return [region]
    return [r for r in REGIONS if not states[r]['isolated']]


@asynccontextmanager
async def banking():
    global active
    async with condition:
        if maintenance:
            raise HTTPException(503, 'Lab reset in progress')
        active += 1
    try:
        yield
    finally:
        async with condition:
            active -= 1
            condition.notify_all()


@app.api_route('/api/bank/{region}/{path:path}', methods=['GET', 'POST'])
async def bank(region: str, path: str, request: Request):
    valid(region)
    if not (path == 'accounts' or path == 'transactions' or
            path.startswith('accounts/') or path.startswith('transactions/')):
        raise HTTPException(404)
    async with banking():
        states = await agent_states()
        if len(component(region, states)) < 2:
            raise HTTPException(503, 'Consistency protection: this region is isolated from the database majority. '
                'No new banking request was forwarded. Reconcile any earlier pending request after recovery.')
        payload = await internal(region, 8001, '/' + path, request.method,
                                 await request.json() if request.method == 'POST' else None)
        if request.method == 'POST':
            event(f'{region.upper()}: {payload["type"]} acknowledged, request {payload["id"]}, primary {payload["primary"]}.')
        return payload


def inspect(region):
    c = local_clients[region]
    try:
        hello = c.admin.command('hello')
        status = c.admin.command('replSetGetStatus')
        me = next(m for m in status['members'] if m.get('self'))
        accounts = list(c.bank.accounts.find({}).sort('_id', 1))
        latest = c.bank.transactions.find_one(sort=[('timestamp', -1), ('_id', -1)])
        applied = me.get('optimeDate')
        return {'region': region, 'host': HOSTS[region], 'reachable': True,
            'role': me['stateStr'], 'primary': hello.get('primary'),
            'election_id': str(hello.get('electionId', '')), 'applied_at': public(applied),
            'optime': str(me.get('optime', {}).get('ts', '')),
            'accounts': public(accounts), 'latest_transaction': public(latest),
            'peers': [{'name': m['name'], 'health': m['health'], 'state': m['stateStr'],
                       'message': m.get('lastHeartbeatMessage', '')} for m in status['members']]}
    except (PyMongoError, StopIteration) as e:
        return {'region': region, 'host': HOSTS[region], 'reachable': False, 'role': 'UNREACHABLE',
                'error': type(e).__name__, 'accounts': []}


@app.get('/api/status')
async def status():
    states, nodes = await asyncio.gather(agent_states(), asyncio.gather(
        *(asyncio.to_thread(inspect, r) for r in REGIONS)))
    for node in nodes:
        node['network'] = states[node['region']]
        key = (node['role'], node['network']['isolated'], node.get('optime'))
        old = previous.get(node['region'])
        if old and old != key:
            if old[:2] != key[:2]:
                event(f'{node["region"].upper()}: observed {node["role"]}; isolated={key[1]}.')
            elif old[2] != key[2]:
                event(f'{node["region"].upper()}: replication advanced to {key[2]}.')
        previous[node['region']] = key
    return {'nodes': nodes, 'events': list(events), 'observed_at': now().isoformat(),
            'note': 'Node inspections are local, potentially stale reads; they are not a simultaneous snapshot.'}


class Partition(BaseModel):
    isolated: bool


@app.post('/api/network/{region}')
async def partition(region: str, body: Partition):
    valid(region)
    async with admin_lock:
        result = await internal(region, 8002, '/partition', 'POST', body.model_dump())
        event(f'{region.upper()}: firewall {"partition applied" if result["isolated"] else "restored"}.')
        return result


async def restore_all():
    results = await asyncio.gather(*(internal(r, 8002, '/partition', 'POST', {'isolated': False})
                                     for r in REGIONS), return_exceptions=True)
    if any(isinstance(x, Exception) for x in results):
        raise HTTPException(503, 'Some firewall agents failed to restore. Retry RESTORE ALL and inspect the notebook.')
    event('All database peer firewall chains cleared. Replicas may need time to catch up.')
    return {'restored': True}


@app.post('/api/restore')
async def restore():
    async with admin_lock:
        return await restore_all()


@app.post('/api/reset')
async def reset():
    global maintenance
    async with admin_lock:
        async with condition:
            maintenance = True
            await condition.wait_for(lambda: active == 0)
        try:
            await restore_all()
            for _ in range(30):
                try:
                    await asyncio.to_thread(seed, cluster, True)
                    event('Demo data reset: five original accounts and opening transactions restored.')
                    return {'reset': True}
                except PyMongoError:
                    await asyncio.sleep(1)
            raise HTTPException(503, 'Reset could not obtain a majority; restore connectivity and retry')
        finally:
            async with condition:
                maintenance = False


from scenarios import run_scenario
scenario_state = {'running': False, 'steps': []}
scenario_task = None


@app.get('/api/scenarios')
async def scenario_status():
    return scenario_state


@app.post('/api/scenarios/{number}')
async def scenario(number: int):
    global scenario_task
    if number not in range(1, 7):
        raise HTTPException(404)
    if scenario_state['running']:
        raise HTTPException(409, 'A scenario is already running')
    scenario_state.clear()
    scenario_state.update(running=True, number=number, steps=[], passed=None)
    scenario_task = asyncio.create_task(run_scenario(number, scenario_state))
    return scenario_state
