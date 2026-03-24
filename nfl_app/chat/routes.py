import json
import sqlite3
import time
import os
from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user

chat = Blueprint('chat', __name__)

DB_FILE = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../data/user_picks.db'))

MAX_BODY_LEN = 2000
MAX_BET_JSON_LEN = 8192


def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_chat_table_exists():
    conn = get_db_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user TEXT NOT NULL,
            created_at REAL NOT NULL,
            message_type TEXT NOT NULL,
            body TEXT,
            bet_json TEXT
        )
        """
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_chat_messages_id ON chat_messages(id)')
    conn.commit()
    conn.close()


def _row_to_dict(row):
    d = dict(row)
    if d.get('bet_json'):
        try:
            d['bet'] = json.loads(d['bet_json'])
        except json.JSONDecodeError:
            d['bet'] = None
    else:
        d['bet'] = None
    del d['bet_json']
    return d


@chat.route('/messages', methods=['GET'])
def get_messages():
    ensure_chat_table_exists()
    after_id = request.args.get('after_id', type=int, default=0)
    limit = request.args.get('limit', type=int, default=50)
    limit = max(1, min(limit, 100))

    conn = get_db_connection()
    try:
        if after_id <= 0:
            rows = conn.execute(
                """
                SELECT id, user, created_at, message_type, body, bet_json
                FROM chat_messages
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = conn.execute(
                """
                SELECT id, user, created_at, message_type, body, bet_json
                FROM chat_messages
                WHERE id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (after_id, limit),
            ).fetchall()
    finally:
        conn.close()

    return jsonify([_row_to_dict(r) for r in rows])


@chat.route('/messages', methods=['POST'])
@login_required
def post_message():
    ensure_chat_table_exists()
    data = request.get_json(silent=True) or {}
    user = current_user.username
    message_type = (data.get('message_type') or '').strip().lower()
    if message_type not in ('text', 'bet'):
        return jsonify({'error': 'message_type must be "text" or "bet".'}), 400

    body = data.get('body')
    bet = data.get('bet')

    if message_type == 'text':
        if body is None or not str(body).strip():
            return jsonify({'error': 'body is required for text messages.'}), 400
        body = str(body).strip()
        if len(body) > MAX_BODY_LEN:
            return jsonify({'error': f'body exceeds {MAX_BODY_LEN} characters.'}), 400
        bet_json = None
    else:
        body = None
        if not isinstance(bet, dict):
            return jsonify({'error': 'bet object is required for bet messages.'}), 400
        try:
            bet_json = json.dumps(bet, separators=(',', ':'))
        except (TypeError, ValueError):
            return jsonify({'error': 'bet must be JSON-serializable.'}), 400
        if len(bet_json) > MAX_BET_JSON_LEN:
            return jsonify({'error': 'bet payload too large.'}), 400

    created_at = time.time()
    conn = get_db_connection()
    try:
        cur = conn.execute(
            """
            INSERT INTO chat_messages (user, created_at, message_type, body, bet_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user, created_at, message_type, body, bet_json),
        )
        conn.commit()
        new_id = cur.lastrowid
        row = conn.execute(
            """
            SELECT id, user, created_at, message_type, body, bet_json
            FROM chat_messages WHERE id = ?
            """,
            (new_id,),
        ).fetchone()
    finally:
        conn.close()

    return jsonify(_row_to_dict(row)), 201
