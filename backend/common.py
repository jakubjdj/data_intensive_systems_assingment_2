import os
from datetime import datetime, timezone
from fastapi import Header, HTTPException
from pymongo import MongoClient
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

REGIONS = ('usa', 'france', 'australia')
HOSTS = {r: f'mongo-{r}' for r in REGIONS}
TOKEN = os.environ.get('LAB_TOKEN', 'local-classroom-lab')
URI = 'mongodb://' + ','.join(f'{h}:27017' for h in HOSTS.values()) + '/?replicaSet=globalbank'


def client():
    return MongoClient(URI, serverSelectionTimeoutMS=3500, connectTimeoutMS=1500,
                       socketTimeoutMS=6000, retryWrites=True, timeoutMS=9000, tz_aware=True)


def direct(region):
    return MongoClient(f'mongodb://{HOSTS[region]}:27017/?directConnection=true',
                       serverSelectionTimeoutMS=1500, connectTimeoutMS=1000,
                       socketTimeoutMS=2000, readPreference='secondaryPreferred', tz_aware=True)


def authorized(x_lab_token: str = Header(default='')):
    import secrets
    if not secrets.compare_digest(x_lab_token, TOKEN):
        raise HTTPException(403, 'Internal lab endpoint')


def now():
    stamp = datetime.now(timezone.utc)
    # BSON stores milliseconds. Normalize before the first receipt is returned so
    # an idempotent replay has exactly the same timestamp after a database read.
    return stamp.replace(microsecond=(stamp.microsecond // 1000) * 1000)


def public(doc):
    if doc is None:
        return None
    if isinstance(doc, list):
        return [public(x) for x in doc]
    if isinstance(doc, dict):
        return {('id' if k == '_id' else k): public(v) for k, v in doc.items()}
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc


def seed(c, reset=False):
    db = c.bank
    db.accounts.create_index('number', unique=True)
    db.transactions.create_index([('account_id', 1), ('timestamp', -1)])
    people = [('Alice Morgan', 100000), ('Bob Wilson', 250000),
              ('Charlie Martin', 75000), ('Diana Cooper', 500000), ('Ethan Taylor', 20000)]

    def apply(s):
        if reset:
            db.transactions.delete_many({}, session=s)
            db.accounts.delete_many({}, session=s)
        for i, (name, balance) in enumerate(people, 1001):
            aid = f'ACC-{i}'
            if db.accounts.find_one({'_id': aid}, session=s):
                continue
            stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
            db.accounts.insert_one({'_id': aid, 'holder': name, 'number': f'GB-0000-{i}',
                'balance_cents': balance, 'currency': 'USD', 'status': 'active', 'created_at': stamp,
                'last_transaction_id': f'SEED-{i}'}, session=s)
            db.transactions.insert_one({'_id': f'SEED-{i}', 'account_id': aid, 'type': 'opening',
                'amount_cents': balance, 'balance_after_cents': balance, 'timestamp': stamp,
                'region': 'usa', 'primary': HOSTS['usa'], 'status': 'committed'}, session=s)
        return True

    with c.start_session() as s:
        s.with_transaction(apply, read_concern=ReadConcern('snapshot'),
                           write_concern=WriteConcern(w='majority', j=True, wtimeout=5000))
