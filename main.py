"""PropertyGuru daily property search agent — dispatcher.

Pipeline runs in three steps (analysis is done by Claude via a skill, not an API call):
  1. `python main.py scrape`    — scrape + filter, write data/pending_analysis.json
  2. Claude runs the `analyze-listings` skill on data/pending_analysis.json
  3. `python main.py finalize`  — persist, update state, write data/email_output.json
"""

import sys

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("scrape", "finalize"):
        raise SystemExit("Usage: python main.py {scrape|finalize}")

    if sys.argv[1] == "scrape":
        import scrape
        scrape.main()
    else:
        import finalize
        finalize.main()
