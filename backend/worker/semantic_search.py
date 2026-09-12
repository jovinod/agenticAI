from sqlalchemy import text as sql_text

from embedding_client import embed_query
from pii_scrub import scrub_pii
from profile_store import engine


async def search_reports(query: str, limit: int = 5) -> list[dict]:
    """Orders reports by cosine distance. Exact scans are adequate for a
    small collection -- an approximate index would need representative
    recall measurements, not an assumption. Scrub first, then embed:
    logging or embedding the raw query would recreate the exposure
    even if the vector path itself were clean."""
    query_embedding = await embed_query(scrub_pii(query))
    vector_literal = "[" + ",".join(str(v) for v in query_embedding) + "]"

    with engine.connect() as connection:
        rows = connection.execute(
            sql_text(
                """
                SELECT job_id, ticker, market, report_text,
                       embedding <=> (:query_vector)::vector AS distance
                FROM research_reports
                ORDER BY distance
                LIMIT :limit
                """
            ),
            {"query_vector": vector_literal, "limit": limit},
        ).fetchall()

    return [
        {
            "job_id": row.job_id,
            "ticker": row.ticker,
            "market": row.market,
            "report_text": row.report_text,
            "distance": row.distance,
        }
        for row in rows
    ]
