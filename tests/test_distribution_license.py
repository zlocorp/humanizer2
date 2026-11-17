"""Ensure standalone skill distributions retain licensing information."""
import unittest
from pathlib import Path
from zipfile import ZipFile
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'humanizer2'


class DistributionLicenseTests(unittest.TestCase):
    def test_standalone_license_and_sources_match_repository(self):
        sources = {
            'LICENSE': ROOT / 'LICENSE',
            'THIRD_PARTY_NOTICES.md': ROOT / 'docs' / 'THIRD_PARTY_NOTICES.md',
        }
        for name, source in sources.items():
            with self.subTest(name=name):
                self.assertEqual(source.read_bytes(), (SKILL / name).read_bytes())
        self.assertIn('license: GPL-3.0-only', (SKILL / 'SKILL.md').read_text())

    def test_complete_skill_directory_is_self_contained(self):
        archive = BytesIO()
        with ZipFile(archive, 'w') as z:
            for path in SKILL.rglob('*'):
                if path.is_file():
                    z.write(path, path.relative_to(SKILL.parent))
        with ZipFile(archive) as z:
            for name in ('SKILL.md', 'LICENSE', 'THIRD_PARTY_NOTICES.md'):
                self.assertEqual(z.read('humanizer2/' + name), (SKILL / name).read_bytes())
