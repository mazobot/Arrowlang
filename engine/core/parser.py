"""Compact syntax front-end. Normalizes new syntax for the stable runtime."""
from .lexer import Lexer, LexerError

class ParserError(Exception):
    pass

class Parser:
    def __init__(self):
        self.lexer = Lexer()

    def parse(self, source: str) -> str:
        try:
            token_result = self.lexer.tokenize(source)
            lines = token_result[1]
        except LexerError as error:
            raise ParserError(str(error)) from error

        normalized = []
        for line in lines:
            text = line.text
            if not text:
                normalized.append("")
                continue


            is_function_line = text.startswith("↑↑ ") and text.endswith(":")
            if is_function_line:
                if text.startswith("↑↑ def "):
                    
                    text = text
                else:
                    header = text[3:-1].strip()
                    if "(" in header and header.endswith(")"):
                        text = "↑↑ def " + header + ":"
                    else:
                        raise ParserError(f"Line {line.number}: expected a function name and parameters.")

            # Compact FOR separator: ↓↓ item ∈ collection:
            if text.startswith("↓↓ ") and text.endswith(":"):
                header = text[3:-1]
                if "∈" in header:
                    parts = header.split("∈", 1)
                    left = parts[0].strip()
                    right = parts[1].strip()
                    text = "↓↓ " + left + " in " + right + ":"

            spaces = " " * line.indentation
            normalized.append(spaces + text)

        return "\n".join(normalized)
