
source venv/bin/activate
setsid python manage.py runserver > .server.log 2>&1 < /dev/null &
echo $! > .server.pid
echo "Server started (PID $(cat .server.pid)). Use ./stop.sh to stop it."