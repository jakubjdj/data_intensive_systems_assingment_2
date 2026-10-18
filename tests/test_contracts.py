"""Input and routing policy tests; no fake database behavior or in-memory bank."""
import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ.setdefault('REGION', 'usa')
from pydantic import ValidationError
from fastapi import HTTPException
from region import Transaction
from control import component
from common import now, public
from bson import BSON
from bson.codec_options import CodecOptions


class InputContractTests(unittest.TestCase):
    def test_receipt_timestamp_survives_bson_round_trip_exactly(self):
        record = {'timestamp': now()}
        stored = BSON.encode(record).decode(codec_options=CodecOptions(tz_aware=True))
        self.assertEqual(public(record), public(stored))

    def test_money_requires_positive_bounded_integer_cents(self):
        for value in (True, False, 0, -1, 1.5, '100', 100000001, None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                Transaction(request_id=uuid4(), account_id='ACC-1001', type='deposit', amount_cents=value)
        self.assertEqual(Transaction(request_id=uuid4(), account_id='ACC-1001',
                                    type='deposit', amount_cents=1).amount_cents, 1)

    def test_invalid_identity_and_operation_are_rejected(self):
        for changes in ({'request_id': 'bad'}, {'account_id': '../admin'}, {'type': 'transfer'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                Transaction(**dict({'request_id': str(uuid4()), 'account_id': 'ACC-1001',
                                    'type': 'deposit', 'amount_cents': 100}, **changes))


class PartitionPolicyTests(unittest.TestCase):
    def test_every_firewall_combination_has_correct_majority_components(self):
        from itertools import product
        regions = ('usa', 'france', 'australia')
        for flags in product((False, True), repeat=3):
            states = {r: {'isolated': f} for r, f in zip(regions, flags)}
            for region in regions:
                expected = [region] if states[region]['isolated'] else [r for r in regions if not states[r]['isolated']]
                self.assertEqual(component(region, states), expected)

    def test_unknown_firewall_state_fails_closed(self):
        with self.assertRaises(HTTPException) as exc:
            component('usa', {'usa': {'isolated': False}, 'france': {'isolated': None}})
        self.assertEqual(exc.exception.status_code, 503)


if __name__ == '__main__':
    unittest.main()
