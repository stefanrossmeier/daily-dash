from __future__ import annotations

from daily_dash.config import YahooMoversProfile, YahooMoversSourceSet
from daily_dash.contracts import (
    MoverEntry,
    MoverSection,
    MoversReportData,
    RawMoverCategory,
    RawMoverSnapshot,
)


def _section(
    category: RawMoverCategory,
    *,
    top_n: int,
) -> MoverSection:
    movers = [
        MoverEntry(
            symbol=entry.symbol,
            name=entry.name,
            price=round(entry.price, 2),
            change_pct=round(entry.change_pct, 2),
        )
        for entry in category.movers[:top_n]
    ]
    return MoverSection(
        category_id=category.category_id,
        name=category.name,
        movers=movers,
    )


def process_movers_snapshot(
    raw: RawMoverSnapshot,
    source_set: YahooMoversSourceSet,
    profile: YahooMoversProfile,
) -> MoversReportData:
    """Trim each screener category to the configured top-n and collect issues."""

    top_n = source_set.top_n
    sections: list[MoverSection] = []
    issues: list[str] = []

    for category in raw.categories:
        if category.error is not None:
            issues.append(f"{category.name}: {category.error}")
            continue
        if not category.movers:
            issues.append(f"{category.name}: no screener results")
            continue
        sections.append(_section(category, top_n=top_n))
        if len(category.movers) < top_n:
            issues.append(
                f"{category.name}: only {len(category.movers)} movers available (expected {top_n})"
            )

    return MoversReportData(
        run_id=raw.run_id,
        profile=profile.profile_id,
        generated_at=raw.retrieved_at,
        sections=sections,
        issues=issues,
    )
