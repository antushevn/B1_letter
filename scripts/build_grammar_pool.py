"""Offline builder for the extended grammar-exercise pool.

The hand-written curriculum (data/grammar_curriculum.json) stays the verified
core; this script batch-generates extra exercises per topic on cheap Haiku
(Batch API = 50% cheaper) into data/grammar_pool.json. The app then samples a
random mix of core + pool exercises per drill session, so answers can't simply
be memorised.

Every generated exercise is structurally validated here; the pool file is then
reviewed by hand before committing (generated content can contain errors).

Usage:
    python scripts/build_grammar_pool.py              # 24 exercises per topic
    python scripts/build_grammar_pool.py --count 40
"""

import argparse
import json
import sys
import time
from pathlib import Path

from anthropic import Anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.common.llm import TOPIC_MODEL  # noqa: E402  (cheap model, same tier)

CURRICULUM_PATH = Path(__file__).resolve().parent.parent / "data" / "grammar_curriculum.json"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "grammar_pool.json"
POLL_SECONDS = 15

SYSTEM = """\
You write practice exercises for the German B1 exam grammar topic given by the user.

Rules:
- Every exercise trains EXACTLY the given topic, at B1 level, everyday vocabulary.
- Two types:
  "mc": a sentence with a blank ___ or a "choose the correct sentence" task, exactly 3 options,
        exactly one correct; "answer" is the 0-based index of the correct option.
  "gap": a sentence with ___ and a hint in parentheses; "accepted" lists every correct fill
         (usually one word; include capitalised variant if the gap starts the sentence).
- The German must be flawless — check every sentence twice. No ambiguous tasks: exactly one
  answer may be correct.
- Do not repeat or trivially rephrase the existing exercises listed by the user.
- "explanation": ONE short sentence per language (ru, de, en) naming the rule that applies.
- Mix roughly half mc, half gap. Vary the vocabulary themes (Arbeit, Familie, Einkaufen,
  Gesundheit, Wohnen, Reisen, Amt).

Return ONLY a raw JSON array of exercise objects, no markdown fences, in this exact shape:
[{"type":"mc","prompt":"…","options":["…","…","…"],"answer":0,
  "explanation":{"ru":"…","de":"…","en":"…"}},
 {"type":"gap","prompt":"… ___ … (Hinweis)","accepted":["…"],
  "explanation":{"ru":"…","de":"…","en":"…"}}]\
"""

USER_TEMPLATE = """\
Topic: {title}

The rule being trained:
{rule}

Existing exercises (do NOT duplicate these):
{existing}

Generate {count} new exercises as a raw JSON array.\
"""


def validate(ex: dict) -> bool:
    if ex.get("type") == "mc":
        return (
            isinstance(ex.get("options"), list) and len(ex["options"]) == 3
            and len(set(ex["options"])) == 3
            and isinstance(ex.get("answer"), int) and 0 <= ex["answer"] < 3
            and isinstance(ex.get("prompt"), str) and ex["prompt"].strip()
            and set(ex.get("explanation", {})) == {"ru", "de", "en"}
        )
    if ex.get("type") == "gap":
        return (
            isinstance(ex.get("prompt"), str) and "___" in ex["prompt"]
            and isinstance(ex.get("accepted"), list) and ex["accepted"]
            and all(isinstance(a, str) and a.strip() for a in ex["accepted"])
            and set(ex.get("explanation", {})) == {"ru", "de", "en"}
        )
    return False


def build(count: int) -> None:
    load_dotenv()
    client = Anthropic()
    topics = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))["topics"]

    requests = []
    for topic in topics:
        existing = "\n".join(f"- {ex['prompt']}" for ex in topic["exercises"])
        requests.append(Request(
            custom_id=topic["id"],
            params=MessageCreateParamsNonStreaming(
                model=TOPIC_MODEL,
                max_tokens=8000,
                system=SYSTEM,
                messages=[{
                    "role": "user",
                    "content": USER_TEMPLATE.format(
                        title=topic["title"],
                        rule=topic["rule"]["de"],
                        existing=existing,
                        count=count,
                    ),
                }],
            ),
        ))

    batch = client.messages.batches.create(requests=requests)
    print(f"Created batch {batch.id} for {len(requests)} topics. Waiting …")

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print(f"  status={batch.processing_status} "
              f"processing={batch.request_counts.processing}")
        time.sleep(POLL_SECONDS)

    pool: dict[str, list] = {}
    for result in client.messages.batches.results(batch.id):
        if result.result.type != "succeeded":
            print(f"  {result.custom_id}: {result.result.type}", file=sys.stderr)
            continue
        text = next(
            (b.text for b in result.result.message.content if b.type == "text"), ""
        ).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        try:
            exercises = json.loads(text)
        except ValueError as e:
            print(f"  {result.custom_id}: bad JSON ({e})", file=sys.stderr)
            continue
        valid = [ex for ex in exercises if validate(ex)]
        pool[result.custom_id] = valid
        print(f"  {result.custom_id}: {len(valid)}/{len(exercises)} valid")

    OUTPUT_PATH.write_text(
        json.dumps(pool, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    total = sum(len(v) for v in pool.values())
    print(f"Wrote {total} exercises to {OUTPUT_PATH} — review before committing!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the grammar exercise pool.")
    parser.add_argument("--count", type=int, default=24, help="exercises per topic")
    args = parser.parse_args()
    build(args.count)
