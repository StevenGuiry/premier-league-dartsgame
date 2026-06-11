(function () {
    'use strict';

    // -----------------------------------------------------------------------
    // Init data
    // -----------------------------------------------------------------------
    const initEl = document.getElementById('init-data');
    const init = JSON.parse(initEl.textContent);
    const CODE = init.code;
    const MY_USER_ID = init.myUserId;
    const MY_USERNAME = init.myUsername;

    let mySeat = null;   // determined after first game_state
    let countdownInterval = null;
    let currentDeadline = 0;
    let gameOver = false;

    // -----------------------------------------------------------------------
    // DOM refs
    // -----------------------------------------------------------------------
    const statusEl   = document.getElementById('session-status');
    const promptEl   = document.getElementById('prompt-box');
    const cardsEl    = document.getElementById('player-cards');
    const inputEl    = document.getElementById('player_name');
    const submitBtn  = document.getElementById('submit-btn');
    const messageEl  = document.getElementById('message-box');
    const timerEl    = document.getElementById('timer');
    const rematchBtn = document.getElementById('rematch-btn');
    const leaveBtn   = document.getElementById('leave-btn');
    const hist0El    = document.getElementById('history-0-entries');
    const hist1El    = document.getElementById('history-1-entries');
    const hist0Title = document.getElementById('history-0-title');
    const hist1Title = document.getElementById('history-1-title');
    const dropEl     = document.getElementById('autocomplete-dropdown');

    // -----------------------------------------------------------------------
    // Socket
    // -----------------------------------------------------------------------
    const socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
        setStatus('Connected', '#4ecdc4');
        socket.emit('join_game', { code: CODE });
    });

    socket.on('connect_error', () => {
        setStatus('Connection error — retrying…', '#e74c3c');
    });

    socket.on('disconnect', () => {
        setStatus('Disconnected…', '#e74c3c');
        stopCountdown();
    });

    socket.on('game_state', (state) => {
        renderState(state);
    });

    socket.on('turn_result', (data) => {
        showMessage(data.message, data.forfeited ? 'error' : 'success');
    });

    socket.on('game_over', (data) => {
        gameOver = true;
        stopCountdown();
        timerEl.textContent = '';
        disableInput();

        const abandoned = data.abandoned ? ' (opponent left)' : '';
        const myWon = (data.winner_seat === mySeat);
        const msg = myWon
            ? `You won!${abandoned} Final score: ${data.final_scores[mySeat] ?? ''}`
            : `${escHtml(data.winner_username)} wins!${abandoned}`;
        showMessage(msg, myWon ? 'success' : 'info');
        rematchBtn.style.display = 'inline-block';
    });

    socket.on('opponent_disconnected', (data) => {
        showMessage('Opponent disconnected. Waiting 60 s for them to return…', 'info');
    });

    socket.on('opponent_reconnected', (data) => {
        showMessage('Opponent reconnected.', 'info');
    });

    socket.on('rematch_waiting', (data) => {
        showMessage(data.message, 'info');
    });

    socket.on('rematch_start', (data) => {
        window.location.href = '/game/' + data.code;
    });

    socket.on('error', (data) => {
        showMessage(data.message, 'error');
    });

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------
    function renderState(state) {
        // Determine my seat
        if (mySeat === null) {
            for (const p of state.players) {
                if (p.username === MY_USERNAME) {
                    mySeat = p.seat;
                    break;
                }
            }
        }

        // Status banner
        if (state.status === 'waiting') {
            setStatus('Waiting for opponent…', '#ff9800');
        } else if (state.status === 'active') {
            setStatus('Game in progress', '#4ecdc4');
        } else {
            setStatus(state.status, '#aaa');
        }

        // Prompt
        if (state.prompt) {
            promptEl.textContent = state.prompt.text;
        } else {
            promptEl.textContent = 'Waiting for prompt…';
        }

        // Player cards
        cardsEl.innerHTML = '';
        for (const p of state.players) {
            const isActive = (state.status === 'active' && p.seat === state.turn_seat);
            const isMe = (p.seat === mySeat);
            const card = document.createElement('div');
            card.className = 'player-card' + (isActive ? ' active' : '');
            let turnLabel = '';
            if (isActive) {
                turnLabel = p.is_cpu
                    ? '<div class="your-turn">Thinking...</div>'
                    : '<div class="your-turn">Your Turn</div>';
            }
            card.innerHTML = `
                <h3>${escHtml(p.username)}${isMe ? ' (you)' : ''}</h3>
                <div class="score">${p.score}</div>
                ${turnLabel}
                ${!p.connected && !p.is_cpu ? '<div class="disconnected">Disconnected</div>' : ''}
            `;
            cardsEl.appendChild(card);
        }

        // History panels — seat 0 = left, seat 1 = right
        if (state.players[0]) {
            hist0Title.textContent = state.players[0].username;
            renderHistory(hist0El, state.players[0].history);
        }
        if (state.players[1]) {
            hist1Title.textContent = state.players[1].username;
            renderHistory(hist1El, state.players[1].history);
        }

        // Input enable/disable
        if (!gameOver && state.status === 'active' && state.turn_seat === mySeat) {
            enableInput();
        } else {
            disableInput();
        }

        // Countdown — suppress during CPU turn
        const cpuTurn = state.status === 'active'
            && state.players[state.turn_seat]
            && state.players[state.turn_seat].is_cpu;
        if (cpuTurn) {
            stopCountdown();
            timerEl.textContent = '';
        } else if (!gameOver && state.status === 'active' && state.deadline_epoch > 0) {
            startCountdown(state.deadline_epoch);
        } else if (state.status === 'waiting') {
            timerEl.textContent = 'Waiting for players…';
            stopCountdown();
        }
    }

    function renderHistory(el, history) {
        el.innerHTML = '';
        const items = [...history].reverse();
        for (const h of items) {
            const div = document.createElement('div');
            let cls = 'history-entry';
            let resultText;
            if (h.result === 'X') {
                cls += ' forfeited';
                resultText = 'X';
            } else if (h.result === 'BUST') {
                cls += ' bust';
                resultText = 'BUST';
            } else {
                resultText = '−' + h.result;
            }
            div.className = cls;
            div.textContent = `${h.name} (${resultText})`;
            el.appendChild(div);
        }
    }

    // -----------------------------------------------------------------------
    // Countdown
    // -----------------------------------------------------------------------
    function startCountdown(deadline) {
        if (currentDeadline === deadline) return;
        currentDeadline = deadline;
        stopCountdown();
        tick();
        countdownInterval = setInterval(tick, 500);

        function tick() {
            const secs = Math.max(0, Math.ceil(deadline - Date.now() / 1000));
            timerEl.textContent = `${secs}s`;
            timerEl.classList.toggle('urgent', secs <= 10);
            if (secs <= 0) stopCountdown();
        }
    }

    function stopCountdown() {
        if (countdownInterval) {
            clearInterval(countdownInterval);
            countdownInterval = null;
        }
    }

    // -----------------------------------------------------------------------
    // Autocomplete
    // -----------------------------------------------------------------------
    let acSelected = -1;

    inputEl.addEventListener('input', () => {
        acSelected = -1;
        const q = inputEl.value.trim();
        if (q.length < 2) { hideDropdown(); return; }
        fetch(`/api/players/search?q=${encodeURIComponent(q)}&code=${encodeURIComponent(CODE)}`)
            .then(r => r.json())
            .then(names => {
                if (!names.length) { hideDropdown(); return; }
                dropEl.innerHTML = '';
                names.forEach((name, i) => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item';
                    item.textContent = name;
                    item.addEventListener('mousedown', (e) => {
                        e.preventDefault();
                        inputEl.value = name;
                        hideDropdown();
                    });
                    dropEl.appendChild(item);
                });
                dropEl.style.display = 'block';
            })
            .catch(() => hideDropdown());
    });

    inputEl.addEventListener('keydown', (e) => {
        const items = dropEl.querySelectorAll('.autocomplete-item');
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            acSelected = Math.min(acSelected + 1, items.length - 1);
            highlightItem(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            acSelected = Math.max(acSelected - 1, -1);
            highlightItem(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (acSelected >= 0 && items[acSelected]) {
                inputEl.value = items[acSelected].textContent;
                hideDropdown();
            } else {
                submitPlayer();
            }
        } else if (e.key === 'Escape') {
            hideDropdown();
        }
    });

    inputEl.addEventListener('blur', () => {
        setTimeout(hideDropdown, 150);
    });

    function highlightItem(items) {
        items.forEach((el, i) => el.classList.toggle('selected', i === acSelected));
        if (acSelected >= 0 && items[acSelected]) {
            inputEl.value = items[acSelected].textContent;
        }
    }

    function hideDropdown() {
        dropEl.style.display = 'none';
        dropEl.innerHTML = '';
    }

    // -----------------------------------------------------------------------
    // Submit
    // -----------------------------------------------------------------------
    submitBtn.addEventListener('click', () => submitPlayer());

    function submitPlayer() {
        const name = inputEl.value.trim();
        if (!name) return;
        socket.emit('submit_player', { code: CODE, name });
        inputEl.value = '';
        hideDropdown();
        disableInput();
    }

    // -----------------------------------------------------------------------
    // Buttons
    // -----------------------------------------------------------------------
    leaveBtn.addEventListener('click', () => {
        socket.emit('leave_game', { code: CODE });
        window.location.href = '/lobby';
    });

    rematchBtn.addEventListener('click', () => {
        socket.emit('rematch', { code: CODE });
        rematchBtn.disabled = true;
    });

    // -----------------------------------------------------------------------
    // Helpers
    // -----------------------------------------------------------------------
    function enableInput() {
        inputEl.disabled = false;
        submitBtn.disabled = false;
        inputEl.focus();
    }

    function disableInput() {
        inputEl.disabled = true;
        submitBtn.disabled = true;
    }

    function setStatus(text, color) {
        statusEl.textContent = text;
        statusEl.style.color = color || '';
    }

    function showMessage(text, type) {
        messageEl.textContent = text;
        messageEl.className = 'message-box';
        if (type === 'success') messageEl.classList.add('success');
        else if (type === 'info') messageEl.classList.add('info');
    }

    function escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();
