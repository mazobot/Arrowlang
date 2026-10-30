"""Lexer for ArrowLang's compact arrow-command syntax."""
from .nodes import Token, SourceLine

COMMANDS = ("↑↑↑", "←←←", "→→→", "←←", "→→", "↓↓", "↑↑", "→", "←:", "↓", "↑")

class LexerError(Exception):
    pass

class Lexer:
    def tokenize(self, source: str):
        tokens = []
        source_lines = []

        for line_number, raw_line in enumerate(source.splitlines(), start=1):
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            line_text = raw_line.strip()

            if not line_text or raw_line.lstrip().startswith("#"):
                source_lines.append(SourceLine(line_number, indent, line_text))
                continue

            leading_whitespace = raw_line[:len(raw_line) - len(raw_line.lstrip())]
            if "\t" in leading_whitespace:
                raise LexerError(f"Line {line_number}: use spaces instead of tabs.")

            source_lines.append(SourceLine(line_number, indent, line_text))

            command = None
            for possible_command in COMMANDS:
                exact_match = line_text == possible_command
                has_payload = line_text.startswith(possible_command + " ")
                colon_match = possible_command.endswith(":") and line_text.startswith(possible_command)

                if exact_match or has_payload or colon_match:
                    command = possible_command
                    break

            if command is None:
                tokens.append(Token("EXPRESSION", line_text, line_number, indent + 1))
                continue

            tokens.append(Token("COMMAND", command, line_number, indent + 1))
            payload = line_text[len(command):].strip()
            if payload:
                tokens.append(Token("PAYLOAD", payload, line_number, indent + len(command) + 1))

        return tokens, source_lines
