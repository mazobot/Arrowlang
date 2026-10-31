"""Lexer for ArrowLang's compact arrow-command syntax."""
from .nodes import Token, SourceLine

COMMANDS = ("↑↑↑", "←←←", "→→→", "←←", "→→", "↓↓", "↑↑", "→", "←:", "↓", "↑")

class LexerError(Exception):
    pass

class Lexer:
    def tokenize(self, source: str):
        tokens = []
        lines = []
        for number, raw in enumerate(source.splitlines(), 1):
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" "))

            if stripped == "" or raw.lstrip().startswith("#"):
                lines.append(SourceLine(number, indent, stripped))
                continue

            leading = raw[:len(raw) - len(raw.lstrip())]
            if "\t" in leading:
                raise LexerError(f"Line {number}: use spaces instead of tabs.")

            text = stripped
            lines.append(SourceLine(number, indent, text))
            command = None
            for item in COMMANDS:
                is_command = text == item or text.startswith(item + " ")
                if item.endswith(":") and text.startswith(item):
                    is_command = True

                if is_command:
                    command = item
                    break
            if command:
                tokens.append(Token("COMMAND", command, number, indent + 1))
                rest = text[len(command):].strip()
                if rest:
                    tokens.append(Token("PAYLOAD", rest, number, indent + len(command) + 1))
            else:
                tokens.append(Token("EXPRESSION", text, number, indent + 1))
        return tokens, lines
