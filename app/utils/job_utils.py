import hashlib


def make_dedup_hash(title: str, company: str, location: str, apply_url: str) -> str:
    """
    SHA-256 hash of normalized job fields used for deduplication.
    Fields are separated by '|' to prevent concatenation collisions
    (e.g. title="ab|cd" vs title="ab", company="cd" produce different hashes).
    """
    raw = "|".join([
        title.lower().strip(),
        company.lower().strip(),
        location.lower().strip(),
        apply_url.lower().strip(),
    ])
    return hashlib.sha256(raw.encode()).hexdigest()
