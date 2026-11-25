"""Fails CI when the mutation score drops below a floor.

mutmut has no fail_under setting, so this reads the stats file that
`mutmut export-cicd-stats` writes and applies the floor itself.

Usage: python scripts/check_mutation_score.py <floor-percent>
"""

import json
import sys
from pathlib import Path

STATS_FILE = Path("mutants/mutmut-cicd-stats.json")


def main(argv: list[str]) -> int:
    floor = float(argv[0])
    stats = json.loads(STATS_FILE.read_text())

    tested = stats["total"] - stats["skipped"]
    caught = stats["killed"] + stats["timeout"]
    score = 100 * caught / tested if tested else 0.0

    print(f"Mutation score: {score:.1f}% ({caught}/{tested} mutants caught), floor {floor:.0f}%")
    if score < floor:
        print("Below the floor. Run `uv run mutmut results` to see which mutants survived.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
