(function () {
    'use strict';

    const socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
        socket.emit('join_lobby');
    });

    socket.on('lobby_update', (data) => {
        const list = document.getElementById('session-list');
        if (!list) return;

        const sessions = data.sessions || [];
        if (sessions.length === 0) {
            list.innerHTML = '<div class="no-sessions" id="no-sessions">No active sessions. Create one!</div>';
            return;
        }

        list.innerHTML = sessions.map(s => {
            const isJoinable = s.status === 'waiting' && s.player_count < 2;
            return `
            <div class="session-item">
                <div>
                    <div class="session-id">${escHtml(s.code)}</div>
                    <div class="session-details">Host: ${escHtml(s.host)} &nbsp;|&nbsp; ${s.player_count}/2 players</div>
                </div>
                <div style="display:flex;align-items:center;gap:10px">
                    ${isJoinable
                        ? `<span><span class="status-dot ready"></span>Ready</span>
                           <a href="/game/${escHtml(s.code)}" class="btn btn-teal" style="padding:8px 18px;font-size:0.85em">Join</a>`
                        : `<span><span class="status-dot full"></span>Full</span>`
                    }
                </div>
            </div>`;
        }).join('');
    });

    socket.on('disconnect', () => {
        // Silently reconnect — socket.io handles this automatically.
    });

    function escHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }
})();
