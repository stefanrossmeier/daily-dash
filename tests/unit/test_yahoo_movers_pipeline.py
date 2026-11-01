from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from daily_dash.config import (
    YahooMoversProfile,
    YahooMoversSourceSet,
    load_yahoo_movers_profile,
    load_yahoo_movers_source_set,
)
from daily_dash.contracts import (
    MoversSnapshotDocument,
    RawMoverCategory,
    RawMoverEntry,
    RawMoverSnapshot,
)
from daily_dash.pipelines.yahoo_movers import run_yahoo_movers_pipeline
from daily_dash.presentation.yahoo_movers import render_movers_report
from daily_dash.processing.yahoo_movers import process_movers_snapshot
from daily_dash.retrieval.yahoo_movers import OfficialYahooMoversRetriever
from daily_dash.storage import JsonFileYahooMoversSnapshotStore

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPOSITORY_ROOT / "config"

NOW = datetime(2026, 10, 30, 16, 45, tzinfo=UTC)


def _quote(symbol: str, price: float, change: float, name: str | None = None) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "shortName": name or f"{symbol} Inc.",
        "regularMarketPrice": price,
        "regularMarketChangePercent": change,
        "regularMarketVolume": 1_000_000,
    }


def _screen_payload() -> dict[str, Any]:
    return {
        "quotes": [
            _quote("AAA", 10.555, 22.217),
            _quote("BBB", 20.0, -5.1),
            _quote("CCC", 30.0, 1.25),
            {"symbol": "DDD"},  # missing fields -> dropped
            _quote("EEE", 40.0, 3.0),
            _quote("FFF", 50.0, -2.0),
            _quote("GGG", 60.0, 0.5),
        ]
    }


@pytest.fixture
def source_set() -> YahooMoversSourceSet:
    return load_yahoo_movers_source_set(CONFIG_DIR / "sources" / "yahoo-movers.yaml")


@pytest.fixture
def profile() -> YahooMoversProfile:
    return load_yahoo_movers_profile(CONFIG_DIR / "profiles" / "yahoo-movers.yaml")


def test_retriever_parses_and_trims_entries(source_set: YahooMoversSourceSet) -> None:
    retriever = OfficialYahooMoversRetriever(screen=lambda screener, count: _screen_payload())

    raw = retriever.retrieve(source_set, run_id="run-1", retrieved_at=NOW)

    assert raw.run_id == "run-1"
    assert [category.category_id for category in raw.categories] == [
        "most-active",
        "top-gainers",
        "top-losers",
    ]
    first = raw.categories[0]
    assert first.error is None
    # count = top_n + 5 requested; the malformed quote is dropped, not counted
    assert [entry.symbol for entry in first.movers] == ["AAA", "BBB", "CCC", "EEE", "FFF", "GGG"]
    assert first.movers[0].price == 10.555
    assert first.movers[0].volume == 1_000_000


def test_retriever_records_category_error(source_set: YahooMoversSourceSet) -> None:
    def failing_screen(screener: str, count: int) -> dict[str, Any]:
        raise RuntimeError("yahoo unavailable")

    retriever = OfficialYahooMoversRetriever(screen=failing_screen)

    raw = retriever.retrieve(source_set, run_id="run-2", retrieved_at=NOW)

    assert all(category.error is not None for category in raw.categories)
    assert "RuntimeError: yahoo unavailable" in raw.categories[0].error


def test_processing_limits_sections_to_top_n(
    source_set: YahooMoversSourceSet,
    profile: YahooMoversProfile,
) -> None:
    raw = RawMoverSnapshot(
        run_id="run-3",
        source_set=source_set.source_set_id,
        retrieved_at=NOW,
        categories=[
            RawMoverCategory(
                category_id="most-active",
                name="Most Active",
                screener="most_actives",
                movers=[
                    RawMoverEntry(
                        symbol=f"S{i}",
                        name=f"S{i} Inc.",
                        price=1.005 * i,
                        change_pct=2.004 * i,
                    )
                    for i in range(1, 8)
                ],
            ),
            RawMoverCategory(
                category_id="top-gainers",
                name="Top Gainers",
                screener="day_gainers",
                error="RuntimeError: boom",
            ),
            RawMoverCategory(
                category_id="top-losers",
                name="Top Losers",
                screener="day_losers",
                movers=[
                    RawMoverEntry(symbol="L1", name="L1 Inc.", price=5.0, change_pct=-1.0),
                ],
            ),
        ],
    )

    report = process_movers_snapshot(raw, source_set, profile)

    assert [section.category_id for section in report.sections] == ["most-active", "top-losers"]
    active = report.sections[0]
    assert len(active.movers) == source_set.top_n
    assert active.movers[0].price == 1.0
    assert active.movers[0].change_pct == 2.0
    assert len(report.issues) == 2
    assert "Top Gainers: RuntimeError: boom" in report.issues
    assert "only 1 movers available" in " ".join(report.issues)


def test_pipeline_fails_when_all_categories_unavailable(
    source_set: YahooMoversSourceSet,
    profile: YahooMoversProfile,
) -> None:
    def failing_screen(screener: str, count: int) -> dict[str, Any]:
        raise RuntimeError("yahoo unavailable")

    retriever = OfficialYahooMoversRetriever(screen=failing_screen)

    with pytest.raises(RuntimeError, match="all Yahoo Movers categories are unavailable"):
        run_yahoo_movers_pipeline(
            profile,
            source_set,
            retriever,
            snapshot_store=JsonFileYahooMoversSnapshotStore(Path("/tmp/does-not-matter")),
        )


def test_pipeline_persists_snapshot(
    tmp_path: Path,
    source_set: YahooMoversSourceSet,
    profile: YahooMoversProfile,
) -> None:
    retriever = OfficialYahooMoversRetriever(screen=lambda screener, count: _screen_payload())

    document, output_path = run_yahoo_movers_pipeline(
        profile,
        source_set,
        retriever,
        snapshot_store=JsonFileYahooMoversSnapshotStore(tmp_path),
        run_id="run-4",
        now=NOW,
    )

    assert output_path.exists()
    assert output_path.parent == tmp_path / "yahoo-movers" / "snapshots"
    assert output_path.name.startswith("20261030T164500Z_run-4")

    reread = MoversSnapshotDocument.model_validate_json(output_path.read_text(encoding="utf-8"))
    assert reread == document


def test_presentation_renders_three_sections(
    source_set: YahooMoversSourceSet,
    profile: YahooMoversProfile,
) -> None:
    raw = RawMoverSnapshot(
        run_id="run-5",
        source_set="yahoo-movers",
        retrieved_at=NOW,
        categories=[
            RawMoverCategory(
                category_id="most-active",
                name="Most Active",
                screener="most_actives",
                movers=[
                    RawMoverEntry(symbol="NVDA", name="NVIDIA", price=101.56, change_pct=-1.32),
                ],
            ),
            RawMoverCategory(
                category_id="top-gainers",
                name="Top Gainers",
                screener="day_gainers",
                movers=[
                    RawMoverEntry(symbol="XYZ", name="XYZ Corp", price=60.27, change_pct=22.22),
                ],
            ),
            RawMoverCategory(
                category_id="top-losers",
                name="Top Losers",
                screener="day_losers",
                movers=[
                    RawMoverEntry(symbol="QRS", name="QRS Corp", price=92.20, change_pct=-0.51),
                ],
            ),
        ],
    )
    report = process_movers_snapshot(raw, source_set, profile)

    artifact = render_movers_report(report, profile)

    content = artifact.content
    assert "*Yahoo Movers*" in content
    assert "*Most Active*" in content
    assert "*Top Gainers*" in content
    assert "*Top Losers*" in content
    nvda_line = next(line for line in content.splitlines() if "NVDA" in line)
    assert nvda_line.startswith(" 1.")
    assert "101.56" in nvda_line
    assert "-1.32%" in nvda_line
    assert nvda_line.endswith("NVIDIA")
    assert "2026-10-30" in content
    assert artifact.metadata["section_count"] == 3
    assert artifact.metadata["mover_count"] == 3
    # Short categories (1 of top_n=5) surface as expected shortness warnings.
    assert "⚠️ Data issues" in content


def test_presentation_lists_issues(
    source_set: YahooMoversSourceSet,
    profile: YahooMoversProfile,
) -> None:
    raw = RawMoverSnapshot(
        run_id="run-6",
        source_set="yahoo-movers",
        retrieved_at=NOW,
        categories=[
            RawMoverCategory(
                category_id="most-active",
                name="Most Active",
                screener="most_actives",
                movers=[
                    RawMoverEntry(symbol="NVDA", name="NVIDIA", price=101.56, change_pct=-1.32),
                ],
            ),
            RawMoverCategory(
                category_id="top-gainers",
                name="Top Gainers",
                screener="day_gainers",
                error="RuntimeError: boom",
            ),
        ],
    )
    report = process_movers_snapshot(raw, source_set, profile)

    artifact = render_movers_report(report, profile)

    assert "⚠️ Data issues" in artifact.content
    assert "Top Gainers: RuntimeError: boom" in artifact.content
