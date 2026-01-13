import os
from typing import Any, Dict, Optional, Tuple, List, TYPE_CHECKING

if TYPE_CHECKING:
    from mysql.connector.connection import MySQLConnection

from connection import get_connection

def _resolve_practice_id_from_reference_id(
    conn: get_connection,
    reference: str,
    reference_id: int,
) -> Optional[str]:
    """
    Reverse lookup:
      internal_data.reference + internal_data.reference_id -> internal_data.practice_id
    """
    ref_type = (reference or "").lower().strip()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        """
        SELECT practice_id
        FROM internal_data
        WHERE reference = %s AND reference_id = %s
        LIMIT 1
        """,
        (ref_type, reference_id),
    )
    row = cursor.fetchone()
    return row.get("practice_id") if row else None


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

def get_individual_associated_clients(practice_id: str, reference: str) -> Dict[str, Any]:
    """
    Purpose:
      For a logged-in MAIN individual, return associated clients split into:
        1) Sub clients who are individuals (chat supported)
        2) Sub clients who are companies   (not chat supported in 1040NR flow)

    Sources:
      A) Manual Associations:
         - client_association_details:
           1) find association_id rows where reference_id = main_individual_id and reference='individual'
           2) fetch all rows for those association_id
      B) Automatic Associations:
         - title table:
           select rows where individual_id = main_individual_id and percentage IS NOT NULL and status=1
           These represent company links (ownership/role).

    Returns:
      {
        "reference": "individual",
        "practice_id": "<main_practice_id>",
        "main_individual_id": <int>,
        "manual": {
          "individual_associations": [...],
          "company_associations": [...]
        },
        "automatic": {
          "company_associations": [...]
        },
        "combined": {
          "individual_associations": [...],
          "company_associations": [...]
        }
      }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "message": "This tool only supports reference='individual' for 1040NR flow.",
            "manual": {"individual_associations": [], "company_associations": []},
            "automatic": {"company_associations": []},
            "combined": {"individual_associations": [], "company_associations": []},
        }

    with get_connection() as conn:
        main_individual_id = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if main_individual_id is None:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "success": False,
                "message": "Main individual not found for this practice_id.",
                "manual": {"individual_associations": [], "company_associations": []},
                "automatic": {"company_associations": []},
                "combined": {"individual_associations": [], "company_associations": []},
            }

        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT DISTINCT association_id
            FROM client_association_details
            WHERE reference_id = %s
              AND LOWER(reference) = 'individual'
              AND status = 1
            """,
            (main_individual_id,),
        )
        assoc_rows = cursor.fetchall() or []
        association_ids = [int(r["association_id"]) for r in assoc_rows if r.get("association_id") is not None]

        manual_individuals: List[Dict[str, Any]] = []
        manual_companies: List[Dict[str, Any]] = []

        if association_ids:
            placeholders = ",".join(["%s"] * len(association_ids))
            cursor.execute(
                f"""
                SELECT
                  id,
                  association_id,
                  association_type,
                  reference_id,
                  reference,
                  client_id,
                  client_name,
                  status,
                  association_main_type,
                  client_association_status
                FROM client_association_details
                WHERE association_id IN ({placeholders})
                  AND status = 1
                ORDER BY association_id ASC, id ASC
                """,
                tuple(association_ids),
            )
            rows = cursor.fetchall() or []

            for r in rows:
                sub_ref = (r.get("reference") or "").lower().strip()
                sub_reference_id = r.get("reference_id")
                sub_reference_id_int = int(sub_reference_id) if sub_reference_id is not None else None

                sub_practice_id = None
                if sub_reference_id_int is not None and sub_ref in ("individual", "company"):
                    sub_practice_id = _resolve_practice_id_from_reference_id(conn, sub_ref, sub_reference_id_int)

                item = {
                    "association_id": r.get("association_id"),
                    "association_type": r.get("association_type"),          
                    "association_main_type": r.get("association_main_type"),
                    "reference": sub_ref,                                   
                    "reference_id": sub_reference_id_int,
                    "practice_id": sub_practice_id,                         
                    "client_id": r.get("client_id"),
                    "client_name": r.get("client_name"),
                    "chat_supported": (sub_ref == "individual"),           
                }

                if sub_ref == "individual":
                    manual_individuals.append(item)
                elif sub_ref == "company":
                    manual_companies.append(item)

        cursor.execute(
            """
            SELECT
              id,
              company_id,
              individual_id,
              title,
              percentage,
              status,
              association_type,
              client_association_status
            FROM title
            WHERE individual_id = %s
              AND percentage IS NOT NULL
              AND status = 1
            """,
            (main_individual_id,),
        )
        auto_rows = cursor.fetchall() or []
        automatic_companies: List[Dict[str, Any]] = []

        for r in auto_rows:
            company_id = r.get("company_id")
            company_id_int = int(company_id) if company_id is not None else None

            company_practice_id = None
            if company_id_int is not None:
                company_practice_id = _resolve_practice_id_from_reference_id(conn, "company", company_id_int)

            automatic_companies.append(
                {
                    "association_type": r.get("association_type") or "Automatic",
                    "reference": "company",
                    "reference_id": company_id_int,
                    "practice_id": company_practice_id,   
                    "title": r.get("title"),
                    "percentage": float(r["percentage"]) if r.get("percentage") is not None else None,
                    "chat_supported": False,        
                }
            )

        combined_individuals = manual_individuals
        combined_companies = manual_companies + automatic_companies

        return {
            "reference": "individual",
            "practice_id": practice_id,
            "main_individual_id": main_individual_id,
            "success": True,
            "manual": {
                "individual_associations": manual_individuals,
                "company_associations": manual_companies,
            },
            "automatic": {
                "company_associations": automatic_companies,
            },
            "combined": {
                "individual_associations": combined_individuals,
                "company_associations": combined_companies,
            },
        }