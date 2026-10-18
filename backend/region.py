import os
from typing import Literal
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, StrictInt
from pymongo import ReturnDocument, timeout
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern
from common import authorized, client, now, public

app = FastAPI(dependencies=[Depends(authorized)])
REGION = os.environ.get('REGION', 'usa')
c = client()
db = c.bank


class Transaction(BaseModel):
    request_id: UUID
    account_id: str = Field(pattern=r'^ACC-\d{4}$')
    type: Literal['deposit', 'withdrawal']
    amount_cents: StrictInt = Field(gt=0, le=100000000)


@app.exception_handler(PyMongoError)
async def unavailable(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={'detail':
        'Database majority unavailable or election in progress. For a submitted transaction, '
        'the outcome may be uncertain: reconcile using the same request ID.'})


@app.get('/accounts')
def accounts():
    # Each balance is a primary linearizable read, bounded by maxTimeMS.
    collection = db.accounts.with_options(read_concern=ReadConcern('linearizable'))
    ids = [x['_id'] for x in db.accounts.with_options(read_concern=ReadConcern('majority')).find({}, {'_id': 1})]
    return public([collection.find_one({'_id': aid}, max_time_ms=3000) for aid in sorted(ids)])


@app.get('/accounts/{aid}/transactions')
def history(aid: str):
    return public(list(db.transactions.with_options(read_concern=ReadConcern('majority'))
                       .find({'account_id': aid}).sort('timestamp', -1).limit(40)))


@app.get('/transactions/{request_id}')
def reconcile(request_id: UUID):
    record = db.transactions.with_options(read_concern=ReadConcern('linearizable')).find_one(
        {'_id': str(request_id)}, max_time_ms=3000)
    return {'transaction': public(record), 'retry_with_same_id': record is None}


@app.post('/transactions')
def transact(body: Transaction):
    key = str(body.request_id)

    def verify(record):
        if any(record[k] != v for k, v in {'account_id': body.account_id, 'type': body.type,
                                          'amount_cents': body.amount_cents}.items()):
            raise HTTPException(409, 'Request ID already belongs to a different operation')
        return public(record)

    def apply(s):
        existing = db.transactions.find_one({'_id': key}, session=s)
        if existing:
            return verify(existing)
        query = {'_id': body.account_id, 'status': 'active'}
        delta = body.amount_cents
        if body.type == 'withdrawal':
            delta = -delta
            query['balance_cents'] = {'$gte': body.amount_cents}
        account = db.accounts.find_one_and_update(query, {'$inc': {'balance_cents': delta},
            '$set': {'last_transaction_id': key}},
            return_document=ReturnDocument.AFTER, session=s)
        if not account:
            raise HTTPException(422, 'Insufficient funds, inactive account, or unknown account')
        # The transaction pins its session to this primary; no static region assumption.
        primary = c.primary
        record = {'_id': key, 'account_id': body.account_id, 'type': body.type,
            'amount_cents': body.amount_cents, 'balance_after_cents': account['balance_cents'],
            'timestamp': now(), 'region': REGION, 'primary': primary[0] if primary else 'unknown',
            'status': 'committed'}
        db.transactions.insert_one(record, session=s)
        return public(record)

    try:
        with timeout(10), c.start_session() as s:
            return s.with_transaction(apply, read_concern=ReadConcern('snapshot'),
                write_concern=WriteConcern(w='majority', j=True, wtimeout=4000), max_commit_time_ms=4000)
    except DuplicateKeyError:
        existing = db.transactions.with_options(read_concern=ReadConcern('linearizable')).find_one(
            {'_id': key}, max_time_ms=3000)
        if existing:
            return verify(existing)
        raise
