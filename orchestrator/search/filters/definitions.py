from orchestrator.search.core.types import FieldType, FilterOp, UIType
from orchestrator.search.schemas.results import TypeDefinition, ValueSchema


def operators_for(ft: FieldType) -> list[FilterOp]:
    """Return the list of valid operators for a given FieldType."""
    return list(value_schema_for(ft).keys())


def value_schema_for(ft: FieldType) -> dict[FilterOp, ValueSchema]:
    """Return the value schema map for a given FieldType."""
    if ft in (FieldType.INTEGER, FieldType.FLOAT):
        return {
            FilterOp.EQ: ValueSchema(kind=UIType.NUMBER),
            FilterOp.NEQ: ValueSchema(kind=UIType.NUMBER),
            FilterOp.LT: ValueSchema(kind=UIType.NUMBER),
            FilterOp.LTE: ValueSchema(kind=UIType.NUMBER),
            FilterOp.GT: ValueSchema(kind=UIType.NUMBER),
            FilterOp.GTE: ValueSchema(kind=UIType.NUMBER),
            FilterOp.BETWEEN: ValueSchema(
                kind="object",
                fields={
                    "start": ValueSchema(kind=UIType.NUMBER),
                    "end": ValueSchema(kind=UIType.NUMBER),
                },
            ),
        }

    if ft == FieldType.BOOLEAN:
        return {
            FilterOp.EQ: ValueSchema(kind=UIType.BOOLEAN),
            FilterOp.NEQ: ValueSchema(kind=UIType.BOOLEAN),
        }

    if ft == FieldType.DATETIME:
        return {
            FilterOp.EQ: ValueSchema(kind=UIType.DATETIME),
            FilterOp.NEQ: ValueSchema(kind=UIType.DATETIME),
            FilterOp.LT: ValueSchema(kind=UIType.DATETIME),
            FilterOp.LTE: ValueSchema(kind=UIType.DATETIME),
            FilterOp.GT: ValueSchema(kind=UIType.DATETIME),
            FilterOp.GTE: ValueSchema(kind=UIType.DATETIME),
            FilterOp.BETWEEN: ValueSchema(
                kind="object",
                fields={
                    "start": ValueSchema(kind=UIType.DATETIME),
                    "end": ValueSchema(kind=UIType.DATETIME),
                },
            ),
        }

    return {
        FilterOp.EQ: ValueSchema(kind=UIType.STRING),
        FilterOp.NEQ: ValueSchema(kind=UIType.STRING),
    }


def generate_definitions() -> dict[UIType, TypeDefinition]:
    """Generate the full definitions dictionary for all UI types."""
    definitions = {}

    for ui_type in UIType:
        if ui_type == UIType.NUMBER:
            rep_ft = FieldType.INTEGER
        elif ui_type == UIType.DATETIME:
            rep_ft = FieldType.DATETIME
        elif ui_type == UIType.BOOLEAN:
            rep_ft = FieldType.BOOLEAN
        else:
            rep_ft = FieldType.STRING

        definitions[ui_type] = TypeDefinition(
            operators=operators_for(rep_ft),
            valueSchema=value_schema_for(rep_ft),
        )
    return definitions
