# EVAL LIVE — the squad, run constantly

Del's order, hackathon day: run the sim constantly against the
event key and log every run, scored the same way as EVAL.md,
against the same bibles. The shipped site keeps the verified
runs from this morning; these are fresh runs, warts kept. A run
that hits the spend cap (429) stops the loop and says so here.

The Duck file is a famous case and lives in the models'
training data; its scores carry that caveat, as in EVAL.md.

| time (UTC) | case | steps | dropped | checks | failed checks |
|---|---|---|---|---|---|
| 19:10:53 | delgado-2019 | 11/11 | 9 | 3/4 | top lead 80 |
| 19:25:04 | screens-2025 | 11/11 | 1 | 3/3 | none |
| 19:44:19 | harborlight-2016 | 11/11 | 1 | 3/4 | top lead names Herrera |
| 20:14:52 | delgado-2019 | 11/11 | 0 | 3/4 | top lead 80 |

> Retired November 21: the Duck rows were removed by the builders. That case is solved and its verdict sat inside its own file, so its runs tested reading, not detection. The Starlite File replaces it in the rotation.
