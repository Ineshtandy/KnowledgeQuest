from collections import Counter


def update_history(history: list[str], new_tag: str | None) -> list[str]:
    updated = list(history)
    if new_tag:
        updated.append(new_tag)
    return updated


def most_common_misconceptions(history: list[str], limit: int = 3) -> list[str]:
    if not history:
        return []
    counts = Counter(history)
    return [tag for tag, _ in counts.most_common(limit)]
