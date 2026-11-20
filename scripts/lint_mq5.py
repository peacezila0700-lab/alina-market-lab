#!/usr/bin/env python3
"""Static checks for the MQL5 EA — we cannot compile MQL5 in this sandbox, so this is the
strongest verification available offline. It is NOT a compiler and passing it proves nothing
about runtime behaviour; it only catches the mistakes that are cheap to catch.

Checks:
  1. brace / parenthesis balance
  2. every function called with `Name(` is defined, or is a known MQL5 builtin
  3. no MQL4-only calls (OrderSend old signature, MarketInfo, OrderSelect(...SELECT_BY_POS))
  4. every `input` variable is declared before first use
  5. no martingale-shaped code: a volume expression that multiplies a previous volume
  6. OnTick / OnInit / OnDeinit present
"""
from __future__ import annotations

import re
import sys

MQL5_BUILTINS = {
    "AccountInfoDouble", "AccountInfoInteger", "AccountInfoString", "SymbolInfoDouble",
    "SymbolInfoInteger", "SymbolInfoString", "PositionsTotal", "PositionGetTicket",
    "PositionSelectByTicket", "PositionGetInteger", "PositionGetDouble", "PositionGetString",
    "OrderSend", "OrderSendAsync", "MqlTradeRequest", "MqlTradeResult", "ZeroMemory",
    "iATR", "iClose", "iOpen", "iHigh", "iLow", "iHighest", "iLowest", "iMA", "iRSI",
    "MathFloor", "MathMax", "MathMin", "MathSqrt", "MathAbs", "MathPow", "MathRound",
    "StringFormat", "TimeToString", "TimeCurrent", "TimeLocal", "Print", "Comment",
    "FileOpen", "FileClose", "FileWrite", "FileFlush", "FileSeek", "DayOfYear",
    "TerminalInfoInteger", "MQLInfoInteger", "GetLastError", "NormalizeDouble",
    "StringLen", "StringSubstr", "StringConcatenate", "ArraySize", "DoubleToString",
    "IntegerToString", "EnumToString", "ChartSymbol", "Period", "Digits", "Point",
}
MQL4_ONLY = ["MarketInfo", "OrderClose", "OrderModify", "OrderDelete", "OrderLots",
             "OrderOpenPrice", "iCustom", "WindowFind"]
FORBIDDEN_MARTINGALE = [r"volume\s*\*\s*2", r"lots\s*\*\s*2", r"lots\s*=\s*lots\s*\*",
                        r"lot\s*\*\s*MathPow\(\s*2"]


def check(path: str) -> int:
    src = open(path, encoding="utf-8", errors="replace").read()
    code = re.sub(r"//.*", "", src)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    # strip string literals, otherwise "%.2f(" and "PAPER %s" look like function calls
    no_str = re.sub(r'"(?:[^"\\]|\\.)*"', '""', code)
    problems: list[str] = []
    ok: list[str] = []

    # 1. balance
    for op, cl, name in (("{", "}", "braces"), ("(", ")", "parens"), ("[", "]", "brackets")):
        if no_str.count(op) != no_str.count(cl):
            problems.append(f"{name} unbalanced: {no_str.count(op)} vs {no_str.count(cl)}")
        else:
            ok.append(f"{name} balanced ({no_str.count(op)})")

    # 2. defined functions
    defined = set(re.findall(r"^\s*(?:void|bool|int|double|string|long|ulong|datetime)\s+(\w+)\s*\(",
                             code, re.M))
    called = set(re.findall(r"\b(\w+)\s*\(", no_str))
    keywords = {"if", "for", "while", "switch", "return", "sizeof", "else", "do"}
    unknown = {c for c in called if c not in defined | MQL5_BUILTINS | keywords
               and not c.startswith(("ENUM_", "MODE_", "SIG_", "ORDER_", "SYMBOL_", "POSITION_",
                                     "TRADE_", "ACCOUNT_", "TERMINAL_", "MQL_", "PERIOD_",
                                     "FILE_", "INIT_", "SEEK_", "TIME_"))}
    if unknown:
        problems.append(f"called but not defined and not a known builtin: {sorted(unknown)}")
    else:
        ok.append(f"all {len(called)} called functions resolved ({len(defined)} defined here)")

    # 3. MQL4 leftovers
    hits = [w for w in MQL4_ONLY if re.search(rf"\b{w}\s*\(", code)]
    if hits:
        problems.append(f"MQL4-only calls present: {hits}")
    else:
        ok.append("no MQL4-only API usage")

    # 4. inputs declared before use
    inputs = re.findall(r"^input\s+\w+\s+(\w+)", code, re.M)
    first_input_pos = code.find("input ")
    for name in inputs:
        uses = [m.start() for m in re.finditer(rf"\b{name}\b", code)]
        if uses and min(uses) < first_input_pos:
            problems.append(f"input {name} used before its declaration")
    ok.append(f"{len(inputs)} inputs declared")

    # 5. martingale shapes
    mh = [p for p in FORBIDDEN_MARTINGALE if re.search(p, code)]
    if mh:
        problems.append(f"martingale-shaped sizing found: {mh}")
    else:
        ok.append("no martingale-shaped volume scaling")

    # 6. lifecycle
    for fn in ("OnInit", "OnDeinit", "OnTick"):
        if fn not in defined:
            problems.append(f"missing {fn}")
    if all(fn in defined for fn in ("OnInit", "OnDeinit", "OnTick")):
        ok.append("lifecycle functions present")

    print(f"=== {path} ===")
    for o in ok:
        print(f"  OK   {o}")
    for p in problems:
        print(f"  FAIL {p}")
    print(f"  -> {'LINT PASS (not a compile)' if not problems else 'LINT FAIL'}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(check(sys.argv[1] if len(sys.argv) > 1 else "ea/AlinaRiskGovernor.mq5"))
