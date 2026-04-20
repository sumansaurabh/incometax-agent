def remove_duplicates(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        key = str(sorted(row.items()))
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out
