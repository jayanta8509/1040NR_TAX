from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING, List
from mcp.server.fastmcp import FastMCP

if TYPE_CHECKING:
    from mysql.connector.connection import MySQLConnection

from connection import get_connection

mcp = FastMCP("Data_Updater")


# helpers
def _get_table_and_pk(reference: str) -> Tuple[str, str]:
    ref = reference.lower()
    if ref == "company":
        return "company", "company_id"
    elif ref == "individual":
        return "individual", "id"
    else:
        raise ValueError(f"Unsupported reference type: {reference!r}")


def _resolve_reference_id_from_practice(
    conn: get_connection,
    practice_id: str,
    reference: str,
) -> Optional[int]:
    """
    Resolve underlying primary key (company.company_id or individual.id)
    using internal_data.practice_id + internal_data.reference.
    """
    ref_type = reference.lower()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT reference_id
        FROM internal_data
        WHERE practice_id = %s
          AND reference = %s
        LIMIT 1
        """,
        (practice_id, ref_type),
    )
    row = cursor.fetchone()
    if row and row.get("reference_id") is not None:
        return int(row["reference_id"])
    return None


def _build_update_query(
    table: str,
    pk_col: str,
    pk_value: int,
    fields: Dict[str, Any],
) -> Optional[Tuple[str, List[Any]]]:
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


# Master data

@mcp.tool()
def get_master_languages_and_countries() -> Dict[str, Any]:
    """
    Read-only helper:
    Returns all languages + countries so the bot can map:
      "India" -> country_id
      "Japanese" -> language_id
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT id, language, status
            FROM languages
            ORDER BY language ASC
            """
        )
        languages = cursor.fetchall() or []

        cursor.execute(
            """
            SELECT id, country_code, country_phone_code, country_name, sort_order
            FROM countries
            ORDER BY country_name ASC
            """
        )
        countries = cursor.fetchall() or []

    return {"languages": languages, "countries": countries}

# update functions
@mcp.tool()
def update_individual_name(
    practice_id: str,
    reference: str,
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the individual's name fields:
          - first_name
          - middle_name
          - last_name

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        first_name (str|None): new first name
        middle_name (str|None): new middle name
        last_name (str|None): new last name

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id>,
              "success": true|false,
              "rows_affected": <int>,
              "updated": {
                  "first_name": "...",   # only if updated
                  "middle_name": "...",  # only if updated
                  "last_name": "..."     # only if updated
              }
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

        fields: Dict[str, Any] = {}
        if first_name is not None:
            fields["first_name"] = first_name
        if middle_name is not None:
            fields["middle_name"] = middle_name
        if last_name is not None:
            fields["last_name"] = last_name

        built = _build_update_query("individual", "id", rid, fields)
        if not built:
            return {"reference": ref_type, "practice_id": practice_id, "reference_id": rid, "success": False, "rows_affected": 0, "updated": {}}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_birth_date(
    practice_id: str,
    reference: str,
    birth_date: Optional[str] = None,  #"YYYY-MM-DD"
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the individual's birth_date.

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        birth_date (str|None): "YYYY-MM-DD"

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id>,
              "success": true|false,
              "rows_affected": <int>,
              "updated": {"birth_date": "YYYY-MM-DD"}
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    if birth_date is None:
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

        fields = {"birth_date": birth_date}
        built = _build_update_query("individual", "id", rid, fields)
        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_ssn_itin_number(
    practice_id: str,
    reference: str,
    ssn_itin: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the individual's ssn_itin field (the number).

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        ssn_itin (str|None): new tax id number stored in individual.ssn_itin

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id>,
              "success": true|false,
              "rows_affected": <int>,
              "updated": {"ssn_itin": "<value>"}
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    if ssn_itin is None:
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

        fields = {"ssn_itin": ssn_itin}
        built = _build_update_query("individual", "id", rid, fields)
        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_language_and_countries(
    practice_id: str,
    reference: str,
    language: Optional[str] = None,
    country_residence: Optional[str] = None,
    country_citizenship: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY these individual fields by mapping STRING inputs to IDs:
          - individual.language (from languages.language)
          - individual.country_residence (from countries.country_name or countries.country_code)
          - individual.country_citizenship (from countries.country_name or countries.country_code)

        IMPORTANT:
          This function does NOT accept integer IDs in args.
          It accepts readable strings and resolves IDs from master tables.

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        language (str|None): example "English"
        country_residence (str|None): example "India" or "IN"
        country_citizenship (str|None): example "India" or "IN"

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id>,
              "success": true|false,
              "rows_affected": <int>,
              "updated": {
                 "language": {"input": "English", "id": 1},
                 "country_residence": {"input": "India", "id": 9},
                 "country_citizenship": {"input": "India", "id": 9}
              }
            }

        Notes:
          - If an input string cannot be matched, that field is not updated.
          - If nothing can be matched/updated, success=false and updated={} is returned.
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

        cursor = conn.cursor(dictionary=True)

        fields: Dict[str, Any] = {}
        updated_payload: Dict[str, Any] = {}

        if language is not None and str(language).strip():
            cursor.execute(
                """
                SELECT id, language
                FROM languages
                WHERE LOWER(language) = LOWER(%s)
                ORDER BY id ASC
                LIMIT 1
                """,
                (language.strip(),),
            )
            lang_row = cursor.fetchone()
            if lang_row and lang_row.get("id") is not None:
                fields["language"] = int(lang_row["id"])
                updated_payload["language"] = {"input": language.strip(), "id": int(lang_row["id"])}

        def _find_country_id(country_str: str) -> Optional[int]:
            s = (country_str or "").strip()
            if not s:
                return None
            cursor.execute(
                """
                SELECT id
                FROM countries
                WHERE LOWER(country_name) = LOWER(%s)
                   OR LOWER(country_code) = LOWER(%s)
                ORDER BY id ASC
                LIMIT 1
                """,
                (s, s),
            )
            r = cursor.fetchone()
            return int(r["id"]) if r and r.get("id") is not None else None

        if country_residence is not None and str(country_residence).strip():
            cid = _find_country_id(country_residence)
            if cid is not None:
                fields["country_residence"] = cid
                updated_payload["country_residence"] = {"input": country_residence.strip(), "id": cid}

        if country_citizenship is not None and str(country_citizenship).strip():
            cid = _find_country_id(country_citizenship)
            if cid is not None:
                fields["country_citizenship"] = cid
                updated_payload["country_citizenship"] = {"input": country_citizenship.strip(), "id": cid}

        if not fields:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": rid,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        built = _build_update_query("individual", "id", rid, fields)
        q, p = built
        cur2 = conn.cursor()
        cur2.execute(q, p)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur2.rowcount > 0,
            "rows_affected": cur2.rowcount,
            "updated": updated_payload,
        }


@mcp.tool()
def update_individual_filing_status(
    practice_id: str,
    reference: str,
    filing_status: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the individual's filing_status.

    Args:
        practice_id (str): internal_data.practice_id
        reference (str): must be "individual"
        filing_status (str|None): new filing status value (stored in individual.filing_status)

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id>,
              "success": true|false,
              "rows_affected": <int>,
              "updated": {"filing_status": "<value>"}
            }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    if filing_status is None:
        return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if rid is None:
            return {"reference": ref_type, "practice_id": practice_id, "success": False, "rows_affected": 0, "updated": {}}

        fields = {"filing_status": filing_status}
        built = _build_update_query("individual", "id", rid, fields)
        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_client_primary_contact_address(
    practice_id: str,
    reference: str,
    address1: Optional[str] = None,
    address2: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the address fields of the client's primary contact record
        in contact_info:
          - address1
          - address2
          - city
          - state
          - zip (from zip_code arg)

        It selects the "primary" contact record as:
            ORDER BY status DESC, id ASC LIMIT 1
        for the given (reference, reference_id).

    Args:
        practice_id (str):
            internal_data.practice_id for the client.
        reference (str):
            "company" or "individual".
        address1 (str | None):
            Street address line 1.
        address2 (str | None):
            Street address line 2 / apartment / suite.
        city (str | None):
            City.
        state (str | None):
            State/Province.
        zip_code (str | None):
            ZIP / Postal code (stored in contact_info.zip).

    Returns:
        dict:
            {
              "reference": "<company|individual>",
              "practice_id": "<practice_id>",
              "reference_id": <company.company_id or individual.id>,
              "contact_id": <contact_info.id>,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": {
                 "address1": "...",   # only if provided
                 "address2": "...",
                 "city": "...",
                 "state": "...",
                 "zip": "..."
              }
            }
    """
    ref_type = (reference or "").lower().strip()

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT reference_id
            FROM internal_data
            WHERE practice_id = %s
              AND reference = %s
            LIMIT 1
            """,
            (practice_id, ref_type),
        )
        row = cursor.fetchone()
        if not row or row.get("reference_id") is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": None,
                "contact_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        reference_id = int(row["reference_id"])

        cursor.execute(
            """
            SELECT id
            FROM contact_info
            WHERE reference = %s
              AND reference_id = %s
            ORDER BY status DESC, id ASC
            LIMIT 1
            """,
            (ref_type, reference_id),
        )
        existing = cursor.fetchone()
        if not existing or existing.get("id") is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": reference_id,
                "contact_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
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

        if not fields:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": reference_id,
                "contact_id": contact_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        set_clause = ", ".join([f"{col} = %s" for col in fields.keys()])
        params = list(fields.values()) + [contact_id]

        query = f"""
            UPDATE contact_info
            SET {set_clause}
            WHERE id = %s
            LIMIT 1
        """

        cur2 = conn.cursor()
        cur2.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": reference_id,
            "contact_id": contact_id,
            "success": cur2.rowcount > 0,
            "rows_affected": cur2.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_client_occupation(
    practice_id: str,
    reference: str,
    occupation: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the `occupation` field for a client (company/individual)
        using practice_id + reference.

    Updates:
        - occupation

    Args:
        practice_id (str):
            internal_data.practice_id of the client.
        reference (str):
            "company" or "individual".
        occupation (str | None):
            New occupation value.

    Returns:
        dict:
            {
              "reference": "company" | "individual",
              "practice_id": "<practice_id>",
              "reference_id": <company.company_id or individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": { "occupation": "<value>" }   # only if provided
            }
    """
    ref_type = (reference or "").lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        reference_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if reference_id is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        if occupation is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": reference_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        fields: Dict[str, Any] = {"occupation": occupation}

        built = _build_update_query(table, pk_col, reference_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": reference_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        query, params = built
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": reference_id,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_client_source_of_us_income(
    practice_id: str,
    reference: str,
    source_of_us_income: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the `source_of_us_income` field for a client (company/individual)
        using practice_id + reference.

    Updates:
        - source_of_us_income

    Args:
        practice_id (str):
            internal_data.practice_id of the client.
        reference (str):
            "company" or "individual".
        source_of_us_income (str | None):
            New value for source_of_us_income.

    Returns:
        dict:
            {
              "reference": "company" | "individual",
              "practice_id": "<practice_id>",
              "reference_id": <company.company_id or individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": { "source_of_us_income": "<value>" }  # only if provided
            }
    """
    ref_type = (reference or "").lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

    with get_connection() as conn:
        reference_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if reference_id is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        if source_of_us_income is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": reference_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        fields: Dict[str, Any] = {"source_of_us_income": source_of_us_income}

        built = _build_update_query(table, pk_col, reference_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": reference_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
            }

        query, params = built
        cur = conn.cursor()
        cur.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": reference_id,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_passport_details(
    practice_id: str,
    reference: str,
    passport_number: Optional[str] = None,
    passport_country: Optional[str] = None,
    passport_expiry: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY passport-related fields for an individual client.

    Updates:
        - passport_number
        - passport_country
        - passport_expiry

    Args:
        practice_id (str):
            internal_data.practice_id for the client.
        reference (str):
            Must be "individual".
        passport_number (str | None):
            Passport number.
        passport_country (str | None):
            Passport issuing country (as stored in your DB).
        passport_expiry (str | None):
            Passport expiry date (YYYY-MM-DD).

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": {
                 "passport_number": "...",
                 "passport_country": "...",
                 "passport_expiry": "YYYY-MM-DD"
              }
            }
            Note: `updated` contains ONLY the fields provided in the request.
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": None,
            "success": False,
            "rows_affected": 0,
            "updated": {},
            "message": "update_individual_passport_details only supports reference='individual'.",
        }

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        reference_id = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not reference_id:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "Client not found for this practice_id.",
            }

        fields: Dict[str, Any] = {}
        if passport_number is not None:
            fields["passport_number"] = passport_number
        if passport_country is not None:
            fields["passport_country"] = passport_country
        if passport_expiry is not None:
            fields["passport_expiry"] = passport_expiry

        built = _build_update_query(table, pk_col, reference_id, fields)
        if not built:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": reference_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "No passport fields provided to update.",
            }

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "reference_id": reference_id,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_visa_details(
    practice_id: str,
    reference: str,
    visa_type: Optional[str] = None,
    visa_issue_country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY visa-related fields for an individual client.

    Updates:
        - visa_type
        - visa_issue_country

    Args:
        practice_id (str):
            internal_data.practice_id for the client.
        reference (str):
            Must be "individual".
        visa_type (str | None):
            Visa type (e.g., F1, J1, H1B).
        visa_issue_country (str | None):
            Country where visa was issued (as stored in your DB).

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": {
                 "visa_type": "...",
                 "visa_issue_country": "..."
              }
            }
            Note: `updated` contains ONLY the fields provided in the request.
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": None,
            "success": False,
            "rows_affected": 0,
            "updated": {},
            "message": "update_individual_visa_details only supports reference='individual'.",
        }

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        reference_id = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not reference_id:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "Client not found for this practice_id.",
            }

        fields: Dict[str, Any] = {}
        if visa_type is not None:
            fields["visa_type"] = visa_type
        if visa_issue_country is not None:
            fields["visa_issue_country"] = visa_issue_country

        built = _build_update_query(table, pk_col, reference_id, fields)
        if not built:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": reference_id,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "No visa fields provided to update.",
            }

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "reference_id": reference_id,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_us_entry_exit_dates(
    practice_id: str,
    reference: str,
    first_entry_date_us: Optional[str] = None,
    last_exit_date_us: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the US entry/exit date fields for an individual.

    Updates:
        - first_entry_date_us
        - last_exit_date_us

    Args:
        practice_id (str):
            internal_data.practice_id for the client.
        reference (str):
            Must be "individual".
        first_entry_date_us (str | None):
            First entry date into the US (YYYY-MM-DD).
        last_exit_date_us (str | None):
            Most recent exit date from the US (YYYY-MM-DD).

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": {
                 "first_entry_date_us": "...",
                 "last_exit_date_us": "..."
              }
            }
            Note: `updated` includes only fields provided in the request.
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": None,
            "success": False,
            "rows_affected": 0,
            "updated": {},
            "message": "update_individual_us_entry_exit_dates only supports reference='individual'.",
        }

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "Client not found for this practice_id.",
            }

        fields: Dict[str, Any] = {}
        if first_entry_date_us is not None:
            fields["first_entry_date_us"] = first_entry_date_us
        if last_exit_date_us is not None:
            fields["last_exit_date_us"] = last_exit_date_us

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": rid,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "No entry/exit date fields provided to update.",
            }

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_us_days_presence(
    practice_id: str,
    reference: str,
    days_in_us_current_year: Optional[int] = None,
    days_in_us_prev_year: Optional[int] = None,
    days_in_us_prev2_years: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update ONLY the physical presence day-count fields for an individual.

    Updates:
        - days_in_us_current_year
        - days_in_us_prev_year
        - days_in_us_prev2_years

    Args:
        practice_id (str):
            internal_data.practice_id for the client.
        reference (str):
            Must be "individual".
        days_in_us_current_year (int | None):
            Days present in the US for current tax year.
        days_in_us_prev_year (int | None):
            Days present in the US for previous tax year.
        days_in_us_prev2_years (int | None):
            Days present in the US for the tax year two years ago.

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": {
                 "days_in_us_current_year": <int>,
                 "days_in_us_prev_year": <int>,
                 "days_in_us_prev2_years": <int>
              }
            }
            Note: `updated` includes only fields provided in the request.
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": None,
            "success": False,
            "rows_affected": 0,
            "updated": {},
            "message": "update_individual_us_days_presence only supports reference='individual'.",
        }

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "Client not found for this practice_id.",
            }

        fields: Dict[str, Any] = {}
        if days_in_us_current_year is not None:
            fields["days_in_us_current_year"] = int(days_in_us_current_year)
        if days_in_us_prev_year is not None:
            fields["days_in_us_prev_year"] = int(days_in_us_prev_year)
        if days_in_us_prev2_years is not None:
            fields["days_in_us_prev2_years"] = int(days_in_us_prev2_years)

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": rid,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "No day-count fields provided to update.",
            }

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cur.rowcount > 0,
            "rows_affected": cur.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_treaty_details(
    practice_id: str,
    reference: str,
    treaty_claimed: Optional[str] = None,
    treaty_country: Optional[str] = None,
    treaty_article: Optional[str] = None,
    treaty_income_type: Optional[str] = None,
    treaty_exempt_amount: Optional[float] = None,
    resident_of_treaty_country: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update tax treaty–related details for an individual client.
        This function handles ALL treaty fields together because they
        represent a single logical tax concept.

    Updates (individual table):
        - treaty_claimed
        - treaty_country
        - treaty_article
        - treaty_income_type
        - treaty_exempt_amount
        - resident_of_treaty_country

    Args:
        practice_id (str):
            internal_data.practice_id for the individual client.
        reference (str):
            Must be "individual".
        treaty_claimed (str | None):
            'y' or 'n' indicating whether a tax treaty is claimed.
        treaty_country (str | None):
            Country under which the treaty is claimed.
        treaty_article (str | None):
            Treaty article number/name.
        treaty_income_type (str | None):
            Type of income covered by the treaty.
        treaty_exempt_amount (float | None):
            Amount exempt under treaty provisions.
        resident_of_treaty_country (str | None):
            'y' or 'n' indicating residency of treaty country.

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "<practice_id>",
              "reference_id": <individual.id> | None,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": {
                  "treaty_claimed": "...",
                  "treaty_country": "...",
                  ...
              }
            }
            Only fields actually updated are returned inside `updated`.
    """

    if (reference or "").lower().strip() != "individual":
        return {
            "reference": reference,
            "practice_id": practice_id,
            "reference_id": None,
            "success": False,
            "rows_affected": 0,
            "updated": {},
            "message": "update_individual_treaty_details only supports reference='individual'.",
        }

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "No matching individual found for this practice_id.",
            }

        fields: Dict[str, Any] = {}
        if treaty_claimed is not None:
            fields["treaty_claimed"] = treaty_claimed
        if treaty_country is not None:
            fields["treaty_country"] = treaty_country
        if treaty_article is not None:
            fields["treaty_article"] = treaty_article
        if treaty_income_type is not None:
            fields["treaty_income_type"] = treaty_income_type
        if treaty_exempt_amount is not None:
            fields["treaty_exempt_amount"] = treaty_exempt_amount
        if resident_of_treaty_country is not None:
            fields["resident_of_treaty_country"] = resident_of_treaty_country

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": rid,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "message": "No treaty fields provided to update.",
            }

        q, p = built
        cursor = conn.cursor()
        cursor.execute(q, p)
        conn.commit()

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "reference_id": rid,
            "success": cursor.rowcount > 0,
            "rows_affected": cursor.rowcount,
            "updated": fields,
        }


@mcp.tool()
def update_individual_income_w2_1042s(
    practice_id: str,
    reference: str,
    w2_wages_amount: Optional[float] = None,
    scholarship_1042s_amount: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update W-2 wages and/or 1042-S scholarship amounts for an individual.

    Updates (individual table):
        - w2_wages_amount
        - scholarship_1042s_amount

    Args:
        practice_id (str): internal_data.practice_id for the client.
        reference (str): must be "individual".
        w2_wages_amount (float | None): new W-2 wages amount.
        scholarship_1042s_amount (float | None): new 1042-S scholarship amount.

    Returns:
        dict:
            {
              "reference": "individual",
              "practice_id": "...",
              "reference_id": <int|None>,
              "success": <bool>,
              "rows_affected": <int>,
              "updated": { "w2_wages_amount": ..., "scholarship_1042s_amount": ... }
            }
            Only updated fields appear inside `updated`.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if w2_wages_amount is not None:
            fields["w2_wages_amount"] = w2_wages_amount
        if scholarship_1042s_amount is not None:
            fields["scholarship_1042s_amount"] = scholarship_1042s_amount

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}


@mcp.tool()
def update_individual_income_investments(
    practice_id: str,
    reference: str,
    interest_amount: Optional[float] = None,
    dividend_amount: Optional[float] = None,
    capital_gains_amount: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update investment income amounts for an individual.

    Updates (individual table):
        - interest_amount
        - dividend_amount
        - capital_gains_amount

    Args:
        practice_id (str): internal_data.practice_id for the client.
        reference (str): must be "individual".
        interest_amount (float | None)
        dividend_amount (float | None)
        capital_gains_amount (float | None)

    Returns:
        dict with only updated values under `updated`.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if interest_amount is not None:
            fields["interest_amount"] = interest_amount
        if dividend_amount is not None:
            fields["dividend_amount"] = dividend_amount
        if capital_gains_amount is not None:
            fields["capital_gains_amount"] = capital_gains_amount

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}

@mcp.tool()
def update_individual_income_business_and_rental(
    practice_id: str,
    reference: str,
    rental_income_amount: Optional[float] = None,
    self_employment_eci_amount: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update rental income and/or self-employment ECI amounts for an individual.

    Updates (individual table):
        - rental_income_amount
        - self_employment_eci_amount

    Args:
        practice_id (str), reference (str)
        rental_income_amount (float | None)
        self_employment_eci_amount (float | None)

    Returns:
        dict with updated values only.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if rental_income_amount is not None:
            fields["rental_income_amount"] = rental_income_amount
        if self_employment_eci_amount is not None:
            fields["self_employment_eci_amount"] = self_employment_eci_amount

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}


@mcp.tool()
def update_individual_withholding(
    practice_id: str,
    reference: str,
    federal_withholding_w2: Optional[float] = None,
    federal_withholding_1042s: Optional[float] = None,
    tax_withheld_1099: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update withholding / taxes withheld amounts for an individual.

    Updates (individual table):
        - federal_withholding_w2
        - federal_withholding_1042s
        - tax_withheld_1099

    Args:
        practice_id (str): internal_data.practice_id for the client.
        reference (str): must be "individual".
        federal_withholding_w2 (float | None)
        federal_withholding_1042s (float | None)
        tax_withheld_1099 (float | None)

    Returns:
        dict with only updated values under `updated`.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if federal_withholding_w2 is not None:
            fields["federal_withholding_w2"] = federal_withholding_w2
        if federal_withholding_1042s is not None:
            fields["federal_withholding_1042s"] = federal_withholding_1042s
        if tax_withheld_1099 is not None:
            fields["tax_withheld_1099"] = tax_withheld_1099

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}
        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}

@mcp.tool()
def update_individual_forms_flags(
    practice_id: str,
    reference: str,
    has_w2: Optional[str] = None,
    has_1042s: Optional[str] = None,
    has_1099: Optional[str] = None,
    has_k1: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update which tax forms the individual has available.

    Updates (individual table):
        - has_w2
        - has_1042s
        - has_1099
        - has_k1

    Args:
        practice_id (str): internal_data.practice_id for the client.
        reference (str): must be "individual".
        has_w2 / has_1042s / has_1099 / has_k1 (str | None): 'y' or 'n'

    Returns:
        dict with only updated values under `updated`.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if has_w2 is not None:
            fields["has_w2"] = has_w2
        if has_1042s is not None:
            fields["has_1042s"] = has_1042s
        if has_1099 is not None:
            fields["has_1099"] = has_1099
        if has_k1 is not None:
            fields["has_k1"] = has_k1

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}


@mcp.tool()
def update_individual_itemized_deductions(
    practice_id: str,
    reference: str,
    itemized_state_local_tax: Optional[float] = None,
    itemized_charity: Optional[float] = None,
    itemized_casualty_losses: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update itemized deduction amounts for an individual.

    Updates (individual table):
        - itemized_state_local_tax
        - itemized_charity
        - itemized_casualty_losses

    Args:
        practice_id (str), reference (str)
        itemized_state_local_tax (float | None)
        itemized_charity (float | None)
        itemized_casualty_losses (float | None)

    Returns:
        dict with updated values only.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if itemized_state_local_tax is not None:
            fields["itemized_state_local_tax"] = itemized_state_local_tax
        if itemized_charity is not None:
            fields["itemized_charity"] = itemized_charity
        if itemized_casualty_losses is not None:
            fields["itemized_casualty_losses"] = itemized_casualty_losses

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}

@mcp.tool()
def update_individual_education_and_dependents(
    practice_id: str,
    reference: str,
    education_expenses: Optional[float] = None,
    student_loan_interest: Optional[float] = None,
    dependents_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update education-related amounts and dependents count for an individual.

    Updates (individual table):
        - education_expenses
        - student_loan_interest
        - dependents_count

    Args:
        practice_id (str), reference (str)
        education_expenses (float | None)
        student_loan_interest (float | None)
        dependents_count (int | None)

    Returns:
        dict with updated values only.
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}
        if education_expenses is not None:
            fields["education_expenses"] = education_expenses
        if student_loan_interest is not None:
            fields["student_loan_interest"] = student_loan_interest
        if dependents_count is not None:
            fields["dependents_count"] = dependents_count

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}


@mcp.tool()
def update_individual_refund_method(
    practice_id: str,
    reference: str,
    refund_method: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update the refund method for an individual.
 
    Allowed refund methods:
        - 'check'
        - 'ACH' (default fallback)
    Args:
        practice_id (str), reference (str)
        refund_method (str | None): 'check' or 'ACH'
 
    Behavior:
        - If an invalid refund_method is provided, the system:
            * Returns an error message
            * Stores 'ACH' as the refund_method
            * Returns available methods in response
 
    Updates (individual table):
        - refund_method
 
    Returns:
        dict with updated value + available methods
    """
 
    AVAILABLE_METHODS = ["check", "ACH"]
    DEFAULT_METHOD = "ACH"
 
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": reference,
            "practice_id": practice_id,
            "reference_id": None,
            "success": False,
            "rows_affected": 0,
            "updated": {},
            "available_refund_methods": AVAILABLE_METHODS,
            "message": "Only supports reference='individual'.",
        }
 
    table, pk_col = _get_table_and_pk("individual")
 
    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "reference_id": None,
                "success": False,
                "rows_affected": 0,
                "updated": {},
                "available_refund_methods": AVAILABLE_METHODS,
                "message": "Client not found for this practice_id.",
            }
 
        requested_method = (refund_method or "").strip()
 
        error_message = None
        final_method = requested_method
 
        if requested_method not in AVAILABLE_METHODS:
            final_method = DEFAULT_METHOD
            error_message = (
                f"Invalid refund method '{refund_method}'. "
                f"Refund method must be one of {AVAILABLE_METHODS}. "
                f"Defaulted to '{DEFAULT_METHOD}'."
            )
 
        fields = {"refund_method": final_method}
 
        built = _build_update_query(table, pk_col, rid, fields)
        q, p = built
 
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()
 
        response = {
            "reference": "individual",
            "practice_id": practice_id,
            "reference_id": rid,
            "success": True,
            "rows_affected": cur.rowcount,
            "updated": fields,
            "available_refund_methods": AVAILABLE_METHODS,
        }
 
        if error_message:
            response["message"] = error_message
 
        return response


@mcp.tool()
def update_individual_bank_details(
    practice_id: str,
    reference: str,
    bank_routing: Optional[str] = None,
    bank_account_last4: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update bank details used for refund via ACH.
        Stores only last 4 digits for account number (safety).

    Updates (individual table):
        - bank_routing
        - bank_account_last4

    Args:
        practice_id (str), reference (str)
        bank_routing (str | None): bank routing number (string).
        bank_account_last4 (str | None): last 4 digits or full account number; we store only last 4.

    Returns:
        dict with updated values only (last4 stored).
    """
    if (reference or "").lower().strip() != "individual":
        return {"reference": reference, "practice_id": practice_id, "reference_id": None,
                "success": False, "rows_affected": 0, "updated": {},
                "message": "Only supports reference='individual'."}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": None,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "Client not found for this practice_id."}

        fields: Dict[str, Any] = {}

        if bank_routing is not None:
            fields["bank_routing"] = bank_routing

        if bank_account_last4 is not None:
            s = str(bank_account_last4).strip()
            fields["bank_account_last4"] = s[-4:] if len(s) >= 4 else s

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                    "success": False, "rows_affected": 0, "updated": {},
                    "message": "No fields provided to update."}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"reference": "individual", "practice_id": practice_id, "reference_id": rid,
                "success": cur.rowcount > 0, "rows_affected": cur.rowcount, "updated": fields}




if __name__ == "__main__":
    mcp.run()