from __future__ import annotations

import asyncio
import json
from pathlib import Path

from itx_workers.quality.parser_scorecard import build_scorecard, load_case_bank


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    case_bank_path = repo_root / "tests" / "fixtures" / "synthetic_docs" / "parser_regression_cases.json"
    scorecard = await build_scorecard(load_case_bank(case_bank_path))
    print(json.dumps(scorecard, indent=2, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())