"""Accent-insensitive BM25; optional exact cosine index + reciprocal rank fusion."""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from .catalog import course_codes, normalize
from .provider import ProviderError

STOP = set("la va cua cho toi cac co thi duoc voi trong mot nhung bao nhieu hay khong nao da muon can".split())


def tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", normalize(text)) if t not in STOP]


def cosine(a, b):
    if len(a) != len(b):
        raise ProviderError("Kích thước vector không khớp; hãy lập lại chỉ mục.")
    denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
    return sum(x*y for x, y in zip(a, b)) / denominator if denominator else 0.0


class Retriever:
    def __init__(self, catalog, settings, provider=None, cache_dir=None):
        self.catalog, self.settings, self.provider = catalog, settings, provider
        self.chunks = catalog.chunks
        self.counts = [Counter(tokens(c["text"])) for c in self.chunks]
        self.lengths = [sum(c.values()) for c in self.counts]
        self.average = sum(self.lengths) / max(len(self.lengths), 1)
        self.df = Counter(t for c in self.counts for t in c)
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.vectors = None

    def _lexical(self, question, indices):
        terms = tokens(question)
        codes = course_codes(question)
        scores = []
        for i in indices:
            score = 0.0
            for term in terms:
                freq = self.counts[i][term]
                if not freq:
                    continue
                idf = math.log(1 + (len(self.chunks) - self.df[term] + .5) / (self.df[term] + .5))
                score += idf * freq * 2.5 / (freq + 1.5 * (.25 + .75 * self.lengths[i] / max(self.average, 1)))
            if self.chunks[i].get("course_code") in codes:
                score += 40
            if score > 0:
                scores.append((i, score))
        return sorted(scores, key=lambda x: (-x[1], self.chunks[x[0]]["id"]))

    def _index_vectors(self):
        usage = {}
        if self.vectors is not None:
            return usage
        key = hashlib.sha256((self.catalog.fingerprint + self.settings.embedding_model).encode()).hexdigest()
        path = self.cache_dir / (key + ".json") if self.cache_dir else None
        if path and path.exists():
            vectors = json.loads(path.read_text())
            if len(vectors) == len(self.chunks):
                self.vectors = vectors
                return usage
        self.vectors, usage = self.provider.embeddings([c["text"] for c in self.chunks])
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.vectors), encoding="utf-8")
            temporary.replace(path)
        return usage

    def search(self, question, cohort, top_k=None, kinds=None, source_ids=None):
        if cohort != self.catalog.cohort or not cohort:
            return [], {"embedding_tokens": 0, "index_embedding_tokens": 0}
        indices = [i for i, c in enumerate(self.chunks) if c["cohort"] == cohort
                   and (not kinds or c["kind"] in kinds) and (not source_ids or c["source_id"] in source_ids)]
        if not indices:
            return [], {"embedding_tokens": 0, "index_embedding_tokens": 0}
        lexical = self._lexical(question, indices)
        usage = {"embedding_tokens": 0, "index_embedding_tokens": 0}
        if self.settings.retriever == "hybrid":
            if not self.provider:
                raise ProviderError("Chưa cấu hình embedding provider.")
            index_usage = self._index_vectors()
            query_vectors, query_usage = self.provider.embeddings([question])
            usage = {"embedding_tokens": query_usage.get("total_tokens", 0),
                     "index_embedding_tokens": index_usage.get("total_tokens", 0)}
            vector = sorted(((i, cosine(query_vectors[0], self.vectors[i])) for i in indices),
                            key=lambda x: -x[1])
            # RRF avoids mixing the incomparable BM25 and cosine score scales.
            fused = Counter()
            for ranked in (lexical, [x for x in vector if x[1] > 0]):
                for rank, (i, _) in enumerate(ranked):
                    fused[i] += 1 / (60 + rank + 1)
            ranked = sorted(fused.items(), key=lambda x: (-x[1], self.chunks[x[0]]["id"]))
            # Exact course IDs must stay resolvable in Vietnamese hybrid search.
            codes = course_codes(question)
            ranked.sort(key=lambda x: (self.chunks[x[0]].get("course_code") not in codes, -x[1]))
        else:
            ranked = lexical
        return [{**self.chunks[i], "retrieval_score": round(score, 6)} for i, score in
                ranked[:top_k or self.settings.top_k]], usage
