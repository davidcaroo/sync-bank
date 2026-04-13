from collections import Counter


def evaluate_account_choice(
    counter: Counter,
    total: int,
    *,
    min_occurrences: int,
    min_share: float,
):
    if total <= 0 or not counter:
        return None

    top_cuenta, top_count = counter.most_common(1)[0]
    share = top_count / total if total else 0.0

    if total >= min_occurrences and share >= min_share:
        return {
            "cuenta": str(top_cuenta),
            "share": share,
            "total": total,
            "count": top_count,
        }

    return None
