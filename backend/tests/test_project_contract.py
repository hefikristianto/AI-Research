from __future__ import annotations

import copy
import unittest

from ai.scripts.validate_project_contract import (
    load_contract,
    validate_contract,
    validate_repository_scope,
)


class ProjectContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = load_contract()

    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual(validate_contract(self.contract), [])

    def test_repository_yolo_artifacts_match_contract(self) -> None:
        self.assertEqual(validate_repository_scope(), [])

    def test_liquidity_cannot_be_added_to_production_yolo_silently(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["analysis_pipeline"]["model_roles"]["yolo"][
            "production_classes"
        ].append("liquidity")

        errors = validate_contract(changed)

        self.assertTrue(any("Kelas YOLO produksi" in error for error in errors))

    def test_raw_prediction_cannot_become_ground_truth(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["incremental_learning"]["raw_prediction_as_ground_truth"] = True

        errors = validate_contract(changed)

        self.assertTrue(any("ground truth" in error for error in errors))

    def test_time_trigger_still_requires_a_minimum_batch(self) -> None:
        changed = copy.deepcopy(self.contract)
        changed["incremental_learning"]["triggers"]["minimum_batch_size"] = 0

        errors = validate_contract(changed)

        self.assertTrue(any("batch trigger" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
