"""Offline builder for the German B1 task pool.

Topics need no user input, so we pre-generate a batch of them via the Anthropic
Batch API (50% cheaper than live calls) and store the results in data/topics.json.
The app then serves topics instantly from that file, keeping the interactive flow
free of live topic-generation calls.

Usage:
    python scripts/build_topic_pool.py            # generate 50 topics
    python scripts/build_topic_pool.py --count 80 # generate 80

Requires ANTHROPIC_API_KEY (loaded from .env).
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

# Import the same prompts and cheap model the live fallback uses.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.nodes import TOPIC_MODEL  # noqa: E402
from src.prompts import TOPIC_SYSTEM, TOPIC_USER  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "topics.json"
POLL_SECONDS = 15


def build(count: int) -> None:
    load_dotenv()
    client = Anthropic()

    requests = [
        Request(
            custom_id=f"topic-{i}",
            params=MessageCreateParamsNonStreaming(
                model=TOPIC_MODEL,
                max_tokens=512,
                system=TOPIC_SYSTEM,
                messages=[{"role": "user", "content": TOPIC_USER}],
            ),
        )
        for i in range(count)
    ]

    batch = client.messages.batches.create(requests=requests)
    print(f"Created batch {batch.id} with {count} requests. Waiting …")

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print(f"  status={batch.processing_status} "
              f"processing={batch.request_counts.processing}")
        time.sleep(POLL_SECONDS)

    topics: list[str] = []
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            text = next(
                (b.text for b in result.result.message.content if b.type == "text"),
                "",
            ).strip()
            if text:
                topics.append(text)
        else:
            print(f"  {result.custom_id}: {result.result.type}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(topics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(topics)} topics to {OUTPUT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the German B1 task pool.")
    parser.add_argument("--count", type=int, default=50, help="number of topics to generate")
    args = parser.parse_args()
    build(args.count)


if __name__ == "__main__":
    main()
