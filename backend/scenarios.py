"""Executable demonstrations. Assertions depend exclusively on real API/database results."""
import asyncio
from uuid import uuid4
import httpx


async def run_scenario(number, state, base_url='http://127.0.0.1:8000'):
    async with httpx.AsyncClient(base_url=base_url, timeout=60,
                                 headers={'X-Lab-Control': '1'}) as h:
        async def req(method, path, body=None):
            r = await h.request(method, '/api' + path, json=body)
            r.raise_for_status()
            return r.json()

        def step(message):
            state['steps'].append(message)

        async def status():
            return await req('GET', '/status')

        async def wait_for(predicate, description):
            for _ in range(40):
                result = await status()
                if predicate(result):
                    step(description)
                    return result
                await asyncio.sleep(1)
            raise AssertionError('Deadline exceeded: ' + description)

        async def balance(region, aid='ACC-1001'):
            rows = await req('GET', f'/bank/{region}/accounts')
            return next(a['balance_cents'] for a in rows if a['id'] == aid)

        async def tx(region, kind='deposit', amount=100, aid='ACC-1001', key=None):
            return await req('POST', f'/bank/{region}/transactions', {
                'request_id': key or str(uuid4()), 'account_id': aid,
                'type': kind, 'amount_cents': amount})

        def converged(s, aid, expected):
            return all(any(a['id'] == aid and a['balance_cents'] == expected
                           for a in n['accounts']) for n in s['nodes'])

        try:
            await req('POST', '/restore')
            healthy = await wait_for(lambda s: sum(n['role'] == 'PRIMARY' for n in s['nodes']) == 1
                and all(n['role'] in ('PRIMARY', 'SECONDARY') for n in s['nodes']), 'Replica set healthy')
            if number == 1:
                old = await balance('usa')
                receipt = await tx('usa')
                assert receipt['balance_after_cents'] == old + 100
                await wait_for(lambda s: converged(s, 'ACC-1001', old + 100), 'All three local replicas show the $1 deposit')
            elif number in (2, 3, 4, 5):
                target = next(n['region'] for n in healthy['nodes'] if (
                    n['role'] == 'PRIMARY' if number == 3 else
                    n['role'] == 'SECONDARY' if number == 2 else n['region'] == 'australia'))
                majority = next(r for r in ('usa', 'france', 'australia') if r != target)
                old = await balance(majority)
                await req('POST', f'/network/{target}', {'isolated': True})
                step(f'Actual firewall partition applied to {target}')
                failed = await h.post(f'/api/bank/{target}/transactions', json={
                    'request_id': str(uuid4()), 'account_id': 'ACC-1001',
                    'type': 'withdrawal', 'amount_cents': 100})
                assert failed.status_code == 503, 'Minority should refuse banking'
                step('Isolated regional withdrawal refused with HTTP 503')
                await wait_for(lambda s: any(n['role'] == 'PRIMARY' and n['region'] != target
                    for n in s['nodes']), 'Majority has an elected primary')
                receipt = await tx(majority)
                assert receipt['balance_after_cents'] == old + 100, 'Unexpected majority balance'
                assert await balance(majority) == old + 100
                step('Majority committed a $1 deposit; rejected withdrawal did not change balance')
                local = await status()
                isolated_node = next(n for n in local['nodes'] if n['region'] == target)
                assert any(a['id'] == 'ACC-1001' and a['balance_cents'] == old for a in isolated_node['accounts'])
                step('Isolated replica remains inspectable and shows the older balance')
                await req('POST', '/restore')
                await wait_for(lambda s: converged(s, 'ACC-1001', old + 100), 'Recovery: all three replicas converged')
            else:
                aid = 'ACC-1005'
                amount = await balance('usa', aid)
                assert amount > 0, 'Reset demo data first: Ethan needs a positive balance'
                keys = [str(uuid4()), str(uuid4())]
                results = await asyncio.gather(*(tx('usa', 'withdrawal', amount, aid, k) for k in keys), return_exceptions=True)
                successes = [r for r in results if isinstance(r, dict)]
                failures = [r for r in results if isinstance(r, httpx.HTTPStatusError) and r.response.status_code == 422]
                assert len(successes) == 1 and len(failures) == 1, str(results)
                assert await balance('usa', aid) == 0
                winner = successes[0]
                replay = await tx('usa', 'withdrawal', amount, aid, winner['id'])
                assert replay['id'] == winner['id'] and await balance('usa', aid) == 0
                history = await req('GET', f'/bank/usa/accounts/{aid}/transactions')
                assert sum(t['id'] == winner['id'] for t in history) == 1
                step('Two concurrent full-balance withdrawals: one commit, one refusal; retry made no duplicate')
                await tx('usa', 'deposit', amount, aid)
                step('Test funds returned to Ethan')
            state['passed'] = True
        except Exception as e:
            state['passed'] = False
            step(f'FAIL: {type(e).__name__}: {e}')
        finally:
            try:
                await req('POST', '/restore')
            except Exception as e:
                state['passed'] = False
                step(f'Restore failed: {e}; use RESTORE ALL')
            state['running'] = False
