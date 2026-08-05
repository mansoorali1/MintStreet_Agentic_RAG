"""
Hybrid retrieval over the RBI report chunks: dense search via Pinecone,
sparse search via BM25, merged with reciprocal rank fusion, then
re-ranked with a cross-encoder before the top 5 go to the LLM.
"""

import re

import numpy as np

from app.clients import all_chunks, bm25, embedder, index, reranker

MIN_YEAR = min((c["metadata"].get("year") or 9999) for c in all_chunks)
MAX_YEAR = max((c["metadata"].get("year") or 0) for c in all_chunks)


def parse_year_query(query):
    """Figure out what year filtering, if any, a question implies.

    Returns one of:
      {"mode": "none"}
      {"mode": "single", "years": [2023]}
      {"mode": "multi",  "years": [2016, 2020, 2025]}
      {"mode": "range",  "years": [2015, 2020]}

    Order matters - FY style (2022-23) has to be matched and stripped out
    before we look for plain 4-digit years, otherwise "2015-16" gets
    misread as a range from 2015 to 16.
    """
    q = query.lower()
    found_years = set()

    # FY style: 2022-23 -> ending year 2023
    fy_matches = re.findall(r'\b(20\d{2})-(\d{2})\b', q)
    for start, end_suffix in fy_matches:
        found_years.add(int(start) + 1)
    q_stripped = re.sub(r'\b20\d{2}-\d{2}\b', ' ', q)

    # explicit range phrasing: "from 2015 to 2020", "between 2015 and 2020"
    range_match = re.search(
        r'(?:from|between)\s+(20\d{2})\s*(?:to|and|-)\s*(20\d{2})', q_stripped
    )
    if range_match:
        lo, hi = int(range_match.group(1)), int(range_match.group(2))
        return {"mode": "range", "years": [min(lo, hi), max(lo, hi)]}

    # bare "2015-2020" range (not FY - that's already been stripped above)
    bare_range = re.search(r'\b(20\d{2})\s*-\s*(20\d{2})\b', q_stripped)
    if bare_range:
        lo, hi = int(bare_range.group(1)), int(bare_range.group(2))
        return {"mode": "range", "years": [min(lo, hi), max(lo, hi)]}

    # "last N years" / "past N years"
    last_n = re.search(r'(?:last|past)\s+(\d+)\s+years?', q_stripped)
    if last_n:
        n = int(last_n.group(1))
        return {"mode": "range", "years": [max(MIN_YEAR, MAX_YEAR - n + 1), MAX_YEAR]}

    # "recent" / "latest" / "current" with no explicit year
    if any(w in q_stripped for w in ["recent", "latest", "current"]):
        found_years.add(MAX_YEAR)

    # whatever plain years are left after stripping FY/range patterns
    leftover_years = re.findall(r'\b(20\d{2})\b', q_stripped)
    for y in leftover_years:
        found_years.add(int(y))

    if not found_years and fy_matches:
        for start, end_suffix in fy_matches:
            found_years.add(int(start) + 1)

    if not found_years:
        return {"mode": "none"}

    years_list = sorted(found_years)
    if len(years_list) == 1:
        return {"mode": "single", "years": years_list}
    return {"mode": "multi", "years": years_list}


def build_pinecone_year_filter(year_info):
    """Turn parsed year info into a Pinecone metadata filter dict."""
    if not year_info or year_info["mode"] == "none":
        return None
    if year_info["mode"] == "single":
        return {"year": {"$eq": year_info["years"][0]}}
    if year_info["mode"] == "multi":
        return {"year": {"$in": year_info["years"]}}
    if year_info["mode"] == "range":
        lo, hi = year_info["years"][0], year_info["years"][-1]
        return {"$and": [{"year": {"$gte": lo}}, {"year": {"$lte": hi}}]}
    return None


def chunk_matches_year_filter(metadata, year_info):
    """Same filtering logic as above, applied by hand to BM25 hits since
    BM25 has no native filter support."""
    if not year_info or year_info["mode"] == "none":
        return True
    y = metadata.get("year")
    if y is None:
        return False
    if year_info["mode"] in ("single", "multi"):
        return y in year_info["years"]
    if year_info["mode"] == "range":
        lo, hi = year_info["years"][0], year_info["years"][-1]
        return lo <= y <= hi
    return True


def hybrid_search(query, top_k=25, year_info=None):
    if year_info is None:
        year_info = parse_year_query(query)

    query_vec = embedder.encode(query).tolist()
    pinecone_filter = build_pinecone_year_filter(year_info)

    dense_results = index.query(
        vector=query_vec,
        top_k=top_k,
        include_metadata=True,
        filter=pinecone_filter,
    )
    dense_hits = {
        m["id"]: {
            "id": m["id"],
            "score": m["score"],
            "metadata": m["metadata"],
            "text": next((c["text"] for c in all_chunks if c["id"] == m["id"]), ""),
        }
        for m in dense_results["matches"]
    }

    tokenized_q = query.lower().split()
    bm25_scores = bm25.get_scores(tokenized_q)
    top_bm25 = np.argsort(bm25_scores)[::-1][:top_k]
    bm25_hits = {}
    for idx in top_bm25:
        chunk = all_chunks[idx]
        if not chunk_matches_year_filter(chunk["metadata"], year_info):
            continue
        bm25_hits[chunk["id"]] = {
            "id": chunk["id"],
            "score": float(bm25_scores[idx]),
            "metadata": chunk["metadata"],
            "text": chunk["text"],
        }

    # reciprocal rank fusion - combine dense + sparse rankings without
    # needing their raw scores to be on the same scale
    all_ids = set(dense_hits) | set(bm25_hits)
    dense_ids = list(dense_hits)
    bm25_ids = list(bm25_hits)
    merged = {}
    for hit_id in all_ids:
        dr = dense_ids.index(hit_id) + 1 if hit_id in dense_ids else top_k + 1
        br = bm25_ids.index(hit_id) + 1 if hit_id in bm25_ids else top_k + 1
        src = dense_hits.get(hit_id) or bm25_hits.get(hit_id)
        merged[hit_id] = {**src, "rrf_score": (1 / (60 + dr)) + (1 / (60 + br))}

    candidates = sorted(merged.values(), key=lambda x: x["rrf_score"], reverse=True)[:25]

    # filtering too aggressively can starve results - year detection can
    # mismatch, or that year's chunks genuinely don't cover the topic.
    # fall back to an unfiltered search rather than returning almost nothing
    if len(candidates) < 3 and year_info.get("mode") != "none":
        return hybrid_search(query, top_k=top_k, year_info={"mode": "none"})

    rerank_scores = reranker.predict([(query, c["text"]) for c in candidates])
    for i, c in enumerate(candidates):
        c["rerank_score"] = float(rerank_scores[i])

    return sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)[:5]

