from ast import Str
import os
from mcp.server.fastmcp import FastMCP
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from mysql.connector.connection import MySQLConnection

from connection import get_connection

mcp = FastMCP("Data_Fetcher")


def _get_table_and_pk(reference: str) -> Tuple[str, str]:
    """
    Internal helper: map reference string to table and primary key column.
    """
    ref = reference.lower()
    if ref == "company":
        return "company", "company_id"
    elif ref == "individual":
        return "individual", "id"
    else:
        raise ValueError(f"Unsupported reference type: {reference!r}")

def _resolve_reference_id(
    conn: get_connection,
    client_id: int,
    reference: str,
) -> int:
    
    ref_type = reference.lower()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT reference_id
        FROM internal_data
        WHERE id = %s AND reference = %s
        LIMIT 1
        """,
        (client_id, ref_type),
    )
    row = cursor.fetchone()

    if row and row.get("reference_id") is not None:
        return int(row["reference_id"])
    return client_id

def _resolve_reference_id_from_practice(
    conn: get_connection,
    practice_id: str,
    reference: str,
) -> Optional[int]:
    """
    Internal helper:
        Resolve internal_data.reference_id using practice_id + reference.
        Returns reference_id (PK of company/individual) or None if not found.
    """
    ref_type = reference.lower().strip()
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
    if not row or row.get("reference_id") is None:
        return None

    return int(row["reference_id"])

# func
@mcp.tool()
def get_client_full_legal_name(
    practice_id: str,
    reference: str,
) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch the client’s full legal name for identity confirmation.

    Args:
        practice_id (str):
            The client’s practice_id stored in internal_data.practice_id.
        reference (str):
            "company" or "individual".

    Returns:
        dict | None:
            For company:
            {
                "reference": "company",
                "practice_id": "<practice_id>",
                "full_legal_name": "<company name>"
            }

            For individual:
            {
                "reference": "individual",
                "practice_id": "<practice_id>",
                "full_legal_name": "<first middle last>"
            }

            Returns None if not found.
    """
    ref_type = reference.lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return None

        cursor = conn.cursor(dictionary=True)

        if ref_type == "company":
            cursor.execute(
                f"""
                SELECT name
                FROM {table}
                WHERE {pk_col} = %s
                LIMIT 1
                """,
                (resolved_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "full_legal_name": row.get("name"),
            }

        if ref_type == "individual":
            cursor.execute(
                f"""
                SELECT first_name, middle_name, last_name
                FROM {table}
                WHERE {pk_col} = %s
                LIMIT 1
                """,
                (resolved_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            parts = [row.get("first_name"), row.get("middle_name"), row.get("last_name")]
            full_name = " ".join([p for p in parts if p]).strip() or None

            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "full_legal_name": full_name,
            }

        return None

@mcp.tool()
def get_client_date_of_birth(
    practice_id: str,
    reference: str,
) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch the client’s date of birth (for individual clients).

    Args:
        practice_id (str):
            The client’s practice_id stored in internal_data.practice_id.
        reference (str):
            Must be "individual". If "company", returns None.

    Returns:
        dict | None:
            {
                "reference": "individual",
                "practice_id": "<practice_id>",
                "date_of_birth": "YYYY-MM-DD" | None
            }

            Returns None if not found or reference != "individual".
    """
    ref_type = reference.lower().strip()
    if ref_type != "individual":
        return None

    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT birth_date
            FROM {table}
            WHERE {pk_col} = %s
            LIMIT 1
            """,
            (resolved_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "date_of_birth": str(row["birth_date"]) if row.get("birth_date") else None,
        }

@mcp.tool()
def get_client_current_us_address(
    practice_id: str,
    reference: str,
) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the client’s current US address fields.
    Args:
        practice_id (str):
            The client’s practice_id stored in internal_data.practice_id.
        reference (str):
            "company" or "individual" (used to match contact_info.reference).

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

            Returns None if no contact_info found.
    """
    ref_type = reference.lower().strip()

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
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
            LEFT JOIN countries c
                ON c.id = ci.country
            WHERE ci.reference = %s
              AND ci.reference_id = %s
            ORDER BY ci.status DESC, ci.id ASC
            LIMIT 1
            """,
            (ref_type, resolved_id),
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
def get_client_occupation_and_us_income_source(
    practice_id: str,
    reference: str,
) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY occupation and source_of_us_income for a client.

    Args:
        practice_id (str):
            The client’s practice_id stored in internal_data.practice_id.
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

            Returns None if not found.
    """
    ref_type = reference.lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT occupation, source_of_us_income
            FROM {table}
            WHERE {pk_col} = %s
            LIMIT 1
            """,
            (resolved_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "occupation": row.get("occupation"),
            "source_of_us_income": row.get("source_of_us_income"),
        }

@mcp.tool()
def get_client_itin_exists(
    practice_id: str,
    reference: str,
) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Answer ONLY whether an ITIN exists on file (without returning the number).

    Args:
        practice_id (str):
            The client’s practice_id stored in internal_data.practice_id.
        reference (str):
            Must be "individual". If "company", returns None.

    Returns:
        dict | None:
            {
                "reference": "individual",
                "practice_id": "<practice_id>",
                "has_itin": true|false
            }

            Returns None if not found or reference != "individual".
    """
    ref_type = reference.lower().strip()
    if ref_type != "individual":
        return None

    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT ssn_itin_type, ssn_itin
            FROM {table}
            WHERE {pk_col} = %s
            LIMIT 1
            """,
            (resolved_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        t = (row.get("ssn_itin_type") or "").strip().upper()
        v = (row.get("ssn_itin") or "").strip()
        has_itin = (t == "ITIN") and (len(v) > 0)

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "has_itin": has_itin,
        }

@mcp.tool()
def get_client_itin_number(
    practice_id: str,
    reference: str,
) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Fetch ONLY the ITIN number (if present) for an individual client.

    Args:
        practice_id (str):
            The client’s practice_id stored in internal_data.practice_id.
        reference (str):
            Must be "individual". If "company", returns None.

    Returns:
        dict | None:
            {
                "reference": "individual",
                "practice_id": "<practice_id>",
                "itin": "<str|None>"
            }

            Returns None if not found, reference != "individual",
            or the stored tax id is not an ITIN.
    """
    ref_type = reference.lower().strip()
    if ref_type != "individual":
        return None

    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return None

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT ssn_itin_type, ssn_itin
            FROM {table}
            WHERE {pk_col} = %s
            LIMIT 1
            """,
            (resolved_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        t = (row.get("ssn_itin_type") or "").strip().upper()
        itin = row.get("ssn_itin") if t == "ITIN" else None

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "itin": itin,
        }


if __name__ == "__main__":
    mcp.run()