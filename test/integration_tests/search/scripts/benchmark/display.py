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


from collections import defaultdict

from rich.console import Console
from rich.table import Table

from ...fixtures import TEST_SUBSCRIPTIONS

console = Console()


def display_ranking_comparison(query_results, expected_ranking: list[str]) -> None:
    """Display side-by-side ranking comparison with visual indicators (✓/⚠/✗)."""
    if not expected_ranking:
        return

    # Build mapping from subscription_id to description (truncated to 50 chars)
    id_to_desc = {
        str(sub["subscription_id"]): (
            str(sub["description"])[:47] + "..." if len(str(sub["description"])) > 50 else str(sub["description"])
        )
        for sub in TEST_SUBSCRIPTIONS
    }

    # Create comparison table
    comparison_table = Table(show_header=True, box=None)
    comparison_table.add_column("Rank", justify="center", width=5)
    comparison_table.add_column("Ground Truth", width=55)

    for result in query_results:
        comparison_table.add_column(result.model_name, width=55)

    max_rank = min(5, len(expected_ranking))
    for rank in range(max_rank):
        expected_id = expected_ranking[rank] if rank < len(expected_ranking) else None
        expected_desc = id_to_desc.get(expected_id, expected_id) if expected_id else "—"
        row = [f"{rank + 1}", expected_desc]

        for result in query_results:
            if rank < len(result.top_results):
                predicted_id = result.top_results[rank]
                predicted_desc = id_to_desc.get(predicted_id, predicted_id)

                if predicted_id in expected_ranking:
                    expected_pos = expected_ranking.index(predicted_id)
                    if expected_pos == rank:
                        row.append(f"✓ {predicted_desc}")
                    else:
                        row.append(f"⚠ {predicted_desc} (exp: #{expected_pos + 1})")
                else:
                    row.append(f"✗ {predicted_desc}")
            else:
                row.append("—")

        comparison_table.add_row(*row)

    console.print(comparison_table)


def display_benchmark_results(results, queries, models) -> None:
    """Display benchmark results with simple metrics and visual comparisons."""
    from statistics import median

    # Group results by model
    results_by_model = defaultdict(list)
    for result in results:
        results_by_model[result.model_name].append(result)

    console.print("\n=== Summary by Model ===\n")
    summary_table = Table(show_header=True)
    summary_table.add_column("Model")
    summary_table.add_column("Median Latency", justify="right")
    summary_table.add_column("Median Rank Corr", justify="right")
    summary_table.add_column("Median Top-5 Overlap", justify="right")

    for model_name, model_results in results_by_model.items():
        median_latency = median(r.latency_ms for r in model_results)

        corr_values = [r.rank_correlation for r in model_results if r.rank_correlation is not None]
        top5_values = [r.top_k_overlap[5] for r in model_results if r.top_k_overlap and 5 in r.top_k_overlap]

        if corr_values:
            median_corr = median(corr_values)
            median_top5 = median(top5_values) if top5_values else 0.0
            summary_table.add_row(model_name, f"{median_latency:.1f}ms", f"{median_corr:.3f}", f"{median_top5:.1%}")
        else:
            summary_table.add_row(model_name, f"{median_latency:.1f}ms", "N/A", "N/A")

    console.print(summary_table)

    # Always show detailed per-query results
    for query in queries:
        console.print(f"\n=== Query: {query.query_text} ===")
        console.print(f"{query.description}\n")

        detail_table = Table(show_header=True)
        detail_table.add_column("Model")
        detail_table.add_column("Latency", justify="right")
        detail_table.add_column("Rank Corr (ρ)", justify="right")
        detail_table.add_column("Top-5 Overlap", justify="right")

        query_results = [r for r in results if r.query_text == query.query_text]
        for result in query_results:
            if result.rank_correlation is not None and result.top_k_overlap is not None:
                top5 = result.top_k_overlap.get(5, 0.0)
                detail_table.add_row(
                    result.model_name,
                    f"{result.latency_ms:.1f}ms",
                    f"{result.rank_correlation:.3f}",
                    f"{top5:.1%}",
                )
            else:
                detail_table.add_row(result.model_name, f"{result.latency_ms:.1f}ms", "N/A", "N/A")

        console.print(detail_table)

        if query.expected_ranking:
            console.print("\n=== Ranking Comparison (Top 5) ===")
            display_ranking_comparison(query_results, query.expected_ranking)
