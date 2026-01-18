import argparse

from .run import run_benchmark


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emb_bench", description="Embedding benchmark suite")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run benchmark")
    run_p.add_argument("--config", required=True, help="Path to config.yaml")
    run_p.add_argument("--phase", choices=["mrl", "local_vs_remote"], required=True)
    run_p.add_argument("--subset-docs", type=int, default=None)
    run_p.add_argument("--subset-queries", type=int, default=None)
    run_p.add_argument("--warmup", type=int, default=None)
    run_p.add_argument("--concurrency", type=int, default=None)

    args = parser.parse_args(argv)

    if args.cmd == "run":
        run_benchmark(
            config_path=args.config,
            phase=args.phase,
            subset_docs=args.subset_docs,
            subset_queries=args.subset_queries,
            warmup_calls=args.warmup,
            concurrency=args.concurrency,
        )
        return 0

    return 2
