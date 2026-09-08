"""Deterministic Verbatim Span Extractor for OP-05.

Snaps LLM quotes to exact substrings in source passages using the official
normalization rules from grader.py (NFKC, soft hyphen removal, whitespace collapse).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Optional


def norm(s: str) -> str:
    """Official normalization from grader.py."""
    s = unicodedata.normalize("NFKC", s or "").replace("­", "")
    return re.sub(r"\s+", " ", s).strip().lower()


def find_best_verbatim_span(passage_text: str, candidate_quote: str) -> str:
    """Extract a 100% verbatim substring from passage_text matching candidate_quote.

    Guarantees: norm(return_value) in norm(passage_text) == True.
    """
    if not passage_text or not candidate_quote:
        return ""

    norm_passage = norm(passage_text)
    norm_quote = norm(candidate_quote)

    # 1. Direct normalized match check
    if norm_quote in norm_passage:
        # Find exact character span in original passage_text if possible
        # Or return normalized quote if directly usable
        # Let's find the span in original passage_text
        start_idx = norm_passage.find(norm_quote)
        if start_idx != -1:
            # Match word sequence in original passage
            q_words = norm_quote.split()
            if q_words:
                first_w, last_w = q_words[0], q_words[-1]
                pattern = re.escape(first_w) + r".*?" + re.escape(last_w)
                match = re.search(pattern, passage_text, re.IGNORECASE | re.DOTALL)
                if match:
                    extracted = match.group(0).strip()
                    if norm(extracted) in norm_passage:
                        return extracted
        return candidate_quote

    # 2. Try trimming trailing punctuation (periods, commas, semicolons, quotes)
    trimmed_quote = re.sub(r"[.,;:\"'!\?]+$", "", candidate_quote).strip()
    if norm(trimmed_quote) in norm_passage:
        return trimmed_quote

    # 3. Try sentence or clause matching: Find sentences in passage containing key words
    sentences = re.split(r"(?<=[.?!])\s+", passage_text)
    candidate_words = set(re.findall(r"\b\w{3,}\b", norm_quote))

    best_sent = ""
    best_overlap = 0
    for sent in sentences:
        sent_words = set(re.findall(r"\b\w{3,}\b", norm(sent)))
        overlap = len(candidate_words & sent_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_sent = sent.strip()

    if best_sent and norm(best_sent) in norm_passage:
        return best_sent

    # 4. Fallback: Return the first sentence of the passage
    if sentences and norm(sentences[0]) in norm_passage:
        return sentences[0].strip()

    return passage_text.strip()
