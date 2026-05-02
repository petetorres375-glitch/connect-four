import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    draws INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0
                )
            ''')
        conn.commit()

def get_or_create_player(name):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO players (name) VALUES (%s) ON CONFLICT (name) DO NOTHING',
                (name,)
            )
        conn.commit()

def record_result(name, result):
    with get_conn() as conn:
        with conn.cursor() as cur:
            if result == 'win':
                cur.execute('UPDATE players SET wins = wins + 1 WHERE name = %s', (name,))
            elif result == 'loss':
                cur.execute('UPDATE players SET losses = losses + 1 WHERE name = %s', (name,))
            elif result == 'draw':
                cur.execute('UPDATE players SET draws = draws + 1 WHERE name = %s', (name,))
        conn.commit()

def update_best_streak(name, streak):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('''
                UPDATE players SET best_streak = GREATEST(best_streak, %s)
                WHERE name = %s
            ''', (streak, name))
        conn.commit()

def get_leaderboard(limit=10):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute('''
                SELECT name, wins, losses, draws, best_streak
                FROM players
                ORDER BY wins DESC, best_streak DESC
                LIMIT %s
            ''', (limit,))
            return [dict(r) for r in cur.fetchall()]

def get_stats():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM players')
            total_players = cur.fetchone()[0]
            cur.execute('SELECT COALESCE(SUM(wins),0), COALESCE(SUM(draws),0) FROM players')
            total_wins, total_draws = cur.fetchone()
            cur.execute('SELECT name, wins FROM players ORDER BY wins DESC LIMIT 1')
            top = cur.fetchone()
            cur.execute('SELECT name, best_streak FROM players ORDER BY best_streak DESC LIMIT 1')
            streak = cur.fetchone()
    return {
        'total_players': total_players,
        'total_games': total_wins + total_draws,
        'total_wins': total_wins,
        'total_draws': total_draws,
        'top_player': {'name': top[0], 'wins': top[1]} if top else None,
        'best_streak': {'name': streak[0], 'streak': streak[1]} if streak else None,
    }

init_db()
