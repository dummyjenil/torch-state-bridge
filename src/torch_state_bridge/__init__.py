import re
import ast
import operator
from dataclasses import dataclass
from typing import Dict, List, Callable

# ---------------- SAFE MATH EVAL ---------------- #

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

def eval_math_expr(expr: str) -> int:
    def _eval(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, int):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _ALLOWED_OPS:
            return _ALLOWED_OPS[type(n.op)](_eval(n.operand))
        raise ValueError("Invalid math expression")

    return _eval(ast.parse(expr, mode="eval").body)


# ---------------- RULE CORE ---------------- #

@dataclass(frozen=True)
class Rule:
    regex: re.Pattern
    transform: Callable[[re.Match], str]


class RuleEngine:
    def __init__(self, rules: List[Rule]):
        self.rules = rules

    def apply(self, key: str) -> str:
        for r in self.rules:
            key = r.regex.sub(r.transform, key)
        return key


# ---------------- RULE COMPILER ---------------- #

_CAPTURE = re.compile(r"\{(\w+)\}")
_MATH = re.compile(r"\{\(([^()]+)\)\}")

def _compile(src: str, dst: str, *, reverse: bool) -> Rule:
    # reverse means swap src <-> dst
    if reverse:
        if _MATH.search(dst):
            raise ValueError("Reverse mapping not allowed with arithmetic")
        src, dst = dst, src

    parts = _CAPTURE.split(src)
    regex_parts = []

    for i, p in enumerate(parts):
        if i % 2 == 0:
            regex_parts.append(re.escape(p))
        else:
            regex_parts.append(rf"(?P<{p}>\d+)")

    regex = re.compile("".join(regex_parts))

    def transform(m: re.Match) -> str:
        out = dst

        # replace captures
        for name, val in m.groupdict().items():
            out = out.replace(f"{{{name}}}", val)

        # math only allowed in forward
        def _math(m2):
            expr = m2.group(1)
            for name, val in m.groupdict().items():
                expr = expr.replace(name, val)
            return str(eval_math_expr(expr))

        out = _MATH.sub(_math, out)
        return out

    return Rule(regex, transform)


def parse_rules(text: str, *, reverse: bool) -> RuleEngine:
    rules = []
    for line in text.strip().splitlines():
        src, dst = map(str.strip, line.split(","))
        rules.append(_compile(src, dst, reverse=reverse))
    return RuleEngine(rules)


# ---------------- PUBLIC API ---------------- #

def state_bridge(
    state_dict: Dict[str, object],
    rules_text: str,
    *,
    reverse: bool = False,
    detect_collision: bool = True,
) -> Dict[str, object]:

    engine = parse_rules(rules_text, reverse=reverse)
    new_sd = {}

    for k, v in state_dict.items():
        nk = engine.apply(k)

        if detect_collision and nk in new_sd:
            raise KeyError(f"Key collision: {nk}")

        new_sd[nk] = v

    return new_sd
