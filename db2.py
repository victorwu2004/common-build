"""DB2 connectivity: connection, schema introspection, and read-only execution.

Uses ibm_db / ibm_db_dbi (IBM's official driver). Install with: pip install ibm_db
Catalog views here are for DB2 LUW (SYSCAT.*). For DB2 z/OS use SYSIBM.*
and for DB2 for i use QSYS2.* — see notes in get_schema().
"""

import os
import re
import ibm_db
import ibm_db_dbi


# ---- Safety: only SELECT / WITH allowed, everything else rejected ----
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|MERGE|"
    r"GRANT|REVOKE|CALL|COMMENT|RENAME|SET)\b",
    re.IGNORECASE,
)
_STARTS_OK = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)

DEFAULT_ROW_CAP = int(os.getenv("DB2_ROW_CAP", "500"))


class Db2:
    def __init__(self):
        conn_str = (
            f"DATABASE={os.environ['DB2_DATABASE']};"
            f"HOSTNAME={os.environ['DB2_HOSTNAME']};"
            f"PORT={os.environ.get('DB2_PORT', '50000')};"
            "PROTOCOL=TCPIP;"
            f"UID={os.environ['DB2_UID']};"
            f"PWD={os.environ['DB2_PWD']};"
        )
        # SECURITY=SSL is strongly recommended in production; append if configured.
        if os.getenv("DB2_USE_SSL", "").lower() in ("1", "true", "yes"):
            conn_str += "SECURITY=SSL;"
        self._raw = ibm_db.connect(conn_str, "", "")
        self._conn = ibm_db_dbi.Connection(self._raw)
        self.schema_name = os.environ.get("DB2_SCHEMA", os.environ["DB2_UID"].upper())

    # -------- Schema introspection --------
    def get_schema(self) -> str:
        """Return a compact text description of tables, columns, and foreign keys.

        DB2 LUW catalog views are used below. To port:
          - z/OS:  SYSIBM.SYSCOLUMNS / SYSIBM.SYSRELS
          - for i: QSYS2.SYSCOLUMNS  / QSYS2.SYSCST + SYSREFCST
        """
        cur = self._conn.cursor()

        # Columns
        cur.execute(
            """
            SELECT TABNAME, COLNAME, TYPENAME, LENGTH, NULLS
            FROM SYSCAT.COLUMNS
            WHERE TABSCHEMA = ?
            ORDER BY TABNAME, COLNO
            """,
            (self.schema_name,),
        )
        tables: dict[str, list[str]] = {}
        for tab, col, typ, length, nulls in cur.fetchall():
            null_txt = "" if nulls == "Y" else " NOT NULL"
            tables.setdefault(tab, []).append(f"{col} {typ}({length}){null_txt}")

        # Foreign keys (greatly improves multi-table join quality)
        cur.execute(
            """
            SELECT TABNAME, REFTABNAME, FK_COLNAMES, PK_COLNAMES
            FROM SYSCAT.REFERENCES
            WHERE TABSCHEMA = ?
            """,
            (self.schema_name,),
        )
        fks = [
            f"{t}({fk.strip()}) -> {rt}({pk.strip()})"
            for t, rt, fk, pk in cur.fetchall()
        ]

        parts = [f"SCHEMA: {self.schema_name}", ""]
        for t, cols in sorted(tables.items()):
            parts.append(f"TABLE {t}:")
            parts.extend(f"  {c}" for c in cols)
            parts.append("")
        if fks:
            parts.append("FOREIGN KEYS:")
            parts.extend(f"  {fk}" for fk in fks)
        return "\n".join(parts)

    # -------- Validation --------
    @staticmethod
    def validate(sql: str) -> str:
        sql = sql.strip().rstrip(";")
        if not _STARTS_OK.match(sql):
            raise ValueError("Only SELECT / WITH queries are permitted.")
        if _FORBIDDEN.search(sql):
            raise ValueError("Statement contains a forbidden (non-read-only) keyword.")
        if "FETCH FIRST" not in sql.upper() and "LIMIT" not in sql.upper():
            sql = f"{sql} FETCH FIRST {DEFAULT_ROW_CAP} ROWS ONLY"
        return sql

    # -------- Execution (read-only) --------
    def run_query(self, sql: str) -> dict:
        safe_sql = self.validate(sql)
        cur = self._conn.cursor()
        cur.execute(safe_sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        return {
            "sql": safe_sql,
            "columns": cols,
            "row_count": len(rows),
            "rows": [
                {c: (str(v) if v is not None else None) for c, v in zip(cols, r)}
                for r in rows
            ],
        }

    def close(self):
        try:
            ibm_db.close(self._raw)
        except Exception:
            pass
