def parse_problem_ids(range_str: str, available_ids: set[int]) -> list[int]:
    """Parse a problem ID range string like '0-9', '5', '0,3,7', or 'all'."""
    if range_str.lower() == "all":
        return sorted(available_ids)

    ids = []
    for part in range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            start, end = int(start), int(end)
            ids.extend(range(start, end + 1))
        else:
            ids.append(int(part))

    # 验证 ID 是否存在
    invalid_ids = set(ids) - available_ids
    if invalid_ids:
        raise ValueError(f"Invalid problem IDs: {sorted(invalid_ids)}")

    return sorted(set(ids))
