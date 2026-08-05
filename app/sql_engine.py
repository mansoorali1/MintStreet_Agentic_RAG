"""
Text-to-SQL with a self-correction loop: generate, run it against Supabase,
and if it errors out or comes back empty, feed the error back to the model
and try again up to max_retries times.
"""

import re

import pandas as pd
import sqlalchemy

from app.clients import engine
from app.llm import call_groq
from app.schema import SCHEMA_DESCRIPTION


def run_sql_with_retry(query, max_retries=3):
    error_feedback = None
    corrections = 0

    for attempt in range(max_retries):
        prompt = f"""{SCHEMA_DESCRIPTION}
Write a PostgreSQL SELECT query to answer: "{query}"
Return only the SQL, no explanation, no markdown."""
        if error_feedback:
            prompt += f"\n\nPrevious attempt failed: {error_feedback}\nFix it."

        sql = call_groq([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=1000)
        sql = re.sub(r"```sql|```", "", sql).strip()

        if not sql:
            error_feedback = "Your previous response was empty. Return ONLY the SQL query, nothing else."
            corrections += 1
            continue

        try:
            # connection context manager rather than engine directly -
            # pandas read_sql can be flaky with newer sqlalchemy + psycopg2
            with engine.connect() as conn:
                df = pd.read_sql_query(sqlalchemy.text(sql), conn)

            if df.empty:
                error_feedback = "query returned zero rows - check table name and column names"
                corrections += 1
                continue
            if df.isnull().all().all():
                error_feedback = "all values null - likely wrong column name"
                corrections += 1
                continue

            return df, sql, corrections, None

        except Exception as e:
            error_feedback = str(e)
            corrections += 1

    return None, sql, corrections, f"Failed after {max_retries} attempts. Last error: {error_feedback}"

