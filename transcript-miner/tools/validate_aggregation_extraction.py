import json
from pathlib import Path


def validate_extraction(summary_path):
    print(f"Testing extraction on: {summary_path}")
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    channel_id = data.get("channel_id", "unknown")
    print(f"Extracted channel_id: {channel_id}")

    items = data.get("knowledge_items", [])
    print(f"Number of knowledge_items found: {len(items)}")

    mentions_count = 0
    for item in items:
        entities = item.get("entities", [])
        for entity in entities:
            symbol = entity if isinstance(entity, str) else entity.get("symbol")
            if symbol:
                mentions_count += 1

    print(f"Number of mentions found: {mentions_count}")

    # Check for actual keys in the file
    print(f"Keys present in JSON: {list(data.keys())}")
    if "source" in data:
        print(f"Source channel_namespace: {data['source'].get('channel_namespace')}")
    if "stocks_covered" in data:
        print(f"Number of stocks_covered: {len(data['stocks_covered'])}")


if __name__ == "__main__":
    sample = Path("output/stocks/2_summaries/_T1WmN_mZzw.json")
    if sample.exists():
        validate_extraction(sample)
    else:
        print(f"File not found: {sample}")
