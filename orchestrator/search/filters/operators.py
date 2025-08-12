from enum import Enum


class FilterOp(str, Enum):
    EQ = "eq"
    NEQ = "neq"
    LT = "lt"
    LIKE = "like"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    BETWEEN = "between"

    MATCHES_LQUERY = "matches_lquery"  # The ~ operator for wildcard matching
    IS_ANCESTOR = "is_ancestor"  # The @> operator
    IS_DESCENDANT = "is_descendant"  # The <@ operator
    PATH_EXISTS = "path_exists"
