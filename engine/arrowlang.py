"""Public API for ArrowLang 2.0."""
from core.runtime import ArrowLang, ArrowLangError, ReturnSignal, BreakSignal, ContinueSignal

__all__ = ["ArrowLang", "ArrowLangError", "ReturnSignal", "BreakSignal", "ContinueSignal"]


def run(source, output=print):
    interpreter = ArrowLang(output=output)
    interpreter.run(source)
    return interpreter.globals
