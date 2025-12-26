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


# Update individual identity & tax/residency

@mcp.tool()
def update_individual_identity_and_tax_id(
    practice_id: str,
    reference: str,
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    last_name: Optional[str] = None,
    birth_date: Optional[str] = None,
    ssn_itin_type: Optional[str] = None,
    ssn_itin: Optional[str] = None,
    language_id: Optional[int] = None,
    country_residence_id: Optional[int] = None,
    country_citizenship_id: Optional[int] = None,
    filing_status: Optional[str] = None,
) -> Dict[str, Any]:
    ref_type = reference.lower()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "updated_fields": [],
            "rows_affected": 0,
            "message": "update_individual_identity_and_tax_id only supports reference='individual'.",
        }

    table, pk_col = _get_table_and_pk(ref_type)

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

        fields: Dict[str, Any] = {}
        if first_name is not None:
            fields["first_name"] = first_name
        if middle_name is not None:
            fields["middle_name"] = middle_name
        if last_name is not None:
            fields["last_name"] = last_name
        if birth_date is not None:
            fields["birth_date"] = birth_date
        if ssn_itin_type is not None:
            fields["ssn_itin_type"] = ssn_itin_type
        if ssn_itin is not None:
            fields["ssn_itin"] = ssn_itin
        if language_id is not None:
            fields["language"] = language_id
        if country_residence_id is not None:
            fields["country_residence"] = country_residence_id
        if country_citizenship_id is not None:
            fields["country_citizenship"] = country_citizenship_id
        if filing_status is not None:
            fields["filing_status"] = filing_status

        built = _build_update_query(table, pk_col, resolved_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": resolved_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No fields provided to update.",
            }

        query, params = built
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": resolved_id,
            "success": cursor.rowcount > 0,
            "updated_fields": list(fields.keys()),
            "rows_affected": cursor.rowcount,
            "message": "Update applied." if cursor.rowcount > 0 else "No rows updated.",
        }


# Update primary contact info (contact_info)

@mcp.tool()
def update_client_primary_contact_info(
    practice_id: str,
    reference: str,
    first_name: Optional[str] = None,
    middle_name: Optional[str] = None,
    last_name: Optional[str] = None,
    phone1_country: Optional[int] = None,
    phone1: Optional[str] = None,
    phone2_country: Optional[int] = None,
    phone2: Optional[str] = None,
    email1: Optional[str] = None,
    email2: Optional[str] = None,
    whatsapp_country: Optional[int] = None,
    whatsapp: Optional[str] = None,
    website: Optional[str] = None,
    address1: Optional[str] = None,
    address2: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    zip_code: Optional[str] = None,
    country_id: Optional[int] = None,
    company_name: Optional[str] = None,
    status: Optional[int] = None,
) -> Dict[str, Any]:
    ref_type = reference.lower()

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, ref_type)
        if resolved_id is None:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": None,
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
            WHERE reference = %s
              AND reference_id = %s
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
                "reference_id": resolved_id,
                "contact_id": None,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No existing contact_info record found to update.",
            }

        contact_id = existing["id"]

        fields: Dict[str, Any] = {}
        if first_name is not None:
            fields["first_name"] = first_name
        if middle_name is not None:
            fields["middle_name"] = middle_name
        if last_name is not None:
            fields["last_name"] = last_name
        if phone1_country is not None:
            fields["phone1_country"] = phone1_country
        if phone1 is not None:
            fields["phone1"] = phone1
        if phone2_country is not None:
            fields["phone2_country"] = phone2_country
        if phone2 is not None:
            fields["phone2"] = phone2
        if email1 is not None:
            fields["email1"] = email1
        if email2 is not None:
            fields["email2"] = email2
        if whatsapp_country is not None:
            fields["whats_app_country"] = whatsapp_country
        if whatsapp is not None:
            fields["whatsapp"] = whatsapp
        if website is not None:
            fields["website"] = website
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
        if company_name is not None:
            fields["company"] = company_name
        if status is not None:
            fields["status"] = status

        built = _build_update_query("contact_info", "id", contact_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": resolved_id,
                "contact_id": contact_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No fields provided to update.",
            }

        query, params = built
        cursor2 = conn.cursor()
        cursor2.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": resolved_id,
            "contact_id": contact_id,
            "success": cursor2.rowcount > 0,
            "updated_fields": list(fields.keys()),
            "rows_affected": cursor2.rowcount,
            "message": "Update applied." if cursor2.rowcount > 0 else "No rows updated.",
        }


# Update internal_data assignments
@mcp.tool()
def update_client_internal_assignments(
    practice_id: str,
    reference: str,
    office: Optional[int] = None,
    brand_id: Optional[int] = None,
    partner: Optional[int] = None,
    manager: Optional[int] = None,
    assistant: Optional[int] = None,
    property_manager: Optional[str] = None,
    client_association: Optional[str] = None,
    new_practice_id: Optional[str] = None,
    referred_by_source: Optional[int] = None,
    referred_by_name: Optional[str] = None,
    language_id: Optional[int] = None,
    status: Optional[int] = None,
    tenant_id: Optional[str] = None,
    customer_vault_id: Optional[str] = None,
) -> Dict[str, Any]:
    ref_type = reference.lower()

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT id, reference_id
            FROM internal_data
            WHERE practice_id = %s
              AND reference = %s
            LIMIT 1
            """,
            (practice_id, ref_type),
        )
        row = cursor.fetchone()
        if not row:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "internal_data_id": None,
                "reference_id": None,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No internal_data record found to update for this practice_id + reference.",
            }

        internal_id = row["id"]
        resolved_reference_id = row.get("reference_id")

        fields: Dict[str, Any] = {}
        if office is not None:
            fields["office"] = office
        if brand_id is not None:
            fields["brand_id"] = brand_id
        if partner is not None:
            fields["partner"] = partner
        if manager is not None:
            fields["manager"] = manager
        if assistant is not None:
            fields["assistant"] = assistant
        if property_manager is not None:
            fields["property_manager"] = property_manager
        if client_association is not None:
            fields["client_association"] = client_association
        if new_practice_id is not None:
            fields["practice_id"] = new_practice_id
        if referred_by_source is not None:
            fields["referred_by_source"] = referred_by_source
        if referred_by_name is not None:
            fields["referred_by_name"] = referred_by_name
        if language_id is not None:
            fields["language"] = language_id
        if status is not None:
            fields["status"] = status
        if tenant_id is not None:
            fields["tenantId"] = tenant_id
        if customer_vault_id is not None:
            fields["customer_vault_id"] = customer_vault_id

        built = _build_update_query("internal_data", "id", internal_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "internal_data_id": internal_id,
                "reference_id": resolved_reference_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No fields provided to update.",
            }

        query, params = built
        cursor2 = conn.cursor()
        cursor2.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "internal_data_id": internal_id,
            "reference_id": resolved_reference_id,
            "success": cursor2.rowcount > 0,
            "updated_fields": list(fields.keys()),
            "rows_affected": cursor2.rowcount,
            "message": "Update applied." if cursor2.rowcount > 0 else "No rows updated.",
        }

#Update occupation and us source of income 
@mcp.tool()
def update_client_occupation_and_income_source(
    practice_id: str,
    reference: str,
    occupation: Optional[str] = None,
    source_of_us_income: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Purpose:
        Update occupation and/or source_of_us_income for a client (company/individual)
        using practice_id + reference.

    Args:
        practice_id (str):
            internal_data.practice_id of the client
        reference (str):
            "company" or "individual"
        occupation (str | None):
            New occupation value
        source_of_us_income (str | None):
            New source_of_us_income value

    Returns:
        dict:
            {
                "reference": "company" | "individual",
                "practice_id": <practice_id>,
                "reference_id": <company.company_id or individual.id>,
                "success": bool,
                "updated_fields": [...],
                "rows_affected": int,
                "message": str,
            }
    """
    ref_type = reference.lower().strip()
    table, pk_col = _get_table_and_pk(ref_type)

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

        fields: Dict[str, Any] = {}
        if occupation is not None:
            fields["occupation"] = occupation
        if source_of_us_income is not None:
            fields["source_of_us_income"] = source_of_us_income

        built = _build_update_query(table, pk_col, resolved_id, fields)
        if not built:
            return {
                "reference": ref_type,
                "practice_id": practice_id,
                "reference_id": resolved_id,
                "success": False,
                "updated_fields": [],
                "rows_affected": 0,
                "message": "No fields provided to update.",
            }

        query, params = built
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()

        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "reference_id": resolved_id,
            "success": cursor.rowcount > 0,
            "updated_fields": list(fields.keys()),
            "rows_affected": cursor.rowcount,
            "message": "Update applied." if cursor.rowcount > 0 else "No rows updated.",
        }

# update Passport & Visa Details
@mcp.tool()
def update_individual_passport_and_visa(
    practice_id: str,
    reference: str,
    passport_number: Optional[str] = None,
    passport_country: Optional[str] = None,
    passport_expiry: Optional[str] = None,
    visa_type: Optional[str] = None,
    visa_issue_country: Optional[str] = None,
) -> Dict[str, Any]:

    if reference.lower() != "individual":
        return {"success": False, "message": "Only for individual"}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        resolved_id = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not resolved_id:
            return {"success": False, "message": "Client not found"}

        fields = {}
        if passport_number is not None:
            fields["passport_number"] = passport_number
        if passport_country is not None:
            fields["passport_country"] = passport_country
        if passport_expiry is not None:
            fields["passport_expiry"] = passport_expiry
        if visa_type is not None:
            fields["visa_type"] = visa_type
        if visa_issue_country is not None:
            fields["visa_issue_country"] = visa_issue_country

        built = _build_update_query(table, pk_col, resolved_id, fields)
        if not built:
            return {"success": False, "message": "No fields provided"}

        q, p = built
        c = conn.cursor()
        c.execute(q, p)
        conn.commit()

        return {
            "success": True,
            "updated_fields": list(fields.keys()),
            "rows_affected": c.rowcount,
        }

# update US Entry / Exit & Physical Presence
@mcp.tool()
def update_individual_us_presence(
    practice_id: str,
    reference: str,
    first_entry_date_us: Optional[str] = None,
    last_exit_date_us: Optional[str] = None,
    days_in_us_current_year: Optional[int] = None,
    days_in_us_prev_year: Optional[int] = None,
    days_in_us_prev2_years: Optional[int] = None,
) -> Dict[str, Any]:
    if reference.lower() != "individual":
        return {"success": False}

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {}
        for k, v in {
            "first_entry_date_us": first_entry_date_us,
            "last_exit_date_us": last_exit_date_us,
            "days_in_us_current_year": days_in_us_current_year,
            "days_in_us_prev_year": days_in_us_prev_year,
            "days_in_us_prev2_years": days_in_us_prev2_years,
        }.items():
            if v is not None:
                fields[k] = v

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}

# update Treaty Claim Details
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

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {}
        for k, v in locals().items():
            if k in [
                "treaty_claimed", "treaty_country", "treaty_article",
                "treaty_income_type", "treaty_exempt_amount",
                "resident_of_treaty_country"
            ] and v is not None:
                fields[k] = v

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        c = conn.cursor()
        c.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}

# update Income Buckets (W-2 / 1042-S / Investment / Rental)
@mcp.tool()
def update_individual_income_amounts(
    practice_id: str,
    reference: str,
    w2_wages_amount: Optional[float] = None,
    scholarship_1042s_amount: Optional[float] = None,
    interest_amount: Optional[float] = None,
    dividend_amount: Optional[float] = None,
    capital_gains_amount: Optional[float] = None,
    rental_income_amount: Optional[float] = None,
    self_employment_eci_amount: Optional[float] = None,
) -> Dict[str, Any]:

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {
            k: v for k, v in locals().items()
            if k.endswith("_amount") and v is not None
        }

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}

# Federal Withholding update
@mcp.tool()
def update_individual_withholding(
    practice_id: str,
    reference: str,
    federal_withholding_w2: Optional[float] = None,
    federal_withholding_1042s: Optional[float] = None,
    tax_withheld_1099: Optional[float] = None,
) -> Dict[str, Any]:

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {}
        if federal_withholding_w2 is not None:
            fields["federal_withholding_w2"] = federal_withholding_w2
        if federal_withholding_1042s is not None:
            fields["federal_withholding_1042s"] = federal_withholding_1042s
        if tax_withheld_1099 is not None:
            fields["tax_withheld_1099"] = tax_withheld_1099

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}

# update Forms Availability Flags
@mcp.tool()
def update_individual_forms_flags(
    practice_id: str,
    reference: str,
    has_w2: Optional[str] = None,
    has_1042s: Optional[str] = None,
    has_1099: Optional[str] = None,
    has_k1: Optional[str] = None,
) -> Dict[str, Any]:

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {}
        for k, v in {
            "has_w2": has_w2,
            "has_1042s": has_1042s,
            "has_1099": has_1099,
            "has_k1": has_k1,
        }.items():
            if v is not None:
                fields[k] = v

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        c = conn.cursor()
        c.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}

# update Itemized Deductions & Education
@mcp.tool()
def update_individual_deductions_and_education(
    practice_id: str,
    reference: str,
    itemized_state_local_tax: Optional[float] = None,
    itemized_charity: Optional[float] = None,
    itemized_casualty_losses: Optional[float] = None,
    education_expenses: Optional[float] = None,
    student_loan_interest: Optional[float] = None,
    dependents_count: Optional[int] = None,
) -> Dict[str, Any]:

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {
            k: v for k, v in locals().items()
            if k not in ["practice_id", "reference"] and v is not None
        }

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        cur = conn.cursor()
        cur.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}

# update Refund & Bank Details
@mcp.tool()
def update_individual_refund_details(
    practice_id: str,
    reference: str,
    refund_method: Optional[str] = None,
    bank_routing: Optional[str] = None,
    bank_account_last4: Optional[str] = None,
) -> Dict[str, Any]:

    table, pk_col = _get_table_and_pk("individual")

    with get_connection() as conn:
        rid = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if not rid:
            return {"success": False}

        fields = {}
        if refund_method is not None:
            fields["refund_method"] = refund_method
        if bank_routing is not None:
            fields["bank_routing"] = bank_routing
        if bank_account_last4 is not None:
            fields["bank_account_last4"] = bank_account_last4[-4:]

        built = _build_update_query(table, pk_col, rid, fields)
        if not built:
            return {"success": False}

        q, p = built
        c = conn.cursor()
        c.execute(q, p)
        conn.commit()

        return {"success": True, "updated_fields": list(fields.keys())}


if __name__ == "__main__":
    mcp.run()
