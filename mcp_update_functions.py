from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING, List
from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from mysql.connector.connection import MySQLConnection

from connection import get_connection

mcp = FastMCP("Data_Updater")

# Helper
def _get_table_and_pk(reference: str) -> Tuple[str, str]:
    """
    Purpose:
        Map reference type to the underlying table and its primary key column.

    Args:
        reference (str): "company" or "individual"

    Returns:
        (table_name, pk_column)
    """
    ref = reference.lower().strip()
    if ref == "company":
        # NOTE: some environments use company_id as PK; some use id.
        # We'll handle mismatch during SELECT/UPDATE where needed.
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
        conn (MySQLConnection): open DB connection
        practice_id (str): internal_data.practice_id
        reference (str): "company" or "individual"

    Returns:
        int | None: resolved underlying reference_id, or None if not found
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


def _build_update_query(
    table: str,
    pk_col: str,
    pk_value: int,
    fields: Dict[str, Any],
) -> Optional[Tuple[str, List[Any]]]:
    """
    Purpose:
        Build a parameterized UPDATE statement for one row.

    Args:
        table (str): table name
        pk_col (str): primary key column
        pk_value (int): primary key value
        fields (dict): column->value map (non-empty)

    Returns:
        (query, params) | None
    """
    if not fields:
        return None

    set_clauses = []
    params: List[Any] = []

    for col, val in fields.items():
        set_clauses.append(f"{col} = %s")
        params.append(val)

    query = f"""
        UPDATE {table}
        SET {", ".join(set_clauses)}
        WHERE {pk_col} = %s
        LIMIT 1
    """
    params.append(pk_value)
    return query, params


def _resolve_company_pk_and_row(conn: get_connection, resolved_id: int) -> Optional[Dict[str, Any]]:
    """
    Purpose:
        Handle the staging mismatch where internal_data.reference_id may map
        to company.id (NOT company.company_id). This helper finds the correct row.

    Args:
        conn (MySQLConnection): open DB connection
        resolved_id (int): internal_data.reference_id

    Returns:
        dict | None:
            {
              "pk_col": "id" or "company_id",
              "pk_value": int
            }
    """
    cursor = conn.cursor(dictionary=True)

    # Try company.id first
    cursor.execute(
        "SELECT id FROM company WHERE id = %s LIMIT 1",
        (resolved_id,),
    )
    row = cursor.fetchone()
    if row:
        return {"pk_col": "id", "pk_value": int(row["id"])}

    # Fallback to company.company_id
    cursor.execute(
        "SELECT company_id FROM company WHERE company_id = %s LIMIT 1",
        (resolved_id,),
    )
    row = cursor.fetchone()
    if row:
        return {"pk_col": "company_id", "pk_value": int(row["company_id"])}

    return None


# UPDATE: Full name

@mcp.tool()
def update_client_full_legal_name(
    practice_id: str,
    reference: str,
    full_legal_name: str,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the client’s full legal name.
        - For company: updates company.name
        - For individual: updates individual.first_name/middle_name/last_name
          by splitting the provided full name.

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): "company" or "individual"
        full_legal_name (str): full legal name string

    Returns:
        dict:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "success": bool,
              "updated_fields": [...],
              "rows_affected": int,
              "message": str
            }
    """
    ref_type = reference.lower().strip()
    full_legal_name = (full_legal_name or "").strip()

    if not full_legal_name:
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "updated_fields": [],
            "rows_affected": 0,
            "message": "full_legal_name is required.",
        }

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No matching internal_data found for this practice_id + reference.",
            }

        if ref_type == "company":
            pk_info = _resolve_company_pk_and_row(conn, resolved_id)
            if not pk_info:
                return {
                    "reference": ref_type,
                    "practice_id": practice_id,
                    "success": False,
                    "updated_fields": [],
                    "rows_affected": 0,
                    "message": "Company record not found.",
                }

            built = _build_update_query(
                "company",
                pk_info["pk_col"],
                pk_info["pk_value"],
                {"name": full_legal_name},
            )
            query, params = built
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()

            return {
                "reference": "company",
                "practice_id": practice_id,
                "success": cur.rowcount > 0,
                "updated_fields": ["name"],
                "rows_affected": cur.rowcount,
                "message": "Update applied." if cur.rowcount > 0 else "No rows updated.",
            }

        if ref_type == "individual":
            # Simple split: first = first token, last = last token, middle = rest
            parts = [p for p in full_legal_name.split(" ") if p]
            first_name = parts[0] if parts else None
            last_name = parts[-1] if len(parts) >= 2 else None
            middle_name = " ".join(parts[1:-1]) if len(parts) > 2 else None

            fields: Dict[str, Any] = {"first_name": first_name}
            # Always set these to avoid leaving old values if user changes name
            fields["middle_name"] = middle_name
            fields["last_name"] = last_name

            built = _build_update_query("individual", "id", resolved_id, fields)
            query, params = built
            cur = conn.cursor()
            cur.execute(query, params)
            conn.commit()

            return {
                "reference": "individual",
                "practice_id": practice_id,
                "success": cur.rowcount > 0,
                "updated_fields": list(fields.keys()),
                "rows_affected": cur.rowcount,
                "message": "Update applied." if cur.rowcount > 0 else "No rows updated.",
            }

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "updated_fields": [],
            "rows_affected": 0,
            "message": "Unsupported reference type.",
        }


# UPDATE: Date of birth
@mcp.tool()
def update_client_date_of_birth(
    practice_id: str,
    reference: str,
    birth_date: str,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the birth_date for an individual client.

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        birth_date (str): "YYYY-MM-DD"

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "success": bool,
              "updated_fields": ["birth_date"],
              "rows_affected": int,
              "message": str
            }
    """
    ref_type = reference.lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "updated_fields": [],
            "rows_affected": 0,
            "message": "update_client_date_of_birth only supports reference='individual'.",
        }

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "Individual record not found for this practice_id.",
            }

        built = _build_update_query("individual", "id", resolved_id, {"birth_date": birth_date})
        query, params = built
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "success": cur.rowcount > 0,
            "updated_fields": ["birth_date"],
            "rows_affected": cur.rowcount,
            "message": "Update applied." if cur.rowcount > 0 else "No rows updated.",
        }


# UPDATE: Current US Address (contact_info)
@mcp.tool()
def update_client_current_us_address(
    practice_id: str,
    reference: str,
    address1: Optional[str] = None,
    address2: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    country_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the address fields on the primary contact_info record
        for the given client (company/individual).

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): "company" or "individual"
        address1 (str|None): contact_info.address1
        address2 (str|None): contact_info.address2
        city (str|None): contact_info.city
        state (str|None): contact_info.state
        zip_code (str|None): contact_info.zip
        country_id (int|None): contact_info.country (countries.id)

    Returns:
        dict:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "contact_id": <int|None>,
              "success": bool,
              "updated_fields": [...],
              "rows_affected": int,
              "message": str
            }
    """
    ref_type = reference.lower().strip()

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "contact_id": None,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No matching internal_data found for this practice_id + reference.",
            }

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id
            FROM contact_info
            WHERE reference = %s AND reference_id = %s
            ORDER BY status DESC, id ASC
            LIMIT 1
            """,
            (ref_type, resolved_id),
        )
        existing = cursor.fetchone()
        if not existing:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "contact_id": None,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No existing contact_info record found to update.",
            }

        contact_id = int(existing["id"])

        fields: Dict[str, Any] = {}
        if address1 is not None:
            fields["address1"] = address1
        if address2 is not None:
            fields["address2"] = address2
        if city is not None:
            fields["city"] = city
        if state is not None:
            fields["state"] = state
        if zip_code is not None:
            fields["zip"] = zip_code
        if country_id is not None:
            fields["country"] = country_id

        built = _build_update_query("contact_info", "id", contact_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "contact_id": contact_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No fields provided to update.",
            }

        query, params = built
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "contact_id": contact_id,
            "success": cur.rowcount > 0,
            "updated_fields": list(fields.keys()),
            "rows_affected": cur.rowcount,
            "message": "Update applied." if cur.rowcount > 0 else "No rows updated.",
        }


# UPDATE: Occupation + US income source
@mcp.tool()
def update_client_occupation_and_us_income_source(
    practice_id: str,
    reference: str,
    occupation: Optional[str] = None,
    source_of_us_income: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY occupation and/or source_of_us_income for a client.

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): "company" or "individual"
        occupation (str|None): new occupation value
        source_of_us_income (str|None): new source_of_us_income value

    Returns:
        dict:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "success": bool,
              "updated_fields": ["occupation", "source_of_us_income"],
              "rows_affected": int,
              "message": str
            }
    """
    ref_type = reference.lower().strip()

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No matching internal_data found for this practice_id + reference.",
            }

        if ref_type == "company":
            pk_info = _resolve_company_pk_and_row(conn, resolved_id)
            if not pk_info:
                return {
                    "reference": "company",
                    "practice_id": practice_id,
                    "success": False,
                    "updated_fields": [],
                    "rows_affected": 0,
                    "message": "Company record not found.",
                }
            pk_col = pk_info["pk_col"]
            pk_value = pk_info["pk_value"]
            table = "company"
        elif ref_type == "individual":
            pk_col = "id"
            pk_value = resolved_id
            table = "individual"
        else:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "Unsupported reference type.",
            }

        fields: Dict[str, Any] = {}
        if occupation is not None:
            fields["occupation"] = occupation
        if source_of_us_income is not None:
            fields["source_of_us_income"] = source_of_us_income

        built = _build_update_query(table, pk_col, pk_value, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No fields provided to update.",
            }

        query, params = built
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": cur.rowcount > 0,
            "updated_fields": list(fields.keys()),
            "rows_affected": cur.rowcount,
            "message": "Update applied." if cur.rowcount > 0 else "No rows updated.",
        }


# UPDATE: ITIN
@mcp.tool()
def update_client_itin_number(
    practice_id: str,
    reference: str,
    itin: Optional[str],
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the ITIN fields for an individual.
        - If itin is a non-empty string: sets ssn_itin_type="ITIN" and ssn_itin=<itin>
        - If itin is None or empty: clears ssn_itin_type and ssn_itin

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        itin (str|None): ITIN number (string). If None/empty, clears it.

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "success": bool,
              "updated_fields": ["ssn_itin_type", "ssn_itin"],
              "rows_affected": int,
              "message": str
            }
    """
    ref_type = reference.lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "updated_fields": [],
            "rows_affected": 0,
            "message": "update_client_itin_number only supports reference='individual'.",
        }

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "Individual record not found for this practice_id.",
            }

        itin_val = (itin or "").strip()
        if itin_val:
            fields = {"ssn_itin_type": "ITIN", "ssn_itin": itin_val}
        else:
            fields = {"ssn_itin_type": None, "ssn_itin": None}

        built = _build_update_query("individual", "id", resolved_id, fields)
        query, params = built
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "success": cur.rowcount > 0,
            "updated_fields": ["ssn_itin_type", "ssn_itin"],
            "rows_affected": cur.rowcount,
            "message": "Update applied." if cur.rowcount > 0 else "No rows updated.",
        }

if __name__ == "__main__":
    mcp.run()
