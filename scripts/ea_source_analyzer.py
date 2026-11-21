#!/usr/bin/env python3
"""Static reverse-engineering parser for MQL4 / MQL5 / MQH source files.
Strictly static analysis only: NEVER executes downloaded code, NEVER guesses
hidden logic or unverified behavior.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

# Official MQL5 / Windows Wingdings character codes used by OBJ_ARROW & PLOT_ARROW
WINGDINGS_MAP: dict[int, str] = {
    33: "Pencil",
    34: "Scissors",
    67: "Thumbs Up",
    68: "Thumbs Down",
    74: "Smiley Face",
    76: "Frown Face",
    81: "Airplane",
    108: "Filled Large Circle",
    109: "Hollow Circle",
    110: "Filled Square",
    111: "Hollow Square",
    113: "Boxed Square",
    115: "Diamond Small",
    116: "Diamond",
    117: "Rhombus",
    118: "Crossed Diamond",
    119: "Small Solid Diamond",
    158: "Small Dot",
    159: "Solid Circle (Default PLOT_ARROW)",
    161: "Hollow Circle Ring",
    162: "Double Circle",
    164: "Bullseye Circle",
    167: "Small Filled Square",
    168: "Small Hollow Square",
    170: "Star / Sparkle",
    171: "Filled Star",
    172: "Circled Number / Star",
    174: "Circled Star",
    181: "Circled Plus",
    217: "Arrow Up (Hollow/Outline)",
    218: "Arrow Down (Hollow/Outline)",
    221: "Up Triangle / Arrow",
    222: "Down Triangle / Arrow",
    225: "Up Arrow (Light/Serif)",
    226: "Down Arrow (Light/Serif)",
    227: "Up-Right Diagonal Arrow",
    228: "Down-Right Diagonal Arrow",
    231: "Left Arrow",
    232: "Right Arrow",
    233: "Up Arrow (Standard Buy Arrow)",
    234: "Down Arrow (Standard Sell Arrow)",
    235: "Left-Right Arrow",
    236: "Up-Down Arrow",
    237: "Up-Left Arrow",
    238: "Up-Right Arrow",
    239: "Left-Wide Arrow",
    240: "Right-Wide Arrow",
    241: "Thick Up Arrow (MQL5 Doc Example)",
    242: "Thick Down Arrow",
    243: "Hollow Left Arrow",
    244: "Hollow Right Arrow",
    245: "Hollow Up Arrow",
    246: "Hollow Down Arrow",
    251: "Cross / X Mark",
    252: "Checkmark",
    253: "Boxed X",
    254: "Boxed Checkmark",
}

BUILTIN_INDICATORS = [
    "iMA", "iRSI", "iMACD", "iBands", "iATR", "iStochastic", "iADX", "iADXWilder",
    "iCCI", "iIchimoku", "iSAR", "iMomentum", "iStdDev", "iOBV", "iMFI", "iWPR",
    "iEnvelopes", "iFractals", "iAlligator", "iAO", "iAC", "iVolumes",
    "iBullsPower", "iBearsPower", "iChaikin", "iDeMarker", "iForce", "iDEMA",
    "iTEMA", "iVIDyA", "iAMA", "iOsMA", "iGator", "iRVI", "iTriX", "iCustom",
]

STANDARD_INCLUDES = {
    "trade\\trade.mqh", "trade/trade.mqh",
    "trade\\symbolinfo.mqh", "trade/symbolinfo.mqh",
    "trade\\positioninfo.mqh", "trade/positioninfo.mqh",
    "trade\\orderinfo.mqh", "trade/orderinfo.mqh",
    "trade\\accountinfo.mqh", "trade/accountinfo.mqh",
    "trade\\dealinfo.mqh", "trade/dealinfo.mqh",
    "trade\\historyorderinfo.mqh", "trade/historyorderinfo.mqh",
    "arrays\\arrayobj.mqh", "arrays/arrayobj.mqh",
    "arrays\\arrayint.mqh", "arrays/arrayint.mqh",
    "arrays\\arraydouble.mqh", "arrays/arraydouble.mqh",
    "arrays\\arraystring.mqh", "arrays/arraystring.mqh",
    "controls\\dialog.mqh", "controls/dialog.mqh",
    "controls\\button.mqh", "controls/button.mqh",
    "controls\\label.mqh", "controls/label.mqh",
    "controls\\edit.mqh", "controls/edit.mqh",
    "indicators\\trend.mqh", "indicators/trend.mqh",
    "indicators\\oscilators.mqh", "indicators/oscilators.mqh",
    "math\\stat\\math.mqh", "math/stat/math.mqh",
    "expert\\expert.mqh", "expert/expert.mqh",
    "expert\\expertsignal.mqh", "expert/expertsignal.mqh",
    "expert\\experttrailing.mqh", "expert/experttrailing.mqh",
    "expert\\expertmoney.mqh", "expert/expertmoney.mqh",
    "files\\filetxt.mqh", "files/filetxt.mqh",
    "files\\file.mqh", "files/file.mqh",
    "stdlib.mqh", "stderror.mqh",
}

EVENT_HANDLERS = [
    "OnInit", "OnDeinit", "OnTick", "OnTimer", "OnTrade",
    "OnTradeTransaction", "OnCalculate", "OnChartEvent", "OnTester", "OnStart",
]


def decode_source_bytes(raw: bytes) -> tuple[str, str]:
    if raw.startswith(b"\xff\xfe"):
        return raw.decode("utf-16-le", errors="replace").lstrip("\ufeff"), "utf-16-le"
    if raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16-be", errors="replace").lstrip("\ufeff"), "utf-16-be"
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw[3:].decode("utf-8", errors="replace"), "utf-8-sig"
    if b"\x00" in raw[:400]:
        return raw.decode("utf-16-le", errors="replace").lstrip("\ufeff"), "utf-16-le-heur"
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return raw.decode("cp1251", errors="replace"), "cp1251-fallback"


def strip_comments_keep_strings(code: str) -> str:
    # Remove /* ... */ and // ... comments while preserving quoted strings
    pattern = re.compile(r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')|(/\*[\s\S]*?\*/|//[^\r\n]*)')
    return pattern.sub(lambda m: m.group(1) if m.group(1) else " ", code)


def strip_comments_and_strings(code: str) -> str:
    # Remove comments AND quoted string literals so description prose never triggers code flags
    pattern = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\r\n]*')
    return pattern.sub(" ", code)


def code_shingles(code_no_comments: str, k: int = 5, max_shingles: int = 500) -> list[str]:
    # Normalize strings/numbers for structural similarity detection across the ENTIRE file
    norm = re.sub(r'"(?:\\.|[^"\\])*"', ' STR ', code_no_comments)
    norm = re.sub(r'\b\d+(?:\.\d+)?\b', ' NUM ', norm)
    tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|[{}()\[\];,<>+\-*/=!&|]+', norm)
    if len(tokens) < k:
        return [" ".join(tokens)] if tokens else []
    total = len(tokens) - k + 1
    stride = max(1, total // max_shingles)
    shingles = []
    seen = set()
    for i in range(0, total, stride):
        s = " ".join(tokens[i:i + k])
        h = hashlib.md5(s.encode("utf-8")).hexdigest()[:10]
        if h not in seen:
            seen.add(h)
            shingles.append(h)
            if len(shingles) >= max_shingles:
                break
    return shingles


def analyze_source_file(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    raw = p.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    text, enc = decode_source_bytes(raw)
    ext = p.suffix.lower()
    code_nc = strip_comments_keep_strings(text)
    code_pure = strip_comments_and_strings(text)

    # Properties
    props = {}
    descriptions = []
    prop_plots: dict[int, dict[str, str]] = {}
    for m in re.finditer(r'^[ \t]*#property[ \t]+([A-Za-z0-9_]+)(?:[ \t]+(.*?))?[ \t]*$', text, re.M):
        key, val = m.group(1), (m.group(2) or "").strip()
        val_clean = val.strip('"').strip()
        if key == "description":
            if val_clean:
                descriptions.append(val_clean)
        elif re.match(r'^indicator_(type|label|color|width|style)(\d+)$', key):
            mm = re.match(r'^indicator_(type|label|color|width|style)(\d+)$', key)
            field, idx = mm.group(1), int(mm.group(2))
            prop_plots.setdefault(idx, {})[field] = val_clean
        else:
            props[key] = val_clean

    # Includes & resources
    includes = re.findall(r'^\s*#include\s+[<"]([^>"]+)[>"]', text, re.M)
    custom_includes = [inc for inc in includes if inc.lower().replace("/", "\\") not in STANDARD_INCLUDES]
    resources = re.findall(r'^\s*#resource\s+"([^"]+)"', text, re.M)

    # Event handlers
    handlers = [
        h for h in EVENT_HANDLERS
        if re.search(rf'\b(?:int|void|double|bool)\s+{h}\s*\(', code_nc)
    ]

    # Platform & type inference strictly from code
    if ext == ".mq4":
        platform = "MT4"
    elif ext == ".mq5":
        platform = "MT5"
    elif ext == ".mqh":
        platform = "MQL_Include"
    elif ext == ".h":
        platform = "MQL_C_Header"
    elif ext == ".py":
        platform = "Python_Bridge"
    else:
        platform = "Unknown"

    is_indicator = (
        "OnCalculate" in handlers
        or "indicator_chart_window" in props
        or "indicator_separate_window" in props
        or "SetIndexBuffer" in code_nc
    )
    has_trade_exec = bool(re.search(
        r'\b(?:CTrade|OrderSend|OrderSendAsync|trade\.Buy|trade\.Sell|PositionOpen|BuyStop|SellStop|BuyLimit|SellLimit)\b',
        code_nc,
    ))
    has_trade_mgmt = bool(re.search(
        r'\b(?:PositionModify|PositionClose|OrderDelete|PositionSelect|PositionsTotal)\b',
        code_nc,
    ))

    if ext == ".mqh":
        role = "Library / Header (.mqh)"
    elif ext == ".h":
        role = "Library / Header (.h)"
    elif is_indicator and not has_trade_exec:
        role = "Indicator"
    elif has_trade_exec:
        role = "Expert Advisor (Trading)"
    elif "OnTick" in handlers and custom_includes and not re.search(r'\b(panel|monitor|tracer|guard|breakeven|trailing|closeall|lock)\b', p.name.lower()):
        role = "Expert Advisor (Modular / Class-based)"
    elif has_trade_mgmt and "OnTick" in handlers:
        role = "Trade / Risk Manager EA"
    elif "OnStart" in handlers:
        role = "Script"
    elif "OnTick" in handlers or "OnTimer" in handlers:
        role = "Utility / Diagnostic EA"
    else:
        role = "Unclassified Source"

    # Inputs
    inputs = []
    for m in re.finditer(
        r'^\s*(?:input|sinput|extern)\s+([A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)(?:\s*=\s*([^;]+))?;(?:\s*//\s*(.*))?$',
        text,
        re.M,
    ):
        inputs.append({
            "type": m.group(1),
            "name": m.group(2),
            "default": (m.group(3) or "").strip(),
            "comment": (m.group(4) or "").strip(),
        })
        if len(inputs) >= 80:
            break

    # Indicators used
    indicators_used = []
    for ind in BUILTIN_INDICATORS:
        if re.search(rf'\b{ind}\s*\(', code_nc):
            indicators_used.append(ind)

    icustom_targets = []
    for m in re.finditer(r'\biCustom\s*\([^,]+,[^,]+,\s*"([^"]+)"', code_nc):
        val = m.group(1).strip()
        if val and val not in icustom_targets:
            icustom_targets.append(val)

    # Visual symbols & Wingdings extraction
    visual_symbols: list[dict[str, Any]] = []
    for idx, pmeta in sorted(prop_plots.items()):
        dtype = pmeta.get("type", "")
        if dtype:
            visual_symbols.append({
                "source_kind": "property_plot",
                "plot_index": idx,
                "draw_type": dtype,
                "label": pmeta.get("label", ""),
                "color": pmeta.get("color", ""),
                "arrow_code": None,
                "wingdings_meaning": None,
            })

    # Dynamic PlotIndexSetInteger(..., PLOT_ARROW, code)
    for m in re.finditer(r'PlotIndexSetInteger\s*\(\s*([^,]+)\s*,\s*PLOT_ARROW\s*,\s*([^)]+)\)', code_nc):
        buf_expr, code_expr = m.group(1).strip(), m.group(2).strip()
        num = int(code_expr) if code_expr.isdigit() else None
        visual_symbols.append({
            "source_kind": "PlotIndexSetInteger_PLOT_ARROW",
            "plot_index": buf_expr,
            "draw_type": "DRAW_ARROW",
            "label": "",
            "color": "",
            "arrow_code": num if num is not None else code_expr,
            "wingdings_meaning": WINGDINGS_MAP.get(num, "Unknown / Variable Code") if num is not None else "Dynamic/Input Variable",
        })

    # ObjectCreate / OBJPROP_ARROWCODE
    obj_types = sorted(set(re.findall(r'\b(OBJ_[A-Z0-9_]+)\b', code_nc)))
    for m in re.finditer(r'ObjectSetInteger\s*\([^,]+,[^,]+,\s*OBJPROP_ARROWCODE\s*,\s*([^)]+)\)', code_nc):
        code_expr = m.group(1).strip()
        num = int(code_expr) if code_expr.isdigit() else None
        visual_symbols.append({
            "source_kind": "OBJPROP_ARROWCODE",
            "plot_index": "",
            "draw_type": "OBJ_ARROW",
            "label": "",
            "color": "",
            "arrow_code": num if num is not None else code_expr,
            "wingdings_meaning": WINGDINGS_MAP.get(num, "Unknown / Variable Code") if num is not None else "Dynamic/Input Variable",
        })

    # Strategy & Execution Archetype Mechanics
    lower_all = text.lower()
    lower_code = code_pure.lower()
    mechanics = {
        "has_new_bar_gate": bool(re.search(r'(?:bars|itime|seriesinfointeger|copytime|lastbar|prevbar|isnewbar)', lower_code)),
        "uses_copybuffer": "CopyBuffer" in code_nc,
        "uses_ctrade": "CTrade" in code_nc,
        "uses_order_check": "OrderCheck" in code_nc,
        "uses_pending_orders": bool(re.search(r'\b(?:BuyStop|SellStop|BuyLimit|SellLimit|ORDER_TYPE_BUY_STOP|ORDER_TYPE_SELL_STOP|ORDER_TYPE_BUY_LIMIT|ORDER_TYPE_SELL_LIMIT)\b', code_nc)),
        "has_sl_logic": bool(re.search(r'(?:stoploss|stop_loss|\bsl\b|positionmodify)', lower_code)),
        "has_tp_logic": bool(re.search(r'(?:takeprofit|take_profit|\btp\b)', lower_code)),
        "has_trailing_stop": bool(re.search(r'(?:trailing|trailstop|chandelier)', lower_code)),
        "has_breakeven": bool(re.search(r'(?:breakeven|break_even|\bbe_)', lower_code)),
        "has_risk_pct_sizing": bool(re.search(r'(?:accountinfodouble|account_balance|account_equity|riskpercent|risk_pct|lotsize)', lower_code)),
        "has_daily_loss_or_dd_guard": bool(re.search(r'(?:dailyloss|daily_loss|maxdrawdown|max_dd|equitystop|basket.*loss|profitlock)', lower_code)),
        "has_session_or_time_filter": bool(re.search(r'(?:mqldatetime|timecurrent|timetostruct|starthour|endhour|session)', lower_code)),
        "has_spread_filter": bool(re.search(r'(?:symbol_spread|maxspread|max_spread)', lower_code)),
        "has_news_calendar": bool(re.search(r'(?:calendarvaluehistory|calendarevent|newsfilter|news_blackout)', lower_code)),
        "has_martingale_or_lot_mult": bool(re.search(r'(?:martingale|\blotmult|\blot_mult|\breallotmultiplier|\bmartingale_?mult|\bmathpow\s*\([^,]+,|\blots?\s*\*=\s*|\blevel\s*\*\s*\w*lot|\blotartisi)', lower_code)),
        "has_grid_or_averaging": bool(re.search(r'(?:gridstep|grid_step|gridsize|opengrid|maxgrid|maxgridkademe|trygridadd|averaging|addgrid)', lower_code)),
        "has_smc_ict_concepts": bool(re.search(r'(?:\borderblock|\border_block|\bfvg\b|\bimbalance|\bbos\b|\bchoch\b|\bliquidity|\bsweep|\bote\b|premium.*discount|\bcisd\b)', lower_all)),
        "has_ml_or_onnx": bool(re.search(r'(?:onnx|neural|perceptron|randomforest|alglib|pytorch|tensorflow)', lower_all)),
        "uses_webrequest_or_telegram": bool(re.search(r'(?:webrequest|telegram|api\.telegram)', lower_code)),
        "uses_file_io": bool(re.search(r'(?:fileopen|filewrite|fileread|csv)', lower_code)),
    }

    # Static repainting / look-ahead risk flags (reported strictly as code warnings)
    repaint_flags = []
    if re.search(r'CopyBuffer\s*\([^;]+,\s*0\s*,\s*0\s*,', code_nc) or re.search(r'\b(?:iClose|iOpen|iHigh|iLow)\s*\([^,]+,[^,]+,\s*0\s*\)', code_nc):
        repaint_flags.append("Reads_Bar0_FormingBar")
    if is_indicator and "OnCalculate" in handlers:
        if not re.search(r'\bprev_calculated\b', code_nc):
            repaint_flags.append("Indicator_Missing_prev_calculated_Guard")
        if re.search(r'\[\s*i\s*-\s*[12]\s*\]', code_nc) and "ArraySetAsSeries" in code_nc:
            repaint_flags.append("Check_Series_Index_i_minus_1_Direction")
    if any(v.get("draw_type") in ("DRAW_ARROW", "DRAW_COLOR_ARROW") for v in visual_symbols):
        if not re.search(r'(?:EMPTY_VALUE|PLOT_EMPTY_VALUE)', code_nc):
            repaint_flags.append("DRAW_ARROW_Missing_Explicit_EMPTY_VALUE")

    # Classify primary category strictly from extracted evidence
    cats = []
    if mechanics["has_ml_or_onnx"]:
        cats.append("ML/Neural/ONNX")
    if mechanics["has_smc_ict_concepts"]:
        cats.append("SMC/ICT")
    if mechanics["has_news_calendar"]:
        cats.append("News/Calendar")
    if mechanics["has_martingale_or_lot_mult"] or mechanics["has_grid_or_averaging"]:
        cats.append("Grid/Martingale/Basket")
    if role in ("Trade / Risk Manager EA", "Utility / Diagnostic EA"):
        cats.append("Risk/Trade Utility")
    if any(x in indicators_used for x in ("iMA", "iADX", "iIchimoku", "iSAR")) or "supertrend" in lower_all or "breakout" in lower_all:
        cats.append("Trend/Breakout")
    if any(x in indicators_used for x in ("iRSI", "iStochastic", "iCCI", "iBands", "iWPR")):
        cats.append("Oscillator/Mean-Reversion")
    if is_indicator and not cats:
        cats.append("Custom Technical Indicator")
    if not cats:
        cats.append("Price Action / General / Unclassified")

    return {
        "file_path": str(p),
        "file_name": p.name,
        "ext": ext,
        "file_bytes": len(raw),
        "line_count": len(text.splitlines()),
        "encoding": enc,
        "sha256": sha256,
        "platform": platform,
        "role": role,
        "categories": cats,
        "properties": props,
        "descriptions": descriptions,
        "includes": includes,
        "custom_includes": custom_includes,
        "resources": resources,
        "event_handlers": handlers,
        "inputs_count": len(inputs),
        "inputs": inputs,
        "indicators_used": indicators_used,
        "icustom_targets": icustom_targets,
        "object_types": obj_types,
        "visual_symbols": visual_symbols,
        "mechanics": mechanics,
        "repaint_flags": repaint_flags,
        "shingles": code_shingles(code_nc),
    }


if __name__ == "__main__":
    import json, sys
    target = sys.argv[1] if len(sys.argv) > 1 else "/home/user/alina_lab/ea/AlinaRiskGovernor.mq5"
    res = analyze_source_file(target)
    res_print = dict(res)
    res_print["shingles_count"] = len(res_print.pop("shingles"))
    print(json.dumps(res_print, indent=2, ensure_ascii=False))
