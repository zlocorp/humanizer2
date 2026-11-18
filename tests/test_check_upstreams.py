import contextlib
import http.client
import importlib.util
import io
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_upstreams.py'


class UpstreamCheckTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), 'upstream checker is missing')
        spec = importlib.util.spec_from_file_location('check_upstreams', SCRIPT)
        self.checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.checker)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manifest = Path(self.temp.name) / 'upstreams.json'

    def run_checker(self, entries, responses):
        self.manifest.write_text(json.dumps(entries), encoding='utf-8')
        before = self.manifest.read_bytes()
        output = io.StringIO()
        with patch.object(self.checker, 'MANIFEST_PATH', self.manifest), \
             patch.object(self.checker.urllib.request, 'urlopen', side_effect=responses) as request, \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.checker.main()
        self.assertEqual(before, self.manifest.read_bytes())
        return code, output.getvalue(), request

    def test_default_manifest_is_read_without_overriding_its_path(self):
        def response(*_args, **_kwargs):
            return io.BytesIO(json.dumps({'sha': 'a' * 40}).encode())

        output = io.StringIO()
        with patch.object(self.checker.urllib.request, 'urlopen', side_effect=response) as request, \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = self.checker.main()
        self.assertEqual(0, code)
        self.assertGreater(request.call_count, 0)
        self.assertIn('thevseprod/humanizer-ru', output.getvalue())

    def test_all_documented_sources_are_monitored(self):
        root = SCRIPT.parents[1]
        docs = (root / 'docs' / 'THIRD_PARTY_NOTICES.md').read_text(encoding='utf-8')
        documented = {name.lower() for name in re.findall(
            r'^\| \[([^]]+)\]\(https://github\.com/[^)]+\)', docs, re.MULTILINE)}
        entries = json.loads((root / 'scripts' / 'upstreams.json').read_text(encoding='utf-8'))
        monitored = {entry['repo'].lower() for entry in entries}
        self.assertTrue(documented, 'no documented sources found')
        self.assertEqual(documented, monitored)

    def test_reports_change_with_review_link_without_writing(self):
        base, current = 'a' * 40, 'b' * 40
        response = io.BytesIO(json.dumps({'sha': current}).encode())
        code, output, request = self.run_checker(
            [{'repo': 'example/editor', 'revision': base}], [response]
        )
        self.assertEqual(0, code)
        self.assertIn('example/editor', output)
        self.assertIn(f'https://github.com/example/editor/compare/{base}...{current}', output)
        sent_request = request.call_args.args[0]
        self.assertEqual('https://api.github.com/repos/example/editor/commits/HEAD', sent_request.full_url)
        self.assertGreater(request.call_args.kwargs['timeout'], 0)

    def test_unchanged_revision_does_not_offer_a_compare_link(self):
        revision = 'a' * 40
        code, output, _ = self.run_checker(
            [{'repo': 'example/editor', 'revision': revision}],
            [io.BytesIO(json.dumps({'sha': revision}).encode())],
        )
        self.assertEqual(0, code)
        self.assertIn('изменений нет', output)
        self.assertNotIn('/compare/', output)

    def test_one_failed_source_does_not_hide_remaining_results(self):
        base, current = 'a' * 40, 'b' * 40
        entries = [{'repo': 'example/one', 'revision': base},
                   {'repo': 'example/two', 'revision': base}]
        code, output, request = self.run_checker(
            entries, [URLError('network unavailable'), io.BytesIO(json.dumps({'sha': current}).encode())]
        )
        self.assertNotEqual(0, code)
        self.assertIn('example/one', output)
        self.assertIn('example/two', output)
        self.assertIn(current, output)
        self.assertEqual(2, request.call_count)

    def test_incomplete_http_response_does_not_stop_remaining_sources(self):
        base, current = 'a' * 40, 'b' * 40
        entries = [{'repo': 'example/one', 'revision': base},
                   {'repo': 'example/two', 'revision': base}]
        code, output, request = self.run_checker(
            entries, [http.client.IncompleteRead(b'partial'),
                      io.BytesIO(json.dumps({'sha': current}).encode())],
        )
        self.assertNotEqual(0, code)
        self.assertIn('example/one', output)
        self.assertIn('example/two', output)
        self.assertEqual(2, request.call_count)

    def test_rejects_invalid_revision_before_any_network_request(self):
        code, output, request = self.run_checker([{'repo': 'example/editor', 'revision': 'main'}], [])
        self.assertNotEqual(0, code)
        self.assertIn('revision', output.lower())
        request.assert_not_called()

    def test_rejects_invalid_repo_before_any_network_request(self):
        code, output, request = self.run_checker(
            [{'repo': 'example/editor/../../../something', 'revision': 'a' * 40}], []
        )
        self.assertNotEqual(0, code)
        self.assertIn('repo', output.lower())
        request.assert_not_called()

    def test_malformed_api_reply_is_reported_not_treated_as_unchanged(self):
        code, output, _ = self.run_checker(
            [{'repo': 'example/editor', 'revision': 'a' * 40}],
            [io.BytesIO(b'{"sha":"not-a-commit"}')],
        )
        self.assertNotEqual(0, code)
        self.assertIn('example/editor', output)
        self.assertNotIn('UNCHANGED', output)


if __name__ == '__main__':
    unittest.main()
