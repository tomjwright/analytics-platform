"""Hello-world job task: proves a deploy reached the right catalog.

Prints one JSON log line, the format every later task will use (ticket 14).
Usage: python hello.py --catalog <catalog>
"""

import argparse
import json
import sys


def build_log_line(catalog: str) -> str:
    return json.dumps({"event": "hello", "catalog": catalog, "status": "ok"})


def main(argv: list[str]) -> int:
    # Stretch: once this runs on Databricks, write the line to <catalog>.ops.hello.
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", required=True)
    args = parser.parse_args(argv)
    print(build_log_line(args.catalog))
    return 0


if __name__ == "__main__":
    exit_code = main(sys.argv[1:])
    if exit_code != 0:
        sys.exit(exit_code)
