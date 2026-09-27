"""Distribution distance and a paired consistency check.

The sigmoid here is a display of separation, not a probability that an
endpoint is a named model.
"""
from __future__ import annotations

import math
from collections import Counter


def normalize(text: str) -> str:
    return " ".join(text.strip().casefold().split())


def counts(answers: list[str]) -> Counter:
    return Counter(normalize(item) for item in answers if normalize(item))


def smoothed(counter: Counter, alphabet: list[str], prior: float = 0.5) -> dict[str, float]:
    total = sum(counter.get(symbol, 0) for symbol in alphabet) + prior * len(alphabet)
    return {symbol: (counter.get(symbol, 0) + prior) / total for symbol in alphabet}


def js_divergence(left: Counter, right: Counter, prior: float = 0.5) -> float:
    alphabet = sorted(set(left) | set(right))
    if not alphabet:
        return 0.0
    p = smoothed(left, alphabet, prior)
    q = smoothed(right, alphabet, prior)
    acc = 0.0
    for symbol in alphabet:
        mid = (p[symbol] + q[symbol]) / 2
        acc += 0.5 * p[symbol] * math.log2(p[symbol] / mid)
        acc += 0.5 * q[symbol] * math.log2(q[symbol] / mid)
    return acc


def mode_share(counter: Counter) -> float:
    total = sum(counter.values())
    if not total:
        return 0.0
    return counter.most_common(1)[0][1] / total


def separation(reference: Counter, sample: Counter) -> float:
    """Map JS divergence in [0, 1] through a logistic for display only."""
    distance = js_divergence(reference, sample)
    # JS is at most 1 bit for two distributions. Values above that are
    # numerical noise from the smoothing prior on tiny samples.
    clipped = min(max(distance, 0.0), 1.0)
    return 1 / (1 + math.exp(-6 * (clipped - 0.35)))


def mcnemar(both_ok: int, only_left: int, only_right: int) -> dict:
    """Exact two-sided McNemar on discordant pairs. No SciPy."""
    discordant = only_left + only_right
    if discordant == 0:
        return {"n": both_ok, "discordant": 0, "p": 1.0, "only_left": 0, "only_right": 0}
    # P(X <= k) under Binomial(n, 0.5), two-sided via twice the smaller tail.
    k = min(only_left, only_right)
    tail = sum(_binom_pmf(discordant, i) for i in range(k + 1))
    p = min(1.0, 2 * tail)
    return {
        "compared": both_ok + discordant,
        "discordant": discordant,
        "only_left": only_left,
        "only_right": only_right,
        "p_two_sided": p,
    }


def _binom_pmf(n: int, k: int) -> float:
    return math.comb(n, k) / (2 ** n)
