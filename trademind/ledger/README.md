# Research ledger

Append-only record of what has been tested, kept in git so it survives new machines and fresh
databases (`docs/DECISIONS.md` D29). Written by the CLI; never edit or delete lines by hand.

- `hypotheses.jsonl`: each distinct hypothesis (strategy, version, timeframe, parameters) ever
  backtested on real research data. The promotion gate's Bonferroni correction counts these lines.
- `holdout_looks.jsonl`: each holdout evaluation. A strategy gets `validation.max_holdout_evals`
  looks per holdout window, whatever its version, timeframe or parameters.

`trademind validate` refuses to run while this folder has uncommitted changes. After a research
backtest or a validation, commit it:

    git add ledger && git commit -m "ledger"
