"""
Tests for the NOVA Sovereignty service.

These tests validate the shape and logical consistency of the real
local runtime snapshot without inventing environment-specific values.
"""

from __future__ import annotations

import unittest

from app.services.sovereignty.service import (
    sovereignty_service,
)


class TestSovereigntyService(
    unittest.TestCase
):

    def test_snapshot_structure(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        required_top_level = {
            "timestamp",
            "scope",
            "truthfulness",
            "runtime",
            "storage",
            "hardware",
            "network",
            "verification",
        }

        self.assertTrue(
            required_top_level.issubset(
                snapshot.keys()
            )
        )

    def test_truthfulness_flags(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        truthfulness = snapshot[
            "truthfulness"
        ]

        self.assertIs(
            truthfulness[
                "synthetic_metrics"
            ],
            False,
        )

        self.assertIn(
            "network_measurement_scope",
            truthfulness,
        )

    def test_runtime_state(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        runtime = snapshot[
            "runtime"
        ]

        self.assertIn(
            runtime["status"],
            {
                "READY",
                "OFFLINE",
            },
        )

        self.assertIsInstance(
            runtime[
                "installed_model_count"
            ],
            int,
        )

        self.assertGreaterEqual(
            runtime[
                "installed_model_count"
            ],
            0,
        )

        self.assertIsInstance(
            runtime[
                "installed_models"
            ],
            list,
        )

    def test_hardware_schema(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        hardware = snapshot[
            "hardware"
        ]

        self.assertIn(
            "cpu",
            hardware,
        )

        self.assertIn(
            "memory",
            hardware,
        )

        self.assertIn(
            "gpu",
            hardware,
        )

        cpu = hardware[
            "cpu"
        ]

        memory = hardware[
            "memory"
        ]

        gpu = hardware[
            "gpu"
        ]

        self.assertIn(
            cpu["status"],
            {
                "AVAILABLE",
                "UNAVAILABLE",
            },
        )

        self.assertIn(
            memory["status"],
            {
                "AVAILABLE",
                "UNAVAILABLE",
            },
        )

        self.assertIn(
            gpu["status"],
            {
                "AVAILABLE",
                "UNAVAILABLE",
            },
        )

    def test_storage_schema(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        storage = snapshot[
            "storage"
        ]

        expected_storage = {
            "knowledge_documents",
            "knowledge_uploads",
            "knowledge_vectorstore",
            "sandbox",
            "workspace",
            "runtime_data",
        }

        self.assertTrue(
            expected_storage.issubset(
                storage.keys()
            )
        )

        for item in storage.values():
            self.assertIn(
                item["status"],
                {
                    "AVAILABLE",
                    "NOT_FOUND",
                    "INVALID",
                },
            )

            self.assertIsInstance(
                item["path"],
                str,
            )

    def test_network_tracking(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        network = snapshot[
            "network"
        ]

        self.assertEqual(
            network["tracking"],
            "application_level",
        )

        self.assertEqual(
            network["status"],
            "TRACKING",
        )

        for field in (
            "external_api_calls",
            "cloud_uploads",
            "local_network_events",
            "network_errors",
            "total_events",
        ):
            self.assertIn(
                field,
                network,
            )

            self.assertIsInstance(
                network[field],
                int,
            )

            self.assertGreaterEqual(
                network[field],
                0,
            )

    def test_verification_consistency(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        verification = snapshot[
            "verification"
        ]

        checks = verification[
            "checks"
        ]

        passed = sum(
            1
            for item in checks
            if item["status"] == "PASS"
        )

        failed = sum(
            1
            for item in checks
            if item["status"] == "FAIL"
        )

        checks_required = sum(
            1
            for item in checks
            if item["status"] == "CHECK"
        )

        self.assertEqual(
            passed,
            verification["passed"],
        )

        self.assertEqual(
            failed,
            verification["failed"],
        )

        self.assertEqual(
            checks_required,
            verification[
                "checks_required"
            ],
        )

        if failed > 0:
            self.assertEqual(
                verification["status"],
                "ATTENTION_REQUIRED",
            )
        elif checks_required > 0:
            self.assertEqual(
                verification["status"],
                "CHECK_REQUIRED",
            )
        else:
            self.assertEqual(
                verification["status"],
                "VERIFIED",
            )

    def test_workspace_is_available(self) -> None:
        snapshot = sovereignty_service.get_snapshot()

        workspace = snapshot[
            "storage"
        ][
            "workspace"
        ]

        self.assertEqual(
            workspace["status"],
            "AVAILABLE",
        )

        self.assertTrue(
            workspace["is_directory"]
        )


if __name__ == "__main__":
    unittest.main()