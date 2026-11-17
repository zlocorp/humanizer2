"""Check package and example structure without running a language model."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / 'skills'
MODES = ('edit', 'review', 'rewrite', 'write')


def frontmatter(text):
    match = re.match(r'\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)', text, re.DOTALL)
    if not match:
        raise ValueError('missing frontmatter delimiters')
    return match.group(1), text[match.end():]


def codex_implicit_disabled(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.fullmatch(r'policy:[ \t]*(?:#.*)?', line):
            block = []
            for child in lines[index + 1:]:
                if child.strip() and not child.startswith((' ', '\t', '#')):
                    break
                block.append(child)
            return bool(re.search(r'(?im)^[ \t]+allow_implicit_invocation:[ \t]*false[ \t]*(?:#.*)?$',
                                  '\n'.join(block)))
    return False


class SkillStructureTests(unittest.TestCase):
    def test_entry_points_have_names_and_descriptions(self):
        required = {'humanizer2', *(f'humanizer2-{mode}' for mode in MODES)}
        entries = {path.parent.name: path for path in SKILLS.glob('*/SKILL.md')}
        self.assertTrue(required <= entries.keys(), f'missing skills: {required - entries.keys()}')

        for folder, path in entries.items():
            with self.subTest(skill=folder):
                metadata, body = frontmatter(path.read_text(encoding='utf-8'))
                names = re.findall(r'^name:[ \t]*(\S[^\n]*)$', metadata, re.MULTILINE)
                descriptions = re.findall(r'^description:[ \t]*(\S[^\n]*)$', metadata, re.MULTILINE)
                self.assertEqual(len(names), 1)
                name = names[0].strip()
                if name.startswith(('"', "'")):
                    self.assertTrue(len(name) >= 2 and name.endswith(name[0]))
                    name = name[1:-1]
                self.assertEqual(name, folder)
                self.assertRegex(folder, r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
                self.assertEqual(len(descriptions), 1)
                description = descriptions[0].strip()
                self.assertNotIn(description, ('""', "''", 'null', '~'))
                self.assertFalse(description.startswith('#'))
                if description.startswith(('"', "'")):
                    self.assertTrue(len(description) >= 2 and description.endswith(description[0]))
                if description in ('>', '>-', '>+', '|', '|-', '|+'):
                    self.assertRegex(metadata, r'(?m)^description:[ \t]*[>|][+-]?[ \t]*\r?\n[ \t]+\S')
                instructions = re.sub(r'<!--.*?-->', '', body, flags=re.DOTALL)
                instructions = re.sub(r'(?m)^[ \t]*#{1,6}(?:[ \t]+.*)?$', '', instructions)
                self.assertTrue(instructions.strip(), 'missing skill instructions')

    def test_main_skill_allows_automatic_selection(self):
        folder = SKILLS / 'humanizer2'
        metadata, _ = frontmatter((folder / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertNotRegex(metadata, r'(?im)^disable-model-invocation:[ \t]*true[ \t]*(?:#.*)?$')
        policy = folder / 'agents' / 'openai.yaml'
        if policy.exists():
            self.assertFalse(codex_implicit_disabled(policy.read_text(encoding='utf-8')))

    def test_explicit_modes_reference_shared_skill_and_require_invocation(self):
        shared = (SKILLS / 'humanizer2' / 'SKILL.md').resolve()
        for mode in MODES:
            with self.subTest(mode=mode):
                folder = SKILLS / f'humanizer2-{mode}'
                text = (folder / 'SKILL.md').read_text(encoding='utf-8')
                metadata, _ = frontmatter(text)
                references = re.findall(r'`(\.\./[^`]+/SKILL\.md)`', text)
                self.assertTrue(any((folder / ref).resolve() == shared for ref in references))
                self.assertTrue(shared.is_file())
                self.assertRegex(metadata, r'(?im)^disable-model-invocation:[ \t]*true[ \t]*(?:#.*)?$')
                policy = (folder / 'agents' / 'openai.yaml').read_text(encoding='utf-8')
                self.assertTrue(codex_implicit_disabled(policy))

    def test_editorial_examples_have_requests_and_checks(self):
        text = (ROOT / 'docs' / 'EDITORIAL_EXAMPLES.md').read_text(encoding='utf-8')
        cases = re.split(r'^## (\d+)\. [^\n]+\n', text, flags=re.MULTILINE)
        self.assertGreater(len(cases), 1, 'no editorial examples found')
        numbers = [int(n) for n in cases[1::2]]
        self.assertEqual(numbers, list(range(1, len(numbers) + 1)))
        for number, body in zip(numbers, cases[2::2]):
            with self.subTest(example=number):
                request = re.search(r'(?im)^(?:\*\*)?(?:Запрос|Request)(?:\*\*)?\s*:', body)
                if not request:
                    request = re.search(r'(?im)^\*\*(?:Запрос|Request)\*\*\s*$', body)
                check = re.search(r'(?im)^(?:Проверка|Критерий|Критерии|Check)[.:]', body)
                self.assertIsNotNone(request, 'missing request')
                self.assertIsNotNone(check, 'missing check')
                self.assertGreater(check.start(), request.end())
                self.assertTrue(body[request.end():check.start()].strip())
                self.assertTrue(body[check.end():].strip())


if __name__ == '__main__':
    unittest.main()
