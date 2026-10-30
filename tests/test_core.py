import unittest
from unittest.mock import patch
from arrowlang import ArrowLang, ArrowLangError

class ArrowLangCoreTests(unittest.TestCase):
    def run_program(self, code):
        results = []
        language = ArrowLang(output=results.append)
        language.run(code)
        return language, results

    def test_function_and_return(self):
        code = '↑↑ podwoj(x):\n    →→→ x * 2\n↑ podwoj(7)'
        _, output = self.run_program(code)
        self.assertEqual(output, [14])

    def test_for_loop(self):
        code = '↑↑↑ suma = 0\n↓↓ i ∈ range(5):\n    ↑↑↑ suma = suma + i\n↑ suma'
        _, output = self.run_program(code)
        self.assertEqual(output, [10])

    def test_if_else(self):
        code = '↑↑↑ x = 4\n→ x > 3:\n    ↑ "yes"\n←:\n    ↑ "no"'
        _, output = self.run_program(code)
        self.assertEqual(output, ['yes'])

    def test_old_function_syntax(self):
        code = '↑↑ def old(x):\n    →→→ x + 1\n↑ old(4)'
        _, output = self.run_program(code)
        self.assertEqual(output, [5])

    def test_bad_indentation_gives_error(self):
        with self.assertRaises(ArrowLangError):
            self.run_program('↑↑ f():\n  ↑ 1')

    @patch("core.runtime.build_opener")
    def test_read_text_accepts_github_file_urls(self, build_opener):
        response = build_opener.return_value.open.return_value.__enter__.return_value
        response.read.return_value = b"hello from GitHub"

        _, output = self.run_program(
            '↑↑↑ contents = read_text("https://github.com/example/project/blob/main/file.txt")\n'
            "↑ contents"
        )

        self.assertEqual(output, ["hello from GitHub"])
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://github.com/example/project/blob/main/file.txt?raw=1",
        )

    def test_read_text_rejects_non_github_urls(self):
        with self.assertRaisesRegex(ArrowLangError, "Only HTTPS URLs"):
            ArrowLang._read_text("https://example.com/file.txt")

if __name__ == '__main__':
    unittest.main()
