
import ast
import operator
import math
import random
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener,
)

from .parser import Parser, ParserError


GITHUB_HOSTS = {"github.com", "raw.githubusercontent.com"}


class ArrowLangError(Exception):
    pass


class _GitHubRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self, request, response, code, message, headers, new_url
    ):
        redirect_url = urlsplit(urljoin(request.full_url, new_url))
        if (
            redirect_url.scheme != "https"
            or redirect_url.hostname not in GITHUB_HOSTS
        ):
            raise ArrowLangError("GitHub file URL redirected to an unsupported host.")
        return super().redirect_request(
            request, response, code, message, headers, new_url
        )


class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value


class BreakSignal(Exception):
    pass


class ContinueSignal(Exception):
    pass


BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.BitAnd: operator.and_,
    ast.BitOr: operator.or_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
}

COMPARE_OPERATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda left, right: left in right,
    ast.NotIn: lambda left, right: left not in right,
    ast.Is: operator.is_,
    ast.IsNot: operator.is_not,
}

UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Not: operator.not_,
}


class ArrowLang:
    def __init__(self, output=print):
        self.globals = {}
        self.functions = {}
        self.output = output
        self.loop_limit = 100_000
        self.loop_steps = 0
        self.external_functions = {}
        self.unused_runtime_noise = (3 * 7) - 21

    # --------------------------------------------------
    # PARSER: converts text into internal instructions
    # --------------------------------------------------

    def parse_block(self, lines, index=0, indentation=0):
        statements = []

        while index < len(lines):
            raw = lines[index]

            if not raw.strip() or raw.lstrip().startswith("#"):
                index += 1
                continue

            if "\t" in raw[:len(raw) - len(raw.lstrip())]:
                raise ArrowLangError(
                    f"Line {index + 1}: use spaces instead of tabs."
                )

            indent = len(raw) - len(raw.lstrip(" "))
            text = raw.strip()

            if indent < indentation:
                break

            if indent > indentation:
                raise ArrowLangError(
                    f"Line {index + 1}: unexpected indentation."
                )

            # These statements belong to the previous if.
            if text == "←:" or text.startswith("←← "):
                break

            # Function: ↑↑ def name(a, b):
            if text.startswith("↑↑ def ") and text.endswith(":"):
                header = text[7:-1].strip()

                if "(" not in header or not header.endswith(")"):
                    raise ArrowLangError(
                        f"Line {index + 1}: invalid function definition."
                    )

                name, params_text = header.split("(", 1)
                name = name.strip()
                params_text = params_text[:-1].strip()

                if not name.isidentifier():
                    raise ArrowLangError(
                        f"Line {index + 1}: invalid function name."
                    )

                params = []
                seen_default = False
                for param in [p.strip() for p in params_text.split(",") if p.strip()]:
                    if "=" in param:
                        param_name, default_value = param.split("=", 1)
                        param_name = param_name.strip()
                        default_value = default_value.strip()
                        if not param_name.isidentifier() or not default_value:
                            raise ArrowLangError(
                                f"Line {index + 1}: invalid function parameter."
                            )
                        seen_default = True
                        params.append((param_name, default_value))
                    else:
                        if seen_default:
                            raise ArrowLangError(
                                f"Line {index + 1}: default parameters must come last."
                            )
                        if not param.isidentifier():
                            raise ArrowLangError(
                                f"Line {index + 1}: invalid function parameter."
                            )
                        params.append(param)

                parameter_names = [
                    param[0] if isinstance(param, tuple) else param
                    for param in params
                ]
                if len(parameter_names) != len(set(parameter_names)):
                    raise ArrowLangError(
                        f"Line {index + 1}: duplicate parameter."
                    )

                body, index = self.parse_block(
                    lines, index + 1, indentation + 4
                )

                statements.append(("def", name, params, body))
                continue

            # Condition: → condition:
            if text.startswith("→ ") and text.endswith(":"):
                condition = text[2:-1].strip()

                if not condition:
                    raise ArrowLangError(
                        f"Line {index + 1}: condition cannot be empty."
                    )

                body, index = self.parse_block(
                    lines, index + 1, indentation + 4
                )

                branches = [(condition, body)]
                else_body = []

                # Handle elif and else.
                while index < len(lines):
                    next_raw = lines[index]

                    if not next_raw.strip() or next_raw.lstrip().startswith("#"):
                        index += 1
                        continue

                    next_indentation = len(next_raw) - len(next_raw.lstrip(" "))
                    if next_indentation != indentation:
                        break

                    next_text = next_raw.strip()

                    if next_text.startswith("←← ") and next_text.endswith(":"):
                        elif_condition = next_text[3:-1].strip()
                        if not elif_condition:
                            raise ArrowLangError(
                                f"Line {index + 1}: condition cannot be empty."
                            )
                        elif_body, index = self.parse_block(
                            lines, index + 1, indentation + 4
                        )
                        branches.append((elif_condition, elif_body))
                        continue

                    if next_text == "←:":
                        else_body, index = self.parse_block(
                            lines, index + 1, indentation + 4
                        )
                        break

                    break

                statements.append(("if", branches, else_body))
                continue

            # While loop: ↓ condition:
            if text.startswith("↓ ") and text.endswith(":"):
                condition = text[2:-1].strip()

                if not condition:
                    raise ArrowLangError(
                        f"Line {index + 1}: condition cannot be empty."
                    )

                body, index = self.parse_block(
                    lines, index + 1, indentation + 4
                )

                else_body = []
                while index < len(lines):
                    next_raw = lines[index]

                    if not next_raw.strip() or next_raw.lstrip().startswith("#"):
                        index += 1
                        continue

                    next_indentation = len(next_raw) - len(next_raw.lstrip(" "))
                    if next_indentation != indentation:
                        break

                    next_text = next_raw.strip()
                    if next_text == "←:":
                        else_body, index = self.parse_block(
                            lines, index + 1, indentation + 4
                        )
                        break

                    break

                statements.append(("while", condition, body, else_body))
                continue

            # For loop: ↓↓ i in range(5):
            if text.startswith("↓↓ ") and text.endswith(":"):
                header = text[3:-1].strip()

                if " in " not in header:
                    raise ArrowLangError(
                        f"Line {index + 1}: expected 'variable in range'."
                    )

                variable, iterable = header.split(" in ", 1)
                variable = variable.strip()
                iterable = iterable.strip()

                if not variable.isidentifier() or not iterable:
                    raise ArrowLangError(
                        f"Line {index + 1}: invalid variable or loop range."
                    )

                body, index = self.parse_block(
                    lines, index + 1, indentation + 4
                )

                else_body = []
                while index < len(lines):
                    next_raw = lines[index]

                    if not next_raw.strip() or next_raw.lstrip().startswith("#"):
                        index += 1
                        continue

                    next_indentation = len(next_raw) - len(next_raw.lstrip(" "))
                    if next_indentation != indentation:
                        break

                    next_text = next_raw.strip()
                    if next_text == "←:":
                        else_body, index = self.parse_block(
                            lines, index + 1, indentation + 4
                        )
                        break

                    break

                statements.append(("for", variable, iterable, body, else_body))
                continue

            # Assignment: ↑↑↑ x = expression
            if text.startswith("↑↑↑ "):
                assignment = text[4:].strip()

                try:
                    assignment_tree = ast.parse(assignment, mode="exec")
                except SyntaxError as error:
                    raise ArrowLangError(
                        f"Line {index + 1}: invalid assignment."
                    ) from error

                if (
                    len(assignment_tree.body) != 1
                    or not isinstance(assignment_tree.body[0], ast.Assign)
                    or len(assignment_tree.body[0].targets) != 1
                ):
                    raise ArrowLangError(
                        f"Line {index + 1}: expected one assignment using '='."
                    )

                assignment_node = assignment_tree.body[0]
                name = ast.get_source_segment(
                    assignment, assignment_node.targets[0]
                ).strip()
                expression = ast.get_source_segment(
                    assignment, assignment_node.value
                ).strip()

                if not expression:
                    raise ArrowLangError(f"Line {index + 1}: missing expression.")

                try:
                    target_node = ast.parse(f"({name})", mode="eval").body
                except SyntaxError as error:
                    raise ArrowLangError(f"Line {index + 1}: invalid assignment.") from error

                if isinstance(target_node, ast.Name):
                    statements.append(("assign", name, expression))
                elif isinstance(target_node, (ast.Tuple, ast.List)):
                    targets = []
                    for element in target_node.elts:
                        if not isinstance(element, ast.Name):
                            raise ArrowLangError(
                                f"Line {index + 1}: destructuring assignment only supports names."
                            )
                        targets.append(element.id)
                    statements.append(("assign_unpack", targets, expression))
                else:
                    if not isinstance(target_node, ast.Subscript):
                        raise ArrowLangError(
                            f"Line {index + 1}: assignment must target a variable, tuple/list, or list/dictionary item."
                        )
                    statements.append(("assign_index", name, expression))
                index += 1
                continue

            # print: ↑ expression
            if text == "↑":
                statements.append(("print", '""'))
                index += 1
                continue

            if text.startswith("↑ "):
                statements.append(("print", text[2:].strip()))
                index += 1
                continue

            # return: →→→ expression
            if text == "→→→":
                statements.append(("return", None))
                index += 1
                continue

            if text.startswith("→→→ "):
                statements.append(("return", text[4:].strip()))
                index += 1
                continue

            # break: →→
            if text == "→→":
                statements.append(("break",))
                index += 1
                continue

            # continue: ←←←
            if text == "←←←":
                statements.append(("continue",))
                index += 1
                continue

            # Standalone expression, e.g. snake.append(head) or draw_rect(...)
            try:
                parsed_expression = ast.parse(text, mode="eval").body
                if isinstance(parsed_expression, ast.Call):
                    statements.append(("expr", text))
                    index += 1
                    continue
            except SyntaxError:
                pass

            raise ArrowLangError(
                f"Line {index + 1}: unknown instruction: {text}"
            )

        return statements, index

    # --------------------------------------------------
    # EXPRESSIONS: math, variables and function calls
    # --------------------------------------------------

    def evaluate(self, expression, local=None):
        try:
            tree = ast.parse(expression, mode="eval")
            return self.evaluate_node(tree.body, local)
        except ArrowLangError:
            raise
        except Exception as error:
            raise ArrowLangError(
                f"Expression error '{expression}': {error}"
            ) from error

    def get_variable(self, name, local):
        # First look for the value in the current function.
        if local is not None:
            if name in local:
                return local[name]

        if name in self.globals:
            return self.globals[name]

        raise ArrowLangError(f"Unknown variable: {name}")

    def evaluate_node(self, node, local=None):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, str, bool)):
                return node.value

            if node.value is None:
                return None

            raise ArrowLangError("Disallowed value.")

        if isinstance(node, ast.Name):
            if node.id in ("True", "False"):
                return node.id == "True"

            if node.id == "None":
                return None

            return self.get_variable(node.id, local)

        if isinstance(node, ast.BinOp):
            operation = BINARY_OPERATORS.get(type(node.op))

            if operation is None:
                raise ArrowLangError("Disallowed operation.")

            left = self.evaluate_node(node.left, local)
            right = self.evaluate_node(node.right, local)

            try:
                return operation(left, right)
            except Exception as error:
                raise ArrowLangError(
                    f"Math error: {error}"
                ) from error

        if isinstance(node, ast.UnaryOp):
            operation = UNARY_OPERATORS.get(type(node.op))

            if operation is None:
                raise ArrowLangError("Disallowed operation.")

            try:
                return operation(self.evaluate_node(node.operand, local))
            except Exception as error:
                raise ArrowLangError(
                    f"Unary operation error: {error}"
                ) from error

        if isinstance(node, ast.Compare):
            left = self.evaluate_node(node.left, local)

            for op_node, comparator in zip(
                node.ops, node.comparators
            ):
                operation = COMPARE_OPERATORS.get(type(op_node))

                if operation is None:
                    raise ArrowLangError("Disallowed comparison.")

                right = self.evaluate_node(comparator, local)

                try:
                    if not operation(left, right):
                        return False
                except Exception as error:
                    raise ArrowLangError(
                        f"Comparison error: {error}"
                    ) from error

                left = right

            return True

        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not self.evaluate_node(value, local):
                        return False
                return True

            if isinstance(node.op, ast.Or):
                for value in node.values:
                    if self.evaluate_node(value, local):
                        return True
                return False

        if isinstance(node, ast.IfExp):
            condition = self.evaluate_node(node.test, local)

            if condition:
                return self.evaluate_node(node.body, local)

            return self.evaluate_node(node.orelse, local)

        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            values = [self.evaluate_node(item, local) for item in node.elts]
            if isinstance(node, ast.List):
                return values
            if isinstance(node, ast.Set):
                return set(values)
            return tuple(values)

        if isinstance(node, ast.Dict):
            result = {}
            for key_node, value_node in zip(node.keys, node.values):
                key = self.evaluate_node(key_node, local)
                result[key] = self.evaluate_node(value_node, local)
            return result

        if isinstance(node, ast.Slice):
            lower = self.evaluate_node(node.lower, local) if node.lower else None
            upper = self.evaluate_node(node.upper, local) if node.upper else None
            step = self.evaluate_node(node.step, local) if node.step else None
            return slice(lower, upper, step)

        if isinstance(node, ast.Subscript):
            container = self.evaluate_node(node.value, local)
            index_value = self.evaluate_node(node.slice, local)

            if isinstance(container, dict):
                try:
                    return container[index_value]
                except (KeyError, TypeError) as error:
                    raise ArrowLangError(f"Key not found: {index_value}.") from error

            if not isinstance(container, (list, tuple, str)):
                raise ArrowLangError("This value does not support indexing.")
            if not isinstance(index_value, (int, slice)):
                raise ArrowLangError("List or string index must be a number or slice.")
            try:
                return container[index_value]
            except IndexError as error:
                raise ArrowLangError(f"Index out of range: {index_value}.") from error

        if isinstance(node, ast.Call):
            if node.keywords:
                raise ArrowLangError(
                    "Named arguments are not supported yet."
                )

            args = [
                self.evaluate_node(arg, local)
                for arg in node.args
            ]

            # Safe list of built-in type methods.
            if isinstance(node.func, ast.Attribute):
                container = self.evaluate_node(node.func.value, local)
                method_name = node.func.attr
                allowed_methods = {
                    list: {"append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse", "count", "index", "copy"},
                    dict: {"get", "keys", "values", "items", "update", "pop", "popitem", "clear", "copy", "setdefault"},
                    str: {"lower", "upper", "title", "capitalize", "strip", "lstrip", "rstrip", "split", "join", "replace", "find", "count", "startswith", "endswith", "isdigit", "isalpha", "isalnum", "format"},
                    set: {"add", "update", "discard", "remove", "pop", "clear", "copy", "union", "intersection", "difference", "issubset", "issuperset", "isdisjoint"},
                }
                allowed = None
                for value_type in allowed_methods:
                    if isinstance(container, value_type):
                        allowed = allowed_methods[value_type]
                        break

                if allowed is None or method_name not in allowed:
                    raise ArrowLangError(f"Method '{method_name}' is not supported for this type.")
                try:
                    return getattr(container, method_name)(*args)
                except Exception as error:
                    raise ArrowLangError(f"Method error {method_name}: {error}") from error

            # Direct function calls
            if not isinstance(node.func, ast.Name):
                raise ArrowLangError(
                    "Disallowed function call."
                )

            name = node.func.id

            if name in self.functions:
                return self.call_function(name, args)

            if name in self.external_functions:
                try:
                    return self.external_functions[name](*args)
                except Exception as error:
                    raise ArrowLangError(f"Function error {name}: {error}") from error

            builtins = {
                "range": range, "len": len, "int": int, "float": float,
                "str": str, "bool": bool, "list": list, "tuple": tuple,
                "dict": dict, "set": set, "abs": abs, "min": min,
                "max": max, "sum": sum, "round": round, "sorted": sorted,
                "reversed": reversed, "enumerate": enumerate, "zip": zip,
                "all": all, "any": any, "ord": ord, "chr": chr,
                "divmod": divmod, "pow": pow,
                "print": lambda *values: self.output(" ".join(str(v) for v in values)),
                "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
                "tan": math.tan, "asin": math.asin, "acos": math.acos,
                "atan": math.atan, "atan2": math.atan2, "hypot": math.hypot,
                "degrees": math.degrees, "radians": math.radians,
                "factorial": math.factorial, "gcd": math.gcd, "lcm": math.lcm,
                "floor": math.floor, "ceil": math.ceil,
                "log": math.log, "log10": math.log10, "exp": math.exp,
                "pi": lambda: math.pi, "euler": lambda: math.e,
                "tau": lambda: math.tau,
                "random_int": random.randint, "random_float": random.random,
                "random_choice": random.choice,
                "time_now": time.time,
                "read_text": self._read_text, "write_text": self._write_text,
            }

            if name in builtins:
                try:
                    return builtins[name](*args)
                except Exception as error:
                    raise ArrowLangError(
                        f"Function error {name}: {error}"
                    ) from error

            raise ArrowLangError(f"Unknown function: {name}")

        raise ArrowLangError(
            "This expression is not supported in ArrowLang."
        )

    # --------------------------------------------------
    # EXECUTING STATEMENTS
    # --------------------------------------------------

    def execute(self, statements, local=None):
        for statement in statements:
            kind = statement[0]

            if kind == "assign":
                _, name, expression = statement
                value = self.evaluate(expression, local)

                if local is None:
                    self.globals[name] = value
                else:
                    local[name] = value

            elif kind == "assign_unpack":
                _, targets, expression = statement
                value = self.evaluate(expression, local)

                if not isinstance(value, (list, tuple)):
                    raise ArrowLangError("Destructuring assignment requires a list or tuple.")
                if len(value) != len(targets):
                    raise ArrowLangError(
                        f"Expected {len(targets)} values, got {len(value)}."
                    )

                for target_name, item_value in zip(targets, value):
                    if local is None:
                        self.globals[target_name] = item_value
                    else:
                        local[target_name] = item_value

            elif kind == "assign_index":
                _, target, expression = statement

                target_node = ast.parse(target, mode="eval").body
                container = self.evaluate_node(target_node.value, local)
                index_value = self.evaluate_node(target_node.slice, local)
                value = self.evaluate(expression, local)
                if not isinstance(container, (list, dict)):
                    raise ArrowLangError("Only list or dictionary items can be changed.")
                if isinstance(container, list) and not isinstance(index_value, int):
                    raise ArrowLangError("List index must be an integer.")
                try:
                    container[index_value] = value
                except (IndexError, KeyError, TypeError) as error:
                    raise ArrowLangError(f"Cannot assign to {target}: {error}") from error

            elif kind == "expr":
                self.evaluate(statement[1], local)

            elif kind == "print":
                self.output(self.evaluate(statement[1], local))

            elif kind == "def":
                _, name, params, body = statement
                self.functions[name] = (params, body)

            elif kind == "if":
                _, branches, else_body = statement

                for condition, body in branches:
                    if self.evaluate(condition, local):
                        self.execute(body, local)
                        break
                else:
                    self.execute(else_body, local)

            elif kind == "while":
                _, condition, body, else_body = statement
                iterations = 0
                break_fired = False

                while self.evaluate(condition, local):
                    iterations += 1
                    self.loop_steps += 1

                    if iterations > self.loop_limit:
                        raise ArrowLangError(
                            "Exceeded while loop iteration limit."
                        )

                    if self.loop_steps > self.loop_limit:
                        raise ArrowLangError(
                            "Program executed too many iterations."
                        )

                    try:
                        self.execute(body, local)
                    except ContinueSignal:
                        continue
                    except BreakSignal:
                        break_fired = True
                        break

                if not break_fired:
                    self.execute(else_body, local)

            elif kind == "for":
                _, variable, expression, body, else_body = statement
                iterable = self.evaluate(expression, local)

                try:
                    iterator = iter(iterable)
                except TypeError as error:
                    raise ArrowLangError(
                        "The value after 'in' is not iterable."
                    ) from error

                iterations = 0
                break_fired = False

                for value in iterator:
                    iterations += 1
                    self.loop_steps += 1

                    if iterations > self.loop_limit:
                        raise ArrowLangError(
                            "Exceeded for loop iteration limit."
                        )

                    if self.loop_steps > self.loop_limit:
                        raise ArrowLangError(
                            "Program executed too many iterations."
                        )

                    if local is None:
                        self.globals[variable] = value
                    else:
                        local[variable] = value

                    try:
                        self.execute(body, local)
                    except ContinueSignal:
                        continue
                    except BreakSignal:
                        break_fired = True
                        break

                if not break_fired:
                    self.execute(else_body, local)

            elif kind == "return":
                _, expression = statement

                if expression is None:
                    value = None
                else:
                    value = self.evaluate(expression, local)

                raise ReturnSignal(value)

            elif kind == "break":
                raise BreakSignal()

            elif kind == "continue":
                raise ContinueSignal()

    @staticmethod
    def _read_text(path):
        """Reads a UTF-8 local file or a file hosted on GitHub."""
        try:
            path = str(path)
            if "://" not in path:
                return Path(path).read_text(encoding="utf-8")

            url = urlsplit(path)
            if (
                url.scheme.lower() != "https"
                or url.hostname not in GITHUB_HOSTS
                or url.username is not None
                or url.password is not None
                or url.port is not None
            ):
                raise ValueError(
                    "Only HTTPS URLs from github.com or raw.githubusercontent.com are supported."
                )

            if url.hostname == "github.com":
                parts = url.path.strip("/").split("/")
                if len(parts) < 5 or parts[2] != "blob":
                    raise ValueError(
                        "Expected a GitHub file URL in the form "
                        "github.com/owner/repository/blob/branch/path."
                    )
                query = parse_qsl(url.query, keep_blank_values=True)
                query = [(key, value) for key, value in query if key != "raw"]
                query.append(("raw", "1"))
                url = url._replace(query=urlencode(query))

            request_url = urlunsplit(url._replace(fragment=""))
            request = Request(request_url, headers={"User-Agent": "ArrowLang"})
            opener = build_opener(_GitHubRedirectHandler())
            with opener.open(request, timeout=15) as response:
                return response.read().decode("utf-8")
        except Exception as error:
            raise ArrowLangError(f"Cannot read file {path}: {error}") from error

    @staticmethod
    def _write_text(path, content):
        """Writes UTF-8 text; returns True after success."""
        try:
            file_path = Path(str(path))
            text = str(content)
            file_path.write_text(text, encoding="utf-8")
            return True
        except Exception as error:
            raise ArrowLangError(f"Cannot write file {path}: {error}") from error

    def call_function(self, name, args):
        params, body = self.functions[name]

        required_params = [p for p in params if not isinstance(p, tuple)]
        if len(args) < len(required_params):
            raise ArrowLangError(
                f"Function {name} expects at least {len(required_params)} arguments, "
                f"got {len(args)}."
            )

        if len(args) > len(params):
            raise ArrowLangError(
                f"Function {name} expects {len(params)} arguments, "
                f"got {len(args)}."
            )

        local = {}
        arg_index = 0

        for param in params:
            if isinstance(param, tuple):
                param_name, default_expression = param
                if arg_index < len(args):
                    local[param_name] = args[arg_index]
                    arg_index += 1
                else:
                    local[param_name] = self.evaluate(default_expression, local)
            else:
                if arg_index >= len(args):
                    raise ArrowLangError(
                        f"Function {name} expects more arguments."
                    )
                local[param] = args[arg_index]
                arg_index += 1

        try:
            self.execute(body, local)
        except ReturnSignal as signal:
            return signal.value
        except (BreakSignal, ContinueSignal) as error:
            raise ArrowLangError(
                "break and continue must be used inside loops."
            ) from error

        return None

    def run(self, source):
        self.loop_steps = 0

        try:
            source = Parser().parse(source)
            lines = source.splitlines()
            statements, index = self.parse_block(lines)

            if index < len(lines):
                raise ArrowLangError(
                    f"Unexpected end of block at line {index + 1}."
                )

            self.execute(statements)

        except ParserError as error:
            raise ArrowLangError(str(error)) from error
        except (ReturnSignal, BreakSignal, ContinueSignal) as error:
            raise ArrowLangError(
                "return, break or continue used outside the appropriate block."
            ) from error


def run(source, output=print):
    interpreter = ArrowLang(output=output)
    interpreter.run(source)
    return interpreter.globals


if __name__ == "__main__":
    from main import main

    main()