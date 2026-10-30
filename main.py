import random
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from arrowlang import ArrowLang, ArrowLangError


EXAMPLE = '''↑↑ double(x):
    →→→ x * 2

↑↑↑ total = 0

↓↓ i ∈ range(5):
    ↑↑↑ total = total + i

↑ "Function result:"
↑ double(7)

↑ "Sum of numbers from 0 to 4:"
↑ total

↑↑↑ counter = 0
↓ counter < 3:
    ↑ counter
    ↑↑↑ counter = counter + 1

→ total == 10:
    ↑ "Everything works!"
←:
    ↑ "Something went wrong."
'''


editor = None
console = None
root_window = None
active_game = None


def write_console(text):
    if console is None:
        return
    console.configure(state="normal")
    console.insert("end", str(text) + "\n")
    console.see("end")
    console.configure(state="disabled")


class ArrowLangGame:
    """Simple graphical API for ArrowLang programs, without pygame."""

    CELL = 20
    WIDTH = 30
    HEIGHT = 20
    KEY_ALIASES = {
        "ARROWUP": "UP",
        "ARROWDOWN": "DOWN",
        "ARROWLEFT": "LEFT",
        "ARROWRIGHT": "RIGHT",
    }

    def __init__(self, root):
        self.root = root
        self.window = None
        self.canvas = None
        self.keys_down = set()
        self.interpreter = None
        self.running = False
        self.after_id = None

    def open_window(self):
        if self.window is not None and self.window.winfo_exists():
            self.window.destroy()

        self.window = tk.Toplevel(self.root)
        self.window.title("ArrowLang Game")
        self.window.resizable(False, False)
        self.canvas = tk.Canvas(
            self.window,
            width=self.WIDTH * self.CELL,
            height=self.HEIGHT * self.CELL,
            background="#101820",
            highlightthickness=0,
        )
        self.canvas.pack()
        self.window.bind("<KeyPress>", self.on_key_down)
        self.window.bind("<KeyRelease>", self.on_key_up)
        self.canvas.bind("<KeyPress>", self.on_key_down)
        self.canvas.bind("<KeyRelease>", self.on_key_up)
        self.canvas.focus_set()
        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def on_key_down(self, event):
        self.keys_down.add(self.normalize_key(event.keysym))

    def on_key_up(self, event):
        self.keys_down.discard(self.normalize_key(event.keysym))

    @classmethod
    def normalize_key(cls, key):
        key = str(key).upper()
        return cls.KEY_ALIASES.get(key, key)

    def key_pressed(self, key):
        return self.normalize_key(key) in self.keys_down

    def clear_screen(self):
        if self.canvas is not None:
            self.canvas.delete("all")

    def draw_text(self, text, x, y, color="white"):
        if self.canvas is not None:
            self.canvas.create_text(
                x, y, text=str(text), fill=str(color),
                anchor="nw", font=("Consolas", 14, "bold")
            )

    def draw_cell(self, x, y, color="lime"):
        if self.canvas is not None:
            x1 = int(x) * self.CELL
            y1 = int(y) * self.CELL
            self.canvas.create_rectangle(
                x1 + 1, y1 + 1, x1 + self.CELL - 1, y1 + self.CELL - 1,
                fill=str(color), outline=""
            )

    def start(self, interpreter):
        self.close()
        self.interpreter = interpreter
        self.open_window()
        self.running = True

        try:
            self.interpreter.call_function("init", [])
            self.tick()
            return True
        except Exception as error:
            self.running = False
            write_console(f"Game error: {error}")
            self.close()
            return False

    def tick(self):
        if not self.running or self.window is None:
            return

        try:
            result = self.interpreter.call_function("update", [])
            if result is False:
                self.running = False
                self.draw_text("KONIEC GRY", 220, 180, "white")
                return
        except Exception as error:
            self.running = False
            write_console(f"Game error: {error}")
            return

        self.after_id = self.root.after(120, self.tick)

    def close(self):
        self.running = False
        if self.after_id is not None:
            try:
                self.root.after_cancel(self.after_id)
            except tk.TclError:
                pass
            self.after_id = None
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self.window.destroy()
            except tk.TclError:
                pass
        self.window = None
        self.canvas = None
        self.keys_down.clear()

    def register_functions(self, interpreter):
        interpreter.external_functions.update({
            "clear_screen": self.clear_screen,
            "draw_text": self.draw_text,
            "draw_cell": self.draw_cell,
            "key_pressed": self.key_pressed,
            "randint": random.randint,
        })


def run_program():
    global active_game

    if active_game is not None:
        active_game.close()
        active_game = None

    console.configure(state="normal")
    console.delete("1.0", "end")
    source = editor.get("1.0", "end-1c")

    interpreter = ArrowLang(
        output=lambda value: console.insert("end", str(value) + "\n")
    )
    game = ArrowLangGame(root_window)
    game.register_functions(interpreter)

    try:
        interpreter.run(source)

        # If the program defines init() and update(), run it as a game.
        if "init" in interpreter.functions and "update" in interpreter.functions:
            if active_game is not None:
                active_game.close()
            active_game = game
            if game.start(interpreter):
                console.insert("end", "\nArrowLang game started.\n")
            else:
                active_game = None
        else:
            console.insert("end", "\nProgram finished.\n")

    except ArrowLangError as error:
        console.insert("end", f"\nArrowLang error: {error}\n")
    except Exception as error:
        console.insert("end", f"\nInternal error: {error}\n")

    console.configure(state="disabled")


def stop_program():
    """Stop the currently running game without closing the IDE."""
    global active_game
    if active_game is not None:
        active_game.close()
        active_game = None
        write_console("\nGame stopped.")
    else:
        write_console("No active game to stop.")


def clear_editor():
    editor.delete("1.0", "end")


def open_file():
    filepath = filedialog.askopenfilename(
        title="Open ArrowLang file",
        filetypes=(("ArrowLang files", "*.arrow"), ("Text files", "*.txt"), ("All files", "*.*")),
    )
    if not filepath:
        return
    try:
        source = Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        write_console(f"Could not open file: {error}")
        return
    editor.delete("1.0", "end")
    editor.insert("1.0", source)
    write_console(f"Opened {Path(filepath).name}.")


def save_file():
    filepath = filedialog.asksaveasfilename(
        title="Save ArrowLang file",
        defaultextension=".arrow",
        filetypes=(("ArrowLang files", "*.arrow"), ("Text files", "*.txt"), ("All files", "*.*")),
    )
    if not filepath:
        return
    try:
        Path(filepath).write_text(editor.get("1.0", "end-1c"), encoding="utf-8")
    except (OSError, UnicodeError) as error:
        write_console(f"Could not save file: {error}")
        return
    write_console(f"Saved {Path(filepath).name}.")


def insert_example():
    editor.delete("1.0", "end")
    editor.insert("1.0", EXAMPLE)


def insert_snake_example():
    """Load the Snake game written in ArrowLang into the editor."""
    snake_path = Path(__file__).parent / "examples" / "snake.arrow"
    try:
        source = snake_path.read_text(encoding="utf-8")
    except OSError as error:
        write_console(f"Could not load Snake example: {error}")
        return
    editor.delete("1.0", "end")
    editor.insert("1.0", source)
    write_console("Snake example loaded. Press Run to start the game.")


class ArrowLangIDE:
    def __init__(self, root):
        global editor, console, root_window
        root_window = root

        root.title("ArrowLang IDE 2.0")
        root.protocol("WM_DELETE_WINDOW", self.close_ide)
        root.geometry("950x700")
        root.minsize(650, 450)

        toolbar = ttk.Frame(root, padding=8)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="ArrowLang IDE 2.0").pack(side="left")

        actions = (
            ("■ Stop", stop_program),
            ("▶ Run", run_program),
            ("Save", save_file),
            ("Open", open_file),
            ("Clear", clear_editor),
            ("Snake", insert_snake_example),
            ("Example", insert_example),
        )
        for label, callback in actions:
            ttk.Button(toolbar, text=label, command=callback).pack(
                side="right", padx=4
            )

        ttk.Label(root, text="Code editor", padding=(8, 4)).pack(anchor="w")

        self.editor = tk.Text(
            root, wrap="none", font=("Consolas", 12),
            undo=True, padx=8, pady=8
        )
        editor = self.editor
        self.editor.bind("<Up>", self.insert_arrow)
        self.editor.bind("<Down>", self.insert_arrow)
        self.editor.bind("<Left>", self.insert_arrow)
        self.editor.bind("<Right>", self.insert_arrow)
        self.editor.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.editor.insert("1.0", EXAMPLE)

        ttk.Label(root, text="Console", padding=(8, 4)).pack(anchor="w")
        console = tk.Text(
            root, height=12, font=("Consolas", 11), state="disabled",
            background="#171717", foreground="#eeeeee", padx=8, pady=8
        )
        console.pack(fill="x", padx=8, pady=(0, 8))

    def close_ide(self):
        global active_game
        if active_game is not None:
            active_game.close()
            active_game = None
        root_window.destroy()

    def insert_arrow(self, event):
        arrow = {"Up": "↑", "Down": "↓", "Left": "←", "Right": "→"}.get(
            event.keysym
        )
        if arrow:
            self.editor.insert("insert", arrow)
            return "break"


def main():
    root = tk.Tk()
    ArrowLangIDE(root)
    root.mainloop()


if __name__ == "__main__":
    main()