"""Compact syntax front-end. Normalizes new syntax for the stable runtime."""
from .lexer import Lexer, LexerError


class ParserError(Exception):
    pass


class Parser:
    def __init__(self):
        self.lexer = Lexer()

    def parse(self, source: str) -> str:
        try:
            unused_tokens, lines = self.lexer.tokenize(source)
        except LexerError as error:
            raise ParserError(str(error)) from error

        output_lines = []
        for line in lines:
            line_text = line.text

            if line_text == "":
                output_lines.append("")
                continue

            # Convert the short function header to the regular one.
            if line_text.startswith("↑↑ ") and line_text.endswith(":"):
                if not line_text.startswith("↑↑ def "):
                    header_text = line_text[3:-1].strip()

                    if "(" in header_text and header_text.endswith(")"):
                        line_text = "↑↑ def " + header_text + ":"
                    else:
                        error_message = f"Line {line.number}: expected a function name and parameters."
                        raise ParserError(error_message)

            # Change the loop separator to the syntax expected by the runtime.
            if line_text.startswith("↓↓ ") and line_text.endswith(":"):
                loop_text = line_text[3:-1]
                if "∈" in loop_text:
                    loop_parts = loop_text.split("∈", 1)
                    item_text = loop_parts[0].strip()
                    collection_text = loop_parts[1].strip()
                    line_text = "↓↓ " + item_text + " in " + collection_text + ":"

            indentation = " " * line.indentation
            output_lines.append(indentation + line_text)

        return "\n".join(output_lines)
