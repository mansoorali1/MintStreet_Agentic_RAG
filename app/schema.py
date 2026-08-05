"""
Natural-language description of the Postgres schema, fed straight into the
text-to-SQL prompt. This is the single most important piece of prompt
engineering in the SQL pipeline - nearly every rule below was added because
the model got something wrong without it (alphabetic year sorting, the
ROUND() cast ordering, treating month_year's day-of-month as real data).

Update this whenever the underlying tables change. Wrong column names here
are the #1 cause of failed SQL generations.
"""

SCHEMA_DESCRIPTION = """
You have access to two PostgreSQL tables:

TABLE 1: digital_payments_yearly
- year column: TEXT, display format 'YYYY-YY' e.g. '2022-23', '2023-24'. Use this ONLY for
  display and for exact single-year filters, e.g. WHERE year = '2022-23'. NEVER use it for
  sorting, MIN/MAX, or range comparisons - it will sort alphabetically, not chronologically.
- fiscal_year_start_int column: INTEGER, e.g. 2022 for FY '2022-23'. ALWAYS use this column
  for ORDER BY, MAX()/MIN(), BETWEEN, or any "highest/lowest/latest/trend over years" question.
  Do not include fiscal_year_start_int in the final SELECT list unless the user explicitly
  asks for the numeric year - select `year` for display instead.
- When user says "2023", interpret as fiscal year ending 2023 = '2022-23' (fiscal_year_start_int = 2022)
- Volume columns end in _vol (unit: lakhs = 100,000 transactions)
- Value columns end in _val (unit: crores = 10 million rupees)

Key columns (use EXACT names):
  payment_systems_credit_transfers_upi_vol
  payment_systems_credit_transfers_upi_val
  payment_systems_card_payments_credit_cards_vol
  payment_systems_card_payments_debit_cards_vol
  payment_systems_total_digital_payments_vol
  payment_systems_total_digital_payments_val
  payment_systems_credit_transfers_neft_vol
  payment_systems_credit_transfers_imps_vol
  payment_systems_large_value_credit_transfers_rtgs_vol
  payment_systems_paper_based_instruments_vol
  payment_systems_prepaid_payment_instruments_ppi_vol

TABLE 2: digital_payments_monthly
- month_year column: DATE type, stored as the first day of the month (e.g. 2019-03-01
  represents March 2019). The day-of-month is always 1 and has NO real meaning - it is a
  storage artifact, not daily-level data. NEVER refer to a specific day in the answer.
  - Filter a single month: WHERE month_year = '2019-03-01'
  - Filter a range: WHERE month_year BETWEEN '2019-01-01' AND '2019-12-01'
  - Extract parts: EXTRACT(YEAR FROM month_year), EXTRACT(MONTH FROM month_year)
  - Sort/compare chronologically: ORDER BY month_year works correctly since it's a real DATE
- Volume columns end in _vol, value columns end in _val

Key columns (use EXACT names):
  payment_systems_retail_credit_transfers_upi_vol
  payment_systems_retail_credit_transfers_upi_val
  payment_systems_retail_card_payments_credit_cards_vol
  payment_systems_retail_card_payments_debit_cards_vol
  payment_systems_total_digital_payments_vol
  payment_systems_total_digital_payments_val
  other_payment_channels_mobile_payments_vol
  payment_system_infrastructures_number_of_atms_vol
  payment_system_infrastructures_upi_qr_vol

RULES:
- yearly trends -> use digital_payments_yearly
- monthly seasonality or specific months -> use digital_payments_monthly
- Infrastructure columns (number_of_atms, number_of_cards) are COUNTS not rupees
- RTGS is wholesale, exclude from retail payment totals
- Only write SELECT statements, no INSERT/UPDATE/DELETE
- ROUND() in PostgreSQL has NO overload for double precision. It only works on numeric.
  Any expression involving division (e.g. computing growth %, ratios, averages) produces
  double precision by default and WILL error if passed directly to ROUND().
  ALWAYS cast the ENTIRE final expression to ::numeric, wrapping the whole thing in
  parentheses, BEFORE calling ROUND. Do this:
      ROUND((( (a - b) * 100.0 / NULLIF(b, 0) ))::numeric, 2)
  NOT this (will fail):
      ROUND((a - b)::numeric / NULLIF(b, 0) * 100, 2)
  The difference: cast AFTER all arithmetic is done, not on one operand mid-expression.

Never include a hardcoded string literal as a column value to answer a qualitative part
of the question (e.g. `'some fact' AS column_name`). Only SELECT real columns from the
two tables above. If part of the question cannot be answered from real columns, simply
don't attempt that part in SQL - leave it entirely to the RAG/qualitative side.
"""

