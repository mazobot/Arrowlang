# ArrowLang 2.0 — Compact Core Preview

ArrowLang 2.0 keeps the existing interpreter capabilities while introducing a compact front end inspired by symbolic languages.

## Requirements
- Python 3.10 or newer (tested with the Python standard library only)
- Tkinter (usually included with the Windows Python installer) for the IDE

## Run

From this folder:

```powershell
python main.py
```

Or run a program from Python:

```python
from arrowlang import ArrowLang

vm = ArrowLang()
vm.run('↑ "Hello from ArrowLang"')
```

## Compact syntax

```text
↑↑ double(x):
    →→→ x * 2

↑↑↑ answer = double(21)
↑ answer

↓↓ item ∈ range(3):
    ↑ item
```

| Symbol | Meaning |
|---|---|
| `↑` | output |
| `↑↑ name(args):` | function definition |
| `↑↑↑ name = value` | assignment |
| `→ condition:` | if |
| `←← condition:` | elif |
| `←:` | else |
| `↓ condition:` | while |
| `↓↓ item ∈ iterable:` | for |
| `→→` | break |
| `←←←` | continue |
| `→→→ value` | return |

The previous `↑↑ def name(args):` and `↓↓ item in iterable:` forms are still accepted for compatibility.

## Project layout

- `arrowlang.py` — stable public import API
- `core/lexer.py` — recognizes compact command tokens and source lines
- `core/parser.py` — normalizes compact syntax and preserves line indentation
- `core/nodes.py` — source token data structures
- `core/runtime.py` — existing execution engine, expression evaluator, functions, collections, math and external-function API
- `main.py` — Tkinter IDE and game drawing/input API
- `examples/` — example ArrowLang programs, including `snake.arrow` (a playable Snake game)
- `tests/` — basic automated tests

## Snake game

Open the IDE with `python main.py`, click **Snake**, then click **Run**.
Use the arrow keys to steer the snake. Press **R** to restart after a collision.
The game logic is written in `examples/snake.arrow`; the Tkinter code in
`main.py` provides only the window, drawing and keyboard input.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Compatibility notes

This is the first Core migration step, not the final expert language release. It introduces a separated lexer/parser front end and compact function/for syntax while retaining the established runtime and old syntax. New types, modules, matrix/vector libraries, debugger and a dedicated memory model are future stages, not claimed as implemented here.

Programs can call `read_text` and `write_text`; `read_text` also accepts HTTPS file
links from GitHub, such as:

```text
↑↑↑ contents = read_text("https://github.com/owner/repository/blob/main/data.txt")
↑ contents
```

Only run code you trust. Local file access and downloads from GitHub are not
sandboxed in this preview.
