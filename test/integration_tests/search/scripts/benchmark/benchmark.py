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


import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console

from orchestrator.db import db

from ...helpers import load_benchmark_queries, load_model_configs
from .display import display_benchmark_results

console = Console()


@dataclass
class BenchmarkResult:
    """Results from benchmarking a single query with a model."""

    query_text: str
    model_name: str
    latency_ms: float
    result_count: int
    top_results: list[str]
    scores: list[float]
    search_type: str
    rank_correlation: float | None = None
    top_k_overlap: dict[int, float] | None = None
    expected_ranking: list[str] | None = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON."""
        from dataclasses import asdict

        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "BenchmarkResult":
        """Deserialize from dictionary, fixing JSON type conversions."""
        # Fix: JSON serializes dict keys as strings, convert back to int
        if data.get("top_k_overlap"):
            data["top_k_overlap"] = {int(k): v for k, v in data["top_k_overlap"].items()}
        return cls(**data)


async def run_benchmark() -> None:
    """Run benchmark comparing multiple embedding models on search ranking quality.

    Each model runs in a separate subprocess to avoid SQLAlchemy Vector dimension caching.
    This ensures each model gets a fresh Python environment with correct Vector dimensions.
    Results are written to temp files.
    """
    console.print("Starting embedding model benchmark")

    queries = load_benchmark_queries()
    models = load_model_configs()

    console.print(f"Loaded {len(queries)} benchmark queries and {len(models)} model configurations")

    all_results = []

    for model in models:
        console.print(f"\nTesting model: {model.name} (dimension: {model.dimension})")

        # Create temp file for results
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            results_file = f.name

        try:
            # Run subprocess with model-specific environment
            result = subprocess.run(  # noqa: S603
                [sys.executable, str(Path(__file__).parent / "single_model.py")],
                capture_output=True,
                text=True,
                check=True,
                env={
                    **os.environ,
                    "PYTHONPATH": str(Path(__file__).parent.parent.parent.parent.parent.parent),
                    "DATABASE_URI": db.engine.url.render_as_string(hide_password=False),
                    "MODEL_NAME": model.name,
                    "MODEL_ID": model.model,
                    "DIMENSION": str(model.dimension),
                    "OUTPUT_FILE": results_file,
                },
            )

            # Show subprocess output (progress messages)
            if result.stdout:
                console.print(result.stdout)

            # Load results from temp file
            with open(results_file) as f:
                model_results = json.load(f)
                all_results.extend(model_results)

            console.print(f"Completed {model.name}")

        except subprocess.CalledProcessError as e:
            console.print(f"[red]Failed to benchmark {model.name}[/red]")
            console.print(f"Error: {e.stderr}")
            raise
        finally:
            Path(results_file).unlink(missing_ok=True)

    results = [BenchmarkResult.from_dict(r) for r in all_results]

    display_benchmark_results(results, queries, models)
