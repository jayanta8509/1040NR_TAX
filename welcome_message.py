from typing import Any, Dict, List, Optional, Tuple
from connection import get_connection

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



def get_client_welcome_message(
    client_id: int,
    reference: str,
) -> Dict[str, Any]:
    """
    Purpose:
        Return a personalized welcome message for the logged-in client.

        The message format is:
            "Welcome, {first_name}. Would you like me to help you with your
             \"1040NR non-resident tax filing\"?"

        For:
        - Individual clients: attempts to use individual.first_name.
        - Company clients: attempts to use the primary contact's first_name
          from contact_info; if not available, falls back to company.contact_name,
          and finally to the first token of company.name.

    Args:
        client_id (int):
            Global client ID used by your application (typically internal_data.id).
        reference (str):
            Client type: "company" or "individual" (case-insensitive).
    """
    ref_type = reference.lower()

    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        resolved_id = _resolve_reference_id(conn, client_id, ref_type)

        first_name: str | None = None
        display_name_source: str = "fallback"

        if ref_type == "individual":
            cursor.execute(
                """
                SELECT first_name, middle_name, last_name
                FROM individual
                WHERE id = %s
                LIMIT 1
                """,
                (resolved_id,),
            )
            row = cursor.fetchone()
            if row and row.get("first_name"):
                first_name = (row["first_name"] or "").strip()
                display_name_source = "individual"


        elif ref_type == "company":
            cursor.execute(
                """
                SELECT first_name, last_name
                FROM contact_info
                WHERE reference = %s
                  AND reference_id = %s
                ORDER BY status DESC, id ASC
                LIMIT 1
                """,
                (ref_type, resolved_id),
            )
            contact_row = cursor.fetchone()
            if contact_row and contact_row.get("first_name"):
                first_name = (contact_row["first_name"] or "").strip()
                display_name_source = "contact_info"

            if not first_name:
                cursor.execute(
                    """
                    SELECT name, contact_name
                    FROM company
                    WHERE company_id = %s
                    LIMIT 1
                    """,
                    (resolved_id,),
                )
                comp_row = cursor.fetchone() or {}
                contact_name = (comp_row.get("contact_name") or "").strip()
                company_name = (comp_row.get("name") or "").strip()

                if contact_name:
                    first_name = contact_name.split()[0]
                    display_name_source = "company_contact_name"
                elif company_name:
                    first_name = company_name.split()[0]
                    display_name_source = "company_name"

        if not first_name:
            first_name = "there"
            display_name_source = "fallback"

        welcome_message = (
            f'Welcome, {first_name}. '
            'Would you like me to help you with your "1040NR non-resident tax filing"?'
        )

        return {
            "reference": ref_type,
            "client_id": client_id,
            "reference_id": resolved_id,
            "first_name": first_name,
            "display_name_source": display_name_source,
            "welcome_message": welcome_message,
        }