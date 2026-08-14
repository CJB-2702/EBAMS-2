
source venv/bin/activate
setsid python manage.py runserver &
echo $! > .server.pid
echo "Server started (PID $(cat .server.pid)). Use ./stop.sh to stop it."