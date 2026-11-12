from collections import Counter

def classify_number(number):
    # Common Wingo convention: 0-4 = Small; 5-9 = Big.
    return "Big" if int(number) >= 5 else "Small"

def make_prediction(history):
    """
    Analyse up to the latest 50 available API results.
    Works with 1..50 records; it does not require 50 records.
    This frequency heuristic is descriptive, not a guaranteed prediction.
    """
    rows = history[:50]
    if not rows:
        raise ValueError("API returned no history records.")

    numbers = []
    for row in rows:
        try:
            n = int(row["number"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Invalid API history row: {row!r}") from exc
        if not 0 <= n <= 9:
            raise ValueError(f"API number out of range: {n}")
        numbers.append(n)

    sides = [classify_number(n) for n in numbers]
    side_counts = Counter(sides)
    if side_counts["Big"] == side_counts["Small"]:
        chosen_side = classify_number(numbers[0])
    else:
        chosen_side = side_counts.most_common(1)[0][0]

    eligible = [n for n in numbers if classify_number(n) == chosen_side]
    counts = Counter(eligible)
    candidates = range(5, 10) if chosen_side == "Big" else range(0, 5)
    ranked = sorted(candidates, key=lambda n: (-counts[n], n))
    return {"side": chosen_side, "numbers": ranked[:2], "counts": dict(counts), "records_used": len(numbers)}
