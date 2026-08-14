#!/usr/bin/env bash

PIDFILE=.server.pid

if [ ! -f "$PIDFILE" ]; then
    echo "No PID file found ($PIDFILE) — is the server running via ./run?"
    exit 1
fi

PID=$(cat "$PIDFILE")

if ! kill -0 "$PID" 2>/dev/null; then
    echo "Process $PID is not running. Removing stale PID file."
    rm -f "$PIDFILE"
    exit 1
fi

# setsid made $PID a session/process-group leader, so runserver's
# autoreload child shares that PGID — kill the whole group.
kill -TERM "-$PID"
rm -f "$PIDFILE"
echo "Stopped server (PID $PID)."
