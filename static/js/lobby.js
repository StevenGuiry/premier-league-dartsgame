(function () {
    'use strict';

    const socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect', () => { socket.emit('join_lobby'); });

    socket.on('lobby_update', (data) => {
        const list = document.getElementById('session-list');
        if (!list) return;

        const sessions = data.sessions || [];
        if (sessions.length === 0) {
            list.innerHTML = '<div class="no-sessions" id="no-sessions">No open sessions — create one above!</div>';
            return;
        }

        list.innerHTML = sessions.map(s => {
            const joinable = s.status === 'waiting' && s.player_count < 2;
            return `<div class="session-item">
                <div>
                    <div class="session-id">${esc(s.code)}</div>
                    <div class="session-details">Host: ${esc(s.host)} &middot; ${s.player_count}/2 players</div>
                </div>
                <div style="display:flex;align-items:center;gap:10px">
                    ${joinable
                        ? `<span style="font-size:0.8rem;color:var(--text-dim)"><span class="status-dot ready"></span>Open</span>
                           <a href="/game/${esc(s.code)}" class="btn btn-teal" style="padding:8px 16px;font-size:0.8rem">Join</a>`
                        : `<span style="font-size:0.8rem;color:var(--text-faint)"><span class="status-dot full"></span>Full</span>`
                    }
                </div>
            </div>`;
        }).join('');
    });

    function esc(s) {
        return String(s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
})();
