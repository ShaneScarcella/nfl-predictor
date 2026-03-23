(function () {
    'use strict';

    const POLL_MS = 4000;
    const MAX_INITIAL = 50;

    let lastMessageId = 0;
    let pollTimer = null;

    function escapeHtml(s) {
        if (s == null) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    }

    function formatAmericanOdds(n) {
        if (n == null || Number.isNaN(Number(n))) return '—';
        const v = Math.round(Number(n));
        return v > 0 ? `+${v}` : `${v}`;
    }

    function formatSpreadForTeam(spreadValue) {
        if (spreadValue == null || Number.isNaN(Number(spreadValue))) return '';
        const n = Number(spreadValue);
        const rounded = Math.abs(n % 1) < 0.01 || Math.abs(n % 1 - 0.5) < 0.01 ? n.toFixed(1).replace(/\.0$/, '') : n.toFixed(1);
        const sign = n > 0 ? '+' : '';
        return `${sign}${rounded}`;
    }

    /**
     * spread_line is home team spread (negative = home favored).
     */
    function buildPickHeadline(game, pickTeam) {
        const sl = game.spread_line;
        if (pickTeam === game.home_team) {
            return `${game.home_team} ${formatSpreadForTeam(sl)}`.trim();
        }
        if (pickTeam === game.away_team) {
            return `${game.away_team} ${formatSpreadForTeam(sl != null ? -Number(sl) : null)}`.trim();
        }
        return pickTeam;
    }

    function buildBetPayload(game, pickTeam, kind, confidenceNote) {
        const isHome = pickTeam === game.home_team;
        const opponent = isHome ? game.away_team : game.home_team;
        const logo = isHome ? game.home_logo : game.away_logo;
        const ml = isHome ? game.home_moneyline : game.away_moneyline;
        const isRisky = kind === 'risky';
        const headline = isRisky ? `${pickTeam} ML` : buildPickHeadline(game, pickTeam);
        const odds = formatAmericanOdds(ml);
        const subtitle = `vs ${opponent}`;
        const payload = {
            variant: isRisky ? 'risky' : 'lock',
            label: isRisky ? 'RISKY' : 'LOCK',
            headline,
            subtitle,
            odds,
            team_logo: logo || '',
        };
        if (isRisky && confidenceNote) {
            payload.confidence = confidenceNote;
        }
        return payload;
    }

    function betCardVariantClass(bet) {
        if (bet.variant === 'risky') return 'variant-risky';
        if (bet.variant === 'matchup') return 'variant-matchup';
        return 'variant-lock';
    }

    function usernameClassForBet(bet) {
        if (!bet) return 'name-default';
        if (bet.variant === 'risky') return 'name-risky';
        return 'name-lock';
    }

    function formatMsgTime(createdAt) {
        if (createdAt == null) return '';
        const ms = typeof createdAt === 'number' && createdAt < 1e12 ? createdAt * 1000 : createdAt;
        const d = new Date(ms);
        return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    }

    function initialsFromUser(name) {
        const t = (name || '?').trim();
        return t.slice(0, 2).toUpperCase();
    }

    function getChatScrollEl() {
        const side = document.getElementById('community-chat-sidebar');
        return side && side.querySelector('.chat-messages-scroll');
    }

    function scrollChatToBottom() {
        const sc = getChatScrollEl();
        if (!sc) return;
        requestAnimationFrame(() => {
            sc.scrollTop = sc.scrollHeight;
        });
    }

    /**
     * True if the message list can scroll further in the direction of deltaY
     * (or if it has no overflow, so the page should receive the wheel instead).
     */
    function chatScrollCanAbsorbWheel(scrollEl, deltaY) {
        const { scrollTop, scrollHeight, clientHeight } = scrollEl;
        const epsilon = 2;
        if (scrollHeight <= clientHeight + epsilon) {
            return false;
        }
        const atTop = scrollTop <= epsilon;
        const atBottom = scrollTop + clientHeight >= scrollHeight - epsilon;
        if (deltaY < 0 && atTop) return false;
        if (deltaY > 0 && atBottom) return false;
        return true;
    }

    /**
     * Wheel over the header/composer does not hit .chat-messages-scroll, so the browser
     * scrolls the page. Route those events to the message list when appropriate.
     */
    function setupSidebarWheelRouting() {
        const side = document.getElementById('community-chat-sidebar');
        if (!side) return;

        side.addEventListener(
            'wheel',
            (e) => {
                const scrollEl = getChatScrollEl();
                if (!scrollEl) return;

                if (scrollEl.contains(e.target)) {
                    return;
                }

                if (!chatScrollCanAbsorbWheel(scrollEl, e.deltaY)) {
                    return;
                }

                scrollEl.scrollTop += e.deltaY;
                e.preventDefault();
            },
            { passive: false }
        );
    }

    function renderBetCard(bet) {
        const variantClass = betCardVariantClass(bet);
        const thumb = bet.team_logo
            ? `<img class="chat-bet-thumb" src="${escapeHtml(bet.team_logo)}" alt="" loading="lazy">`
            : '<div class="chat-bet-thumb"></div>';
        const confidenceLine =
            bet.confidence && String(bet.confidence).trim()
                ? `<div class="chat-bet-confidence">Confidence: ${escapeHtml(String(bet.confidence).trim())}</div>`
                : '';
        return `
            <div class="chat-bet-card ${variantClass}">
                ${thumb}
                <div class="chat-bet-mid">
                    <div class="chat-bet-label">${escapeHtml(bet.label || '')}</div>
                    <div class="chat-bet-headline">${escapeHtml(bet.headline || '')}</div>
                    <div class="chat-bet-subtitle">${escapeHtml(bet.subtitle || '')}</div>
                    ${confidenceLine}
                </div>
                <div class="chat-bet-right">
                    <span class="chat-bet-odds">${escapeHtml(bet.odds)}</span>
                </div>
            </div>`;
    }

    function appendMessageRow(msg) {
        const el = document.getElementById('chat-messages');
        if (!el) return;

        const userClass =
            msg.message_type === 'bet' && msg.bet ? usernameClassForBet(msg.bet) : 'name-default';

        let inner = '';
        if (msg.message_type === 'bet' && msg.bet) {
            inner = renderBetCard(msg.bet);
        } else {
            inner = `<div class="chat-bubble">${escapeHtml(msg.body || '')}</div>`;
        }

        const row = document.createElement('div');
        row.className = 'chat-msg';
        row.dataset.msgId = String(msg.id);
        row.innerHTML = `
            <div class="chat-msg-avatar">${escapeHtml(initialsFromUser(msg.user))}</div>
            <div class="chat-msg-body">
                <div class="chat-msg-meta">
                    <span class="chat-msg-user ${userClass}">${escapeHtml(msg.user)}</span>
                    <span class="chat-msg-time">${escapeHtml(formatMsgTime(msg.created_at))}</span>
                </div>
                ${inner}
            </div>`;
        el.appendChild(row);
        scrollChatToBottom();
    }

    function clearEmptyPlaceholder() {
        const el = document.getElementById('chat-messages');
        if (!el) return;
        el.querySelectorAll('.chat-share-empty').forEach((n) => n.remove());
    }

    async function fetchMessages(initial) {
        const url = initial
            ? `/chat/messages?after_id=0&limit=${MAX_INITIAL}`
            : `/chat/messages?after_id=${lastMessageId}&limit=50`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('chat fetch failed');
        return res.json();
    }

    async function loadInitialMessages() {
        const el = document.getElementById('chat-messages');
        if (!el) return;
        const existingIds = new Set();
        try {
            const data = await fetchMessages(true);
            el.innerHTML = '';
            lastMessageId = 0;
            data.forEach((msg) => {
                existingIds.add(msg.id);
                appendMessageRow(msg);
                if (msg.id > lastMessageId) lastMessageId = msg.id;
            });
            if (data.length === 0) {
                el.innerHTML =
                    '<p class="chat-share-empty" style="padding:24px 8px;">No messages yet. Say hello or share a pick.</p>';
            }
        } catch (e) {
            console.error(e);
            el.innerHTML =
                '<p class="chat-share-empty" style="color:#f87171;">Could not load chat. Is the server running?</p>';
        }
        scrollChatToBottom();
    }

    async function pollNew() {
        if (lastMessageId <= 0) return;
        try {
            const data = await fetchMessages(false);
            const el = document.getElementById('chat-messages');
            if (!el) return;
            const existing = new Set(
                [...el.querySelectorAll('.chat-msg[data-msg-id]')].map((n) => Number(n.dataset.msgId))
            );
            const placeholder = el.querySelector('.chat-share-empty');
            if (placeholder && data.length) placeholder.remove();
            data.forEach((msg) => {
                if (!existing.has(msg.id)) {
                    existing.add(msg.id);
                    appendMessageRow(msg);
                    if (msg.id > lastMessageId) lastMessageId = msg.id;
                }
            });
        } catch (e) {
            console.warn('chat poll', e);
        }
    }

    async function postChatMessage(payload) {
        const res = await fetch('/chat/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || 'Send failed');
        return data;
    }

    function getUsername() {
        const inp = document.getElementById('username');
        return (inp && inp.value && inp.value.trim()) || '';
    }

    function isChatDrawerLayout() {
        return window.matchMedia('(max-width: 1023px)').matches;
    }

    function openDrawer(open) {
        const side = document.getElementById('community-chat-sidebar');
        const back = document.getElementById('chat-backdrop');
        const toggle = document.getElementById('chat-drawer-toggle');
        if (!side) return;
        side.classList.toggle('is-open', open);
        if (back) {
            if (isChatDrawerLayout()) {
                back.classList.toggle('is-visible', open);
                back.setAttribute('aria-hidden', open ? 'false' : 'true');
            } else {
                back.classList.remove('is-visible');
                back.setAttribute('aria-hidden', 'true');
            }
        }
        if (toggle) {
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        }
        if (open) scrollChatToBottom();
    }

    function setupDrawer() {
        const toggle = document.getElementById('chat-drawer-toggle');
        const back = document.getElementById('chat-backdrop');
        if (toggle) {
            toggle.addEventListener('click', () => {
                const side = document.getElementById('community-chat-sidebar');
                const isOpen = side && side.classList.contains('is-open');
                openDrawer(!isOpen);
            });
        }
        if (back) {
            back.addEventListener('click', () => openDrawer(false));
        }
    }

    async function sendText() {
        const input = document.getElementById('chat-input');
        const user = getUsername();
        if (!user) {
            alert('Enter your name in the header to chat.');
            return;
        }
        const text = (input && input.value && input.value.trim()) || '';
        if (!text) return;
        try {
            const data = await postChatMessage({ user, message_type: 'text', body: text });
            if (input) input.value = '';
            clearEmptyPlaceholder();
            appendMessageRow(data);
            if (data.id > lastMessageId) lastMessageId = data.id;
        } catch (e) {
            alert(e.message || 'Could not send');
        }
    }

    function openShareModal() {
        const modal = document.getElementById('chat-share-modal');
        const list = document.getElementById('chat-share-list');
        const empty = document.getElementById('chat-share-empty');
        if (!modal || !list) return;

        const user = getUsername();
        if (!user) {
            alert('Enter your name in the header to share picks.');
            return;
        }

        const core = window.NFLPredictorCore;
        if (!core || !core.loadUserPicks || !core.getWeeklyMatchups) {
            alert('App not ready. Try again in a moment.');
            return;
        }

        core
            .loadUserPicks()
            .then((picks) => {
                const games = core.getWeeklyMatchups() || [];
                const { season, week } = core.getSeasonWeek();
                const weekPicks = picks.filter((p) => String(p.season) === String(season) && String(p.week) === String(week));

                list.innerHTML = '';
                if (!weekPicks.length) {
                    empty.hidden = false;
                    modal.classList.add('is-open');
                    modal.setAttribute('aria-hidden', 'false');
                    return;
                }
                empty.hidden = true;

                weekPicks.forEach((p) => {
                    const game = games.find(
                        (g) => g.home_team === p.home_team && g.away_team === p.away_team
                    );
                    if (!game) return;

                    const row = document.createElement('div');
                    row.className = 'chat-share-row';
                    row.innerHTML = `
                        <div class="chat-share-matchup">${escapeHtml(p.away_team)} @ ${escapeHtml(p.home_team)} — <strong>${escapeHtml(p.pick)}</strong></div>
                        <div class="chat-share-actions">
                            <button type="button" class="chat-share-variant lock" data-kind="lock">Lock</button>
                            <button type="button" class="chat-share-variant risky" data-kind="risky">Risky</button>
                        </div>`;

                    row.querySelectorAll('.chat-share-variant').forEach((btn) => {
                        btn.addEventListener('click', async () => {
                            const kind = btn.getAttribute('data-kind');
                            let confidenceNote = '';
                            if (kind === 'risky') {
                                const conf = window.prompt(
                                    'How confident are you in this pick?\n(e.g. "8/10", "65%", or a short note)',
                                    ''
                                );
                                if (conf === null) return;
                                confidenceNote = conf.trim();
                                if (!confidenceNote) {
                                    alert('Add how confident you are so others have context.');
                                    return;
                                }
                            }
                            const bet = buildBetPayload(game, p.pick, kind, confidenceNote);
                            try {
                                const data = await postChatMessage({ user, message_type: 'bet', bet });
                                modal.classList.remove('is-open');
                                modal.setAttribute('aria-hidden', 'true');
                                clearEmptyPlaceholder();
                                appendMessageRow(data);
                                if (data.id > lastMessageId) lastMessageId = data.id;
                            } catch (err) {
                                alert(err.message || 'Could not share pick');
                            }
                        });
                    });

                    list.appendChild(row);
                });

                if (!list.children.length) {
                    empty.hidden = false;
                    empty.textContent =
                        'Games for this week are not loaded. Open the AI Model tab to load the schedule, then try again.';
                }

                modal.classList.add('is-open');
                modal.setAttribute('aria-hidden', 'false');
            })
            .catch(() => {
                alert('Could not load your picks.');
            });
    }

    function closeShareModal() {
        const modal = document.getElementById('chat-share-modal');
        if (modal) {
            modal.classList.remove('is-open');
            modal.setAttribute('aria-hidden', 'true');
        }
    }

    function setupComposer() {
        const send = document.getElementById('chat-send-btn');
        const input = document.getElementById('chat-input');
        const share = document.getElementById('chat-share-pick-btn');
        const stats = document.getElementById('chat-stats-btn');
        const closeM = document.getElementById('chat-share-modal-close');

        if (send) send.addEventListener('click', () => sendText());
        if (input) {
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendText();
                }
            });
        }
        if (share) share.addEventListener('click', () => openShareModal());
        if (stats) {
            stats.addEventListener('click', () => {
                if (window.NFLPredictorCore && window.NFLPredictorCore.showTab) {
                    window.NFLPredictorCore.showTab('leaderboard');
                }
                openDrawer(false);
            });
        }
        if (closeM) closeM.addEventListener('click', closeShareModal);
        const modal = document.getElementById('chat-share-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) closeShareModal();
            });
        }
    }

    function startPolling() {
        if (pollTimer) clearInterval(pollTimer);
        pollTimer = setInterval(pollNew, POLL_MS);
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') pollNew();
        });
    }

    function initCommunityChat() {
        setupDrawer();
        setupComposer();
        setupSidebarWheelRouting();
        loadInitialMessages().then(() => startPolling());
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initCommunityChat);
    } else {
        initCommunityChat();
    }
})();
