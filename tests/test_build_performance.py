"""Tests for scripts/build_performance.py. Run from the repository root:

    py -m pytest tests

Synthetic data only, so the tests keep passing as the real record grows.
"""
import csv
import json
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_performance as bp  # noqa: E402


# ---- 32nds ------------------------------------------------------------------

@pytest.mark.parametrize("text, value", [
    ("110'06'0", 110 + 6 / 32),
    ("110'06", 110 + 6 / 32),
    ("108'15'5", 108 + 15.5 / 32),      # half tick, as TradingView shows ZN
    ("108'15'2", 108 + 15.25 / 32),     # quarter tick
    ("108'15'7", 108 + 15.75 / 32),
    ("107'07'0", 107.21875),
    ("7593.71", 7593.71),
])
def test_parse_price(text, value):
    assert bp.parse_price(text) == pytest.approx(value)


@pytest.mark.parametrize("bad", ["110'32'0", "110'06'4", "abc", "", "110'x'0"])
def test_parse_price_rejects(bad):
    with pytest.raises(ValueError):
        bp.parse_price(bad)


def test_price_round_trip():
    for text in ("110'06'0", "108'15'5", "109'00'0", "107'07'0"):
        assert bp.fmt_price(bp.parse_price(text), bond=True) == text


# ---- open R sign --------------------------------------------------------------

def make_trade(direction, entry, stop, risk=2.0, opened=date(2026, 7, 22), **kw):
    return bp.Trade("T9", "TH9", "X", "X", direction, entry, stop, risk, None, opened,
                    {"event_id": "E9"}, False, **kw)


def test_open_r_short_and_long():
    short = make_trade(-1, 100.0, 102.0)
    assert short.open_r(98.0) == pytest.approx(1.0)        # price fell: short gains
    assert short.open_r(102.0) == pytest.approx(-1.0)      # stopped: -1R
    long_ = make_trade(1, 100.0, 98.0)
    assert long_.open_r(104.0) == pytest.approx(2.0)
    assert long_.open_pct(98.0) == pytest.approx(-2.0)     # -1R x 2% risk


def test_real_trade_arithmetic():
    zb = make_trade(-1, bp.parse_price("110'06'0"), bp.parse_price("110'26'0"), risk=2.02)
    assert zb.open_r(bp.parse_price("107'07'0")) == pytest.approx(4.75)
    assert zb.open_pct(bp.parse_price("107'07'0")) == pytest.approx(9.595)


# ---- months, compounding, quarter splits -------------------------------------

def two_month_trade():
    """Short opened 22 Jul at 100, stop 101 (1R = 2%), marked 99 at July-end, closed 98 in Aug."""
    t = make_trade(-1, 100.0, 101.0, risk=2.0, opened=date(2026, 7, 22))
    t.exit_date, t.exit_price, t.result_r, t.result_pct = date(2026, 8, 10), 98.0, 2.0, 4.0
    t.exit_row = {"event_id": "E10", "ts_utc": "2026-08-10"}
    return t


def test_month_split_sums_to_full_result():
    t = two_month_trade()
    marks = {(date(2026, 7, 31), "T9"): 99.0}
    months = bp.compute_months({"T9": t}, marks, {}, date(2026, 8, 31))
    jul, aug = months
    assert jul.ret == pytest.approx(2.0)          # +1R open at July-end
    assert aug.ret == pytest.approx(2.0)          # remaining +1R realised in August
    assert jul.ret + aug.ret == pytest.approx(t.result_pct)
    assert aug.index == pytest.approx(104.0)              # added, not compounded (methodology §7)


def test_daily_matches_month_end():
    t = two_month_trade()
    marks = {(date(2026, 7, 31), "T9"): 99.0}
    prices = {"X": {date(2026, 7, 22): (100, 100.5, 99.8, 100.0), date(2026, 7, 31): (99, 99, 99, 99.0),
                    date(2026, 8, 5): (100.5, 100.8, 100.2, 100.5), date(2026, 8, 10): (98, 98, 98, 98.0)}}
    months = bp.compute_months({"T9": t}, marks, prices, date(2026, 8, 31))
    daily = dict(bp.compute_daily({"T9": t}, months, marks, prices, date(2026, 8, 31)))
    assert daily[date(2026, 7, 31)] == pytest.approx(months[0].index)
    assert daily[date(2026, 8, 31)] == pytest.approx(months[1].index)
    assert daily[date(2026, 8, 5)] < daily[date(2026, 7, 31)]   # intra-month give-back is visible


# ---- drawdown -----------------------------------------------------------------

def test_drawdown_peak_and_trough():
    pts = [("a", 100), ("b", 110), ("c", 99), ("d", 105), ("e", 120)]
    _, (mdd, peak, trough) = bp.drawdown_series(pts)
    assert mdd == pytest.approx(-11.0)        # points of starting equity, not a ratio
    assert (peak, trough) == ("b", "c")


def test_under_water_recovered_and_ongoing():
    assert bp.longest_under_water([100, 110, 99, 105, 120]) == (2, False)
    assert bp.longest_under_water([100, 110, 99, 105, 108]) == (3, True)
    assert bp.longest_under_water([100, 101, 102]) == (0, False)


# ---- statistics ----------------------------------------------------------------

def closed(tid, r, risk=1.0, opened=date(2026, 8, 1), closed_on=date(2026, 8, 5)):
    t = make_trade(-1, 100.0, 101.0, risk=risk, opened=opened)
    t.trade_id = tid
    t.exit_date, t.result_r, t.result_pct = closed_on, r, r * risk
    t.exit_row = {"event_id": tid, "ts_utc": closed_on.isoformat()}
    return t


def test_profit_factor_with_no_losses():
    s = bp.trade_stats({"A": closed("A", 2.0), "B": closed("B", 0.05)})
    assert s["profit_factor"] is None
    assert s["profit_factor_text"] == "n/a (no losses)"
    assert s["n_scratch"] == 1


def test_stats_on_record_shape():
    ts = {"T1": closed("T1", -1.0, closed_on=date(2026, 8, 5)),
          "T3": closed("T3", -1.0, closed_on=date(2026, 9, 3)),
          "T2": closed("T2", 4.75, closed_on=date(2026, 9, 10)),
          "T4": closed("T4", 3.74, closed_on=date(2026, 9, 11))}
    s = bp.trade_stats(ts)
    assert s["win_rate"] == pytest.approx(50)
    assert s["profit_factor"] == pytest.approx(8.49 / 2)
    assert s["expectancy"] == pytest.approx(6.49 / 4)
    assert s["loss_streak"] == 2
    assert s["best_trade"] == "T2"


def test_annualised_gate():
    assert bp.annualised_stats([1.0] * (bp.MIN_MONTHS_FOR_ANNUALISED - 1)) is None
    out = bp.annualised_stats([1.0] * bp.MIN_MONTHS_FOR_ANNUALISED)
    assert out["annualised_return"] == pytest.approx(12.0)   # simple: mean x 12


# ---- validation ----------------------------------------------------------------

def test_validation_catches_stop_before_exit_and_bad_fill(tmp_path):
    t = make_trade(-1, 100.0, 101.0, opened=date(2026, 8, 3),
                   exit_date=date(2026, 8, 6), exit_price=98.0, result_r=2.0, result_pct=4.0)
    t.open_row = {"event_id": "E1", "ts_utc": "2026-08-03"}
    t.exit_row = {"event_id": "E2", "ts_utc": "2026-08-06"}
    prices = {"X": {date(2026, 8, 3): (100, 100.2, 99.5, 100),
                    date(2026, 8, 4): (100, 101.5, 99.9, 100.2),   # stop traded
                    date(2026, 8, 6): (99, 99.5, 98.5, 99)}}       # 98.0 not in range
    errors, _ = bp.validate([], {"T9": t}, {}, prices, [])
    assert any("stop" in e and "2026-08-04" in e for e in errors)
    assert any("E2" in e and "outside" in e for e in errors)


# ---- frozen files ----------------------------------------------------------------

def test_frozen_files_are_not_regenerated(tmp_path, monkeypatch):
    root = tmp_path
    (root / "trades").mkdir()
    (root / "trades" / "t.md").write_text("line1\nline2\nline3\n")
    (root / "methodology").mkdir()
    (root / "methodology" / "v1.md").write_text("**Version:** 1.1 ·\n")
    perf = root / "performance"
    (perf / "prices").mkdir(parents=True)
    rows = [
        ["event_id", "ts_utc", "ts_source", "trade_id", "thesis_id", "event", "instrument", "contract",
         "direction", "price", "stop", "risk_pct", "notional_pct", "result_r", "result_pct",
         "pct_source", "verdict", "file", "line", "note"],
        ["E1", "2026-07-22", "date", "T1", "TH1", "open", "X", "", "short", "100", "101", "2.00",
         "", "", "", "", "", "trades/t.md", "1", ""],
        ["E2", "2026-08-10", "date", "T1", "TH1", "exit", "X", "", "short", "98", "101", "2.00",
         "", "2.00", "4.00", "stated", "Confirmed", "trades/t.md", "2", ""],
    ]
    with open(perf / "registry.csv", "w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    (perf / "marks.csv").write_text("month_end,trade_id,instrument,mark,price_source,source_url\n"
                                    "2026-07-31,T1,X,99,test,test\n")
    (perf / "prices" / "X.csv").write_text(
        "date,open,high,low,close,source\n2026-07-22,100,100.5,99.8,100,t\n"
        "2026-07-31,99,99.2,98.9,99,t\n2026-08-10,98.5,98.6,97.9,98,t\n")
    monkeypatch.chdir(root)
    assert bp.main(["--today", "2026-09-15"]) == 0
    frozen = perf / "months" / "2026-07.json"
    assert json.loads(frozen.read_text())["label"] == "Backfilled on 2026-09-15"
    frozen.write_text('{"label": "Frozen on 2026-08-01", "sentinel": true}')
    assert bp.main(["--today", "2026-09-16"]) == 0
    assert json.loads(frozen.read_text())["sentinel"] is True          # untouched
    before = (root / "PERFORMANCE.md").read_text()
    assert bp.main(["--today", "2026-09-16"]) == 0
    assert (root / "PERFORMANCE.md").read_text() == before            # idempotent


def test_compounded_side_figure():
    assert bp.compounded_equivalent([10.0, -10.0]) == pytest.approx(-1.0)   # 1.1 x 0.9 - 1
    assert bp.compounded_equivalent([]) == pytest.approx(0.0)


def test_readme_block_only_touches_markers(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(f"# Title\n\nintro\n\n{bp.README_START}\nold\n{bp.README_END}\n\n## Rest\nkept\n")
    ctx = {"metrics": {"since_inception": 10.0, "compounded": 10.5, "mdd_m": -2.0, "mdd_d": -3.0,
                       "n_open": 0},
           "stats": {"win_rate": 50.0, "payoff": None, "n_win": 1, "n_closed": 2},
           "months": [bp.Month(2026, 8, date(2026, 7, 31), date(2026, 8, 31), True, False, ret=4.0)],
           "as_of": date(2026, 8, 31)}
    assert bp.update_readme(ctx, str(readme))
    text = readme.read_text()
    assert "old" not in text and "intro" in text and "kept" in text
    assert "**+10.00%**" in text and "**\u22122.00%**" in text
    assert not bp.update_readme(ctx, str(readme))           # second run: no change


def test_readme_without_markers_is_untouched(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("# Title\nno markers\n")
    assert not bp.update_readme({}, str(readme))
    assert readme.read_text() == "# Title\nno markers\n"


# ---- proof of timing table --------------------------------------------------------

def test_proof_table_rows():
    sha = "a" * 40
    proofs = {"trades/x.md": {"commit": sha, "by": ("2026-09-15T18:56:40Z", sha + ".json", "receipt")},
              "trades/y.md": {"commit": sha, "by": ("2026-08-24T22:03:38Z", None, "GH Archive")},
              "trades/z.md": {"commit": sha, "by": None}}
    L = bp.proof_table(["trades/x.md", "trades/y.md", "trades/z.md"], proofs)
    assert any("15 Sep 2026 18:56" in l and "Bitcoin proof" in l for l in L)
    assert any("24 Aug 2026 22:03" in l and "[GH Archive]" in l for l in L)
    assert any("not covered" in l for l in L)


def test_proof_table_push_log_links_activity_and_bitcoin():
    sha = "b" * 40
    proofs = {"trades/p.md": {"commit": sha, "bitcoin": "c" * 40 + ".json",
                              "by": ("2026-08-05T10:09:18Z", None, "GitHub push log")}}
    L = bp.proof_table(["trades/p.md"], proofs)
    row = [l for l in L if "p.md" in l][0]
    assert "5 Aug 2026 10:09" in row
    assert "/activity?ref=main&sort=asc" in row and "Bitcoin proof" in row
