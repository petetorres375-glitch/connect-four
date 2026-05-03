from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room
from logic import ConnectFour
from database import get_or_create_player, record_result, update_best_streak, get_leaderboard, get_stats
import random
import string

app = Flask(__name__)
app.secret_key = "connect-four-secret"
socketio = SocketIO(app, cors_allowed_origins="*")

# rooms[code] = { game, players: {sid: {color, name}}, scores, streaks, rematch, mode, difficulty }
rooms = {}

def make_room_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase, k=4))
        if code not in rooms:
            return code

def get_names(room):
    names = {'Red': 'Red', 'Yellow': 'Cyan'}
    for sid, p in room['players'].items():
        names[p['color']] = p['name']
    return names

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ping')
def ping():
    return 'OK', 200

@app.route('/leaderboard')
def leaderboard():
    return jsonify(get_leaderboard())

@app.route('/admin')
def admin():
    password = request.args.get('pw', '')
    if password != 'connectfour2026':
        return 'Access denied. Add ?pw=connectfour2026 to the URL.', 403
    return render_template('admin.html',
        stats=get_stats(),
        players=get_leaderboard(50),
        active_rooms=len(rooms)
    )

@socketio.on('create_room')
def on_create_room(data):
    name = data.get('name', 'Red').strip()[:20] or 'Player 1'
    get_or_create_player(name)
    code = make_room_code()
    rooms[code] = {
        'game': ConnectFour(),
        'players': {request.sid: {'color': 'Red', 'name': name}},
        'scores': {'Red': 0, 'Yellow': 0},
        'streaks': {'Red': 0, 'Yellow': 0},
        'rematch': set(),
        'mode': 'pvp',
        'difficulty': 'easy'
    }
    join_room(code)
    emit('room_created', {'code': code, 'color': 'Red', 'name': name})

@socketio.on('join_room')
def on_join_room(data):
    code = data.get('code', '').upper().strip()
    name = data.get('name', 'Cyan').strip()[:20] or 'Player 2'
    if code not in rooms:
        emit('error', {'message': 'Room not found'})
        return
    room = rooms[code]
    if len(room['players']) >= 2:
        emit('error', {'message': 'Room is full'})
        return
    get_or_create_player(name)
    room['players'][request.sid] = {'color': 'Yellow', 'name': name}
    join_room(code)
    names = get_names(room)
    for sid, p in room['players'].items():
        socketio.emit('game_start', {
            'color': p['color'],
            'name': p['name'],
            'opponent_name': names['Yellow'] if p['color'] == 'Red' else names['Red'],
            'scores': room['scores'],
            'streaks': room['streaks'],
            'mode': 'pvp',
            'code': code
        }, to=sid)

@socketio.on('start_vs_computer')
def on_start_vs_computer(data):
    difficulty = data.get('difficulty', 'easy')
    name = data.get('name', 'Player').strip()[:20] or 'Player'
    get_or_create_player(name)
    code = make_room_code()
    rooms[code] = {
        'game': ConnectFour(),
        'players': {request.sid: {'color': 'Red', 'name': name}},
        'scores': {'Red': 0, 'Yellow': 0},
        'streaks': {'Red': 0, 'Yellow': 0},
        'rematch': set(),
        'mode': 'pvc',
        'difficulty': difficulty
    }
    join_room(code)
    emit('game_start', {
        'color': 'Red',
        'name': name,
        'opponent_name': f'AI ({difficulty})',
        'scores': {'Red': 0, 'Yellow': 0},
        'streaks': {'Red': 0, 'Yellow': 0},
        'mode': 'pvc',
        'code': code,
        'difficulty': difficulty
    })

@socketio.on('make_move')
def on_make_move(data):
    code = data.get('code')
    col = data.get('column')
    if code not in rooms:
        return
    room = rooms[code]
    game = room['game']
    player_info = room['players'].get(request.sid)
    if not player_info:
        return
    player_color = player_info['color']

    if game.current_player != player_color:
        emit('error', {'message': "Not your turn"})
        return

    result = game.drop_piece(col)
    if result is None:
        emit('error', {'message': 'Invalid move'})
        return

    draw = not result['winner'] and len(game.get_valid_columns()) == 0
    names = get_names(room)

    if result['winner']:
        room['scores'][result['winner']] += 1
        room['streaks'][result['winner']] += 1
        loser = 'Yellow' if result['winner'] == 'Red' else 'Red'
        room['streaks'][loser] = 0
        if room['mode'] == 'pvp':
            winner_name = names[result['winner']]
            loser_name = names[loser]
            record_result(winner_name, 'win')
            record_result(loser_name, 'loss')
            update_best_streak(winner_name, room['streaks'][result['winner']])
        elif room['mode'] == 'pvc':
            player_name = names['Red']
            record_result(player_name, 'win')
            update_best_streak(player_name, room['streaks']['Red'])
    elif draw:
        if room['mode'] == 'pvp':
            for p in room['players'].values():
                record_result(p['name'], 'draw')

    payload = {
        'row': result['row'],
        'col': result['col'],
        'player': result['player'],
        'winner': result['winner'],
        'winner_name': names.get(result['winner']) if result['winner'] else None,
        'winning_cells': result['winning_cells'],
        'draw': draw,
        'next_turn': game.current_player,
        'scores': room['scores'],
        'streaks': room['streaks'],
        'ai_move': None
    }

    # AI move for PvC
    if not result['winner'] and not draw and room['mode'] == 'pvc':
        ai_col = game.get_ai_move(room['difficulty'])
        if ai_col is not None:
            ai_result = game.drop_piece(ai_col)
            if ai_result:
                ai_draw = not ai_result['winner'] and len(game.get_valid_columns()) == 0
                if ai_result['winner']:
                    room['scores'][ai_result['winner']] += 1
                    room['streaks'][ai_result['winner']] += 1
                    player_name = names['Red']
                    record_result(player_name, 'loss')
                    room['streaks']['Red'] = 0
                payload['ai_move'] = {
                    'row': ai_result['row'],
                    'col': ai_result['col'],
                    'player': ai_result['player'],
                    'winner': ai_result['winner'],
                    'winner_name': names.get(ai_result['winner']) if ai_result['winner'] else None,
                    'winning_cells': ai_result['winning_cells'],
                    'draw': ai_draw,
                }
                payload['scores'] = room['scores']
                payload['streaks'] = room['streaks']

    socketio.emit('move_made', payload, room=code)

@socketio.on('reaction')
def on_reaction(data):
    code = data.get('code')
    emoji = data.get('emoji')
    if code not in rooms or emoji not in ['👍', '😂', '😮', '💀', '🔥']:
        return
    color = rooms[code]['players'].get(request.sid, {}).get('color', 'Red')
    socketio.emit('reaction', {'emoji': emoji, 'color': color}, room=code)

@socketio.on('request_rematch')
def on_rematch(data):
    code = data.get('code')
    if code not in rooms:
        return
    room = rooms[code]
    room['rematch'].add(request.sid)
    needed = 1 if room['mode'] == 'pvc' else len(room['players'])
    socketio.emit('rematch_requested', {
        'count': len(room['rematch']),
        'needed': needed
    }, room=code)
    if len(room['rematch']) >= needed:
        room['game'].reset()
        room['rematch'].clear()
        socketio.emit('game_reset', {
            'scores': room['scores'],
            'streaks': room['streaks']
        }, room=code)

@socketio.on('chat_message')
def on_chat(data):
    code = data.get('code')
    message = data.get('message', '').strip()[:200]
    if not message or code not in rooms:
        return
    player = rooms[code]['players'].get(request.sid, {})
    name = player.get('name', 'Unknown')
    color = player.get('color', 'Red')
    socketio.emit('chat_message', {'name': name, 'color': color, 'message': message}, room=code)

@socketio.on('quit_game')
def on_quit(data):
    code = data.get('code')
    if code not in rooms:
        return
    room = rooms[code]
    if request.sid in room['players']:
        del room['players'][request.sid]
    if not room['players'] or room['mode'] == 'pvc':
        if code in rooms:
            del rooms[code]
    else:
        socketio.emit('opponent_left', {}, room=code)

@socketio.on('disconnect')
def on_disconnect():
    for code, room in list(rooms.items()):
        if request.sid in room['players']:
            del room['players'][request.sid]
            if not room['players']:
                del rooms[code]
            else:
                socketio.emit('opponent_left', {}, room=code)
            break

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)
