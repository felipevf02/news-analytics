"""Lightweight, deterministic text statistics for Brazilian Portuguese news."""

import re
import unicodedata
from collections import Counter

ANALYZER_VERSION = "ptbr-terms-v1"

STOPWORDS = {
    "a", "à", "agora", "ainda", "algo", "algum", "alguma", "algumas", "alguns",
    "ao", "aos", "aquela", "aquelas", "aquele", "aqueles", "aquilo", "as",
    "até", "com", "como", "da", "das", "de", "dela", "delas", "dele", "deles",
    "depois", "do", "dos", "e", "ela", "elas", "ele", "eles", "em", "entre",
    "era", "essa", "essas", "esse", "esses", "esta", "está", "estão", "estas",
    "este", "estes", "eu", "foi", "foram", "há", "isso", "isto", "já", "lhe",
    "lhes", "mais", "mas", "me", "mesmo", "meu", "meus", "minha", "minhas",
    "muito", "na", "nas", "não", "nem", "no", "nos", "nós", "num", "numa",
    "o", "os", "ou", "para", "pela", "pelas", "pelo", "pelos", "por", "qual",
    "quando", "que", "quem", "se", "sem", "ser", "seu", "seus", "sua", "suas",
    "também", "te", "tem", "têm", "um", "uma", "umas", "uns", "você", "vocês",
}

TOKEN_RE = re.compile(r"[^\W_]+", re.UNICODE)


def analyze_text(title: str | None, description: str | None, excerpt: str | None) -> dict:
    """Return word counts, lexical diversity, average word length, and key terms."""
    text = " ".join(part for part in (title, description, excerpt) if part)
    normalized = unicodedata.normalize("NFKC", text).lower()
    words = TOKEN_RE.findall(normalized)
    terms = [
        word for word in words
        if (len(word) > 2 or word == "ia") and word not in STOPWORDS and not word.isdigit()
    ]
    counts = Counter(terms)
    return {
        "analyzer_version": ANALYZER_VERSION,
        "word_count": len(words),
        "unique_word_count": len(set(words)),
        "avg_word_length": round(sum(map(len, words)) / len(words), 2) if words else 0,
        "top_terms": [
            {"term": term, "count": count}
            for term, count in counts.most_common(20)
        ],
    }
