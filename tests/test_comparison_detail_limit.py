from datetime import date
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.services.excel_preview import PreviewResult
from app.services.schedule_compare import MAX_CHANGE_DETAILS, compare_preview_to_database


class ComparisonDetailLimitTests(unittest.TestCase):
    def test_large_first_import_keeps_full_counts_and_truncates_details(self):
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)

        employees = []
        day_entries = []
        for employee_index in range(17):
            work_number = f"T{employee_index:03d}"
            full_name = f"Тест Служител {employee_index}"
            employees.append({
                "work_number": work_number,
                "full_name": full_name,
                "team": "А",
                "day": 31,
                "night": 0,
                "leave": 0,
                "sick_leave": 0,
                "rest": 0,
                "unknown": 0,
            })
            for day in range(1, 32):
                day_entries.append({
                    "work_number": work_number,
                    "full_name": full_name,
                    "team": "А",
                    "work_date": date(2026, 8, day),
                    "shift_type": "day",
                    "raw_code": "1",
                })

        preview = PreviewResult(
            employees=employees,
            day_entries=day_entries,
            schedule_blocks=1,
            duplicate_employee_rows=0,
            conflicting_days=0,
            unknown_codes={},
            totals={"day": len(day_entries)},
        )

        with Session(engine) as db:
            result = compare_preview_to_database(db, preview, 2026, 8)

        self.assertEqual(result["new_days"], 527)
        self.assertEqual(result["changed_days"], 0)
        self.assertEqual(result["total_changes"], 527)
        self.assertEqual(len(result["details"]), MAX_CHANGE_DETAILS)
        self.assertTrue(result["details_truncated"])
        self.assertEqual(result["detail_limit"], MAX_CHANGE_DETAILS)


if __name__ == "__main__":
    unittest.main()
