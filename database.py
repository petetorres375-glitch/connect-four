import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'leaderboard.db')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                draws INTEGER DEFAULT 0,
                best_streak INTEGER DEFAULT 0
            )
        ''')
        conn.commit()

def get_or_create_player(name):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            'INSERT OR IGNORE INTO players (name) VALUES (?)', (name,)
        )
        conn.commit()

def record_result(name, result):
    """result: 'win', 'loss', or 'draw'"""
    with sqlite3.connect(DB_PATH) as conn:
        if result == 'win':
            conn.execute('UPDATE players SET wins = wins + 1 WHERE name = ?', (name,))
        elif result == 'loss':
            conn.execute('UPDATE players SET losses = losses + 1 WHERE name = ?', (name,))
        elif result == 'draw':
            conn.execute('UPDATE players SET draws = draws + 1 WHERE name = ?', (name,))
        conn.commit()

def update_best_streak(name, streak):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            UPDATE players SET best_streak = MAX(best_streak, ?)
            WHERE name = ?
        ''', (streak, name))
        conn.commit()

def get_leaderboard(limit=10):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute('''
            SELECT name, wins, losses, draws, best_streak
            FROM players
            ORDER BY wins DESC, best_streak DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [
            {'name': r[0], 'wins': r[1], 'losses': r[2], 'draws': r[3], 'best_streak': r[4]}
            for r in rows
        ]

init_db()
