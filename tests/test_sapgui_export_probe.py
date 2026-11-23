from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from sapgui_export_probe import workbook_evidence


class ExportEvidenceTests(unittest.TestCase):
    def write_workbook(self, path: Path, rows: str) -> None:
        with ZipFile(path, "w") as workbook:
            workbook.writestr("xl/workbook.xml", "<workbook/>")
            workbook.writestr(
                "xl/worksheets/sheet1.xml",
                '<worksheet xmlns="http://schemas.openxmlformats.org/'
                f'spreadsheetml/2006/main"><sheetData>{rows}</sheetData></worksheet>',
            )

    def test_requires_data_not_just_an_existing_workbook(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "export.xlsx"
            self.write_workbook(path, '<row r="1"><c><v>header</v></c></row><row r="2"/>')
            with self.assertRaisesRegex(RuntimeError, "no data rows"):
                workbook_evidence(path)
            self.write_workbook(
                path,
                '<row r="1"><c><v>header</v></c></row>'
                '<row r="2"><c><v>data</v></c></row>',
            )
            evidence = workbook_evidence(path)
            self.assertEqual(evidence["worksheet_rows"], [2])
            self.assertEqual(evidence["populated_worksheet_rows"], [2])

    def test_rejects_empty_file_and_missing_worksheets(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "export.xlsx"
            path.touch()
            with self.assertRaisesRegex(RuntimeError, "empty"):
                workbook_evidence(path)
            with ZipFile(path, "w") as workbook:
                workbook.writestr("xl/workbook.xml", "<workbook/>")
            with self.assertRaisesRegex(RuntimeError, "no worksheets"):
                workbook_evidence(path)


if __name__ == "__main__":
    unittest.main()
