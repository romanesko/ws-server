import json
import os
import signal
import time
from threading import Thread
from typing import NamedTuple

from flask import Flask, request
import requests
from simple_websocket import Server, ConnectionClosed

app = Flask(__name__)

clients = {}

import psycopg

state = {
    'ready': False
}


def one_signal_push(user_id, key, data):
    url = "https://onesignal.com/api/v1/notifications"

    payload = json.dumps({
        "app_id": os.environ['ONESIGNAL_APP_ID'],
        "target_channel": "push",
        "include_aliases": {
            "ConfabUser": [
                user_id
            ]
        },
        "contents": {
            "en": "Получено новое сообщение"
        },
        "data": {
            "type": key,
            "data": data
        }
    })
    headers = {
        'Authorization': 'Basic ' + os.environ['ONESIGNAL_API_KEY'],
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.json())


class Notification(NamedTuple):
    id: int
    user_id: int
    key: str
    data: dict
    online: bool


def background():
    try:
        conn = psycopg.connect( os.environ['PG_CONNECTION'], autocommit=True)
    except Exception as e:
        print(e)
        print("EXITING 1")
        os.kill(os.getpid(), signal.SIGTERM)
        exit(1)

    def mark_sent(id, channel):
        conn.execute('select public.set_notification_sent(%s::bigint, %s::text)', (id, channel))
        conn.commit()

    while state['ready']:

        res = conn.execute('select public.get_next_notification()').fetchone()[0]
        if not res:
            time.sleep(1)
            continue

        n = Notification(**res)

        if n.online and n.user_id in clients:
            print('sending directly to user', n.user_id);
            clients[n.user_id].send(n.key + " " + json.dumps(n.data))
            mark_sent(n.id, 'direct')
        else:
            print('sending push (user', n.user_id, 'is', 'online' if n.online else 'OFFLINE', 'and',
                  'has' if n.user_id in clients else 'HAS NO', 'direct connection)')
            one_signal_push(n.user_id, n.key, n.data)
            mark_sent(n.id, 'push')

        time.sleep(0.1)


@app.route('/ws', websocket=True)
def echo():
    ws = Server.accept(request.environ)
    try:
        while True:
            data = ws.receive()
            if data.startswith('AUTH'):
                token = data.split(' ')[1].strip()
                if not token:
                    print("AUTH without token... skip")
                    continue
                print('AUTH', token)
                clients[token] = ws
                ws.send("AUTH OK")
                continue

    except ConnectionClosed:
        print('user disconnected')
        pass
    return ''


if __name__ == '__main__':
    state['ready'] = True
    t = Thread(target=background)
    t.start()
    from waitress import create_server

    def handle_sig(sig, frame):
        print(f"Got signal {sig}, now close worker...")
        server.close()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGQUIT, signal.SIGHUP):
        signal.signal(sig, handle_sig)

    server = create_server(app, host="0.0.0.0", port=5000)
    server.run()
    # app.run("0.0.0.0")
    state['ready'] = False
