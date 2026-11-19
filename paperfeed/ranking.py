from dataclasses import dataclass
from math import exp, log1p

@dataclass(frozen=True)
class Features:
    semantic: float
    topic: float
    age_hours: float
    followed: bool
    engagement: int
    history: float

def score(f: Features) -> float:
    clamp = lambda x: max(0.0, min(1.0, x))
    return (.35 * clamp(f.semantic) + .20 * clamp(f.topic)
            + .15 * exp(-max(0, f.age_hours)/72) + .10 * f.followed
            + .10 * min(1, log1p(max(0, f.engagement))/log1p(100))
            + .10 * clamp(f.history))

def merge_candidates(sources):
    """Preserve source priority while eliminating duplicate post IDs."""
    unique = {}
    for source in sources:
        for post in source:
            unique.setdefault(post['id'], post)
    return list(unique.values())

def diversify(posts):
    remaining = list(posts)
    result = []
    while remaining:
        index = next((i for i,p in enumerate(remaining) if len(result)<2 or
                      not (p['author_id']==result[-1]['author_id']==result[-2]['author_id'])), 0)
        result.append(remaining.pop(index))
    return result
