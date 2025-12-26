import os
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from mysql.connector.connection import MySQLConnection

from connection import get_connection

mcp = FastMCP("Data_Fetcher")


# Helpers
def _get_table_and_pk(reference: str) -> Tuple[str, str]:
    """
    Purpose:
        Map a client reference type to its table name and primary key column.

    Args:
        reference (str):
            "company" or "individual".

    Returns:
        tuple[str, str]:
            (table_name, pk_column)
    """
    ref = (reference or "").lower().strip()
    if ref == "company":
        return "company", "company_id"
    if ref == "individual":
        return "individual", "id"
    raise ValueError(f"Unsupported reference type: {reference!r}")


def _resolve_reference_id_from_practice(
    conn: get_connection,
    practice_id: str,
    reference: str,
) -> Optional[int]:
    """
    Purpose:
        Resolve internal_data.reference_id using practice_id + reference.

    Args:
        conn (MySQLConnection):
            Open DB connection.
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            "company" or "individual" (stored in internal_data.reference).

    Returns:
        int | None:
            reference_id (PK of company/individual) if found, else None.
    """
    ref_type = (reference or "").lower().strip()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT reference_id
        FROM internal_data
        WHERE practice_id = %s AND reference = %s
        LIMIT 1
        """,
        (practice_id, ref_type),
    )
    row = cursor.fetchone()
    if row and row.get("reference_id") is not None:
        return int(row["reference_id"])
    return None


@mcp.tool()
def get_client_full_legal_name(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the client’s full legal name for identity confirmation.

    Args:
        practice_id (str):
            The client’s practice_id (internal_data.practice_id).
        reference (str):
            "company" or "individual".

    Returns:
        dict | None:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "full_legal_name": "<str|None>"
            }
            None if not found.
    """
    ref_type = (reference or "").lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)

        if ref_type == "company":
            cursor.execute(
                f"SELECT name FROM {table} WHERE {pk_col} = %s LIMIT 1",
                (rid,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {"reference": ref_type, "practice_id": practice_id, "full_legal_name": row.get("name")}

        cursor.execute(
            f"SELECT first_name, middle_name, last_name FROM {table} WHERE {pk_col} = %s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        parts = [row.get("first_name"), row.get("middle_name"), row.get("last_name")]
        full_name = " ".join([p for p in parts if p]).strip() or None
        return {"reference": ref_type, "practice_id": practice_id, "full_legal_name": full_name}


@mcp.tool()
def get_client_date_of_birth(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the client’s date of birth (individual only).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "date_of_birth": "YYYY-MM-DD" | None
            }
            None if not found or reference != "individual".
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None

    table, pk_col = _get_table_and_pk(ref_type)
    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT birth_date FROM {table} WHERE {pk_col} = %s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"reference": ref_type, "practice_id": practice_id, "date_of_birth": str(row["birth_date"]) if row.get("birth_date") else None}


@mcp.tool()
def get_client_current_us_address(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the client’s current address fields and return country as country_name.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            "company" or "individual" (contact_info.reference).

    Returns:
        dict | None:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "address1": "<str|None>",
              "address2": "<str|None>",
              "city": "<str|None>",
              "state": "<str|None>",
              "zip": "<str|None>",
              "country": "<country_name|None>"
            }
            None if not found.
    """
    ref_type = (reference or "").lower().strip()

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                ci.address1,
                ci.address2,
                ci.city,
                ci.state,
                ci.zip,
                c.country_name AS country
            FROM contact_info ci
            LEFT JOIN countries c ON c.id = ci.country
            WHERE ci.reference = %s AND ci.reference_id = %s
            ORDER BY ci.status DESC, ci.id ASC
            LIMIT 1
            """,
            (ref_type, rid),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "address1": row.get("address1"),
            "address2": row.get("address2"),
            "city": row.get("city"),
            "state": row.get("state"),
            "zip": row.get("zip"),
            "country": row.get("country"),
        }


@mcp.tool()
def get_client_occupation_and_us_income_source(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY occupation and source_of_us_income for a client.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            "company" or "individual".

    Returns:
        dict | None:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "occupation": "<str|None>",
              "source_of_us_income": "<str|None>"
            }
            None if not found.
    """
    ref_type = (reference or "").lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT occupation, source_of_us_income FROM {table} WHERE {pk_col} = %s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {"reference": ref_type, "practice_id": practice_id, "occupation": row.get("occupation"), "source_of_us_income": row.get("source_of_us_income")}

@mcp.tool()
def get_client_itin_number(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the ITIN number (if present) for an individual client.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "itin": "<str|None>"
            }
            None if not found / not ITIN / reference != "individual".
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None

    table, pk_col = _get_table_and_pk(ref_type)
    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT ssn_itin_type, ssn_itin FROM {table} WHERE {pk_col} = %s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        t = (row.get("ssn_itin_type") or "").strip().upper()
        return {"reference": ref_type, "practice_id": practice_id, "itin": row.get("ssn_itin") if t == "ITIN" else None}


# NEW 1040-NR (individual)

@mcp.tool()
def get_individual_passport_details(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY passport details for the individual (number/country/expiry).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "passport_number": "<str|None>",
              "passport_country": "<str|None>",
              "passport_expiry": "YYYY-MM-DD"|None
            }
            None if not found or reference != "individual".
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None

    table, pk_col = _get_table_and_pk(ref_type)
    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT passport_number, passport_country, passport_expiry
            FROM {table}
            WHERE {pk_col} = %s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "passport_number": row.get("passport_number"),
            "passport_country": row.get("passport_country"),
            "passport_expiry": str(row["passport_expiry"]) if row.get("passport_expiry") else None,
        }


@mcp.tool()
def get_individual_visa_details(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY visa type and visa issue country for the individual.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "visa_type":"<str|None>",
              "visa_issue_country":"<str|None>"
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT visa_type, visa_issue_country FROM {table} WHERE {pk_col}=%s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"reference": ref_type, "practice_id": practice_id, "visa_type": row.get("visa_type"), "visa_issue_country": row.get("visa_issue_country")}


@mcp.tool()
def get_individual_us_entry_exit_dates(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY first entry date and last exit date for U.S. travel history.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "first_entry_date_us":"YYYY-MM-DD"|None,
              "last_exit_date_us":"YYYY-MM-DD"|None
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT first_entry_date_us, last_exit_date_us FROM {table} WHERE {pk_col}=%s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "first_entry_date_us": str(row["first_entry_date_us"]) if row.get("first_entry_date_us") else None,
            "last_exit_date_us": str(row["last_exit_date_us"]) if row.get("last_exit_date_us") else None,
        }


@mcp.tool()
def get_individual_days_in_us(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY days-in-US counts for current/previous/prev2 tax years.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "days_in_us_current_year": <int|None>,
              "days_in_us_prev_year": <int|None>,
              "days_in_us_prev2_years": <int|None>
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT days_in_us_current_year, days_in_us_prev_year, days_in_us_prev2_years
            FROM {table}
            WHERE {pk_col}=%s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "days_in_us_current_year": row.get("days_in_us_current_year"),
            "days_in_us_prev_year": row.get("days_in_us_prev_year"),
            "days_in_us_prev2_years": row.get("days_in_us_prev2_years"),
        }


@mcp.tool()
def get_individual_treaty_claim_details(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY treaty claim fields (whether claimed + details).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "treaty_claimed":"y|n|None",
              "treaty_country":"<str|None>",
              "treaty_article":"<str|None>",
              "treaty_income_type":"<str|None>",
              "treaty_exempt_amount": <decimal|None>,
              "resident_of_treaty_country":"y|n|None"
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT
              treaty_claimed,
              treaty_country,
              treaty_article,
              treaty_income_type,
              treaty_exempt_amount,
              resident_of_treaty_country
            FROM {table}
            WHERE {pk_col}=%s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "treaty_claimed": row.get("treaty_claimed"),
            "treaty_country": row.get("treaty_country"),
            "treaty_article": row.get("treaty_article"),
            "treaty_income_type": row.get("treaty_income_type"),
            "treaty_exempt_amount": float(row.get("treaty_exempt_amount")) if row.get("treaty_exempt_amount") is not None else None,
            "resident_of_treaty_country": row.get("resident_of_treaty_country"),
        }


@mcp.tool()
def get_individual_income_amounts(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the key 1040-NR income amount fields for the individual.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "w2_wages_amount": <decimal|None>,
              "scholarship_1042s_amount": <decimal|None>,
              "interest_amount": <decimal|None>,
              "dividend_amount": <decimal|None>,
              "capital_gains_amount": <decimal|None>,
              "rental_income_amount": <decimal|None>,
              "self_employment_eci_amount": <decimal|None>
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT
              w2_wages_amount,
              scholarship_1042s_amount,
              interest_amount,
              dividend_amount,
              capital_gains_amount,
              rental_income_amount,
              self_employment_eci_amount
            FROM {table}
            WHERE {pk_col}=%s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # return raw values (MySQL driver often returns Decimal -> fine for JSON, but keep float safe)
        def _to_float(v):
            return float(v) if v is not None else None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "w2_wages_amount": _to_float(row.get("w2_wages_amount")),
            "scholarship_1042s_amount": _to_float(row.get("scholarship_1042s_amount")),
            "interest_amount": _to_float(row.get("interest_amount")),
            "dividend_amount": _to_float(row.get("dividend_amount")),
            "capital_gains_amount": _to_float(row.get("capital_gains_amount")),
            "rental_income_amount": _to_float(row.get("rental_income_amount")),
            "self_employment_eci_amount": _to_float(row.get("self_employment_eci_amount")),
        }


@mcp.tool()
def get_individual_withholding_amounts(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY withholding/tax paid fields for the individual.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "federal_withholding_w2": <decimal|None>,
              "federal_withholding_1042s": <decimal|None>,
              "tax_withheld_1099": <decimal|None>
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT federal_withholding_w2, federal_withholding_1042s, tax_withheld_1099
            FROM {table}
            WHERE {pk_col}=%s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        def _to_float(v):
            return float(v) if v is not None else None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "federal_withholding_w2": _to_float(row.get("federal_withholding_w2")),
            "federal_withholding_1042s": _to_float(row.get("federal_withholding_1042s")),
            "tax_withheld_1099": _to_float(row.get("tax_withheld_1099")),
        }


@mcp.tool()
def get_individual_document_flags(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY document presence flags for the individual (W2/1042-S/1099/K-1).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "has_w2":"y|n|None",
              "has_1042s":"y|n|None",
              "has_1099":"y|n|None",
              "has_k1":"y|n|None"
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT has_w2, has_1042s, has_1099, has_k1
            FROM {table}
            WHERE {pk_col}=%s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "has_w2": row.get("has_w2"),
            "has_1042s": row.get("has_1042s"),
            "has_1099": row.get("has_1099"),
            "has_k1": row.get("has_k1"),
        }


@mcp.tool()
def get_individual_itemized_deductions(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY itemized deduction fields relevant to 1040-NR.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "itemized_state_local_tax": <decimal|None>,
              "itemized_charity": <decimal|None>,
              "itemized_casualty_losses": <decimal|None>
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT itemized_state_local_tax, itemized_charity, itemized_casualty_losses
            FROM {table}
            WHERE {pk_col}=%s
            LIMIT 1
            """,
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        def _to_float(v):
            return float(v) if v is not None else None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "itemized_state_local_tax": _to_float(row.get("itemized_state_local_tax")),
            "itemized_charity": _to_float(row.get("itemized_charity")),
            "itemized_casualty_losses": _to_float(row.get("itemized_casualty_losses")),
        }


@mcp.tool()
def get_individual_education_items(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY education-related expense fields (if stored for 1040-NR).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "education_expenses": <decimal|None>,
              "student_loan_interest": <decimal|None>
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT education_expenses, student_loan_interest FROM {table} WHERE {pk_col}=%s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        def _to_float(v):
            return float(v) if v is not None else None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "education_expenses": _to_float(row.get("education_expenses")),
            "student_loan_interest": _to_float(row.get("student_loan_interest")),
        }


@mcp.tool()
def get_individual_dependents_count(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY dependents_count for the individual.

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "dependents_count": <int|None>
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT dependents_count FROM {table} WHERE {pk_col}=%s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {"reference": ref_type, "practice_id": practice_id, "dependents_count": row.get("dependents_count")}


@mcp.tool()
def get_individual_refund_method(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY refund_method for the individual (check/ACH).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "refund_method":"check|ACH|None"
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT refund_method FROM {table} WHERE {pk_col}=%s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {"reference": ref_type, "practice_id": practice_id, "refund_method": row.get("refund_method")}


@mcp.tool()
def get_individual_bank_details_last4(practice_id: str, reference: str) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY bank routing and last4 (do NOT fetch/store full account number).

    Args:
        practice_id (str):
            internal_data.practice_id.
        reference (str):
            Must be "individual".

    Returns:
        dict | None:
            {
              "reference":"individual",
              "practice_id":"<practice_id>",
              "bank_routing":"<str|None>",
              "bank_account_last4":"<str|None>"
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return None
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"SELECT bank_routing, bank_account_last4 FROM {table} WHERE {pk_col}=%s LIMIT 1",
            (rid,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "bank_routing": row.get("bank_routing"),
            "bank_account_last4": row.get("bank_account_last4"),
        }


if __name__ == "__main__":
    mcp.run()
