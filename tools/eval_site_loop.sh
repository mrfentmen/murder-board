#!/bin/bash
cd ~/workspace/murder-board-repo
LOG=live-eval/site-loop.log
echo "[site-loop] start $(date -u +%H:%M:%S)" >> $LOG
LAST=0
while true; do
  hour=$(TZ=America/New_York date +%H); min=$(TZ=America/New_York date +%M)
  if [ "$hour" -gt 16 ] || { [ "$hour" -eq 16 ] && [ "$min" -ge 30 ]; }; then echo "[site-loop] 16:30 ET, stopping" >> $LOG; break; fi
  [ -f live-eval/STOP ] && { echo "[site-loop] STOP file, halting" >> $LOG; break; }
  if [ -f live-eval/results.jsonl ]; then
    M=$(stat -c %Y live-eval/results.jsonl)
    if [ "$M" -gt "$LAST" ]; then
      LAST=$M
      python3 tools/build_eval_data.py >> $LOG 2>&1
      python3 /tmp/push_all.py app/eval-data.js live-eval/results.jsonl >> $LOG 2>&1
      for i in 1 2 3; do
        ~/workspace/.deploy-venv/bin/python ~/workspace/custom-connectors/custom.legacy-cloudflare/bin/pages_deploy.py --project murder-board --dir ~/workspace/murder-board-repo/app >> $LOG 2>&1 && break
        sleep 5
      done
      echo "[site-loop] eval data rebuilt, pushed, deployed $(date -u +%H:%M:%S)" >> $LOG
    fi
  fi
  sleep 60
done
