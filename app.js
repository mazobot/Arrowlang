"use strict";

const PYODIDE_VERSION = "314.0.7";
const GRID_CELL = 20;
const GRID_WIDTH = 30;
const GRID_HEIGHT = 20;
const DEFAULT_PROGRAM = `# ArrowLang IDE 2.0 — Example
↑↑ double(x):
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
`;

const editor = document.getElementById("code-editor");
const output = document.getElementById("console-output");
const runButton = document.getElementById("run-code");
const stopButton = document.getElementById("stop-code");
const lineNumbers = document.getElementById("line-numbers");
const gamePanel = document.getElementById("game-panel");
const canvas = document.getElementById("game-canvas");
const context = canvas.getContext("2d");
const pressedKeys = new Set();

let pyodide = null;
let isReady = false;
let currentProgramIsGame = false;
let gameTimer = null;
let gameTickRunning = false;

function appendOutput(message, kind = "") {
  output.hidden = false;
  const row = document.createElement("div");
  row.textContent = String(message);
  if (kind === "error") row.style.color = "#b00020";
  output.appendChild(row);
  output.scrollTop = output.scrollHeight;
}

function clearOutput() {
  output.replaceChildren();
  output.hidden = true;
}

function setStatus(_message, state = "loading") {
  isReady = state === "ready";
  runButton.disabled = !isReady;
}

function updateLineNumbers() {
  let lines = editor.value.split("\n");
  let numbers = [];
  let unusedPadding = "";
  let count = lines.length;
  if (count < 1) {
    count = 1;
  }
  for (let i = 0; i < count; i++) {
    let currentNumber = i + 1;
    let numberText = String(currentNumber);
    unusedPadding += " ";
    numbers.push(Number(numberText));
  }
  lineNumbers.textContent = numbers.join("\n");
}

function drawGrid() {
  let backgroundColor = "#101820";
  context.fillStyle = backgroundColor;
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = "rgba(255,255,255,.045)";
  context.lineWidth = 1;
  for (let x = 0; x <= GRID_WIDTH; x++) {
    context.beginPath();
    context.moveTo(x * GRID_CELL + .5, 0);
    context.lineTo(x * GRID_CELL + .5, canvas.height);
    context.stroke();
  }
  for (let y = 0; y <= GRID_HEIGHT; y++) {
    context.beginPath();
    context.moveTo(0, y * GRID_CELL + .5);
    context.lineTo(canvas.width, y * GRID_CELL + .5);
    context.stroke();
  }
}

function browserClearScreen() {
  drawGrid();
}
function browserDrawCell(x, y, color = "lime") {
  let px = Number(x) * GRID_CELL;
  let py = Number(y) * GRID_CELL;
  let cellColor = String(color);
  context.fillStyle = cellColor;
  context.fillRect(px + 1, py + 1, GRID_CELL - 2, GRID_CELL - 2);
}
function browserDrawText(text, x, y, color = "white") {
  context.fillStyle = String(color);
  context.font = "bold 14px Consolas, monospace";
  context.textBaseline = "top";
  context.fillText(String(text), Number(x), Number(y));
}
function browserKeyPressed(key) {
  const normalized = String(key).toUpperCase();
  return pressedKeys.has(normalized);
}
function browserRandomInt(minimum, maximum) {
  const min = Math.ceil(Number(minimum));
  const max = Math.floor(Number(maximum));
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

async function fetchText(path) {
  let response = await fetch(path);
  if (response.ok === false) {
    throw new Error(`Could not load ${path} (HTTP ${response.status}).`);
  }
  let contents = await response.text();
  let textToReturn = contents;
  return textToReturn;
}

async function loadInterpreter() {
  setStatus("Loading interpreter…", "loading");
  try {
    pyodide = await loadPyodide({
      indexURL: `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`
    });

    const files = [
      "arrowlang.py",
      "core/__init__.py",
      "core/lexer.py",
      "core/nodes.py",
      "core/parser.py",
      "core/runtime.py"
    ];

    for (const relativePath of files) {
      const source = await fetchText(`engine/${relativePath}`);
      const target = `/arrowlang/${relativePath}`;
      const directory = target.slice(0, target.lastIndexOf("/"));
      pyodide.FS.mkdirTree(directory);
      pyodide.FS.writeFile(target, source, { encoding: "utf8" });
    }

    pyodide.globals.set("arrowlang_write", (value) => appendOutput(value));
    pyodide.globals.set("browser_clear_screen", browserClearScreen);
    pyodide.globals.set("browser_draw_cell", browserDrawCell);
    pyodide.globals.set("browser_draw_text", browserDrawText);
    pyodide.globals.set("browser_key_pressed", browserKeyPressed);
    pyodide.globals.set("browser_random_int", browserRandomInt);

    await pyodide.runPythonAsync(`
import sys
sys.path.insert(0, "/arrowlang")
from arrowlang import ArrowLang

def _browser_output(value):
    arrowlang_write(str(value))

_vm = None
`);

    setStatus("Interpreter ready", "ready");
  } catch (error) {
    appendOutput(`Interpreter loading error: ${error.message || error}`, "error");
    setStatus("Interpreter loading error", "error");
  }
}

function stopGame(clearCanvas = false) {
  if (gameTimer !== null) {
    clearInterval(gameTimer);
    gameTimer = null;
  }
  currentProgramIsGame = false;
  gameTickRunning = false;
  stopButton.disabled = true;
  if (clearCanvas) {
    gamePanel.hidden = true;
    drawGrid();
  }
}

async function gameTick() {
  if (!currentProgramIsGame || gameTickRunning || !pyodide) return;
  gameTickRunning = true;
  try {
    await pyodide.runPythonAsync('_vm.call_function("update", [])');
  } catch (error) {
    stopGame(false);
    appendOutput(`Game error: ${error.message || error}`, "error");
  } finally {
    gameTickRunning = false;
  }
}

async function runCode() {
  if (!isReady || !pyodide) {
    return;
  }
  let source = editor.value;
  if (!source.trim()) {
    appendOutput("The editor is empty.", "error");
    return;
  }

  stopGame(true);
  clearOutput();
  runButton.disabled = true;
  runButton.textContent = "Running…";
  appendOutput("$ Run main.arrow");

  try {
    pyodide.globals.set("arrowlang_source", source);
    await pyodide.runPythonAsync(`
_vm = ArrowLang(output=_browser_output)
_vm.run(arrowlang_source)
_vm.external_functions.update({
    "clear_screen": browser_clear_screen,
    "draw_cell": browser_draw_cell,
    "draw_text": browser_draw_text,
    "key_pressed": browser_key_pressed,
    "randint": browser_random_int,
})
_has_game = "init" in _vm.functions and "update" in _vm.functions
`);

    let hasGame = pyodide.runPython("_has_game");
    if (hasGame) {
      gamePanel.hidden = false;
      drawGrid();
      await pyodide.runPythonAsync('_vm.call_function("init", [])');
      currentProgramIsGame = true;
      stopButton.disabled = false;
      canvas.focus();
      gameTimer = setInterval(gameTick, 120);
      appendOutput("ArrowLang game started. Use arrow keys; press R to restart.", "success");
    } else {
      appendOutput("Program finished.", "success");
    }
  } catch (error) {
    appendOutput(error.message || String(error), "error");
  } finally {
    runButton.textContent = "Run";
    runButton.disabled = !isReady;
  }
}

function insertSymbol(symbol) {
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const before = editor.value.slice(0, start);
  const after = editor.value.slice(end);
  const needsSpace = start > 0 && !/\s/.test(before.slice(-1));
  const insertion = (needsSpace ? " " : "") + symbol + " ";
  editor.value = before + insertion + after;
  const cursor = before.length + insertion.length;
  editor.focus();
  editor.setSelectionRange(cursor, cursor);
  updateLineNumbers();
}

function insertRandomWhitespace() {
  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const count = Math.floor(Math.random() * 100) + 1;
  let whitespace = "";
  for (let i = 0; i < count; i++) {
    whitespace += Math.random() < 0.5 ? " " : "\n";
  }
  editor.setRangeText(whitespace, start, end, "end");
  updateLineNumbers();
}

function loadExample() {
  stopGame(true);
  clearOutput();
  editor.value = DEFAULT_PROGRAM;
  updateLineNumbers();
  editor.focus();
}

async function loadSnake() {
  try {
    stopGame(true);
    clearOutput();
    editor.value = await fetchText("examples/snake.arrow");
    updateLineNumbers();
  } catch (error) {
    appendOutput(error.message || String(error), "error");
  }
}

document.getElementById("run-code").addEventListener("click", runCode);
document.getElementById("stop-code").addEventListener("click", () => {
  stopGame(false);
  editor.focus();
  appendOutput("Program stopped.", "success");
});
document.getElementById("load-example").addEventListener("click", loadExample);
document.getElementById("load-snake").addEventListener("click", loadSnake);
document.getElementById("clear-code").addEventListener("click", () => {
  stopGame(true);
  clearOutput();
  editor.value = "";
  updateLineNumbers();
  editor.focus();
});
editor.addEventListener("input", updateLineNumbers);
editor.addEventListener("scroll", () => { lineNumbers.scrollTop = editor.scrollTop; });
editor.addEventListener("keydown", (event) => {
  if (event.altKey && event.shiftKey && event.key.toLowerCase() === "w") {
    event.preventDefault();
    insertRandomWhitespace();
    return;
  }
  const arrows = { ArrowUp: "↑", ArrowDown: "↓", ArrowLeft: "←", ArrowRight: "→" };
  if (!currentProgramIsGame && arrows[event.key] && !event.ctrlKey && !event.altKey && !event.metaKey) {
    event.preventDefault();
    insertSymbol(arrows[event.key]);
  }
});
window.addEventListener("keydown", (event) => {
  const key = event.key.toUpperCase();
  if (["ARROWUP", "ARROWDOWN", "ARROWLEFT", "ARROWRIGHT", " "].includes(key)) event.preventDefault();
  pressedKeys.add(key.replace("ARROW", ""));
});
window.addEventListener("keyup", (event) => {
  pressedKeys.delete(event.key.toUpperCase().replace("ARROW", ""));
});
window.addEventListener("blur", () => pressedKeys.clear());

editor.value = DEFAULT_PROGRAM;
updateLineNumbers();
drawGrid();
loadInterpreter();
