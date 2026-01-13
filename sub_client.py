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
      For a logged-in MAIN individual, return ONLY associated INDIVIDUAL sub-clients
      (chat supported in 1040NR flow).
 
    Manual Associations (client_association_details):
      - Find association_ids for this main individual (reference='individual', status=1)
      - Fetch rows for those association_ids
      - Return ONLY rows where:
          association_type = 'Sub Client'
          reference = 'individual'
          status = 1
 
    Automatic Associations (title):
      - Some title rows might represent links; for this requirement:
        return ONLY if there exists rows where reference='individual' from title table.
        (If your title table does NOT contain reference columns, this will return empty.)
 
    Returns:
      {
        "reference": "individual",
        "practice_id": "<main_practice_id>",
        "main_individual_id": <int>,
        "success": True|False,
        "manual": { "individual_associations": [...] },
        "automatic": { "individual_associations": [...] },
        "combined": { "individual_associations": [...] }
      }
    """
    ref_type = (reference or "").lower().strip()
    if ref_type != "individual":
        return {
            "reference": ref_type,
            "practice_id": practice_id,
            "success": False,
            "message": "This tool only supports reference='individual' for 1040NR flow.",
            "manual": {"individual_associations": []},
            "automatic": {"individual_associations": []},
            "combined": {"individual_associations": []},
        }
 
    with get_connection() as conn:
        main_individual_id = _resolve_reference_id_from_practice(conn, practice_id, "individual")
        if main_individual_id is None:
            return {
                "reference": "individual",
                "practice_id": practice_id,
                "main_individual_id": None,
                "success": False,
                "message": "Main individual not found for this practice_id.",
                "manual": {"individual_associations": []},
                "automatic": {"individual_associations": []},
                "combined": {"individual_associations": []},
            }
 
        cursor = conn.cursor(dictionary=True)
 
        # Manual associations
        cursor.execute(
            """
            SELECT
              cad_sub.association_id,
              cad_sub.association_type,
              cad_sub.association_main_type,
              cad_sub.reference_id AS sub_reference_id,
              idmap.practice_id AS sub_practice_id,
              cad_sub.client_id,
              cad_sub.client_name,
              cad_sub.client_association_status
            FROM client_association_details cad_main
            JOIN client_association_details cad_sub
              ON cad_sub.association_id = cad_main.association_id
             AND cad_sub.status = 1
             AND cad_sub.reference = 'individual'
             AND cad_sub.association_type = 'Sub Client'
            LEFT JOIN internal_data idmap
              ON idmap.reference = 'individual'
             AND idmap.reference_id = cad_sub.reference_id
            WHERE cad_main.reference_id = %s
              AND cad_main.reference = 'individual'
              AND cad_main.status = 1
            ORDER BY cad_sub.association_id ASC, cad_sub.id ASC
            """,
            (main_individual_id,),
        )
 
        manual_rows = cursor.fetchall() or []
        manual_individuals: List[Dict[str, Any]] = [
            {
                "association_id": r.get("association_id"),
                "association_type": r.get("association_type"),  # Sub Client
                "association_main_type": r.get("association_main_type"),
                "reference": "individual",
                "reference_id": int(r["sub_reference_id"]) if r.get("sub_reference_id") is not None else None,
                "practice_id": r.get("sub_practice_id"),
                "client_id": r.get("client_id"),
                "client_name": r.get("client_name"),
                "chat_supported": True,
                "client_association_status": r.get("client_association_status"),
            }
            for r in manual_rows
            if r.get("sub_reference_id") is not None
        ]
 
        # Automatic associations
        automatic_individuals: List[Dict[str, Any]] = []
        try:
            cursor.execute(
                """
                SELECT
                  reference_id,
                  association_type,
                  title,
                  percentage
                FROM title
                WHERE individual_id = %s
                  AND percentage IS NOT NULL
                  AND status = 1
                  AND reference = 'individual'
                """,
                (main_individual_id,),
            )
            auto_rows = cursor.fetchall() or []
            for r in auto_rows:
                ref_id = r.get("reference_id")
                if ref_id is None:
                    continue
                automatic_individuals.append(
                    {
                        "association_type": r.get("association_type") or "Automatic",
                        "reference": "individual",
                        "reference_id": int(ref_id),
                        "practice_id": None,
                        "title": r.get("title"),
                        "percentage": float(r["percentage"]) if r.get("percentage") is not None else None,
                        "chat_supported": True,
                    }
                )
        except Exception:
            automatic_individuals = []
 
        combined_individuals = manual_individuals + automatic_individuals
 
        return {
            "reference": "individual",
            "practice_id": practice_id,
            "main_individual_id": main_individual_id,
            "success": True,
            "manual": {"individual_associations": manual_individuals},
            "automatic": {"individual_associations": automatic_individuals},
            "combined": {"individual_associations": combined_individuals},
        }