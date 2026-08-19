from scripts.write_script import _normalize_script


def test_normalize_script_drops_empty_segments():
    topic = {"title": "Black Holes", "keywords": "black hole"}
    result = _normalize_script(
        {"title": "Black Holes", "description": "desc", "tags": ["Space"], "segments": [
            {"text": "", "visual_hint": ""},
            {"text": "Black holes bend spacetime.", "visual_hint": "black hole"},
            {"text": "", "visual_hint": ""},
            {"text": "They can be observed indirectly.", "visual_hint": "galaxy"},
            {"text": "Follow for more.", "visual_hint": "stars"},
        ]}, topic)
    assert len(result["segments"]) == 3
    assert result["tags"] == ["space"]
    assert result["source"] == "llm"
