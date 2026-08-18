"""Writes the narration script for a video.

Primary path: call the Groq API (free tier) with a prompt that asks for a
segment-based script as JSON. Each segment has narration text plus a visual
hint used later to find images.

Fallback path: if the API is unavailable, an original narration is assembled
locally from the topic's seed facts using varied templates -- still original,
never a copy of NASA's text, so the channel keeps variety even during outages.
"""

from __future__ import annotations

import json
import random
import re
from typing import Any

from scripts.config import settings

HOOK_STYLES = [
    "Start with a stunning, slightly mysterious sentence.",
    "Start with a surprising fact most people don't know.",
    "Start with a short punchy question that grabs attention.",
]

NARRATION_STYLES = [
    "Storyteller: vivid imagery, a sense of wonder, easy to visualize.",
    "Curious explorer: questions that make the viewer lean in.",
    "Fact-dense: rapid-fire surprising numbers and comparisons.",
    "Calm educator: clear, measured, confident explanations.",
]

CTA_TEMPLATES = [
    "If space amazes you, hit follow — there's a new cosmic story every day.",
    "Follow for your daily dose of the universe.",
    "Like this video if the cosmos blew your mind, and follow for more.",
]

SYSTEM_PROMPT = """You are a scriptwriter for short vertical space-science videos (YouTube Shorts / TikTok).
You write ORIGINAL narration -- never copy NASA's or Wikipedia's text verbatim.
Keep it accurate, conversational, and built for spoken audio.
Rules:
- Output ONLY valid JSON. No markdown fences, no commentary.
- The JSON schema must be exactly:
{{"title": string, "description": string, "tags": string[], "segments": [{{"text": string, "visual_hint": string}}]}}
- title: a catchy YouTube title under 80 characters.
- description: 2-4 sentences for the video description, ending with 3-5 relevant hashtags.
- tags: 8-12 lowercase keyword tags for YouTube discovery.
- segments: 5 to 7 segments total. The first segment is the hook, the last is the call-to-action (follow/like).
- Spoken text totals roughly {target} seconds at a natural talking pace (~150 words per minute), so aim for about 15-30 words per segment and keep every segment under 45 words.
- Each segment's text must stand alone as spoken narration.
- Each segment's visual_hint is a short phrase for finding a NASA image (e.g. "jupiter surface storm")."""


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output")
    return json.loads(text[start : end + 1])


def _normalize_script(data: dict[str, Any], topic: dict[str, Any]) -> dict[str, Any]:
    """Sanitize model output into the shape the rest of the pipeline expects."""
    segments = data.get("segments") or []
    cleaned: list[dict[str, str]] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        cleaned.append(
            {
                "text": text,
                "visual_hint": (seg.get("visual_hint") or topic.get("keywords") or topic["title"]).strip(),
            }
        )
    if len(cleaned) < 3:
        raise ValueError("Model returned too few valid segments")
    return {
        "title": (data.get("title") or topic["title"])[:95],
        "description": (data.get("description") or f"Daily dose of space: {topic['title']}.")[:4800],
        "tags": [str(t).strip().lower()[:40] for t in (data.get("tags") or []) if str(t).strip()][:15],
        "segments": cleaned,
        "source": "llm",
    }


def generate_with_llm(topic: dict[str, Any]) -> dict[str, Any]:
    from groq import Groq

    client = Groq(api_key=settings.groq_api_key)
    style = random.choice(NARRATION_STYLES)
    hook = random.choice(HOOK_STYLES)
    cta = random.choice(CTA_TEMPLATES)

    user_prompt = (
        f"Write a script for a vertical video about: {topic['title']}.\n"
        f"Category: {topic['category']}.\n"
        f"Target duration: about {settings.target_seconds} seconds of spoken audio.\n"
        f"Suggested hook direction: {hook}\n"
        f"Narration style: {style}\n"
        f"Last segment should be a call-to-action like: \"{cta}\"\n"
        f"Visual hints should be simple noun phrases good for a NASA image search."
    )

    response = client.chat.completions.create(
        model=settings.groq_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT.format(target=settings.target_seconds)},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=1600,
    )
    raw = response.choices[0].message.content or ""
    data = _extract_json(raw)
    return _normalize_script(data, topic)


def generate_fallback(topic: dict[str, Any]) -> dict[str, Any]:
    """Original offline narration built from the topic's seed facts."""
    facts = topic.get("facts") or []
    title = topic["title"]
    segments: list[dict[str, str]] = []

    def seg(text: str) -> None:
        segments.append({"text": text, "visual_hint": topic.get("keywords") or title})

    seg(topic["hook"])
    intro = "Here's the story you probably didn't hear in school. It's one of the most fascinating chapters in space exploration, and the details will genuinely change how you see the night sky."
    seg(intro)

    lines = facts or [
        "Scientists are still uncovering new surprises every year.",
        "Every observation teaches us something we never expected.",
        "This corner of the universe holds far more than meets the eye.",
    ]
    random.shuffle(lines)
    prefixes = [
        "Here's the part that surprises most people:",
        "Consider this:",
        "Most people don't know that",
        "Get this:",
        "Here's something wild:",
        "Here's a fact that stops astronomers in their tracks:",
    ]
    random.shuffle(prefixes)
    for i, fact in enumerate(lines[:3]):
        seg(f"{prefixes[i]} {fact}")

    seg(random.choice(CTA_TEMPLATES))

    return {
        "title": title[:95],
        "description": f"Daily dose of space: {title}. New videos twice a day. "
        + " ".join(f"#tag" for _ in range(0))
        + "#space #nasa #astronomy #universe #science",
        "tags": ["space", "nasa", "astronomy", "universe", "science", topic["category"].lower().replace(" ", "")],
        "segments": segments,
        "source": "fallback",
    }


def write_script(topic: dict[str, Any]) -> dict[str, Any]:
    """Best-effort LLM generation with a guaranteed local fallback."""
    if settings.groq_api_key:
        try:
            return generate_with_llm(topic)
        except Exception:
            # Log quietly -- the fallback is intentionally self-healing.
            pass
    return generate_fallback(topic)


def save_script(script: dict[str, Any]) -> None:
    import os

    os.makedirs(settings.output_dir, exist_ok=True)
    with open(settings.script_file, "w", encoding="utf-8") as fh:
        json.dump(script, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys

    sys.path.insert(0, settings.output_dir)
    # Allow standalone use: python scripts/write_script.py <topic.json>
    topic_path = sys.argv[1] if len(sys.argv) > 1 else settings.topic_file
    with open(topic_path, "r", encoding="utf-8") as fh:
        topic = json.load(fh)
    script = write_script(topic)
    save_script(script)
    print(json.dumps(script, ensure_ascii=False, indent=2))
