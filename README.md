
# ArrowLang Web IDE 2.0

This is the browser-based version of ArrowLang. This repository does not include a desktop version or the files needed to create a Windows EXE program.


## Project files

- `index.html` — the page with the editor.
- `style.css` — the page's appearance.
- `app.js` — behavior for the buttons, editor, and preview.
- `engine/` — ArrowLang interpreter files.
- `examples/` — example programs, including Snake.

## What you can do in Arrowlang

- write code in the editor with line numbers;
- use the Run, Example, Snake, Stop, and Clear buttons;
- see a program's output or errors;
- view games in the Canvas preview;
- use ArrowLang functions: `clear_screen()`, `draw_cell(x, y, color)`, `draw_text(text, x, y, color)`, `key_pressed(key)`, and `randint(min, max)`.


## Limitations

This version uses HTML Canvas instead of Tkinter. Features from the desktop version will not work in the browser unless adapted for JavaScript or Canvas. The interpreter runs in Pyodide's virtual file system, not directly on the computer's files.

