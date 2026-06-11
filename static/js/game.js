(function () {
    'use strict';

    // ── Init data ────────────────────────────────────────────
    const init = JSON.parse(document.getElementById('init-data').textContent);
    const CODE        = init.code;
    const MY_USER_ID  = init.myUserId;
    const MY_USERNAME = init.myUsername;

    // ── DOM refs ─────────────────────────────────────────────
    const side0El       = document.getElementById('side-0');
    const side1El       = document.getElementById('side-1');
    const name0El       = document.getElementById('name-0');
    const name1El       = document.getElementById('name-1');
    const score0El      = document.getElementById('score-0');
    const score1El      = document.getElementById('score-1');
    const turnLabel0    = document.getElementById('turn-label-0');
    const turnLabel1    = document.getElementById('turn-label-1');
    const timerEl       = document.getElementById('timer-pill');
    const statusEl      = document.getElementById('session-status');
    const promptEl      = document.getElementById('prompt-box');
    const messageEl     = document.getElementById('message-box');
    const feedEl        = document.getElementById('turn-feed');
    const inputEl       = document.getElementById('player_name');
    const dropEl        = document.getElementById('autocomplete-dropdown');
    const submitBtn     = document.getElementById('submit-btn');
    const leaveBtn      = document.getElementById('leave-btn');
    const rematchBtn    = document.getElementById('rematch-btn');
    const winOverlay    = document.getElementById('win-overlay');
    const winWinnerName = document.getElementById('win-winner-name');
    const winWins       = document.getElementById('win-wins');
    const winScoresRow  = document.getElementById('win-scores-row');
    const turnBanner    = document.getElementById('turn-banner');

    // ── State ────────────────────────────────────────────────
    let mySeat        = null;
    let prevScores    = {};   // seat → last rendered score (for animation)
    let prevTurnSeat  = null;
    let countdownId   = null;
    let currentDeadline = 0;
    let gameOver      = false;
    let bannerTimeout = null;

    // ── Socket ───────────────────────────────────────────────
    const socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect',       () => { setStatus('Connected', '#4ade80'); socket.emit('join_game', { code: CODE }); });
    socket.on('connect_error', () => setStatus('Reconnecting…', '#facc15'));
    socket.on('disconnect',    () => { setStatus('Disconnected', '#f87171'); stopCountdown(); });
    socket.on('game_state',    renderState);
    socket.on('turn_result',   onTurnResult);
    socket.on('game_over',     onGameOver);
    socket.on('opponent_disconnected', () => showMessage('Opponent disconnected. Waiting 60 s…', 'info'));
    socket.on('opponent_reconnected',  () => showMessage('Opponent reconnected.', 'info'));
    socket.on('rematch_waiting', d => showMessage(d.message, 'info'));
    socket.on('rematch_start',   d => { window.location.href = '/game/' + d.code; });
    socket.on('error',           d => showMessage(d.message, 'error'));

    // ── renderState ──────────────────────────────────────────
    function renderState(state) {
        // Determine my seat on first state
        if (mySeat === null) {
            for (const p of state.players) {
                if (p.username === MY_USERNAME) { mySeat = p.seat; break; }
            }
        }

        // Status
        const statusMap = { waiting: 'Waiting for opponent…', active: 'In progress', finished: 'Finished', abandoned: 'Abandoned' };
        setStatus(statusMap[state.status] || state.status, state.status === 'active' ? '#4ade80' : '#9aa4b5');

        // Prompt
        promptEl.textContent = state.prompt ? state.prompt.text : 'Waiting for prompt…';

        // Scoreboard sides
        const sides   = [side0El, side1El];
        const nameEls = [name0El, name1El];
        const scoreEls = [score0El, score1El];
        const labelEls = [turnLabel0, turnLabel1];

        for (let i = 0; i < 2; i++) {
            const p = state.players[i];
            if (!p) continue;

            nameEls[i].textContent = p.username + (p.seat === mySeat ? ' (you)' : '');

            // Animate score change
            const prev = prevScores[i] ?? p.score;
            if (prev !== p.score) {
                animateScore(scoreEls[i], prev, p.score);
                spawnDelta(scoreEls[i], prev - p.score);
            } else {
                scoreEls[i].textContent = p.score;
            }
            prevScores[i] = p.score;

            // Active side glow
            const isActive = state.status === 'active' && p.seat === state.turn_seat;
            sides[i].classList.toggle('active', isActive);

            // Turn label
            if (isActive) {
                if (p.is_cpu) {
                    labelEls[i].innerHTML = '<span class="sb-cpu-thinking">Thinking</span>';
                } else if (p.seat === mySeat) {
                    labelEls[i].textContent = 'Your turn';
                } else {
                    labelEls[i].textContent = "Opponent's turn";
                }
            } else {
                labelEls[i].textContent = '';
            }
        }

        // Rebuild unified feed
        renderFeed(state);

        // Input enable/disable
        if (!gameOver && state.status === 'active' && state.turn_seat === mySeat) {
            enableInput();
        } else {
            disableInput();
        }

        // Turn banner — flash when it becomes my turn
        const nowMyTurn = !gameOver && state.status === 'active' && state.turn_seat === mySeat;
        const wasMyTurn = prevTurnSeat === mySeat;
        if (nowMyTurn && !wasMyTurn && prevTurnSeat !== null) {
            showTurnBanner();
        }
        prevTurnSeat = state.turn_seat;

        // Timer
        const cpuTurn = state.status === 'active'
            && state.players[state.turn_seat]
            && state.players[state.turn_seat].is_cpu;

        if (gameOver || state.status !== 'active') {
            stopCountdown();
            timerEl.textContent = '—';
            timerEl.classList.remove('urgent');
        } else if (cpuTurn) {
            stopCountdown();
            timerEl.textContent = '—';
            timerEl.classList.remove('urgent');
        } else if (state.deadline_epoch > 0) {
            startCountdown(state.deadline_epoch);
        }

        // Waiting state
        if (state.status === 'waiting') timerEl.textContent = '—';
    }

    // ── Feed ─────────────────────────────────────────────────
    function renderFeed(state) {
        // Interleave both histories into chronological order.
        // Each entry: {seat, username, name, result}
        const rows = [];
        const hists = state.players.map(p => p ? p.history.map(h => ({ ...h, seat: p.seat, username: p.username, is_cpu: p.is_cpu })) : []);

        // Since we don't have timestamps, keep them in per-player order and interleave round by round.
        // The feed length matches the total turns taken across both seats.
        // Simplest correct approach: merge by seat alternation (first seat 0 row, then seat 1, etc.)
        // Actually the history arrays are in order of that player's turns, not global turn order.
        // Most natural: display in absolute turn order.
        // Turn 0 → seat 0's first entry, Turn 1 → seat 1's first entry, Turn 2 → seat 0's second, …
        // But that's only correct if game started on seat 0. Use current_turn to infer start.
        // Safer: just show all entries in a simple interleaved pass — it reads naturally.
        const maxLen = Math.max(...state.players.map(p => p ? p.history.length : 0));
        for (let i = 0; i < maxLen; i++) {
            for (const p of state.players) {
                if (p && p.history[i]) {
                    rows.push({ seat: p.seat, username: p.username, is_cpu: p.is_cpu, ...p.history[i] });
                }
            }
        }

        if (rows.length === 0) {
            feedEl.innerHTML = '<div class="feed-empty">No turns yet — good luck!</div>';
            return;
        }

        // Newest first
        feedEl.innerHTML = '';
        [...rows].reverse().forEach(row => {
            const isMe = row.seat === mySeat;
            const div = document.createElement('div');
            let cls = 'feed-row ' + (isMe ? 'mine' : 'theirs');
            let resultText;
            if (row.result === 'X') {
                cls += ' forfeit';
                resultText = 'MISS';
            } else if (row.result === 'BUST') {
                cls += ' bust';
                resultText = 'BUST';
            } else {
                resultText = '−' + row.result;
            }
            div.className = cls;
            div.innerHTML = `<span class="feed-player">${escHtml(row.username)}</span>
                             <span class="feed-name">${escHtml(row.name)}</span>
                             <span class="feed-result">${resultText}</span>`;
            feedEl.appendChild(div);
        });
    }

    // ── Score animation ──────────────────────────────────────
    function animateScore(el, from, to) {
        const start = performance.now();
        const dur   = 600;
        function tick(now) {
            const t = Math.min((now - start) / dur, 1);
            const ease = 1 - Math.pow(1 - t, 3);
            el.textContent = Math.round(from + (to - from) * ease);
            if (t < 1) requestAnimationFrame(tick);
        }
        requestAnimationFrame(tick);
    }

    function spawnDelta(anchorEl, delta) {
        if (delta === 0) return;
        const span = document.createElement('span');
        span.className = 'score-delta';
        span.textContent = (delta > 0 ? '−' : '+') + Math.abs(delta);
        anchorEl.style.position = 'relative';
        anchorEl.appendChild(span);
        span.addEventListener('animationend', () => span.remove(), { once: true });
    }

    // ── Turn banner ──────────────────────────────────────────
    function showTurnBanner() {
        clearTimeout(bannerTimeout);
        turnBanner.hidden = false;
        bannerTimeout = setTimeout(() => { turnBanner.hidden = true; }, 1200);
    }

    // ── Event handlers ───────────────────────────────────────
    function onTurnResult(data) {
        const type = data.forfeited ? 'error' : 'success';
        showMessage(data.message, type);
    }

    function onGameOver(data) {
        gameOver = true;
        stopCountdown();
        timerEl.textContent = '—';
        timerEl.classList.remove('urgent');
        disableInput();

        const abandoned = data.abandoned ? ' (opponent left)' : '';
        const myWon = data.winner_seat === mySeat;

        winWinnerName.textContent = data.winner_username;
        winWins.textContent = myWon ? 'You win!' + abandoned : 'Better luck next time' + abandoned;
        winWins.style.color = myWon ? 'var(--success)' : 'var(--danger)';

        // Score blocks
        winScoresRow.innerHTML = '';
        (data.final_scores || []).forEach((score, i) => {
            const isWinner = i === data.winner_seat;
            const div = document.createElement('div');
            div.className = 'win-score-block' + (isWinner ? ' winner' : '');
            // Get name from current DOM
            const nameEl = i === 0 ? name0El : name1El;
            div.innerHTML = `<div class="wsb-name">${escHtml(nameEl.textContent.replace(' (you)', ''))}</div>
                             <div class="wsb-val">${score}</div>`;
            winScoresRow.appendChild(div);
        });

        winOverlay.hidden = false;
    }

    // ── Countdown ────────────────────────────────────────────
    function startCountdown(deadline) {
        if (currentDeadline === deadline) return;
        currentDeadline = deadline;
        stopCountdown();
        tick();
        countdownId = setInterval(tick, 500);
        function tick() {
            const secs = Math.max(0, Math.ceil(deadline - Date.now() / 1000));
            timerEl.textContent = secs + 's';
            timerEl.classList.toggle('urgent', secs <= 10);
            if (secs <= 0) stopCountdown();
        }
    }
    function stopCountdown() {
        clearInterval(countdownId);
        countdownId = null;
    }

    // ── Autocomplete ─────────────────────────────────────────
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
                names.forEach(name => {
                    const item = document.createElement('div');
                    item.className = 'autocomplete-item';
                    item.textContent = name;
                    item.addEventListener('mousedown', e => {
                        e.preventDefault();
                        inputEl.value = name;
                        hideDropdown();
                    });
                    dropEl.appendChild(item);
                });
                dropEl.style.display = 'block';
            })
            .catch(hideDropdown);
    });

    inputEl.addEventListener('keydown', e => {
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

    inputEl.addEventListener('blur', () => setTimeout(hideDropdown, 150));

    function highlightItem(items) {
        items.forEach((el, i) => el.classList.toggle('selected', i === acSelected));
        if (acSelected >= 0 && items[acSelected]) inputEl.value = items[acSelected].textContent;
    }
    function hideDropdown() { dropEl.style.display = 'none'; dropEl.innerHTML = ''; }

    // ── Submit ────────────────────────────────────────────────
    submitBtn.addEventListener('click', submitPlayer);

    function submitPlayer() {
        const name = inputEl.value.trim();
        if (!name) return;
        socket.emit('submit_player', { code: CODE, name });
        inputEl.value = '';
        hideDropdown();
        disableInput();
    }

    // ── Buttons ───────────────────────────────────────────────
    leaveBtn.addEventListener('click', () => {
        socket.emit('leave_game', { code: CODE });
        window.location.href = '/lobby';
    });

    rematchBtn.addEventListener('click', () => {
        socket.emit('rematch', { code: CODE });
        rematchBtn.disabled = true;
        rematchBtn.textContent = 'Waiting…';
    });

    // ── Helpers ───────────────────────────────────────────────
    function enableInput()  { inputEl.disabled = false; submitBtn.disabled = false; inputEl.focus(); }
    function disableInput() { inputEl.disabled = true;  submitBtn.disabled = true; }

    function setStatus(text, color) {
        statusEl.textContent = text;
        statusEl.style.color = color || '';
    }

    function showMessage(text, type) {
        messageEl.textContent = text;
        messageEl.className = 'message-strip';
        if (type === 'success') messageEl.classList.add('success');
        else if (type === 'info')  messageEl.classList.add('info');
        else if (type === 'error') messageEl.classList.add('error');
    }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
})();
