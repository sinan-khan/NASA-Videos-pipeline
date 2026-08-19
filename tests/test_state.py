import json
from pathlib import Path

from scripts.state import load_state, mark_used, recent_ids


def test_state_round_trip(tmp_path: Path):
    path = tmp_path / "state.json"
    assert load_state(str(path))["used_topic_ids"] == []
    mark_used(str(path), "topic-1", "A Space Story")
    mark_used(str(path), "topic-2", "Another Space Story")
    data = json.loads(path.read_text())
    assert data["used_topic_ids"] == ["topic-1", "topic-2"]
    assert recent_ids(str(path)) == ["topic-2", "topic-1"]


def test_state_recovers_from_invalid_json(tmp_path: Path):
    path = tmp_path / "state.json"
    path.write_text("not json")
    assert load_state(str(path))["history"] == []
