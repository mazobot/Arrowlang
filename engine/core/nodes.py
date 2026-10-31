"""Small source-level structures used by the ArrowLang front end."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int

@dataclass(frozen=True)
class SourceLine:
    number: int
    indentation: int
    text: str
