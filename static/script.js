const socket = io();

const dropSound = new Audio('/static/drop.mp3');
const winSound  = new Audio('/static/yippee.mp3');

let myColor    = null;
let myName     = null;
let roomCode   = null;
let gameOver   = false;
let myTurn     = false;
let gameMode   = null;

// ─── Leaderboard ─────────────────────────────────────────

async function loadLeaderboard() {
    try {
        const res = await fetch('/leaderboard');
        const data = await res.json();
        const el = document.getElementById('leaderboard-list');
        if (!data.length) { el.innerHTML = '<div class="lb-empty">No games played yet</div>'; return; }
        el.innerHTML = data.map((p, i) => `
            <div class="lb-row">
                <span class="lb-rank">${i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `#${i+1}`}</span>
                <span class="lb-name">${escapeHTML(p.name)}</span>
                <span class="lb-wins">${p.wins}W</span>
                <span class="lb-losses">${p.losses}L</span>
                <span class="lb-streak">${p.best_streak > 0 ? '🔥'+p.best_streak : ''}</span>
            </div>
        `).join('');
    } catch(e) { document.getElementById('leaderboard-list').innerHTML = 'Could not load'; }
}

loadLeaderboard();

// ─── Lobby ───────────────────────────────────────────────

let selectedDiff = 'easy';

function selectDiff(btn) {
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    selectedDiff = btn.dataset.diff;
}

function getName() {
    return document.getElementById('nameInput').value.trim() || 'Player';
}

function startVsComputer() {
    socket.emit('start_vs_computer', { difficulty: selectedDiff, name: getName() });
}

function createRoom() {
    document.getElementById('lobbyStatus').innerText = 'Creating room...';
    socket.emit('create_room', { name: getName() });
}

function joinRoom() {
    const code = document.getElementById('codeInput').value.trim().toUpperCase();
    if (code.length !== 4) { document.getElementById('lobbyStatus').innerText = 'Enter a 4-letter code'; return; }
    document.getElementById('lobbyStatus').innerText = 'Joining...';
    socket.emit('join_room', { code, name: getName() });
}

socket.on('room_created', (data) => {
    roomCode = data.code;
    myColor  = data.color;
    myName   = data.name;
    document.getElementById('lobbyStatus').innerText =
        `Room created! Share code: ${roomCode} — waiting for opponent...`;
});

socket.on('room_joined', (data) => {
    roomCode = data.code;
    myColor  = data.color;
    myName   = data.name;
});

socket.on('error', (data) => {
    document.getElementById('lobbyStatus').innerText = data.message;
});

// ─── Game Start ───────────────────────────────────────────

socket.on('game_start', (data) => {
    myColor  = data.color;
    myName   = data.name;
    roomCode = data.code || roomCode;
    gameMode = data.mode;
    showGame(data);
});

function showGame(data) {
    document.getElementById('lobby').style.display = 'none';
    document.getElementById('game').style.display  = 'flex';
    document.getElementById('roomCode').innerText  = roomCode;

    // Set player names
    const myDisplayName   = data.name;
    const oppDisplayName  = data.opponent_name;
    if (myColor === 'Red') {
        document.getElementById('redName').innerText    = myDisplayName;
        document.getElementById('yellowName').innerText = oppDisplayName;
    } else {
        document.getElementById('yellowName').innerText = myDisplayName;
        document.getElementById('redName').innerText    = oppDisplayName;
    }

    if (data.mode === 'pvc') {
        document.getElementById('chat-panel').style.display  = 'none';
        document.getElementById('room-info').style.display   = 'none';
        document.getElementById('reaction-bar').style.display = 'none';
    } else {
        document.getElementById('chat-panel').style.display  = 'flex';
        document.getElementById('room-info').style.display   = 'block';
        document.getElementById('reaction-bar').style.display = 'flex';
    }

    updateScores(data.scores);
    updateStreaks(data.streaks || {Red: 0, Yellow: 0});
    createBoard();
    myTurn = (myColor === 'Red');
    updateStatus();
}

// ─── Board ────────────────────────────────────────────────

function createBoard() {
    const boardEl = document.getElementById('board');
    boardEl.innerHTML = '';
    gameOver = false;
    document.getElementById('rematchBtn').style.display = 'none';

    for (let r = 0; r < 6; r++) {
        for (let c = 0; c < 7; c++) {
            const cell = document.createElement('div');
            cell.classList.add('cell');
            cell.dataset.col = c;
            cell.addEventListener('click', () => handleMove(c));
            boardEl.appendChild(cell);
        }
    }
}

function handleMove(col) {
    if (gameOver || !myTurn) return;
    myTurn = false;
    socket.emit('make_move', { code: roomCode, column: col });
}

// ─── Move Result ──────────────────────────────────────────

socket.on('move_made', (data) => {
    updateCell(data.row, data.col, data.player);
    updateScores(data.scores);
    updateStreaks(data.streaks);

    if (data.winner) { highlightWin(data.winning_cells); endGame(data.winner, data.winner_name); return; }
    if (data.draw)   { endDraw(); return; }

    if (data.ai_move) {
        updateStatus('thinking');
        setTimeout(() => {
            updateCell(data.ai_move.row, data.ai_move.col, data.ai_move.player);
            updateScores(data.scores);
            updateStreaks(data.streaks);
            if (data.ai_move.winner) {
                highlightWin(data.ai_move.winning_cells);
                endGame(data.ai_move.winner, data.ai_move.winner_name);
            } else if (data.ai_move.draw) {
                endDraw();
            } else {
                myTurn = true;
                updateStatus();
            }
        }, 550);
        return;
    }

    myTurn = (data.next_turn === myColor);
    updateStatus();
});

// ─── Reactions ───────────────────────────────────────────

function sendReaction(emoji) {
    socket.emit('reaction', { code: roomCode, emoji });
}

socket.on('reaction', (data) => {
    const float = document.getElementById('reaction-float');
    const el = document.createElement('div');
    el.classList.add('reaction-pop');
    el.classList.add(data.color === 'Red' ? 'reaction-left' : 'reaction-right');
    el.innerText = data.emoji;
    float.appendChild(el);
    setTimeout(() => el.remove(), 2000);
});

// ─── Rematch / Reset ─────────────────────────────────────

socket.on('game_reset', (data) => {
    createBoard();
    myTurn = (myColor === 'Red');
    updateScores(data.scores);
    updateStreaks(data.streaks || {Red: 0, Yellow: 0});
    const statusEl = document.getElementById('status');
    statusEl.classList.remove('winner-text');
    statusEl.style.color = '';
    updateStatus();
});

socket.on('rematch_requested', (data) => {
    const btn = document.getElementById('rematchBtn');
    if (data.count < data.needed) {
        btn.innerText = 'Waiting for opponent...';
        btn.disabled  = true;
    }
});

socket.on('opponent_left', () => {
    document.getElementById('status').innerText = 'Opponent disconnected';
    gameOver = true;
});

// ─── Quit ────────────────────────────────────────────────

function quitGame() {
    socket.emit('quit_game', { code: roomCode });
    returnToLobby();
}

function returnToLobby() {
    document.getElementById('game').style.display  = 'none';
    document.getElementById('lobby').style.display = 'flex';
    document.getElementById('lobbyStatus').innerText = '';
    document.getElementById('chat-messages').innerHTML = '';
    myColor = null; roomCode = null; gameOver = false; myTurn = false;
    loadLeaderboard();
}

// ─── Helpers ─────────────────────────────────────────────

function updateCell(row, col, player) {
    const idx  = row * 7 + col;
    const cell = document.getElementById('board').children[idx];
    dropSound.currentTime = 0;
    dropSound.play().catch(() => {});
    cell.classList.add(player);
    const dur = 0.1 * (row + 1);
    cell.style.animation = `dropAnim ${dur}s ease-out`;
}

function highlightWin(cells) {
    const boardEl = document.getElementById('board');
    Array.from(boardEl.children).forEach(c => c.classList.add('dimmed'));
    cells.forEach(([r, c]) => {
        const cell = boardEl.children[r * 7 + c];
        cell.classList.remove('dimmed');
        cell.classList.add('winning-cell');
    });
}

function updateScores(scores) {
    if (!scores) return;
    document.getElementById('redScore').innerText    = scores.Red;
    document.getElementById('yellowScore').innerText = scores.Yellow;
}

function updateStreaks(streaks) {
    if (!streaks) return;
    document.getElementById('redStreak').innerText    = streaks.Red    > 1 ? `🔥${streaks.Red}`    : '';
    document.getElementById('yellowStreak').innerText = streaks.Yellow > 1 ? `🔥${streaks.Yellow}` : '';
}

function updateStatus(override) {
    const statusEl  = document.getElementById('status');
    const redTag    = document.getElementById('redTag');
    const yellowTag = document.getElementById('yellowTag');
    const oppColor  = myColor === 'Red' ? 'Yellow' : 'Red';

    if (override === 'thinking') {
        statusEl.innerText   = 'AI thinking...';
        statusEl.style.color = 'var(--muted)';
        redTag.classList.remove('active-tag');
        yellowTag.classList.add('active-tag');
        return;
    }

    if (myTurn) {
        statusEl.innerText   = 'Your Turn';
        statusEl.style.color = myColor === 'Red' ? 'var(--red)' : 'var(--cyan)';
    } else {
        statusEl.innerText   = gameMode === 'pvc' ? "AI's Turn" : "Opponent's Turn";
        statusEl.style.color = 'var(--muted)';
    }

    redTag.classList.toggle('active-tag',    myTurn ? myColor === 'Red'    : oppColor === 'Red');
    yellowTag.classList.toggle('active-tag', myTurn ? myColor === 'Yellow' : oppColor === 'Yellow');
}

function endGame(winner, winnerName) {
    gameOver = true;
    const isMe     = winner === myColor;
    const statusEl = document.getElementById('status');
    const displayName = winnerName || winner;

    if (gameMode === 'pvc') {
        statusEl.innerText = isMe ? 'You Win! 🎉' : 'AI Wins 🤖';
    } else {
        statusEl.innerText = isMe ? 'You Win! 🎉' : `${displayName} Wins! 🎉`;
    }
    statusEl.style.color = winner === 'Red' ? 'var(--red)' : 'var(--cyan)';
    statusEl.classList.add('winner-text');

    if (isMe) setTimeout(() => { winSound.currentTime = 0; winSound.play().catch(() => {}); }, 350);

    const btn = document.getElementById('rematchBtn');
    btn.style.display = 'inline-block';
    btn.innerText     = 'Rematch';
    btn.disabled      = false;
}

function endDraw() {
    gameOver = true;
    const statusEl     = document.getElementById('status');
    statusEl.innerText = "It's a Draw! 🤝";
    statusEl.style.color = '#aaa';
    statusEl.classList.add('winner-text');
    const btn = document.getElementById('rematchBtn');
    btn.style.display = 'inline-block';
    btn.innerText     = 'Rematch';
    btn.disabled      = false;
}

function requestRematch() {
    socket.emit('request_rematch', { code: roomCode });
    if (gameMode === 'pvp') {
        document.getElementById('rematchBtn').innerText = 'Waiting for opponent...';
        document.getElementById('rematchBtn').disabled  = true;
    }
}

// ─── Chat ────────────────────────────────────────────────

function sendChat() {
    const input   = document.getElementById('chatInput');
    const message = input.value.trim();
    if (!message || !roomCode) return;
    socket.emit('chat_message', { code: roomCode, message });
    input.value = '';
}

socket.on('chat_message', (data) => {
    const messages = document.getElementById('chat-messages');
    const line     = document.createElement('div');
    line.classList.add('chat-line');
    const cls      = data.color === 'Red' ? 'chat-red' : 'chat-yellow';
    line.innerHTML = `<span class="${cls}">${escapeHTML(data.name)}</span> ${escapeHTML(data.message)}`;
    messages.appendChild(line);
    messages.scrollTop = messages.scrollHeight;
});

function escapeHTML(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
