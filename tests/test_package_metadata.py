"""Check manifest consistency, icon files and local documentation link targets offline."""

import json
import re
import struct
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class PackageMetadataTests(unittest.TestCase):
    def test_manifest_versions_match(self):
        manifests = [json.loads((ROOT / name).read_text(encoding='utf-8'))
                     for name in ('plugin.json', '.claude-plugin/plugin.json')]
        version = manifests[0]['version']
        self.assertRegex(version, r'^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$')
        self.assertEqual(version, manifests[1]['version'])

    def test_declared_icons_exist_inside_package(self):
        manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
        interface = manifest['extensions']['com.openai']['interface']
        for key in ('logo', 'composerIcon'):
            with self.subTest(icon=key):
                value = interface[key]
                self.assertTrue(value)
                self.assertFalse(urlsplit(value).scheme, 'expected a packaged icon')
                target = (ROOT / value).resolve()
                self.assertTrue(target.is_relative_to(ROOT.resolve()))
                self.assertTrue(target.is_file(), f'missing icon: {value}')
                self.assertGreater(target.stat().st_size, 0)

    def test_listing_icons_are_512px_png_with_svg_source(self):
        manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
        interface = manifest['extensions']['com.openai']['interface']
        for key in ('logo', 'composerIcon'):
            with self.subTest(icon=key):
                self.assertEqual(interface[key], './assets/humanizer2.png')
                data = (ROOT / interface[key]).read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(data[12:16], b'IHDR')
                self.assertEqual(struct.unpack('>II', data[16:24]), (512, 512))
        self.assertTrue((ROOT / 'assets/humanizer2.svg').is_file())

    def test_russian_listing_translation(self):
        manifest = json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))
        translation = manifest['extensions']['com.openai']['publication']['translations']['ru-RU']
        for field, limit in (('subtitle', 30), ('description', 4000)):
            with self.subTest(field=field):
                value = translation[field]
                self.assertTrue(value.strip())
                self.assertLessEqual(len(value), limit)
                self.assertFalse(any(ord(c) < 32 and c != '\n' for c in value))
        self.assertNotIn('\n', translation['subtitle'])

    def test_local_documentation_link_targets_exist(self):
        # Check inline Markdown links outside fenced examples. Fragments are not
        # rendered here; this test validates file targets, not heading anchors.
        documents = [ROOT / name for name in ('README.md', 'CHANGELOG.md', 'SECURITY.md')]
        documents += sorted((ROOT / 'docs').glob('*.md'))
        for document in documents:
            text = re.sub(r'^```[^\n]*\n.*?^```[^\n]*$', '',
                          document.read_text(encoding='utf-8'), flags=re.MULTILINE | re.DOTALL)
            for link in re.findall(r'!?\[[^\]\n]*\]\(([^\s)]+)\)', text):
                parsed = urlsplit(link)
                if parsed.scheme or parsed.netloc or not parsed.path:
                    continue
                with self.subTest(document=str(document.relative_to(ROOT)), link=link):
                    target = (document.parent / unquote(parsed.path)).resolve()
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.exists(), f'missing link target: {link}')


if __name__ == '__main__':
    unittest.main()
