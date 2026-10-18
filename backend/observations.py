"""Record observations from local reads, never from operation timestamps."""
import json
from copy import deepcopy


class RecordObserver:
    def __init__(self):
        self.versions = {}
        self.initialized = False
        self.accepted = set()
        self.majorities = set()
        self.majority_confirmed = set()

    def observe(self, nodes, emit):
        # Gather commit evidence before presenting acceptances. Independent local
        # reads can discover majority visibility before discovering replica copies.
        self.majority_confirmed.update(transaction_id for node in nodes if node['reachable']
                                       for transaction_id in node.get('majority_transactions', []))
        copies = {}
        for node in nodes:
            if not node['reachable']:
                continue
            transactions = {t['id']: t for t in node['transactions']}
            for collection, documents in (('transactions', node['transactions']),
                                          ('accounts', node['accounts'])):
                for document in documents:
                    transaction_id = (document['id'] if collection == 'transactions'
                                      else document.get('last_transaction_id'))
                    transaction = transactions.get(transaction_id, {})
                    source = transaction.get('primary')
                    # Legacy accounts have no transaction link; don't guess their origin.
                    if not source:
                        continue
                    version = (collection, document['id'], json.dumps(document, sort_keys=True))
                    observation = self.versions.get(version)
                    if observation is None:
                        observation = {'seen': set(), 'source': source, 'replication': None,
                                       'record': deepcopy(document), 'transaction_id': transaction_id}
                        self.versions[version] = observation
                        if self.initialized:
                            action = 'updated' if collection == 'accounts' and transaction.get('type') != 'opening' else 'created'
                            emit(f'{collection} record {document["id"]} {action} in {source} '
                                 f'by transaction {transaction_id} (origin: {transaction.get("region", "unknown").upper()}).',
                                 kind='record', collection=collection, record_id=document['id'],
                                 transaction_id=transaction_id, source=source, record=deepcopy(document))
                    observation['seen'].add(node['host'])
                    if collection == 'transactions':
                        copies.setdefault(transaction_id, []).append((node, document, source))
        # Present record changes first, then primary/secondary copy observations.
        # Majority needs both MongoDB confirmation and two displayed acceptances.
        for transaction_id, observations in copies.items():
            for node, document, source in sorted(observations, key=lambda item: item[0]['host'] != item[2]):
                acceptance = (transaction_id, node['host'])
                if acceptance not in self.accepted and self.initialized:
                    emit(f'{node["host"]} accepted transaction record {transaction_id}: '
                         'local copy observed.', kind='accepted', collection='transactions',
                         record_id=transaction_id, transaction_id=transaction_id,
                         source=source, database=node['host'], record=deepcopy(document))
                self.accepted.add(acceptance)
                accepted_by = sorted(host for key, host in self.accepted if key == transaction_id)
                if (transaction_id in self.majority_confirmed and len(accepted_by) >= 2
                        and transaction_id not in self.majorities):
                    if self.initialized:
                        emit(f'Majority accepted transaction {transaction_id}. '
                             'MongoDB confirmed majority commit (at least 2 of 3 databases). '
                             f'Observed copies: {", ".join(accepted_by)}.',
                             kind='majority', collection='transactions', record_id=transaction_id,
                             transaction_id=transaction_id, source=source,
                             databases=accepted_by, record=deepcopy(document))
                    self.majorities.add(transaction_id)
        # Group all destinations for the same record version into one stable entry.
        for (collection, record_id, _), observation in self.versions.items():
            destinations = sorted(observation['seen'] - {observation['source']})
            if not self.initialized:
                observation['baseline'] = set(destinations)
                continue
            if not set(destinations) - observation.get('baseline', set()):
                continue
            message = (f'{collection} record {record_id} replicated from originating primary '
                       f'{observation["source"]} to: {", ".join(destinations)}. '
                       f'Transaction {observation["transaction_id"]}.')
            if observation['replication'] is None:
                observation['replication'] = emit(message, kind='replication', collection=collection,
                    record_id=record_id, transaction_id=observation['transaction_id'],
                    source=observation['source'], destinations=destinations, record=observation['record'])
            else:
                observation['replication'].update(message=message, destinations=destinations)
        if any(n['reachable'] for n in nodes):
            self.initialized = True


class ElectionObserver:
    def __init__(self):
        self.primary = None
        self.missing = False

    def observe(self, nodes, emit):
        primaries = [n for n in nodes if n['reachable'] and n['role'] == 'PRIMARY']
        if len(primaries) != 1:
            if not self.missing:
                emit('No single primary currently observed. Waiting for the replica set to settle.', kind='election')
            self.missing = True
            return
        node = primaries[0]
        key = (node['host'], node.get('election_id'))
        if key != self.primary:
            label = 'New primary elected' if self.primary else 'Current elected primary'
            emit(f'{label}: {node["host"]}.', kind='election', database=node['host'])
        elif self.missing:
            emit(f'Primary reachable again: {node["host"]}.', kind='election', database=node['host'])
        self.primary = key
        self.missing = False
