from datetime import datetime
from io import BytesIO
import unittest

from openpyxl import Workbook

from app.services.excel_period import detect_schedule_period


class ExcelPeriodDetectionTests(unittest.TestCase):
    def _bytes(self, value, title="ГРАФИК") -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = title
        ws["A1"] = value
        stream = BytesIO()
        wb.save(stream)
        return stream.getvalue()

    def test_detects_bulgarian_month_and_year_from_text(self):
        result = detect_schedule_period(
            self._bytes("Месечен график за август 2026 г."),
            "schedule.xlsx",
        )
        self.assertIsNotNone(result)
        self.assertEqual((result.year, result.month), (2026, 8))

    def test_detects_period_from_excel_date(self):
        result = detect_schedule_period(
            self._bytes(datetime(2026, 9, 1)),
            "schedule.xlsx",
        )
        self.assertIsNotNone(result)
        self.assertEqual((result.year, result.month), (2026, 9))
        self.assertEqual(result.confidence, "high")

    def test_returns_none_when_period_is_missing(self):
        result = detect_schedule_period(
            self._bytes("График без посочен месец"),
            "schedule.xlsx",
        )
        self.assertIsNone(result)

    def test_filename_can_supply_period(self):
        result = detect_schedule_period(
            self._bytes("График"),
            "MMI2_07-2026.xlsx",
        )
        self.assertIsNotNone(result)
        self.assertEqual((result.year, result.month), (2026, 7))


if __name__ == "__main__":
    unittest.main()
