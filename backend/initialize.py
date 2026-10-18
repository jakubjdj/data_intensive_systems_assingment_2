import time
from pymongo.errors import OperationFailure, PyMongoError
from common import REGIONS, HOSTS, client, direct, seed


def main():
    with direct('usa') as c:
        try:
            c.admin.command('replSetGetStatus')
        except OperationFailure as e:
            if e.code != 94:
                raise
            c.admin.command('replSetInitiate', {
                '_id': 'globalbank', 'members': [
                    {'_id': i, 'host': f'{HOSTS[r]}:27017', 'priority': 2 if i == 0 else 1}
                    for i, r in enumerate(REGIONS)],
                'settings': {'electionTimeoutMillis': 5000}})
    with client() as c:
        for _ in range(90):
            try:
                c.admin.command('ping')
                seed(c)
                print('Replica set ready; deterministic seed committed.', flush=True)
                return
            except PyMongoError:
                time.sleep(2)
    raise RuntimeError('No writable majority after initialization deadline')


if __name__ == '__main__':
    main()
