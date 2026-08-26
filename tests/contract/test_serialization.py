from datetime import UTC, datetime

from daily_dash.contracts import CandidateBatch, SourceItem, SourceKind


def test_candidate_batch_round_trip_json() -> None:
    batch = CandidateBatch(
        run_id="run-123",
        profile="news-top",
        items=[
            SourceItem(
                id="story-1",
                source="example",
                source_kind=SourceKind.RSS,
                title="Example",
                url="https://example.com/story",
                retrieved_at=datetime.now(UTC),
            )
        ],
    )

    serialized = batch.model_dump_json()

    restored = CandidateBatch.model_validate_json(serialized)

    assert restored == batch
