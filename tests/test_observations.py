"""Observation behavior with independently sampled replica contents."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from observations import RecordObserver, ElectionObserver


def node(region, transactions=(), accounts=(), reachable=True):
    return dict(region=region, host=f'mongo-{region}', reachable=reachable,
                transactions=deepcopy(list(transactions)), accounts=deepcopy(list(accounts)))


def transaction(key='request-1', primary='mongo-usa'):
    return dict(id=key, account_id='ACC-1001', type='deposit', amount_cents=100,
                balance_after_cents=1100, primary=primary, region='france')


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.observer = RecordObserver()
        self.events = []
        self.observe([node('usa'), node('france'), node('australia')])

    def emit(self, message, **details):
        entry = dict(message=message, **details)
        self.events.append(entry)
        return entry

    def observe(self, nodes):
        self.observer.observe(nodes, self.emit)

    def test_idle_inspections_do_not_create_events(self):
        self.observe([node('usa'), node('france')])
        self.assertEqual(self.events, [])

    def test_creation_links_actual_record_and_originating_transaction(self):
        receipt = transaction()
        account = dict(id='ACC-1001', balance_cents=1100, last_transaction_id=receipt['id'])
        self.observe([node('usa', [receipt], [account])])
        changes = [e for e in self.events if e['kind'] == 'record']
        self.assertEqual(len(changes), 2)
        self.assertIn('created in mongo-usa', changes[0]['message'])
        self.assertIn('updated in mongo-usa', changes[1]['message'])
        self.assertEqual(changes[1]['transaction_id'], receipt['id'])
        self.assertEqual(changes[1]['record'], account)

    def test_recovery_extends_one_replication_entry_without_duplicates(self):
        receipt = transaction()
        self.observe([node('usa', [receipt]), node('france', [receipt]), node('australia')])
        replication = self.events[-1]
        self.assertEqual(replication['destinations'], ['mongo-france'])
        self.observe([node('usa', [receipt]), node('france', [receipt]), node('australia', [receipt])])
        self.assertEqual(len([e for e in self.events if e['kind'] == 'replication']), 1)
        self.assertEqual(replication['destinations'], ['mongo-australia', 'mongo-france'])
        self.observe([node('france', [receipt])])
        self.assertEqual(len([e for e in self.events if e['kind'] == 'replication']), 1)
        self.assertEqual(len([e for e in self.events if e['kind'] == 'accepted']), 3)

    def test_multiple_transactions_between_polls_are_all_logged(self):
        self.observe([node('usa', [transaction('first'), transaction('second')])])
        self.assertEqual([e['transaction_id'] for e in self.events if e['kind'] == 'record'], ['first', 'second'])

    def test_failover_uses_receipt_primary_not_fixed_region(self):
        receipt = transaction(primary='mongo-france')
        self.observe([node('australia', [receipt]), node('usa', reachable=False)])
        self.assertEqual(self.events[-1]['source'], 'mongo-france')
        self.assertEqual(self.events[-1]['destinations'], ['mongo-australia'])

    def test_baseline_is_quiet_but_later_catch_up_is_reported(self):
        self.observer = RecordObserver()
        receipt = transaction()
        self.observe([node('usa', [receipt]), node('france', [receipt]), node('australia')])
        self.assertEqual(self.events, [])
        self.observe([node('australia', [receipt])])
        self.assertEqual([e['kind'] for e in self.events], ['accepted', 'replication'])

    def test_account_versions_require_matching_contents(self):
        receipt = transaction()
        old = dict(id='ACC-1001', balance_cents=1000, last_transaction_id='old')
        new = dict(id='ACC-1001', balance_cents=1100, last_transaction_id=receipt['id'])
        self.observe([node('usa', [receipt], [new]), node('france', [receipt], [old])])
        self.assertFalse(any(e['kind'] == 'replication' and e['collection'] == 'accounts' for e in self.events))
        self.observe([node('france', [receipt], [new])])
        self.assertEqual(self.events[-1]['collection'], 'accounts')
        self.assertEqual(self.events[-1]['destinations'], ['mongo-france'])

    def test_majority_requires_database_confirmation_not_counted_local_copies(self):
        receipt = transaction()
        nodes = [node('usa', [receipt]), node('france', [receipt])]
        self.observe(nodes)
        self.assertFalse(any(e['kind'] == 'majority' for e in self.events))
        nodes[0]['majority_transactions'] = [receipt['id']]
        self.observe(nodes)
        self.observe(nodes)
        majority = [e for e in self.events if e['kind'] == 'majority']
        self.assertEqual(len(majority), 1)
        self.assertEqual(majority[0]['record'], receipt)

    def test_acceptance_logged_once_per_database(self):
        receipt = transaction()
        nodes = [node('usa', [receipt]), node('france', [receipt])]
        self.observe(nodes)
        self.observe(nodes)
        self.assertEqual([e['database'] for e in self.events if e['kind'] == 'accepted'],
                         ['mongo-usa', 'mongo-france'])

    def test_majority_follows_second_acceptance_before_third_copy(self):
        receipt = transaction(primary='mongo-france')
        account = dict(id='ACC-1001', balance_cents=1100, last_transaction_id=receipt['id'])
        nodes = [node('usa', [receipt], [account]), node('france', [receipt], [account]),
                 node('australia', [receipt], [account])]
        nodes[0]['majority_transactions'] = [receipt['id']]
        self.observe(nodes)
        self.assertEqual([e['kind'] for e in self.events],
                         ['record', 'record', 'accepted', 'accepted', 'majority',
                          'accepted', 'replication', 'replication'])
        accepted = [e['database'] for e in self.events if e['kind'] == 'accepted']
        self.assertEqual(accepted, ['mongo-france', 'mongo-usa', 'mongo-australia'])
        self.assertEqual(next(e for e in self.events if e['kind'] == 'majority')['databases'],
                         ['mongo-france', 'mongo-usa'])

    def test_majority_evidence_waits_until_second_local_copy_is_observed(self):
        receipt = transaction()
        primary = node('usa', [receipt])
        primary['majority_transactions'] = [receipt['id']]
        self.observe([primary])
        self.assertFalse(any(e['kind'] == 'majority' for e in self.events))
        self.observe([node('france', [receipt])])
        self.assertEqual([e['kind'] for e in self.events][:4],
                         ['record', 'accepted', 'accepted', 'majority'])
        self.observe([primary, node('france', [receipt])])
        self.assertEqual(len([e for e in self.events if e['kind'] == 'majority']), 1)

    def test_elections_and_reelections_are_logged_without_polling_noise(self):
        observer = ElectionObserver()
        primary = dict(node('usa'), role='PRIMARY', election_id='one')
        observer.observe([primary], self.emit)
        observer.observe([primary], self.emit)
        self.assertEqual(len(self.events), 1)
        observer.observe([dict(primary, role='SECONDARY')], self.emit)
        replacement = dict(node('france'), role='PRIMARY', election_id='two')
        observer.observe([replacement], self.emit)
        self.assertIn('New primary elected: mongo-france', self.events[-1]['message'])
        observer.observe([dict(replacement, election_id='three')], self.emit)
        self.assertEqual(len(self.events), 4)


if __name__ == '__main__':
    unittest.main()
