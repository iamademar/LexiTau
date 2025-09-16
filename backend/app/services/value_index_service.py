from datasketch import MinHash, MinHashLSH
from typing import Dict, List, Iterable, Tuple, Optional, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

def _kshingles(s: str, k: int = 4) -> Iterable[str]:
    s = s.strip().lower()
    if len(s) < k:
        return [s]
    return [s[i:i+k] for i in range(len(s)-k+1)]

def _minhash_from_values(values: Iterable[str], num_perm: int = 128, k: int = 4) -> MinHash:
    m = MinHash(num_perm=num_perm)
    for v in values:
        for sh in _kshingles(str(v), k=k):
            m.update(sh.encode("utf-8"))
    return m

class ValueLSHIndex:
    """
    In-memory LSH over per-column MinHashes (built from distinct samples / top_k values).
    Query: give a literal -> candidate (table, column) pairs likely to contain it.
    """
    def __init__(self, threshold: float = 0.4, num_perm: int = 128, k: int = 4):
        self.threshold = threshold
        self.num_perm = num_perm
        self.k = k
        self.lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
        self._col_mh: Dict[int, MinHash] = {}
        self._id_to_field: Dict[int, Tuple[str, str]] = {}
        self._is_built = False

    def build_from_db(self, db: Session) -> None:
        """Build the LSH index from database column profiles."""
        logger.info("Building ValueLSHIndex from database...")

        rows = db.execute(text("""
          SELECT id, table_name, column_name, top_k_values, distinct_sample
          FROM column_profiles
          WHERE (top_k_values IS NOT NULL OR distinct_sample IS NOT NULL)
        """)).mappings().all()

        processed_count = 0
        for r in rows:
            samples = []
            if isinstance(r["top_k_values"], list):
                for kv in r["top_k_values"]:
                    samples.append(str(kv.get("value") if isinstance(kv, dict) else kv))
            if isinstance(r["distinct_sample"], list):
                samples.extend([str(x) for x in r["distinct_sample"]])
            if not samples:
                continue

            try:
                mh = _minhash_from_values(samples, num_perm=self.num_perm, k=self.k)
                self._col_mh[r["id"]] = mh
                self._id_to_field[r["id"]] = (r["table_name"], r["column_name"])
                self.lsh.insert(str(r["id"]), mh)
                processed_count += 1
            except Exception as e:
                logger.warning(f"Failed to process column {r['table_name']}.{r['column_name']}: {e}")

        self._is_built = True
        logger.info(f"ValueLSHIndex built with {processed_count} columns")

    def lookup_literal(self, literal: str) -> List[Tuple[str, str]]:
        """
        Find columns that likely contain the given literal.

        Args:
            literal: The literal value to search for

        Returns:
            List of (table_name, column_name) tuples
        """
        if not self._is_built:
            logger.warning("Index not built yet. Call build_from_db() first.")
            return []

        if not literal or not literal.strip():
            return []

        try:
            q = _minhash_from_values([literal], num_perm=self.num_perm, k=self.k)
            ids = [int(x) for x in self.lsh.query(q)]
            return [self._id_to_field[i] for i in ids if i in self._id_to_field]
        except Exception as e:
            logger.warning(f"Failed to lookup literal '{literal}': {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the index."""
        return {
            "is_built": self._is_built,
            "num_columns": len(self._col_mh),
            "num_fields_mapped": len(self._id_to_field),
            "threshold": self.threshold,
            "num_perm": self.num_perm,
            "k": self.k,
        }

    def is_built(self) -> bool:
        """Check if the index has been built."""
        return self._is_built

    def clear(self) -> None:
        """Clear the index."""
        self.lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)
        self._col_mh.clear()
        self._id_to_field.clear()
        self._is_built = False

    def get_candidate_columns_for_table(self, table_name: str) -> List[str]:
        """Get all columns for a specific table that are indexed."""
        return [
            col_name for (tbl_name, col_name) in self._id_to_field.values()
            if tbl_name == table_name
        ]
