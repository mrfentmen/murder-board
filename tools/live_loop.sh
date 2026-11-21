#!/bin/bash
cd ~/workspace/murder-board-repo
LOG=live-eval/loop.log
echo "[loop] start $(date -u +%H:%M:%S)" >> $LOG
while true; do
  hour=$(TZ=America/New_York date +%H); min=$(TZ=America/New_York date +%M)
  if [ "$hour" -gt 16 ] || { [ "$hour" -eq 16 ] && [ "$min" -ge 30 ]; }; then
    echo "[loop] 16:30 ET reached, stopping $(date -u +%H:%M:%S)" >> $LOG; break
  fi
  for CASE in delgado-2019 screens-2025 harborlight-2016 duck-2020; do
    [ -f live-eval/STOP ] && { echo "[loop] STOP file, halting" >> $LOG; exit 0; }
    start=$(date +%s)
    echo "[loop] running $CASE $(date -u +%H:%M:%S)" >> $LOG
    MB_CASE_ID=$CASE node tools/run_live.js > live-eval/last-run.log 2>&1
    if grep -qiE "429|spend cap|RESOURCE_EXHAUSTED" live-eval/last-run.log; then
      echo "[loop] SPEND CAP / 429 on $CASE, loop stopped $(date -u +%H:%M:%S)" >> $LOG
      echo "| $(date -u +%H:%M:%S) | $CASE | STOPPED: 429 / spend cap | | | |" >> EVAL_LIVE.md
      exit 0
    fi
    if [ "$(stat -c %Y cache/$CASE.json)" -ge "$start" ]; then
      ts=$(date +%Y%m%d-%H%M%S)
      cp cache/$CASE.json live-eval/runs/$CASE-$ts.json
      python3 tools/score_run.py live-eval/runs/$CASE-$ts.json >> $LOG 2>&1
      python3 /tmp/push_all.py EVAL_LIVE.md >> $LOG 2>&1
      echo "[loop] $CASE scored and logged" >> $LOG
    else
      echo "[loop] $CASE produced no fresh cache (run failed?)" >> $LOG
    fi
    cp live-eval/pristine/$CASE.json cache/$CASE.json
    sleep 20
  done
done
