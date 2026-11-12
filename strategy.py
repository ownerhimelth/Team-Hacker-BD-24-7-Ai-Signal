from collections import Counter

def classify_number(number):
    # Common Wingo convention: 0-4 = Small, 5-9 = Big.
    return "Big" if int(number) >= 5 else "Small"

def make_prediction(history):
    """
    Transparent baseline heuristic over the latest 50 results:
    1) Count Big/Small outcomes.
    2) Predict the more frequent side (tie -> side of the newest result).
    3) Pick the two most frequent numbers belonging to that side (tie -> smaller number).
    This is descriptive pattern analysis, NOT a reliable edge or guaranteed prediction.
    """
    rows=history[:50]
    if len(rows)<50:
        raise ValueError("At least 50 API records are required.")
    numbers=[int(row["number"]) for row in rows]
    sides=[classify_number(n) for n in numbers]
    side_counts=Counter(sides)
    if side_counts["Big"]==side_counts["Small"]:
        chosen_side=classify_number(numbers[0])
    else:
        chosen_side=side_counts.most_common(1)[0][0]
    eligible=[n for n in numbers if classify_number(n)==chosen_side]
    counts=Counter(eligible)
    candidates=range(5,10) if chosen_side=="Big" else range(0,5)
    ranked=sorted(candidates,key=lambda n:(-counts[n],n))
    return {"side":chosen_side,"numbers":ranked[:2],"counts":dict(counts)}
