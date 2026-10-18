"""Run against the complete running Compose stack: python integration_check.py."""
import asyncio
import sys
from uuid import uuid4
import httpx
from scenarios import run_scenario


async def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'http://127.0.0.1:8000'
    async with httpx.AsyncClient(base_url=base, timeout=180,
                                 headers={'X-Lab-Control': '1'}) as h:
        reset = await h.post('/api/reset')
        reset.raise_for_status()
        await asyncio.sleep(3)
        original = (await h.get('/api/bank/usa/accounts')).json()
        assert len(original) == 5 and sum(a['balance_cents'] for a in original) == 945000
        for amount in (0, -1, 1.5, True, 100000001, '100'):
            r = await h.post('/api/bank/usa/transactions', json={
                'request_id': str(uuid4()), 'account_id': 'ACC-1001',
                'type': 'deposit', 'amount_cents': amount})
            assert r.status_code == 422, (amount, r.text)
        key = str(uuid4())
        body = {'request_id': key, 'account_id': 'ACC-1001', 'type': 'deposit', 'amount_cents': 1}
        first = await h.post('/api/bank/usa/transactions', json=body)
        first.raise_for_status()
        again = await h.post('/api/bank/france/transactions', json=body)
        again.raise_for_status()
        assert first.json() == again.json(), 'Cross-region retry must return the same receipt'
        mismatch = await h.post('/api/bank/usa/transactions', json={**body, 'amount_cents': 2})
        assert mismatch.status_code == 409
        overdraw = await h.post('/api/bank/usa/transactions', json={**body,
            'request_id': str(uuid4()), 'type': 'withdrawal', 'amount_cents': 100000000})
        assert overdraw.status_code == 422
        bad_origin = await h.post('/api/restore', headers={'Origin': 'https://unrelated.example'})
        assert bad_origin.status_code == 403
        print('PASS: seed, validation, overdraft, cross-region idempotency, request mismatch, origin protection')
    for number in range(1, 7):
        state = {'running': True, 'steps': [], 'passed': None}
        await run_scenario(number, state, base)
        for line in state['steps']:
            print(f'Test {number}: {line}', flush=True)
        assert state['passed'], f'Scenario {number} failed'
    print('PASS: all six live distributed-database scenarios')


if __name__ == '__main__':
    asyncio.run(main())
