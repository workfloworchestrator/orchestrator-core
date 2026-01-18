# Copyright 2019-2025 SURF, GÉANT.
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

"""Schemas for agent graph structure."""

from pydantic import BaseModel


class GraphNode(BaseModel):
    """A node in the graph."""

    id: str
    label: str
    description: str | None


class GraphEdge(BaseModel):
    """An edge connecting two nodes."""

    source: str
    target: str
    label: str | None


class GraphStructure(BaseModel):
    """Response model for graph structure visualization."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    start_node: str
