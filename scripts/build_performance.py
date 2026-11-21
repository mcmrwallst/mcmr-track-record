#!/usr/bin/env python3
"""
build_performance.py — generate the performance pages from the ledger data.

Why this exists: a performance page written by hand drifts from the evidence
and invites the suspicion that the numbers were chosen. This script makes every
figure a function of four data files, checks those files before using them, and
refuses to build if they disagree with each other or with the trade files.

Inputs (never the trade markdown itself; its formats vary):
    performance/registry.csv     one row per trade event, append-only
    performance/marks.csv        month-end closes for open positions
    performance/prices/*.csv     daily open/high/low/close per instrument
    performance/theses.csv       thesis names
    methodology/v1.md            the rules; only its version line is read here

Outputs:
    PERFORMANCE.md                       live
    performance/theses/THxx.md           live
    performance/charts/*.svg             live
    performance/VALIDATION.md            live
    performance/months/YYYY-MM.json      frozen once written
    performance/quarters/YYYY-Qn.md      frozen once written
    performance/years/YYYY.md            frozen once written

Run from the repository root:

    py scripts\\build_performance.py

Requires the packages in scripts/requirements.txt (exact versions, so the charts
rebuild byte-for-byte). Everything else is standard library.
"""

import argparse
import calendar
import csv
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

PERF = "performance"
INCEPTION = date(2026, 7, 22)
SCRATCH_R = 0.10                  # methodology §8: win > +0.10R, loss < -0.10R
PCT_TOLERANCE = 0.05              # result_pct vs result_r x risk_pct
R_TOLERANCE = 0.02                # stated R vs R recomputed from prices
BACKFILL_AFTER_DAYS = 7           # a period frozen later than this is labelled backfilled
MIN_MONTHS_FOR_ANNUALISED = 24    # methodology §8 gate

REPO_URL = "https://github.com/mcmrwallst/mcmr-track-record"
MINUS = "\u2212"                  # typographic minus for displayed figures
GREEN = "#1D9E75"
RED = "#D85A30"
GREY = "#8A8A8A"

# CME notation: the digit after the second apostrophe is a fraction of a 32nd.
# 108'15'5 = 108 + 15.5/32. 2 and 7 are the quarter ticks (.25 / .75).
_FRACTION_DIGIT = {"0": 0.0, "1": 0.125, "2": 0.25, "3": 0.375,
                   "5": 0.5, "6": 0.625, "7": 0.75, "8": 0.875}


class BuildError(Exception):
    pass


# --------------------------------------------------------------------- prices

def parse_price(text):
    """Price from the registry: decimal, or bond notation 110'06'0 / 110'06."""
    s = str(text).strip()
    if not s:
        raise ValueError("empty price")
    if "'" not in s:
        return float(s)
    parts = s.split("'")
    if len(parts) not in (2, 3) or not parts[0].isdigit() or not parts[1].isdigit():
        raise ValueError(f"bad 32nds price {s!r}")
    whole, thirty_seconds = int(parts[0]), int(parts[1])
    if thirty_seconds > 31:
        raise ValueError(f"bad 32nds price {s!r}: {thirty_seconds} >= 32")
    frac = 0.0
    if len(parts) == 3 and parts[2] != "":
        if parts[2] not in _FRACTION_DIGIT:
            raise ValueError(f"bad 32nds price {s!r}: fraction digit {parts[2]!r}")
        frac = _FRACTION_DIGIT[parts[2]]
    return whole + (thirty_seconds + frac) / 32


def fmt_price(x, bond):
    """Display a price the way it is published."""
    if x is None:
        return "—"
    if not bond:
        return f"{x:,.2f}"
    whole = int(x + 1e-9)
    ticks = (x - whole) * 32
    t = int(ticks + 1e-9)
    rem = ticks - t
    digit = min(_FRACTION_DIGIT, key=lambda k: abs(_FRACTION_DIGIT[k] - rem))
    return f"{whole}'{t:02d}'{digit}"


def fmt_pct(x, signed=True, nd=2):
    if x is None:
        return "—"
    if abs(x) < 0.5 * 10 ** -nd:
        return f"{0:.{nd}f}%"
    return (f"{x:+.{nd}f}%" if signed else f"{x:.{nd}f}%").replace("-", MINUS)


def fmt_r(x):
    return "—" if x is None else f"{x:+.2f}R".replace("-", MINUS)


def fmt_date(d):
    return f"{d.day} {d:%b %Y}"


def _dm(d):
    return f"{d.day} {d:%b}"


def month_end(y, m):
    return date(y, m, calendar.monthrange(y, m)[1])


def file_link(path, prefix=""):
    return prefix + quote(path)


# ----------------------------------------------------------------- data model

@dataclass
class Trade:
    trade_id: str
    thesis_id: str
    instrument: str
    price_key: str
    direction: int                  # +1 long, -1 short
    entry: float
    stop: float                     # live stop: last correction, else as opened
    risk_pct: float
    notional_pct: float | None
    open_date: date
    open_row: dict
    bond: bool
    exit_date: date | None = None
    exit_price: float | None = None
    result_r: float | None = None
    result_pct: float | None = None
    exit_row: dict | None = None
    events: list = field(default_factory=list)

    @property
    def stop_distance(self):
        return abs(self.stop - self.entry)

    def open_r(self, price):
        return self.direction * (price - self.entry) / self.stop_distance

    def open_pct(self, price):
        return self.open_r(price) * self.risk_pct

    def is_open_at(self, d):
        """Open at the close of date d."""
        return self.open_date <= d and (self.exit_date is None or self.exit_date > d)

    @property
    def closed(self):
        return self.exit_date is not None


def event_date(row):
    ts = row["ts_utc"].strip()
    if len(ts) == 10:
        return date.fromisoformat(ts)
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc).date()


def event_sort_key(row):
    ts = row["ts_utc"].strip()
    if len(ts) == 10:
        # A date-only fill sorts after timed events of the same day that are
        # stated before it in the registry; event_id breaks the tie.
        return (date.fromisoformat(ts), "99", row["event_id"])
    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    return (t.date(), t.strftime("%H:%M:%S"), row["event_id"])


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def load_prices(folder):
    prices = {}
    if not os.path.isdir(folder):
        return prices
    for name in sorted(os.listdir(folder)):
        if not name.endswith(".csv"):
            continue
        key = name[:-4]
        series = {}
        for r in read_csv(os.path.join(folder, name)):
            series[date.fromisoformat(r["date"])] = tuple(
                float(r[k]) for k in ("open", "high", "low", "close"))
        prices[key] = series
    return prices


def close_on_or_before(series, d):
    best = None
    for k in series:
        if k <= d and (best is None or k > best):
            best = k
    return None if best is None else series[best][3]


def methodology_version(path="methodology/v1.md"):
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        raise BuildError(f"{path} not found; run from the repository root")
    m = re.search(r"\*\*Version:\*\*\s*([0-9.]+)", text)
    if not m:
        raise BuildError(f"no '**Version:**' line in {path}")
    return m.group(1)


DATA_PATHS = ["performance/registry.csv", "performance/marks.csv", "performance/prices",
              "performance/theses.csv", "scripts/build_performance.py", "methodology/v1.md"]


def git_commit():
    """The last commit that changed an input, so unrelated pushes don't change the pages."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%h", "--abbrev=7", "--"] + DATA_PATHS,
                             capture_output=True, text=True, check=True).stdout.strip()
        return out or "working-copy"
    except (OSError, subprocess.CalledProcessError):
        return "working-copy"


# ----------------------------------------------------------------- validation

REQUIRED = {
    "open": ["trade_id", "thesis_id", "instrument", "direction", "price", "stop", "risk_pct"],
    "exit": ["trade_id", "thesis_id", "price", "result_r", "result_pct"],
    "update": ["trade_id"],
    "correction": ["trade_id"],
    "add": ["trade_id", "price"],
    "reduce": ["trade_id", "price"],
    "conclusion": ["thesis_id"],
    "non-trade": [],
}


def build_trades(rows, errors):
    """Group registry rows into trades. Problems go to `errors`."""
    trades = {}
    for row in sorted(rows, key=event_sort_key):
        ev = row["event"]
        tid = row["trade_id"]
        if ev in ("non-trade", "conclusion"):
            continue
        if ev in ("add", "reduce"):
            errors.append(f"{row['event_id']}: '{ev}' events are not supported yet; "
                          "the methodology has no rule for scaling, so this needs a rule first")
            continue
        if ev == "open":
            if tid in trades:
                errors.append(f"{row['event_id']}: second OPEN for {tid}")
                continue
            try:
                instrument = row["instrument"]
                key = row["contract"] or instrument
                t = Trade(
                    trade_id=tid, thesis_id=row["thesis_id"], instrument=instrument,
                    price_key=key,
                    direction=1 if row["direction"] == "long" else -1,
                    entry=parse_price(row["price"]), stop=parse_price(row["stop"]),
                    risk_pct=float(row["risk_pct"]),
                    notional_pct=float(row["notional_pct"]) if row.get("notional_pct") else None,
                    open_date=event_date(row), open_row=row, bond="'" in row["price"])
            except (ValueError, KeyError) as e:
                errors.append(f"{row['event_id']}: cannot read OPEN row ({e})")
                continue
            if row["direction"] not in ("long", "short"):
                errors.append(f"{row['event_id']}: direction must be long or short")
            t.events.append(row)
            trades[tid] = t
            continue
        if tid not in trades:
            errors.append(f"{row['event_id']}: {ev} for {tid or '(no trade)'} before its OPEN")
            continue
        t = trades[tid]
        if t.closed:
            errors.append(f"{row['event_id']}: {ev} for {tid} after its EXIT")
            continue
        t.events.append(row)
        if ev == "correction" and row["stop"]:
            t.stop = parse_price(row["stop"])
        if ev == "exit":
            t.exit_date = event_date(row)
            t.exit_price = parse_price(row["price"])
            t.result_r = float(row["result_r"])
            t.result_pct = float(row["result_pct"])
            t.exit_row = row
    return trades


def validate(rows, trades, marks, prices, month_ends, root=".", errors=None):
    """Return (errors, warnings). Errors stop the build."""
    errors = [] if errors is None else errors
    warnings = []
    seen_ids = set()
    file_lines = {}

    for row in rows:
        eid = row["event_id"]
        if eid in seen_ids:
            errors.append(f"{eid}: duplicate event_id")
        seen_ids.add(eid)
        ev = row["event"]
        if ev not in REQUIRED:
            errors.append(f"{eid}: unknown event type {ev!r}")
            continue
        for col in REQUIRED[ev]:
            if not row.get(col, "").strip():
                errors.append(f"{eid}: {ev} row is missing '{col}'")
        try:
            event_date(row)
        except ValueError:
            errors.append(f"{eid}: unreadable ts_utc {row['ts_utc']!r}")
        if row["ts_source"] not in ("file", "date", "receipt"):
            errors.append(f"{eid}: ts_source must be file, date or receipt")
        if row["ts_source"] == "receipt" and ev in ("open", "exit", "add", "reduce"):
            errors.append(f"{eid}: a fill may not be timed by push receipt (methodology §4)")
        for col in ("price", "stop"):
            if row.get(col):
                try:
                    parse_price(row[col])
                except ValueError as e:
                    errors.append(f"{eid}: {col} {e}")
        path = os.path.join(root, row["file"])
        if path not in file_lines:
            try:
                with open(path, encoding="utf-8") as fh:
                    file_lines[path] = sum(1 for _ in fh)
            except OSError:
                file_lines[path] = None
        n = file_lines[path]
        if n is None:
            errors.append(f"{eid}: file not found: {row['file']}")
        elif not row["line"].isdigit() or not 1 <= int(row["line"]) <= n:
            errors.append(f"{eid}: line {row['line']} is outside {row['file']} ({n} lines)")
        if row.get("result_r") and row.get("result_pct") and row.get("risk_pct"):
            implied = float(row["result_r"]) * float(row["risk_pct"])
            gap = abs(implied - float(row["result_pct"]))
            if gap > PCT_TOLERANCE + 1e-9:
                if row["note"].strip():
                    warnings.append(f"{eid}: result_pct {row['result_pct']} vs R x risk "
                                    f"{implied:.2f} (explained in note)")
                else:
                    errors.append(f"{eid}: result_pct {row['result_pct']} disagrees with "
                                  f"result_r x risk_pct = {implied:.2f}, and no note explains it")
        if row.get("pct_source") == "derived":
            warnings.append(f"{eid}: percentage derived from R x risk, not stated in the file")
        if row["ts_source"] == "date" and ev in ("open", "exit"):
            warnings.append(f"{eid}: date-only fill ({row['ts_utc']}); checked against that day's range")

    for t in trades.values():
        series = prices.get(t.price_key)
        if t.closed:
            recomputed = t.open_r(t.exit_price)
            if abs(recomputed - t.result_r) > R_TOLERANCE:
                errors.append(f"{t.trade_id}: stated {t.result_r:+.2f}R but entry, exit and stop "
                              f"give {recomputed:+.2f}R")
        if series is None:
            warnings.append(f"{t.trade_id}: no daily prices for {t.price_key}; fill ranges and "
                            "daily drawdown not checked")
            continue
        fills = [(t.open_row, t.entry)] + ([(t.exit_row, t.exit_price)] if t.closed else [])
        for row, px in fills:
            d = event_date(row)
            bar = series.get(d)
            if bar is None:
                errors.append(f"{row['event_id']}: no {t.price_key} bar for {d}")
            elif not bar[2] - 1e-9 <= px <= bar[1] + 1e-9:
                errors.append(f"{row['event_id']}: {px} is outside {t.price_key} range on {d} "
                              f"({bar[2]}–{bar[1]})")
        last = t.exit_date or max(series)
        for d, (o, h, l, c) in series.items():
            if not (t.open_date < d < last) and not (t.exit_date is None and d == last and d > t.open_date):
                continue
            hit = h >= t.stop if t.direction == -1 else l <= t.stop
            if hit:
                errors.append(f"{t.trade_id}: stop {t.stop} traded on {d}, before the recorded exit")

    for me in month_ends:
        for t in trades.values():
            if t.is_open_at(me) and (me, t.trade_id) not in marks:
                errors.append(f"marks.csv: no {me} mark for {t.trade_id}, open at that month-end")
    mark_dates = marks.get("_dates", {})
    for (me, tid), px in ((k, v) for k, v in marks.items() if k != "_dates"):
        t = trades.get(tid)
        if t is None:
            errors.append(f"marks.csv: {me} mark for unknown trade {tid}")
            continue
        if not t.is_open_at(me):
            errors.append(f"marks.csv: {me} mark for {tid}, which was not open then")
        series = prices.get(t.price_key, {})
        d = mark_dates.get((me, tid), me)
        if series:
            last = max((x for x in series if x <= me), default=None)
            if last != d:
                errors.append(f"marks.csv: {tid} {me:%Y-%m} mark is dated {d}, but the last "
                              f"{t.price_key} close on or before month-end is {last}")
            elif abs(series[d][3] - px) > 1e-6:
                errors.append(f"marks.csv: {d} {tid} mark {px} disagrees with "
                              f"prices/{t.price_key}.csv close {series[d][3]}")
    return errors, warnings


# --------------------------------------------------------------- calculations

@dataclass
class Month:
    y: int
    m: int
    start: date              # exclusive
    end: date                # inclusive: month-end, or as-of date for the live month
    complete: bool
    partial: bool            # month contains inception
    ret: float = 0.0
    index: float = 100.0
    open_at_end: list = field(default_factory=list)   # (trade, mark, open_r, open_pct)
    closed_in: list = field(default_factory=list)     # trades
    start_open_pct: float = 0.0

    @property
    def key(self):
        return f"{self.y}-{self.m:02d}"


def month_list(as_of):
    out = []
    y, m = INCEPTION.year, INCEPTION.month
    while (y, m) <= (as_of.year, as_of.month):
        me = month_end(y, m)
        start = INCEPTION - timedelta(days=1) if (y, m) == (INCEPTION.year, INCEPTION.month) \
            else month_end(*((y, m - 1) if m > 1 else (y - 1, 12)))
        complete = me <= as_of
        out.append(Month(y, m, start, me if complete else as_of, complete,
                         (y, m) == (INCEPTION.year, INCEPTION.month)))
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return out


def value_at(t, d, marks, prices, use_marks):
    """Open price of trade t at the close of d: the mark at a month-end, else the daily close."""
    if use_marks and (d, t.trade_id) in marks:
        return marks[(d, t.trade_id)]
    series = prices.get(t.price_key)
    if series is None:
        return None
    return close_on_or_before(series, d)


def compute_months(trades, marks, prices, as_of):
    months = month_list(as_of)
    index = 100.0
    prev_open = {}          # trade_id -> open % at the previous month boundary
    for mo in months:
        realised = 0.0
        for t in trades.values():
            if t.closed and mo.start < t.exit_date <= mo.end:
                realised += t.result_pct
                mo.closed_in.append(t)
        end_open = 0.0
        now_open = {}
        for t in trades.values():
            if t.is_open_at(mo.end):
                px = value_at(t, mo.end, marks, prices, use_marks=mo.complete)
                if px is None:
                    raise BuildError(f"no price for {t.trade_id} at {mo.end}")
                pct = t.open_pct(px)
                now_open[t.trade_id] = pct
                end_open += pct
                mo.open_at_end.append((t, px, t.open_r(px), pct))
        mo.start_open_pct = sum(prev_open.values())
        mo.ret = realised + end_open - mo.start_open_pct
        index += mo.ret                       # simple, not compounded (methodology §7)
        mo.index = index
        if mo.complete:
            prev_open = now_open
    return months


def compute_daily(trades, months, marks, prices, as_of):
    """Index at every daily close from inception to as_of (methodology §8, daily drawdown)."""
    days = set()
    for t in trades.values():
        series = prices.get(t.price_key, {})
        last = t.exit_date or as_of
        days.update(d for d in series if t.open_date <= d <= last)
        days.add(t.open_date)
        if t.exit_date:
            days.add(t.exit_date)
    days.update(mo.end for mo in months)
    out = []
    start_index = 100.0
    for mo in months:
        realised = 0.0
        for d in sorted(x for x in days if mo.start < x <= mo.end):
            realised = sum(t.result_pct for t in trades.values()
                           if t.closed and mo.start < t.exit_date <= d)
            open_now = 0.0
            for t in trades.values():
                if t.is_open_at(d):
                    use_marks = mo.complete and d == mo.end
                    px = value_at(t, d, marks, prices, use_marks)
                    if px is not None:
                        open_now += t.open_pct(px)
            out.append((d, start_index + realised + open_now - mo.start_open_pct))
        start_index = mo.index
    return out


def drawdown_series(points):
    """[(label, value)] -> [(label, drawdown%)], plus (mdd%, peak_label, trough_label)."""
    peak_v, peak_l = None, None
    worst = (0.0, None, None)
    out = []
    for label, v in points:
        if peak_v is None or v > peak_v:
            peak_v, peak_l = v, label
        dd = v - peak_v                       # points of starting equity below the peak
        out.append((label, dd))
        if dd < worst[0] - 1e-12:
            worst = (dd, peak_l, label)
    return out, worst


def longest_under_water(values):
    """Most consecutive points below a previous peak; (count, ongoing)."""
    peak = None
    run = best = 0
    for v in values:
        if peak is None or v >= peak - 1e-12:
            peak = v if peak is None or v > peak else peak
            run = 0
        else:
            run += 1
            best = max(best, run)
    return best, run > 0


def annualised_stats(monthly_returns):
    """Methodology §8 gate: below MIN_MONTHS_FOR_ANNUALISED nothing is calculated at all.

    Sharpe, Sortino and S&P 500 correlation also need a T-bill series and the
    index's monthly returns; they are added when the record first reaches the
    gate, as a methodology-logged change.
    """
    n = len(monthly_returns)
    if n < MIN_MONTHS_FOR_ANNUALISED:
        return None
    mean = sum(monthly_returns) / n
    var = sum((r - mean) ** 2 for r in monthly_returns) / (n - 1)
    return {"annualised_return": mean * 12,
            "annualised_volatility": var ** 0.5 * 12 ** 0.5}


def compounded_equivalent(monthly_returns):
    """Side figure only (methodology §7): the same monthly returns, compounded."""
    g = 1.0
    for r in monthly_returns:
        g *= 1 + r / 100
    return (g - 1) * 100


def classify(r):
    if r > SCRATCH_R:
        return "win"
    if r < -SCRATCH_R:
        return "loss"
    return "scratch"


def trade_stats(trades):
    closed = sorted((t for t in trades.values() if t.closed),
                    key=lambda t: (t.exit_date, event_sort_key(t.exit_row)))
    rs = [t.result_r for t in closed]
    wins = [t for t in closed if classify(t.result_r) == "win"]
    losses = [t for t in closed if classify(t.result_r) == "loss"]
    total = sum(rs)
    s = {"n_closed": len(closed), "n_win": len(wins), "n_loss": len(losses),
         "n_scratch": len(closed) - len(wins) - len(losses), "total_r": total}
    s["win_rate"] = len(wins) / len(closed) * 100 if closed else None
    s["avg_win"] = sum(t.result_r for t in wins) / len(wins) if wins else None
    s["avg_loss"] = sum(t.result_r for t in losses) / len(losses) if losses else None
    s["payoff"] = (s["avg_win"] / abs(s["avg_loss"])) if wins and losses else None
    s["expectancy"] = total / len(closed) if closed else None
    gross_win = sum(t.result_r for t in wins)
    gross_loss = abs(sum(t.result_r for t in losses))
    s["profit_factor"] = gross_win / gross_loss if gross_loss else None
    s["profit_factor_text"] = ("n/a (no losses)" if closed and not gross_loss
                               else "—" if not closed else f"{s['profit_factor']:.2f}")
    best = max(closed, key=lambda t: t.result_r) if closed else None
    s["best_share"] = (best.result_r / total * 100) if best and total > 0 else None
    s["best_trade"] = best.trade_id if best else None
    s["worst_r"] = min(rs) if rs else None
    hold = lambda ts: sum((t.exit_date - t.open_date).days for t in ts) / len(ts) if ts else None
    s["hold_win"], s["hold_loss"] = hold(wins), hold(losses)
    streak = longest = 0
    for t in closed:
        streak = streak + 1 if classify(t.result_r) == "loss" else 0
        longest = max(longest, streak)
    s["loss_streak"] = longest
    all_t = list(trades.values())
    s["avg_risk"] = sum(t.risk_pct for t in all_t) / len(all_t) if all_t else None
    s["max_risk"] = max((t.risk_pct for t in all_t), default=None)
    notionals = [t.notional_pct for t in all_t if t.notional_pct is not None]
    s["max_notional"] = max(notionals) if notionals else None
    s["closed_order"] = closed
    return s


def thesis_verdicts(rows, trades):
    verdicts = {}
    for row in sorted(rows, key=event_sort_key):
        if row.get("verdict"):
            verdicts[row["thesis_id"]] = (row["verdict"], row)
    out = {}
    for th in {t.thesis_id for t in trades.values()} | set(verdicts):
        if th in verdicts:
            out[th] = verdicts[th]
        elif any(t.thesis_id == th and not t.closed for t in trades.values()):
            out[th] = ("Open", None)
        else:
            out[th] = ("Not yet judged", None)
    return out


# --------------------------------------------------------------------- charts

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    matplotlib.rcParams.update({
        "svg.hashsalt": "mcmr-track-record", "svg.fonttype": "path",
        "font.family": "DejaVu Sans",
        "font.size": 10, "text.color": GREY, "axes.labelcolor": GREY,
        "axes.edgecolor": GREY, "xtick.color": GREY, "ytick.color": GREY,
        "axes.spines.top": False, "axes.spines.right": False,
        "savefig.transparent": True, "figure.facecolor": "none", "axes.facecolor": "none",
    })
    return plt


def _month_axis(ax):
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))


def _pad_bars(ax, vals):
    lo, hi = min(vals + [0]), max(vals + [0])
    span = (hi - lo) or 1
    ax.set_ylim(lo - 0.22 * span, hi + 0.18 * span)


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, format="svg", metadata={"Date": None, "Creator": None})
    import matplotlib.pyplot as plt
    plt.close(fig)


def draw_charts(out_dir, months, daily, trades, stats):
    plt = _plt()
    os.makedirs(out_dir, exist_ok=True)
    complete = [mo for mo in months if mo.complete]
    live = months[-1] if months and not months[-1].complete else None

    pts = [(INCEPTION, 100.0)] + [(mo.end, mo.index) for mo in complete]
    fig, ax = plt.subplots(figsize=(7.5, 3.2))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=GREEN, marker="o", lw=2)
    if live:
        ax.plot([pts[-1][0], live.end], [pts[-1][1], live.index], color=GREEN, lw=1.5, ls="--")
        ax.plot([live.end], [live.index], marker="o", mfc="none", mec=GREEN, ms=7)
        ax.annotate(f"{live.index:.1f} to {_dm(live.end)}", (live.end, live.index),
                    textcoords="offset points", xytext=(-10, -3), ha="right", fontsize=8)
    for d, v in pts[1:]:
        ax.annotate(f"{v:.1f}", (d, v), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=8)
    ax.axhline(100, color=GREY, lw=0.6, ls=":")
    ax.set_ylabel("Index (start = 100)")
    ax.set_title("100 + cumulative return (simple) · month-end; dashed = month to date",
                 fontsize=10, color=GREY)
    _month_axis(ax)
    _save(fig, os.path.join(out_dir, "index.svg"))

    m_dd, (m_mdd, _, m_trough) = drawdown_series(pts)
    d_dd, (d_mdd, _, d_trough) = drawdown_series(daily)
    fig, ax = plt.subplots(figsize=(7.5, 2.6))
    ax.plot([d for d, _ in d_dd], [v for _, v in d_dd], color=GREY, lw=1, label="daily")
    ax.fill_between([d for d, _ in m_dd], [v for _, v in m_dd], 0, color=RED, alpha=0.25,
                    step=None, label="month-end")
    ax.plot([d for d, _ in m_dd], [v for _, v in m_dd], color=RED, marker="o", lw=1.5)
    if d_trough:
        ax.annotate(f"daily MDD {d_mdd:.1f}%".replace("-", MINUS), (d_trough, d_mdd), textcoords="offset points",
                    xytext=(-8, -2), ha="right", fontsize=8)
    if m_trough:
        ax.annotate(f"month-end MDD {m_mdd:.1f}%".replace("-", MINUS), (m_trough, m_mdd), textcoords="offset points",
                    xytext=(6, -10), fontsize=8, color=RED)
    ax.set_ylabel("Below peak (% of start equity)")
    ax.set_ylim(min(d_mdd, m_mdd, -1) * 1.3, 0.5)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    _month_axis(ax)
    _save(fig, os.path.join(out_dir, "drawdown.svg"))

    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    labels = [f"{calendar.month_abbr[mo.m]} {mo.y % 100:02d}" + ("*" if mo.partial else "")
              + ("†" if not mo.complete else "") for mo in months]
    vals = [mo.ret for mo in months]
    bars = ax.bar(labels, vals, color=[GREEN if v >= 0 else RED for v in vals])
    for b, mo in zip(bars, months):
        if mo.partial or not mo.complete:
            b.set_hatch("///")
            b.set_edgecolor("white")
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:+.1f}%".replace("-", MINUS), (b.get_x() + b.get_width() / 2, v), textcoords="offset points",
                    xytext=(0, 4 if v >= 0 else -12), ha="center", fontsize=8)
    ax.axhline(0, color=GREY, lw=0.8)
    _pad_bars(ax, vals)
    ax.set_ylabel("Monthly return (%)")
    ax.set_title("* partial month   † month to date", fontsize=9, color=GREY)
    _save(fig, os.path.join(out_dir, "monthly.svg"))

    closed = stats["closed_order"]
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    vals = [t.result_r for t in closed]
    bars = ax.bar([t.trade_id for t in closed], vals,
                  color=[GREEN if v >= 0 else RED for v in vals])
    for b, v in zip(bars, vals):
        ax.annotate(f"{v:+.2f}R".replace("-", MINUS), (b.get_x() + b.get_width() / 2, v), textcoords="offset points",
                    xytext=(0, 4 if v >= 0 else -12), ha="center", fontsize=8)
    ax.axhline(0, color=GREY, lw=0.8)
    _pad_bars(ax, vals)
    ax.set_ylabel("Result (R)")
    ax.set_title("Closed trades, in the order closed", fontsize=9, color=GREY)
    _save(fig, os.path.join(out_dir, "trades_r.svg"))

    ordered = sorted(trades.values(), key=lambda t: (t.open_date, t.trade_id))
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    for i, t in enumerate(ordered):
        if not t.closed:
            style = dict(marker="D", mfc="none", mec=GREY)
            tag = "open"
        elif classify(t.result_r) == "win":
            style = dict(marker="o", mfc=GREEN, mec=GREEN)
            tag = f"{t.result_r:+.2f}R".replace("-", MINUS)
        else:
            style = dict(marker="o", mfc="none", mec=RED)
            tag = f"{t.result_r:+.2f}R".replace("-", MINUS)
        ax.plot([i], [t.risk_pct], ms=9, ls="none", **style)
        ax.annotate(f"{t.risk_pct:.2f}%\n{tag}", (i, t.risk_pct), textcoords="offset points",
                    xytext=(0, 9), ha="center", fontsize=8)
    ax.set_xticks(range(len(ordered)), [t.trade_id for t in ordered])
    ax.set_ylim(0, max(t.risk_pct for t in ordered) * 1.45)
    ax.set_xlim(-0.6, len(ordered) - 0.4)
    ax.set_ylabel("Risk at entry (1R, % of equity)")
    ax.set_title("filled = win · hollow = loss · diamond = open", fontsize=9, color=GREY)
    _save(fig, os.path.join(out_dir, "risk.svg"))


# ---------------------------------------------------------------------- pages

def page_header(version, commit, as_of):
    return [
        "> **Model portfolio**: the reference book for my trading. Decisions are published and",
        "> timestamped in real time; live execution follows the same theses, though sizing and",
        "> timing can differ. Results are gross and are not an account statement. Returns are",
        "> **simple, not compounded**: % of starting equity, added across months (methodology §7).",
        f"> Rules: [methodology v{version}](methodology/v1.md) · Data to {fmt_date(as_of)} close "
        f"· Built from commit `{commit}`",
        "",
    ]


def monthly_grid(months):
    years = sorted({mo.y for mo in months})
    lines = ["| Year | " + " | ".join(calendar.month_abbr[1:]) + " | Year |",
             "|---|" + "---:|" * 13]
    for y in years:
        cells, comp = [], 0.0
        for m in range(1, 13):
            mo = next((x for x in months if x.y == y and x.m == m), None)
            if mo is None:
                cells.append("")
                continue
            mark = ("*" if mo.partial else "") + ("†" if not mo.complete else "")
            cells.append(f"{mo.ret:+.2f}{mark}".replace("-", MINUS))
            comp += mo.ret
        ytd_mark = "" if all(x.complete for x in months if x.y == y) else "†"
        lines.append(f"| {y} | " + " | ".join(cells) + f" | **{comp:+.2f}{ytd_mark}** |".replace("-", MINUS))
    return lines


def headline_cells(ctx, where="page"):
    """The five numbers a reader sees first, shared by PERFORMANCE.md and the README."""
    m, s = ctx["metrics"], ctx["stats"]
    live = ctx["months"][-1]
    mtd_label = "This month" + ("" if live.complete else " (to date)")
    win = "—" if s["win_rate"] is None else f"{s['win_rate']:.0f}%"
    payoff = "" if s["payoff"] is None else f"wins avg {s['payoff']:.1f}× losses"
    n_open = m["n_open"]
    return [
        ("Since inception", f"**{fmt_pct(m['since_inception'])}**",
         f"simple · compounded {fmt_pct(m['compounded'])}"),
        (mtd_label, f"**{fmt_pct(live.ret)}**", f"{calendar.month_abbr[live.m]} {live.y}"),
        ("Max drawdown", f"**{fmt_pct(m['mdd_m'])}**", f"month-end · daily {fmt_pct(m['mdd_d'], nd=1)}"),
        ("Win rate", f"**{win}**", f"{s['n_win']} of {s['n_closed']} · {payoff}" if payoff
         else f"{s['n_win']} of {s['n_closed']} closed"),
        ("Open positions", f"**{n_open}**",
         ("none" if not n_open else "listed below" if where == "page" else "on the performance page")),
    ]


def headline_table(ctx, where="page"):
    cells = headline_cells(ctx, where)
    return ["| " + " | ".join(c[0] for c in cells) + " |",
            "|" + ":---:|" * len(cells),
            "| " + " | ".join(c[1] for c in cells) + " |",
            "| " + " | ".join(f"<sub>{c[2]}</sub>" for c in cells) + " |"]


def build_performance_md(ctx):
    """Front page. The first screen answers 'how has it done, and how risky' in under 30
    seconds; everything else sits in collapsed sections below, in the order a reviewer
    would ask for it."""
    m, s, months, trades = ctx["metrics"], ctx["stats"], ctx["months"], ctx["trades"]
    verdicts, names, as_of = ctx["verdicts"], ctx["names"], ctx["as_of"]
    L = ["# MCMR · Model Portfolio", "",
         f"**Discretionary macro, published before the outcome.** Data to {fmt_date(as_of)} close · "
         f"inception {fmt_date(INCEPTION)}", "",
         "<sub>Model portfolio: every decision is published and timestamped in real time; "
         "results are simple (not compounded), gross, and not an account statement.</sub>", ""]
    L += headline_table(ctx) + ["", "![Growth](performance/charts/index.svg)", "",
                                "### Monthly returns (%)", ""]
    L += monthly_grid(months)
    notes = ["\\* partial month"]
    if months and not months[-1].complete:
        notes.append(f"† to {fmt_date(as_of)}, includes open position; not final")
    L += ["", "<sub>" + " · ".join(notes) + "</sub>", ""]

    open_now = [t for t in trades.values() if not t.closed]
    if open_now:
        L += ["### Open position" + ("s" if len(open_now) > 1 else ""), "",
              "| Trade | Thesis | Direction | Entry | Stop | Last close | Open result |",
              "|---|---|---|---:|---:|---:|---:|"]
        for t in open_now:
            px = value_at(t, as_of, {}, ctx["prices"], False)
            L.append(f"| [{t.trade_id}](performance/theses/{t.thesis_id}.md) | "
                     f"{names.get(t.thesis_id, t.thesis_id)} | {'Long' if t.direction == 1 else 'Short'} "
                     f"{t.price_key} | {fmt_price(t.entry, t.bond)} | {fmt_price(t.stop, t.bond)} | "
                     f"{fmt_price(px, t.bond)} | **{fmt_pct(t.open_pct(px))}** ({fmt_r(t.open_r(px))}) |")
        L += ["", "<sub>Unrealised. Included in this month's figure, never in trade statistics.</sub>", ""]

    L += ["### Reports", ""] + reports_table(months) + [""]

    # ---- detail, collapsed ----
    uw_n, uw_on = m["under_water"]
    payoff_text = "—" if s["payoff"] is None else f"{s['payoff']:.2f}"
    best_share_text = ("—" if s["best_share"] is None
                       else f"{s['best_share']:.0f}% ({s['best_trade']})")
    L += ["---", "", "<details>", "<summary><b>Risk and statistics</b></summary>", "",
          "![Drawdown](performance/charts/drawdown.svg)", "",
          "| Returns | | Trades | |", "|---|---:|---|---:|",
          f"| Completed months | {m['n_months']} | Closed trades | {s['n_closed']} |",
          f"| Best / worst month | {fmt_pct(m['best'])} / {fmt_pct(m['worst'])} | Win rate | "
          f"{fmt_pct(s['win_rate'], False, 0)} |",
          f"| Positive months | {m['pos_months']} of {m['n_months']} | Avg win / avg loss | "
          f"{fmt_r(s['avg_win'])} / {fmt_r(s['avg_loss'])} |",
          f"| Max drawdown, month-end | {fmt_pct(m['mdd_m'])} ({m['mdd_m_span']}) | Payoff ratio | {payoff_text} |",
          f"| Max drawdown, daily | {fmt_pct(m['mdd_d'])} ({m['mdd_d_span']}) | Expectancy | {fmt_r(s['expectancy'])} |",
          f"| Current drawdown | {fmt_pct(m['current_dd'])} | Profit factor | {s['profit_factor_text']} |",
          f"| Longest under water | {uw_n} month{'s' if uw_n != 1 else ''}{' (ongoing)' if uw_on else ''} "
          f"| Best-trade share of total R | {best_share_text} |",
          f"| Return ÷ max drawdown | {m['ret_mdd']} | Avg hold, winners / losers | "
          f"{_days(s['hold_win'])} / {_days(s['hold_loss'])} |",
          f"| Avg / max risk per trade | {fmt_pct(s['avg_risk'], False)} / {fmt_pct(s['max_risk'], False)} "
          f"| Longest losing streak | {s['loss_streak']} |",
          f"| Max notional exposure | {fmt_pct(s['max_notional'], False, 0)} of equity | Thesis hit rate | "
          f"{ctx['hit']['text']} |",
          "",
          f"<sub>Returns and drawdowns are % of starting equity (simple). Annualised return, "
          f"volatility, Sharpe, Sortino and S&P 500 correlation appear once "
          f"{MIN_MONTHS_FOR_ANNUALISED} monthly returns exist ({m['n_months']} so far).</sub>", "",
          "</details>", "",
          "<details>", "<summary><b>Trades and theses</b></summary>", "",
          "| Thesis | Trades | Closed R | Closed % | Verdict |", "|---|---|---:|---:|---|"]
    for th in sorted(verdicts):
        ts = [t for t in trades.values() if t.thesis_id == th]
        closed = [t for t in ts if t.closed]
        r = sum(t.result_r for t in closed) if closed else None
        p = sum(t.result_pct for t in closed) if closed else None
        extra = f" + {len(ts) - len(closed)} open" if len(closed) < len(ts) else ""
        L.append(f"| [{th} · {names.get(th, '')}](performance/theses/{th}.md) | {len(closed)}{extra} | "
                 f"{fmt_r(r)} | {fmt_pct(p)} | {verdicts[th][0]} |")
    L += ["", "**Was the idea right, and did the trade pay?**", "",
          "|  | Trade won | Trade lost |", "|---|---|---|"]
    for label, keys in (("Thesis confirmed", ("Confirmed",)), ("Thesis killed", ("Killed",)),
                        ("Untested / open", None)):
        cells = []
        for outcome in ("win", "loss"):
            ids = sorted(t.trade_id for t in s["closed_order"]
                         if classify(t.result_r) == outcome and
                         ((verdicts[t.thesis_id][0] in keys) if keys else
                          verdicts[t.thesis_id][0] not in ("Confirmed", "Killed")))
            cells.append(f"{len(ids)}" + (f" ({', '.join(ids)})" if ids else ""))
        L.append(f"| {label} | {cells[0]} | {cells[1]} |")
    L += ["", "![Result per trade](performance/charts/trades_r.svg)", "",
          "![Risk per trade](performance/charts/risk.svg)", "",
          "![Monthly returns](performance/charts/monthly.svg)", "",
          "</details>", "",
          "<details>", "<summary><b>Method and data</b></summary>", ""]
    backfilled = [mo for mo in months if mo.complete
                  and ctx["frozen_labels"].get(mo.key, "").startswith("Backfilled")]
    L += [f"- **Model portfolio.** The reference book for my trading. Live execution follows the "
          f"same theses, though sizing and timing can differ.",
          f"- **Simple returns.** % of starting equity, added across months. The compounded "
          f"equivalent ({fmt_pct(m['compounded'])}) is shown for comparison only.",
          "- **Valuation.** Open positions at the official close: month-end marks for monthly "
          "figures, the latest daily close for this month.",
          "- **Gross.** Transaction costs assumed negligible; futures carry not modelled."]
    if backfilled:
        L.append(f"- **Backfilled months.** {', '.join(f'{calendar.month_abbr[mo.m]} {mo.y}' for mo in backfilled)} "
                 f"were calculated on {ctx['frozen_labels'][backfilled[0].key].split(' on ')[1]} from public "
                 "closing prices, after the fact; later months freeze at month-end.")
    L += [f"- **Rules:** [methodology v{ctx['version']}](methodology/v1.md). "
          f"**Data:** [registry](performance/registry.csv) · [marks](performance/marks.csv) · "
          f"[daily prices](performance/prices/) · [validation report](performance/VALIDATION.md). "
          f"Built from data commit `{ctx['commit']}`.", "",
          "</details>", ""]
    return "\n".join(L)


README_START = "<!-- performance:start (generated by scripts/build_performance.py; do not edit) -->"
README_END = "<!-- performance:end -->"


def update_readme(ctx, path="README.md"):
    """Refresh the headline numbers between the markers in README.md, if the markers exist.
    Nothing else in the README is touched."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return False
    if README_START not in text or README_END not in text:
        return False
    head, rest = text.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    block = "\n".join([README_START] + headline_table(ctx, "readme") + [
        "", f"<sub>Model portfolio · simple returns · data to {fmt_date(ctx['as_of'])} close · "
            f"[full performance →](PERFORMANCE.md)</sub>", README_END])
    return write_if_changed(path, head + block + tail)


def reports_table(months):
    """One row per frozen quarter and year, plus the periods still in progress."""
    rows = []
    def period_row(label, ms, link, status):
        total = sum(mo.ret for mo in ms)
        pts = [("start", 100.0)] + [(mo.key, mo.index) for mo in months if mo.complete]
        dd = dict(drawdown_series(pts)[0])
        worst = min((dd.get(mo.key, 0.0) for mo in ms if mo.complete), default=0.0)
        name = f"[{label}]({link})" if link else label
        rows.append(f"| {name} | {fmt_pct(total)} | {fmt_pct(worst)} | {status} |")
    by_q, by_y = {}, {}
    for mo in months:
        by_q.setdefault((mo.y, (mo.m - 1) // 3 + 1), []).append(mo)
        by_y.setdefault(mo.y, []).append(mo)
    for (y, q), ms in sorted(by_q.items(), reverse=True):
        f = os.path.join(PERF, "quarters", f"{y}-Q{q}.md")
        if os.path.exists(f):
            label = json.load(open(os.path.join(PERF, "months", f"{ms[-1].key}.json"),
                                   encoding="utf-8"))["label"].split(" on ")[0]
            period_row(f"{y}-Q{q}", ms, f"performance/quarters/{y}-Q{q}.md", f"Frozen ({label.lower()})")
        else:
            period_row(f"{y}-Q{q}", ms, None, "In progress")
    for y, ms in sorted(by_y.items(), reverse=True):
        f = os.path.join(PERF, "years", f"{y}.md")
        period_row(str(y), ms, f"performance/years/{y}.md" if os.path.exists(f) else None,
                   "Frozen" if os.path.exists(f) else "In progress")
    return ["| Period | Return | Worst month-end drawdown | Report |", "|---|---:|---:|---|"] + rows


def _days(x):
    return "—" if x is None else f"{x:.1f} days"


def _git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def proof_index(files, receipts_dir="receipts"):
    """For each trade file: the commit that first added it, and the earliest time
    GitHub is independently recorded as holding that commit. Sources: per-push
    receipts (from 11 Sep 2026, each with an OpenTimestamps Bitcoin proof) and the
    GitHub event records in receipts/ for earlier pushes (GH Archive and the API
    backfill). A record for any later commit also covers every commit before it."""
    heads = []                                    # (utc, head sha, receipt file or None, label)
    for name, label in (("push_receipts_backfill.json", "GitHub event log"),
                        ("push_receipts_gharchive.json", "GH Archive")):
        try:
            d = json.load(open(os.path.join(receipts_dir, name), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for ev in d.get("push_events", []):
            if ev.get("head") and ev.get("received_by_github_utc"):
                heads.append((ev["received_by_github_utc"], ev["head"], None, label))
    if os.path.isdir(receipts_dir):
        for name in os.listdir(receipts_dir):
            if not re.fullmatch(r"[0-9a-f]{40}\.json", name):
                continue
            if not os.path.exists(os.path.join(receipts_dir, name + ".ots")):
                continue
            try:
                r = json.load(open(os.path.join(receipts_dir, name), encoding="utf-8"))
                heads.append((r["received_by_github_utc"], r["commit"], name, "receipt"))
            except (OSError, ValueError, KeyError):
                continue
    heads.sort()
    out = {}
    for f in sorted(set(files)):
        added = _git("log", "--follow", "--diff-filter=A", "--format=%H", "--", f)
        if not added:
            continue
        sha = added.splitlines()[-1]
        info = {"commit": sha, "by": None}
        for when, head, name, label in heads:
            if head == sha or _git("merge-base", "--is-ancestor", sha, head) is not None:
                info["by"] = (when, name, label)
                break
        out[f] = info
    return out


def _utc_short(ts):
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return f"{t.day} {t:%b %Y %H:%M}"


def proof_table(files, proofs):
    """Per-file proof of timing, beneath the event table."""
    L = ["", "#### Proof of timing", "",
         "*Each file's first commit, and the earliest time GitHub is independently recorded as "
         "holding it. [Check one yourself in 2 minutes →](../../VERIFICATION.md#check-a-trade-in-2-minutes)*", "",
         "| File | First commit | GitHub had it by (UTC) | Evidence |",
         "|---|---|---|---|"]
    for f in files:
        info = proofs.get(f)
        if not info:
            continue
        c = info["commit"]
        name = os.path.basename(f)
        row = f"| [{name}](../../{file_link(f)}) | [`{c[:7]}`]({REPO_URL}/commit/{c}) | "
        if info["by"]:
            when, rec, label = info["by"]
            row += f"{_utc_short(when)} | "
            row += (f"[receipt](../../receipts/{rec}) · [Bitcoin proof](../../receipts/{rec}.ots) |"
                    if rec else f"[{label}](../../VERIFICATION.md#coverage) |")
        else:
            row += "— | [not covered](../../VERIFICATION.md#coverage) |"
        L.append(row)
    return L


def build_thesis_md(th, name, verdict, trades, rows, version, commit, as_of, prices, proofs=None):
    ts = [t for t in trades.values() if t.thesis_id == th]
    closed = [t for t in ts if t.closed]
    v, vrow = verdict
    src = (f" — [source](../../{file_link(vrow['file'])}#L{vrow['line']})" if vrow else "")
    res = (f"{fmt_r(sum(t.result_r for t in closed))} / {fmt_pct(sum(t.result_pct for t in closed))} closed"
           if closed else "nothing closed yet")
    L = [f"# {th} — {name}", "",
         f"**Verdict:** {v}{src}  ·  **Result:** {res}"
         + (f"  ·  {len(ts) - len(closed)} open" if len(closed) < len(ts) else ""), "",
         f"*Model portfolio. Methodology v{version}; built from commit `{commit}`.*", "",
         "| Date (UTC) | Event | Trade | Instrument | Price | Stop | R | % | Source |",
         "|---|---|---|---|---:|---:|---:|---:|---|"]
    proofs = proofs or {}
    th_rows = [r for r in rows if r["thesis_id"] == th]
    for r in sorted(th_rows, key=event_sort_key):
        t = trades.get(r["trade_id"])
        bond = t.bond if t else ("'" in r["price"])
        when = r["ts_utc"] if r["ts_source"] != "receipt" else r["ts_utc"]
        when = when.replace("T", " ").replace("Z", "")[:16] + (" (date only)" if r["ts_source"] == "date" else "")
        px = fmt_price(parse_price(r["price"]), bond) if r["price"] else ""
        st = fmt_price(parse_price(r["stop"]), bond) if r["stop"] else ""
        rr = r["result_r"] and fmt_r(float(r["result_r"]))
        pp = r["result_pct"] and fmt_pct(float(r["result_pct"]))
        if r["event"] == "update" and rr:
            rr, pp = f"{rr} open", f"{pp} open"
        inst = (r["contract"] or r["instrument"]) if r["instrument"] else ""
        L.append(f"| {when} | {r['event']} | {r['trade_id']} | {inst} | {px} | {st} | {rr} | {pp} | "
                 f"[L{r['line']}](../../{file_link(r['file'])}#L{r['line']}) |")
    open_now = [t for t in ts if not t.closed]
    if open_now:
        L += ["", f"**At {fmt_date(as_of)} close:** " + "; ".join(
            f"{t.trade_id} {fmt_r(t.open_r(value_at(t, as_of, {}, prices, False)))} / "
            f"{fmt_pct(t.open_pct(value_at(t, as_of, {}, prices, False)))} open"
            for t in open_now)]
    L += ["", "*Rows marked `update` show open profit as published in that file: the path, "
          "including give-backs, not only the result.*"]
    seen = []
    for r in sorted(th_rows, key=event_sort_key):
        if r["file"] and r["file"] not in seen:
            seen.append(r["file"])
    L += proof_table(seen, proofs)
    L.append("")
    return "\n".join(L)


def month_json(mo, version, commit, frozen_on, label):
    return {
        "_what_this_is": "Frozen month-end record. Never regenerated; corrections go in a dated "
                         "notice beside this file (methodology §10).",
        "month": mo.key, "partial_month": mo.partial, "methodology_version": version,
        "built_from_commit": commit, "frozen_on": frozen_on.isoformat(), "label": label,
        "return_pct": round(mo.ret, 4), "index": round(mo.index, 4),
        "open_at_month_end": [
            {"trade_id": t.trade_id, "instrument": t.price_key, "mark": px,
             "open_r": round(r, 4), "open_pct": round(p, 4)} for t, px, r, p in mo.open_at_end],
        "closed_in_month": [
            {"trade_id": t.trade_id, "exit_date": t.exit_date.isoformat(),
             "result_r": t.result_r, "result_pct": t.result_pct} for t in mo.closed_in],
    }


def build_period_md(title, months_in, months_all, trades, version, commit, label, as_of_label):
    first, last = months_in[0], months_in[-1]
    comp = 1.0
    for mo in months_in:
        comp += mo.ret
    ytd = 0.0
    for mo in months_all:
        if mo.y == last.y and (mo.m <= last.m):
            ytd += mo.ret
    pts = [("start", 100.0)] + [(mo.key, mo.index) for mo in months_all if mo.complete]
    dd_map = dict(drawdown_series(pts)[0])
    in_dd = drawdown_series([("start", 100.0)] + [(mo.key, mo.index) for mo in months_all
                                                  if mo.complete and mo.end <= last.end])[0]
    worst_in = min((v for k, v in in_dd if k in {mo.key for mo in months_in}), default=0.0)
    L = [f"# {title}", "",
         f"Model portfolio · Methodology v{version} · {label} from commit `{commit}`", "",
         f"**Period return:** {fmt_pct(comp)}  ·  **Year to date:** "
         f"{fmt_pct(ytd)}  ·  **Since inception:** {fmt_pct(last.index - 100)}  ·  "
         f"**Worst month-end drawdown in period:** {fmt_pct(worst_in)}", "",
         "| Month | Return | Index | Drawdown |", "|---|---:|---:|---:|"]
    for mo in months_in:
        L.append(f"| {calendar.month_name[mo.m]} {mo.y}{' *' if mo.partial else ''} | "
                 f"{fmt_pct(mo.ret)} | {mo.index:.2f} | {fmt_pct(dd_map.get(mo.key, 0.0))} |")
    if any(mo.partial for mo in months_in):
        L.append(f"\n*\\* partial month, from inception on {fmt_date(INCEPTION)}.*")
    start_open = {}
    before = [mo for mo in months_all if mo.end < first.end and mo.complete]
    if before:
        start_open = {t.trade_id: p for t, _, _, p in before[-1].open_at_end}
    L += ["", "## Closed in this period", ""]
    closed = [t for mo in months_in for t in mo.closed_in]
    if closed:
        L += ["| Trade | Thesis | Opened | Closed | Full R | Full % | Part in this period |",
              "|---|---|---|---|---:|---:|---:|"]
        for t in closed:
            part = t.result_pct - start_open.get(t.trade_id, 0.0)
            L.append(f"| {t.trade_id} | {t.thesis_id} | {t.open_date} | {t.exit_date} | "
                     f"{fmt_r(t.result_r)} | {fmt_pct(t.result_pct)} | {fmt_pct(part)} |")
    else:
        L.append("None.")
    L += ["", f"## Open at period end ({as_of_label})", ""]
    if last.open_at_end:
        L += ["| Trade | Thesis | Mark | Open R | Open % |", "|---|---|---:|---:|---:|"]
        for t, px, r, p in last.open_at_end:
            L.append(f"| {t.trade_id} | {t.thesis_id} | {fmt_price(px, t.bond)} | {fmt_r(r)} | {fmt_pct(p)} |")
    else:
        L.append("None.")
    L += ["", "*Frozen: this file is never regenerated. Corrections appear as dated notices beside "
          "it (methodology §10).*", ""]
    return "\n".join(L)


# ----------------------------------------------------------------------- main

def write_if_changed(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        if open(path, encoding="utf-8").read() == text:
            return False
    except OSError:
        pass
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    return True


def load_all(root="."):
    rows = read_csv(os.path.join(root, PERF, "registry.csv"))
    marks, mark_dates = {}, {}
    for r in read_csv(os.path.join(root, PERF, "marks.csv")):
        # The mark is the last close on or before month-end (methodology §6), so its
        # date may be a Friday before a weekend month-end. Key it by the month.
        d = date.fromisoformat(r["month_end"])
        key = (month_end(d.year, d.month), r["trade_id"])
        if key in marks:
            raise BuildError(f"marks.csv: two marks for {r['trade_id']} in {d:%Y-%m}")
        marks[key] = parse_price(r["mark"])
        mark_dates[key] = d
    marks["_dates"] = mark_dates
    prices = load_prices(os.path.join(root, PERF, "prices"))
    names_path = os.path.join(root, PERF, "theses.csv")
    names = {r["thesis_id"]: r["name"] for r in read_csv(names_path)} if os.path.exists(names_path) else {}
    return rows, marks, prices, names


def determine_as_of(trades, prices, today):
    """Latest date the data covers: the last daily close for an open position, else the last event."""
    candidates = []
    for t in trades.values():
        if not t.closed and t.price_key in prices:
            candidates.append(max(d for d in prices[t.price_key] if d <= today))
        elif t.closed:
            candidates.append(t.exit_date)
    return max(candidates) if candidates else INCEPTION


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--allow-refreeze", action="store_true",
                    help="regenerate frozen files that already exist (never used by the workflow)")
    ap.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    args = ap.parse_args(argv)
    today = date.fromisoformat(args.today) if args.today else datetime.now(timezone.utc).date()

    rows, marks, prices, names = load_all()
    errors = []
    trades = build_trades(rows, errors)
    as_of = determine_as_of(trades, prices, today)
    months = month_list(as_of)
    month_ends = [mo.end for mo in months if mo.complete]
    errors, warnings = validate(rows, trades, marks, prices, month_ends, errors=errors)
    if errors:
        print("Build stopped. Fix these in performance/ and run again:\n")
        for e in errors:
            print("  -", e)
        return 1

    version = methodology_version()
    commit = git_commit()
    months = compute_months(trades, marks, prices, as_of)
    daily = compute_daily(trades, months, marks, prices, as_of)
    complete = [mo for mo in months if mo.complete]
    stats = trade_stats(trades)
    verdicts = thesis_verdicts(rows, trades)

    # Frozen periods: write once, never again.
    frozen_labels = {}
    for mo in complete:
        path = os.path.join(PERF, "months", f"{mo.key}.json")
        if os.path.exists(path) and not args.allow_refreeze:
            frozen_labels[mo.key] = json.load(open(path, encoding="utf-8"))["label"]
            continue
        late = (today - mo.end).days > BACKFILL_AFTER_DAYS
        label = f"{'Backfilled' if late else 'Frozen'} on {today.isoformat()}"
        frozen_labels[mo.key] = label
        write_if_changed(path, json.dumps(month_json(mo, version, commit, today, label), indent=2) + "\n")
    quarters = {}
    for mo in complete:
        quarters.setdefault((mo.y, (mo.m - 1) // 3 + 1), []).append(mo)
    for (y, q), ms in quarters.items():
        if month_end(y, q * 3) > as_of:
            continue
        path = os.path.join(PERF, "quarters", f"{y}-Q{q}.md")
        if os.path.exists(path) and not args.allow_refreeze:
            continue
        late = (today - month_end(y, q * 3)).days > BACKFILL_AFTER_DAYS
        label = f"{'Backfilled' if late else 'Frozen'} on {today.isoformat()}"
        write_if_changed(path, build_period_md(f"{y}-Q{q}", ms, months, trades, version, commit,
                                               label, f"marked {fmt_date(ms[-1].end)} close"))
    years = {}
    for mo in complete:
        years.setdefault(mo.y, []).append(mo)
    for y, ms in years.items():
        if date(y, 12, 31) > as_of:
            continue
        path = os.path.join(PERF, "years", f"{y}.md")
        if os.path.exists(path) and not args.allow_refreeze:
            continue
        late = (today - date(y, 12, 31)).days > BACKFILL_AFTER_DAYS
        label = f"{'Backfilled' if late else 'Frozen'} on {today.isoformat()}"
        write_if_changed(path, build_period_md(str(y), ms, months, trades, version, commit, label,
                                               f"marked {fmt_date(date(y, 12, 31))} close"))

    # Live figures.
    me_points = [(INCEPTION, 100.0)] + [(mo.end, mo.index) for mo in complete]
    _, (mdd_m, pk_m, tr_m) = drawdown_series(me_points)
    _, (mdd_d, pk_d, tr_d) = drawdown_series(daily)
    live_index = months[-1].index
    peak_all = max([v for _, v in me_points] + [v for _, v in daily])
    ytd = 0.0
    for mo in months:
        if mo.y == as_of.year:
            ytd += mo.ret
    since = live_index - 100
    judged = [th for th, (v, _) in verdicts.items() if v in ("Confirmed", "Killed")]
    conf = [th for th in judged if verdicts[th][0] == "Confirmed"]
    other = len(verdicts) - len(judged)
    hit_text = ("—" if not judged else f"{len(conf) / len(judged) * 100:.0f}% ({len(conf)} of "
                f"{len(judged)} judged; {other} untested/open)")
    span = lambda p, t, fmt: "—" if t is None else f"{fmt(p)} → {fmt(t)}"
    metrics = {
        "index": live_index, "since_inception": since, "ytd": ytd,
        "mdd_m": mdd_m, "mdd_m_span": span(pk_m, tr_m, lambda d: d.strftime("%b %Y")),
        "mdd_d": mdd_d, "mdd_d_span": span(pk_d, tr_d, lambda d: _dm(d)),
        "current_dd": live_index - peak_all,
        "n_open": sum(1 for t in trades.values() if not t.closed),
        "n_months": len(complete),
        "best": max((mo.ret for mo in complete), default=None),
        "worst": min((mo.ret for mo in complete), default=None),
        "pos_months": sum(1 for mo in complete if mo.ret > 0),
        "under_water": longest_under_water([v for _, v in me_points]),
        "ret_mdd": "—" if not mdd_m else f"{since / abs(mdd_m):.1f}",
        "annualised": annualised_stats([mo.ret for mo in complete]),
        "compounded": compounded_equivalent([mo.ret for mo in months]),
    }
    ctx = dict(metrics=metrics, stats=stats, months=months, trades=trades, verdicts=verdicts,
               names=names, version=version, commit=commit, as_of=as_of, prices=prices,
               frozen_labels=frozen_labels, hit={"text": hit_text})

    draw_charts(os.path.join(PERF, "charts"), months, daily, trades, stats)
    write_if_changed("PERFORMANCE.md", build_performance_md(ctx))
    update_readme(ctx)
    proofs = proof_index([r["file"] for r in rows if r.get("file")])
    for th in verdicts:
        write_if_changed(os.path.join(PERF, "theses", f"{th}.md"),
                         build_thesis_md(th, names.get(th, ""), verdicts[th], trades, rows,
                                         version, commit, as_of, prices, proofs))
    vlines = ["# Validation report", "",
              f"Generated from commit `{commit}` with methodology v{version}. All checks passed; "
              "the build stops instead of publishing if any check fails.", "",
              "Checks run: required fields, event order, file and line references, R and % "
              "arithmetic, every fill inside that day's range, no stop traded before its exit, "
              "a month-end mark for every open position, marks equal to the daily closes.", "",
              "## Warnings (do not stop the build)", ""]
    vlines += [f"- {w}" for w in warnings] or ["None."]
    write_if_changed(os.path.join(PERF, "VALIDATION.md"), "\n".join(vlines) + "\n")

    print(f"Built PERFORMANCE.md to {as_of}: index {live_index:.2f}, "
          f"month-end MDD {mdd_m:.2f}%, daily MDD {mdd_d:.2f}%")
    for w in warnings:
        print("  warning:", w)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BuildError as e:
        sys.exit(f"Build stopped: {e}")
