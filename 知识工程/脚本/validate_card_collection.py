from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from common import load_json, utc_now, write_json
from validate_card import validate_card


def validate_collection(card_paths: list[Path], registry: dict) -> dict:
    cards = [load_json(path) for path in card_paths]
    reports = [validate_card(card, registry) for card in cards]
    errors = [
        f"{path.name}: {error}"
        for path, report in zip(card_paths, reports)
        for error in report["errors"]
    ]

    card_ids = Counter(card.get("card_id") for card in cards)
    for card_id, count in card_ids.items():
        if count > 1:
            errors.append(f"Duplicate card_id: {card_id}")

    concept_keys = Counter(
        (card.get("work_id"), card.get("concept_key"))
        for card in cards
    )
    for (work_id, concept_key), count in concept_keys.items():
        if count > 1:
            errors.append(
                f"Duplicate concept_key in one work; merge edition evidence into one card: "
                f"{work_id}/{concept_key}"
            )

    return {
        "checked_at": utc_now(),
        "status": "pass" if not errors else "fail",
        "card_count": len(cards),
        "errors": errors,
        "card_reports": reports,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--cards", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    card_paths = sorted(args.cards.rglob("*.json"))
    report = validate_collection(card_paths, load_json(args.registry))
    if args.report:
        write_json(args.report, report)
    print(f"Card collection validation: {report['status']} ({report['card_count']} cards)")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
