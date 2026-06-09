from __future__ import annotations

import argparse

from runner.match_runner import run_match
from runner.tournament_runner import format_match_progress, run_tournament, summarize_tournament


def main() -> None:
    parser = argparse.ArgumentParser(description="Run corridor AI matches and tournaments.")
    sub = parser.add_subparsers(dest="command", required=True)

    match = sub.add_parser("match")
    match.add_argument("--p1", required=True)
    match.add_argument("--p2", required=True)
    match.add_argument("--log", default=None)
    match.add_argument("--seed", type=int, default=None)
    match.add_argument("--timeout", type=float, default=1.0)

    tournament = sub.add_parser("tournament")
    tournament.add_argument("--p1", required=True)
    tournament.add_argument("--p2", required=True)
    tournament.add_argument("--games", type=int, default=100)
    tournament.add_argument("--results", default="results/results.csv")
    tournament.add_argument("--seed", type=int, default=None)
    tournament.add_argument("--timeout", type=float, default=1.0)

    args = parser.parse_args()
    if args.command == "match":
        result = run_match(args.p1, args.p2, log_file=args.log, seed=args.seed, timeout_seconds=args.timeout)
        print(result.to_csv_row())
    else:
        results = run_tournament(
            args.p1,
            args.p2,
            games=args.games,
            results_file=args.results,
            seed=args.seed,
            timeout_seconds=args.timeout,
            on_match_complete=lambda index, total, result: print(format_match_progress(index, total, result), flush=True),
        )
        print(f"Wrote {len(results)} results to {args.results}")
        print(summarize_tournament(results))


if __name__ == "__main__":
    main()
