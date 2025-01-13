def validate_data_version(current_version: int, new_version: int | None = None) -> bool:
    return (new_version is not None and new_version == current_version) or new_version is None
