import unittest

from app.services.update_checker import _parse_merged_prs
from app.version import CURRENT_PR


class UpdateCheckerTests(unittest.TestCase):
    def test_only_new_merged_main_prs_are_updates(self):
        rows = [
            {
                "number": CURRENT_PR + 1,
                "title": "feat: next production update",
                "html_url": "https://github.com/drnecrotix/MMI2/pull/999",
                "merged_at": "2026-09-01T10:00:00Z",
                "base": {"ref": "main"},
            },
            {
                "number": CURRENT_PR + 2,
                "title": "open work",
                "html_url": "https://github.com/drnecrotix/MMI2/pull/1000",
                "merged_at": None,
                "base": {"ref": "main"},
            },
            {
                "number": CURRENT_PR + 3,
                "title": "merged to another branch",
                "html_url": "https://github.com/drnecrotix/MMI2/pull/1001",
                "merged_at": "2026-09-01T11:00:00Z",
                "base": {"ref": "develop"},
            },
        ]

        result = _parse_merged_prs(rows)

        self.assertTrue(result.update_available)
        self.assertEqual(result.latest_pr, CURRENT_PR + 1)
        self.assertEqual(len(result.merged_updates), 1)

    def test_current_or_older_prs_are_not_updates(self):
        rows = [
            {
                "number": CURRENT_PR,
                "title": "current build",
                "html_url": "https://github.com/drnecrotix/MMI2/pull/current",
                "merged_at": "2026-09-01T10:00:00Z",
                "base": {"ref": "main"},
            }
        ]

        result = _parse_merged_prs(rows)
        self.assertFalse(result.update_available)
        self.assertEqual(result.latest_pr, CURRENT_PR)


if __name__ == "__main__":
    unittest.main()
