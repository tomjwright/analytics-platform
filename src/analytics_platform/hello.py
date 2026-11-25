"""Hello-world job task: proves a deploy reached the right catalog.

Prints one JSON log line, the format every later task will use (ticket 14).
Usage: python hello.py --catalog <catalog>
"""

import sys


def build_log_line(catalog: str) -> str:
    # TODO return a JSON string (json.dumps) with three keys:
    #   "event": "hello", "catalog": the catalog, and "status": "ok".
    raise NotImplementedError


def main(argv: list[str]) -> int:
    # TODO parse --catalog with argparse, print build_log_line(catalog), return 0.
    # Stretch: once this runs on Databricks, write the line to <catalog>.ops.hello.
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
