# Copyright 2022-2023 SURF.
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Any

import structlog
from graphql import GraphQLField, GraphQLResolveInfo
from graphql.pyutils import Path
from strawberry.extensions import SchemaExtension
from strawberry.field import StrawberryField
from strawberry.types.types import TypeDefinition

from orchestrator.utils.helpers import to_camel

logger = structlog.get_logger()


DeprecatedPaths = dict[str, str]


def get_path_as_string(path: Path) -> str:
    if path.prev:
        return f"{get_path_as_string(path.prev)}/{path.key}"
    return f"{path.key}"


def get_root_path(path: Path) -> Path:
    while path.prev:
        path = path.prev
    return path


def get_field_deprecation(info: GraphQLResolveInfo) -> str | None:
    field = info.parent_type.fields.get(info.field_name)
    if isinstance(field, GraphQLField):
        return field.deprecation_reason
    return None


class DeprecationCheckerExtension(SchemaExtension):
    deprecated_queries: DeprecatedPaths = {}
    deprecated_mutations: DeprecatedPaths = {}

    def resolve(self, _next: Any, root: Any, info: GraphQLResolveInfo, *args: Any, **kwargs: Any) -> Any:
        pathstring = get_path_as_string(info.path)
        root_type = get_root_path(info.path).typename

        reason = None
        if root_type == "Query":
            reason = self.deprecated_queries.get(pathstring)
        elif root_type == "Mutation":
            reason = self.deprecated_mutations.get(pathstring)

        if reason:
            logger.warning("Use of deprecated path", type=root_type, path=pathstring, deprecation_reason=repr(reason))
        elif field_deprecation := get_field_deprecation(info):
            logger.warning(
                "Use of deprecated field",
                field=info.field_name,
                type=info.parent_type.name,
                path=pathstring,
                deprecation_reason=repr(field_deprecation),
            )

        return _next(root, info, *args, **kwargs)


def get_deprecated_paths(type_definition: TypeDefinition) -> DeprecatedPaths:
    """Find all deprecated paths in the given Strawberry type.

    Returns:
        mapping of deprecated paths to deprecation reasons
    """
    to_inspect: list[tuple[list[str], list[StrawberryField]]] = [([], type_definition.fields)]
    deprecated_paths = {}
    while to_inspect:
        path, fields = to_inspect.pop()
        for field in fields:
            field_path = path + [to_camel(field.name)]
            if field.deprecation_reason:
                deprecated_paths["/".join(field_path)] = field.deprecation_reason
            elif hasattr(field.type, "__strawberry_definition__") and field.type.__strawberry_definition__.fields:
                to_inspect.append((field_path, field.type.__strawberry_definition__.fields))
    return deprecated_paths


def make_deprecation_checker_extension(
    query: type | None = None, mutation: type | None = None
) -> type[DeprecationCheckerExtension]:
    def deprecations_for(_type: type | None) -> DeprecatedPaths:
        type_def: TypeDefinition | None = getattr(_type, "__strawberry_definition__", None) if _type else None
        if not type_def:
            return {}
        return get_deprecated_paths(type_def) if type_def else {}

    deprecated_queries = deprecations_for(query)
    deprecated_mutations = deprecations_for(mutation)

    logger.debug("Deprecations", queries=",".join(deprecated_queries), mutations=",".join(deprecated_mutations))

    # Modify class in-place; a bit dirty, but not dirty enough to warrant some metaclass-fu?
    DeprecationCheckerExtension.deprecated_queries = deprecated_queries
    DeprecationCheckerExtension.deprecated_mutations = deprecated_mutations
    return DeprecationCheckerExtension
