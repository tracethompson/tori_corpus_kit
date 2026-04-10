"""
Filter comments by trigram.

Reads the searchable comments file, finds all comments containing
the given trigram, and writes them to a new file.

Usage:
    python scripts/filter_by_trigram.py "one's own body"
    python scripts/filter_by_trigram.py "not a drug" --output results.txt
"""
import argparse
import html
import re
from pathlib import Path

COMMENTS_FILE = Path(__file__).parent.parent / "data" / "raw" / "comments_searchable_ALL.txt"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "filtered"
SEPARATOR = "=" * 80


def parse_comments(filepath: Path) -> list[dict]:
    """Parse the searchable comments file into individual comment blocks."""
    text = filepath.read_text(encoding="utf-8")
    blocks = text.split(SEPARATOR)

    comments = []
    i = 0
    while i < len(blocks):
        block = blocks[i].strip()
        if block.startswith("COMMENT ID:"):
            lines = block.splitlines()
            comment_id = lines[0].replace("COMMENT ID:", "").strip()
            date = lines[1].replace("DATE:", "").strip() if len(lines) > 1 else ""

            # The comment body is the next block
            body = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
            comments.append({
                "id": comment_id,
                "date": date,
                "body": body,
            })
            i += 2
        else:
            i += 1

    return comments


def clean_text(text: str) -> str:
    """Strip HTML tags and decode entities for matching."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def main():
    parser = argparse.ArgumentParser(description="Filter comments by trigram")
    parser.add_argument("trigram", help="Trigram to search for (e.g. \"one's own body\")")
    parser.add_argument("--input", type=Path, default=COMMENTS_FILE, help="Input comments file")
    parser.add_argument("--output", type=Path, default=None, help="Output file path")
    args = parser.parse_args()

    trigram = args.trigram.lower()
    comments = parse_comments(args.input)
    print(f"Loaded {len(comments)} comments")

    matches = []
    for comment in comments:
        cleaned = clean_text(comment["body"]).lower()
        if trigram in cleaned:
            matches.append(comment)

    print(f"Found {len(matches)} comments containing \"{args.trigram}\"")

    if not matches:
        return

    # Build output path
    if args.output:
        output_path = args.output
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^\w]+", "_", args.trigram).strip("_")
        output_path = OUTPUT_DIR / f"comments_{safe_name}.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"TRIGRAM FILTER: \"{args.trigram}\"\n")
        f.write(f"MATCHES: {len(matches)} of {len(comments)} comments\n")
        f.write(f"{SEPARATOR}\n\n")

        for comment in matches:
            f.write(f"{SEPARATOR}\n")
            f.write(f"COMMENT ID: {comment['id']}\n")
            f.write(f"DATE: {comment['date']}\n")
            f.write(f"{SEPARATOR}\n\n")
            f.write(f"{clean_text(comment['body'])}\n\n")

    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
