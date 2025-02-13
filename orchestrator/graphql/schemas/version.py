import strawberry


@strawberry.type
class VersionType:
    application_versions: list[str]
