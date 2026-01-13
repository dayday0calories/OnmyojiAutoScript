# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
"""
Generic MQTT-based sync barrier.

This module is intentionally task-agnostic. It provides a small helper that
can be used by *any* workflow to coordinate timing between two or more local
processes. It does not contain game-specific logic.
"""
from __future__ import annotations

import json
import time
from threading import Lock
from typing import Dict, List

from paho.mqtt import client as mqtt_client

from tasks.GlobalGame.config import TeamFlow, Transport
from module.logger import logger


class SyncBarrier:
    def __init__(self, team_flow: TeamFlow, group: str = 'default') -> None:
        # Use a single topic per logical group so multiple processes can coordinate.
        self.group = group
        self.topic = f'OAS_SYNC/{group}'
        # Cache messages by run_id; waiters scan this list for the expected kind.
        self._lock = Lock()
        self._messages: Dict[str, List[dict]] = {}

        # Create MQTT client and connect immediately.
        self.client = mqtt_client.Client(userdata=self)
        if team_flow.transport == Transport.SSL_TLS:
            self.client.tls_set(ca_certs=team_flow.ca)
        if team_flow.username:
            self.client.username_pw_set(team_flow.username, team_flow.password)
        self.client.on_message = self._on_message
        self.client.connect(team_flow.broker, team_flow.port)
        self.client.subscribe(self.topic, qos=0)
        self.client.loop_start()

    def _on_message(self, client, userdata, msg) -> None:
        # Decode message and store by run_id for later waiters.
        try:
            payload = json.loads(msg.payload)
        except Exception:
            logger.warning(f'Invalid sync payload: {msg.payload!r}')
            return
        run_id = payload.get('run_id')
        if not run_id:
            return
        with self._lock:
            self._messages.setdefault(run_id, []).append(payload)

    def publish(self, kind: str, run_id: str, data: dict, retain: bool = False) -> None:
        # Retain lets late subscribers receive the most recent state.
        payload = {'kind': kind, 'run_id': run_id, **data}
        self.client.publish(self.topic, json.dumps(payload), retain=retain)

    def wait_for(self, run_id: str, kind: str, count: int, timeout: float = 20.0) -> bool:
        # Poll the cache until we have enough matching messages or timeout.
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                got = [m for m in self._messages.get(run_id, []) if m.get('kind') == kind]
            if len(got) >= count:
                return True
            time.sleep(0.1)
        return False
