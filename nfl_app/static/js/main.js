let seasonsData = {};
let weeklyMatchups = [];
let allTeams = [];

const modal = document.getElementById('details-modal');
const modalBody = document.getElementById('modal-body');

const getCurrentUsername = () => {
    const el = document.getElementById('current-username');
    return (el && el.value && el.value.trim()) || '';
};

const updateAuthUI = () => {
    const myBetsButton = document.getElementById('my-bets-button');
    if (!myBetsButton) return;
    myBetsButton.style.display = getCurrentUsername() ? '' : 'none';
};

const showTab = (tabId) => {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    
    document.getElementById(tabId).classList.add('active');
    document.querySelector(`.tab-button[onclick="showTab('${tabId}')"]`).classList.add('active');
    
    if (tabId === 'leaderboard') {
        loadLeaderboard();
    } else if (tabId === 'my-picks') {
        loadMyPicks();
    } else if (tabId === 'my-bets') {
        loadMyBets();
    } else {
        onWeekChange();
    }
};

const savePick = (game, selectedTeam, teamElement, opponentElement) => {
    if (!getCurrentUsername()) {
        alert('Please log in to save picks.');
        return;
    }

    teamElement.classList.add('selected-pick');
    opponentElement.classList.remove('selected-pick');

    const seasonFromUi = parseInt(document.getElementById('season-select').value, 10);
    const weekFromUi = parseInt(document.getElementById('week-select').value, 10);
    const payload = {
        season: Number.isFinite(game.season) ? game.season : seasonFromUi,
        week: Number.isFinite(game.week) ? game.week : weekFromUi,
        home_team: game.home_team,
        away_team: game.away_team,
        pick: selectedTeam
    };

    fetch('/save_pick', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        credentials: 'same-origin',
        body: JSON.stringify(payload)
    })
    .then(res => {
        if (res.status === 401) {
            return res.json().then((d) => {
                throw new Error(d.error || 'Please log in to save picks.');
            });
        }
        return res.json();
    })
    .then(data => {
        if (data.error) {
            alert("Error: " + data.error);
            teamElement.classList.remove('selected-pick');
        } else {
            console.log(data.message);
        }
    })
    .catch(err => {
        console.error("Error saving pick:", err);
        alert("Network error: Could not connect to the server to save your pick.");
        teamElement.classList.remove('selected-pick');
    });
};

const loadUserPicks = async () => {
    const season = document.getElementById('season-select').value;
    const week = document.getElementById('week-select').value;

    if (!getCurrentUsername() || !season || !week) return [];

    try {
        const res = await fetch(
            `/get_user_picks?season=${encodeURIComponent(season)}&week=${encodeURIComponent(week)}`,
            { credentials: 'same-origin' }
        );
        if (!res.ok) return [];
        return await res.json();
    } catch (e) {
        console.error("Error loading user picks:", e);
        return [];
    }
};

window.NFLPredictorCore = {
    getWeeklyMatchups: () => weeklyMatchups,
    loadUserPicks,
    getCurrentUsername,
    getSeasonWeek: () => {
        const s = document.getElementById('season-select');
        const w = document.getElementById('week-select');
        return { season: s?.value, week: w?.value };
    },
    showTab,
};

const fetchAIPredictions = async () => {
    const season = document.getElementById('season-select').value;
    const week = document.getElementById('week-select').value;
    const gameList = document.getElementById('game-list');
    const weeklySummary = document.getElementById('weekly-summary');
    const weeklyHeader = document.getElementById('ai-weekly-header');

    if (!season || !week) return;

    const userPicks = await loadUserPicks();
    const pickMap = {}; 
    userPicks.forEach(p => pickMap[`${p.home_team}-${p.away_team}`] = p.pick);

    weeklyHeader.textContent = `Predictions for ${season} - Week ${week}`;
    gameList.innerHTML = `<div class="loader">Loading AI predictions...</div>`;
    weeklySummary.style.display = 'none';

    fetch(`/get_predictions?season=${season}&week=${week}`)
        .then(res => res.json())
        .then(data => {
            if (data.error) {
                gameList.innerHTML = `<p style="color: var(--incorrect-color); text-align:center;">${data.error}</p>`;
                return;
            }

            gameList.innerHTML = '';
            weeklyMatchups = data.predictions;

            if (data.weekly_stats && data.weekly_stats.record) {
                weeklySummary.innerHTML = `
                    <h3>AI Results for ${season} - Week ${week}</h3>
                    <div class="stats-container">
                        <div class="stat"><span class="stat-value">${data.weekly_stats.record}</span><span class="stat-label">Record</span></div>
                        <div class="stat"><span class="stat-value">${data.weekly_stats.accuracy}</span><span class="stat-label">Accuracy</span></div>
                        <div class="stat"><span class="stat-value">${data.weekly_stats.roi}</span><span class="stat-label">Simulated ROI</span></div>
                    </div>`;
                weeklySummary.style.display = 'block';
            }

            weeklyMatchups.forEach(game => {
                const card = document.createElement('div');
                card.className = 'game-card';

                let actualWinnerHtml = '';
                if (game.actual_winner) {
                    const isCorrect = game.predicted_winner === game.actual_winner;
                    const icon = isCorrect ? '<span class="prediction-icon correct">✓</span>' : '<span class="prediction-icon incorrect">✗</span>';
                    actualWinnerHtml = `<div class="actual-winner">${icon}Actual Winner: <span class="actual-winner-text ${isCorrect ? 'correct' : 'incorrect'}">${game.actual_winner}</span></div>`;
                }

                const key = `${game.home_team}-${game.away_team}`;
                const userPick = pickMap[key];
                const awaySelected = userPick === game.away_team ? 'selected-pick' : '';
                const homeSelected = userPick === game.home_team ? 'selected-pick' : '';

                card.innerHTML = `
                    <div class="teams">
                        <div class="team ${awaySelected}" id="away-${key}">
                            <img src="${game.away_logo}" alt="${game.away_team} logo" onerror="this.style.display='none'">
                            <span>${game.away_team}</span>
                        </div>
                        <span class="vs">@</span>
                        <div class="team ${homeSelected}" id="home-${key}">
                            <img src="${game.home_logo}" alt="${game.home_team} logo" onerror="this.style.display='none'">
                            <span>${game.home_team}</span>
                        </div>
                    </div>
                    <div class="ai-prediction-summary">
                        <div>AI Predicted Winner: <span class="ai-winner">${game.predicted_winner}</span> (${(game.confidence * 100).toFixed(1)}%)</div>
                        ${actualWinnerHtml} 
                        <button class="details-button">Show Details</button>
                    </div>
                `;

                const awayDiv = card.querySelector(`#away-${key}`);
                const homeDiv = card.querySelector(`#home-${key}`);
                
                awayDiv.addEventListener('click', () => savePick(game, game.away_team, awayDiv, homeDiv));
                homeDiv.addEventListener('click', () => savePick(game, game.home_team, homeDiv, awayDiv));
                
                card.querySelector('.details-button').addEventListener('click', () => showAIDetails(game));

                gameList.appendChild(card);
            });

            populateCustomGames();
        })
        .catch(err => {
            console.error(err);
            gameList.innerHTML = `<p style="color: var(--incorrect-color); text-align:center;">Failed to load predictions. Please check your network connection.</p>`;
        });
};

const populateCustomGames = () => {
    const season = document.getElementById('season-select').value;
    const week = document.getElementById('week-select').value;
    const customGameList = document.getElementById('custom-game-list');
    const weeklyHeader = document.getElementById('custom-weekly-header');
    
    if (!season || !week) return;
    
    weeklyHeader.textContent = `Matchups for ${season} - Week ${week}`;
    
    if (parseInt(week) === 1) { 
        customGameList.innerHTML = `<div class="dashboard"><p>The Custom Matchup Engine requires prior game data. Select Week 2 or later.</p></div>`; 
        return; 
    }
    
    customGameList.innerHTML = '';
    
    if (weeklyMatchups.length === 0) { 
        customGameList.innerHTML = `<div class="loader">Loading matchups...</div>`; 
        return; 
    }
    
    weeklyMatchups.forEach(game => {
        const newCard = document.createElement('div'); 
        newCard.className = 'game-card';
        newCard.innerHTML = `
            <div class="teams">
                <div class="team">
                    <img src="${game.away_logo}" alt="${game.away_team} logo" onerror="this.style.display='none'">
                    <span>${game.away_team}</span>
                </div>
                <span class="vs">VS</span>
                <div class="team">
                    <img src="${game.home_logo}" alt="${game.home_team} logo" onerror="this.style.display='none'">
                    <span>${game.home_team}</span>
                </div>
            </div>
            <button class="custom-predict-button" onclick="runCustomPrediction('${game.home_team}', '${game.away_team}', ${season}, ${week}, '${game.actual_winner}')">Build & Predict</button>
        `;
        customGameList.appendChild(newCard);
    });
};

const runCustomPrediction = (homeTeam, awayTeam, season, week, actualWinner) => {
    const weights = {
        offense_yards: parseInt(document.getElementById('offense-slider').value),
        offense_td: parseInt(document.getElementById('offense-td-slider').value),
        defense_yards: parseInt(document.getElementById('defense-slider').value),
        defense_td: parseInt(document.getElementById('defense-td-slider').value),
        turnovers: parseInt(document.getElementById('turnovers-slider').value),
        def_turnovers: parseInt(document.getElementById('def-turnover-slider').value)
    };

    modalBody.innerHTML = `<div class="loader">Calculating...</div>`; 
    openModal();

    fetch('/custom_predict', { 
        method: 'POST', 
        headers: {'Content-Type': 'application/json'}, 
        body: JSON.stringify({ home_team: homeTeam, away_team: awayTeam, season, week, weights }) 
    })
    .then(res => res.json())
    .then(result => {
        if (result.error) { 
            modalBody.innerHTML = `<h3>Error</h3><p style="color: var(--incorrect-color);">${result.error}</p>`; 
            return; 
        }
        
        let breakdownHtml = '<div class="breakdown-container">';
        result.breakdown.forEach(item => { 
            breakdownHtml += `
                <div class="breakdown-row">
                    <h5>${item.cat}</h5>
                    <div class="breakdown-stats">
                        <span>${item.a_val}</span>
                        <div class="breakdown-bar">
                            <div class="breakdown-bar-away" style="width: ${item.a_share * 100}%"></div>
                            <div class="breakdown-bar-home" style="width: ${item.h_share * 100}%"></div>
                        </div>
                        <span>${item.h_val}</span>
                    </div>
                </div>`; 
        }); 
        breakdownHtml += '</div>';

        let actualWinnerHtml = '';
        if (actualWinner && actualWinner !== 'null') { 
            const isCorrect = result.winner === actualWinner; 
            const icon = isCorrect ? '<span class="prediction-icon correct">✓</span>' : '<span class="prediction-icon incorrect">✗</span>'; 
            actualWinnerHtml = `<h4>${icon}Actual Winner: <span class="actual-winner-text ${isCorrect ? 'correct' : 'incorrect'}">${actualWinner}</span></h4>`; 
        }

        modalBody.innerHTML = `
            <h3>Custom Prediction Result</h3>
            <div class="teams">
                <div class="team"><span>${awayTeam}</span><h4>${result.away_score}</h4></div>
                <span class="vs">FINAL SCORE</span>
                <div class="team"><span>${homeTeam}</span><h4>${result.home_score}</h4></div>
            </div>
            <hr>
            <h4>Predicted Winner: <span style="color:var(--accent-color)">${result.winner}</span></h4>
            ${actualWinnerHtml}
            <h4>Scoring Breakdown:</h4>
            ${breakdownHtml}
        `;
    })
    .catch(err => {
        console.error("Error generating custom prediction:", err);
        modalBody.innerHTML = `<h3>Error</h3><p style="color: var(--incorrect-color);">Could not connect to the engine. Please verify the backend is running.</p>`;
    });
};

const buildSoSPanelHtml = (data, teamLabel) => {
    if (data.error) {
        return `<p class="sos-panel-error">${data.error}</p>`;
    }
    if (data.message) {
        return `<div class="sos-summary"><p>${data.message}</p></div>`;
    }
    const gamesCount = data.games_considered != null ? data.games_considered : (data.breakdown?.length ?? 0);
    const scorePrefix = data.total_score > 0 ? '+' : '';
    let tableHtml = `
        <div class="sos-summary">
            <p class="sos-panel-team">${teamLabel}</p>
            <h3>Total SoS Score: <span class="sos-score">${scorePrefix}${data.total_score}</span></h3>
            <p class="sos-games-count">Games counted: ${gamesCount}</p>
        </div>
        <div class="sos-table-container">
            <table class="sos-table">
                <thead><tr><th>Wk</th><th>Opp</th><th>Result</th><th>Margin</th><th>Opp Rec (entering)</th><th>Opp Strength</th><th>Game Value</th></tr></thead>
                <tbody>`;
    (data.breakdown || []).forEach(game => {
        const resultClass = game.result === 'W' ? 'sos-win' : (game.result === 'L' ? 'sos-loss' : '');
        tableHtml += `
                    <tr>
                        <td>${game.week}</td>
                        <td>${game.opponent}</td>
                        <td class="${resultClass}">${game.result}</td>
                        <td>${game.margin > 0 ? '+' : ''}${game.margin}</td>
                        <td>${game.opp_record}</td>
                        <td>${game.opp_strength ?? game.opp_win_pct ?? '—'}</td>
                        <td>${game.game_value > 0 ? '+' : ''}${game.game_value}</td>
                    </tr>`;
    });
    tableHtml += `</tbody></table></div>`;
    return tableHtml;
};

const sosFilterDescription = () => {
    const filter = document.querySelector('input[name="sos-filter"]:checked')?.value || 'all';
    if (filter === 'last5') return 'last 5 completed games (or fewer if not available)';
    if (filter === 'last3') return 'last 3 completed games (or fewer if not available)';
    return 'all completed games through the selected week';
};

const fetchSoSAnalysis = () => {
    const season = document.getElementById('season-select').value;
    const week = document.getElementById('week-select').value;
    const team = document.getElementById('sos-team-select').value;
    const compareTeam = document.getElementById('sos-compare-team-select').value;
    const filter = document.querySelector('input[name="sos-filter"]:checked').value;
    const resultsDiv = document.getElementById('sos-results');
    const compareDiv = document.getElementById('sos-compare-results');
    const noteEl = document.getElementById('sos-compare-note');

    const clearNote = () => { if (noteEl) noteEl.textContent = ''; };

    if (!team || !season || !week) {
        resultsDiv.innerHTML = `<div class="loader">Select a team and week.</div>`;
        if (compareDiv) {
            compareDiv.innerHTML = `<div class="sos-compare-placeholder">Select a comparison team to see their SoS for the same season, week, and filter.</div>`;
        }
        clearNote();
        return;
    }

    const baseParams = `season=${encodeURIComponent(season)}&week=${encodeURIComponent(week)}&filter=${encodeURIComponent(filter)}`;
    const primaryUrl = `/get_sos_analysis?${baseParams}&team=${encodeURIComponent(team)}`;

    resultsDiv.innerHTML = `<div class="loader">Analyzing Strength of Schedule for ${team}...</div>`;

    const applyComparePlaceholder = (html) => {
        if (compareDiv) compareDiv.innerHTML = html;
    };

    if (!compareTeam) {
        applyComparePlaceholder(`<div class="sos-compare-placeholder">Select a comparison team to see their SoS for the same season, week, and filter.</div>`);
        clearNote();
        fetch(primaryUrl)
            .then(res => res.json())
            .then(data => {
                resultsDiv.innerHTML = buildSoSPanelHtml(data, team);
            })
            .catch(err => {
                console.error("Error fetching SoS:", err);
                resultsDiv.innerHTML = `<p class="sos-panel-error">Network error: Could not load SoS analysis.</p>`;
            });
        return;
    }

    if (compareTeam === team) {
        applyComparePlaceholder(`<p class="sos-compare-hint">Choose a different team than the primary selection.</p>`);
        clearNote();
        fetch(primaryUrl)
            .then(res => res.json())
            .then(data => {
                resultsDiv.innerHTML = buildSoSPanelHtml(data, team);
            })
            .catch(err => {
                console.error("Error fetching SoS:", err);
                resultsDiv.innerHTML = `<p class="sos-panel-error">Network error: Could not load SoS analysis.</p>`;
            });
        return;
    }

    applyComparePlaceholder(`<div class="loader">Loading comparison for ${compareTeam}...</div>`);

    Promise.all([
        fetch(primaryUrl).then(res => res.json()),
        fetch(`/get_sos_analysis?${baseParams}&team=${encodeURIComponent(compareTeam)}`).then(res => res.json())
    ])
        .then(([primaryData, compareData]) => {
            resultsDiv.innerHTML = buildSoSPanelHtml(primaryData, team);
            compareDiv.innerHTML = buildSoSPanelHtml(compareData, compareTeam);

            const n1 = primaryData.games_considered ?? primaryData.breakdown?.length;
            const n2 = compareData.games_considered ?? compareData.breakdown?.length;
            const hasBoth =
                !primaryData.error && !compareData.error && !primaryData.message && !compareData.message;
            if (noteEl && hasBoth && n1 != null && n2 != null && n1 !== n2) {
                const filterDesc = sosFilterDescription();
                noteEl.textContent =
                    `Each team uses the ${filterDesc} through Week ${week}. ${team}: ${n1} game(s); ${compareTeam}: ${n2} game(s).`;
            } else {
                clearNote();
            }
        })
        .catch(err => {
            console.error("Error fetching SoS:", err);
            resultsDiv.innerHTML = `<p class="sos-panel-error">Network error: Could not load SoS analysis.</p>`;
            compareDiv.innerHTML = `<p class="sos-panel-error">Network error: Could not load comparison.</p>`;
            clearNote();
        });
};

const loadMyPicks = () => {
    const messageEl = document.getElementById('my-picks-message');
    const listEl = document.getElementById('my-picks-list');

    if (!getCurrentUsername()) {
        messageEl.textContent = 'Log in to see your picks.';
        messageEl.className = 'my-picks-message prompt';
        listEl.innerHTML = '';
        return;
    }

    messageEl.textContent = '';
    messageEl.className = 'my-picks-message';
    listEl.innerHTML = '<div class="loader">Loading your picks...</div>';

    fetch('/get_my_picks', { credentials: 'same-origin' })
        .then(res => res.json())
        .then(picks => {
            if (!picks || picks.length === 0) {
                listEl.innerHTML = '<div class="my-picks-empty">No picks yet. Make your selections in the AI Model tab!</div>';
                return;
            }

            const byGroup = {};
            picks.forEach(p => {
                const key = `${p.season}-${p.week}`;
                if (!byGroup[key]) byGroup[key] = { season: p.season, week: p.week, games: [] };
                byGroup[key].games.push(p);
            });
            const groups = Object.values(byGroup);

            let html = '';
            groups.forEach(group => {
                html += `<div class="my-picks-group">
                    <h3 class="my-picks-group-title">${group.season} Season — Week ${group.week}</h3>
                    <div class="my-picks-cards">`;
                group.games.forEach(game => {
                    const awayIsPick = game.pick === game.away_team;
                    const homeIsPick = game.pick === game.home_team;
                    html += `
                        <div class="my-picks-card">
                            <div class="my-picks-matchup">
                                <span class="my-picks-team ${awayIsPick ? 'picked' : ''}">${game.away_team}</span>
                                <span class="my-picks-vs">@</span>
                                <span class="my-picks-team ${homeIsPick ? 'picked' : ''}">${game.home_team}</span>
                            </div>
                            <div class="my-picks-badge">You picked <strong>${game.pick}</strong></div>
                        </div>`;
                });
                html += '</div></div>';
            });
            listEl.innerHTML = html;
        })
        .catch(err => {
            console.error('Error loading my picks:', err);
            listEl.innerHTML = '<div class="my-picks-message error">Could not load your picks. Check your connection.</div>';
        });
};

const loadMyBets = () => {
    const season = document.getElementById('season-select').value;
    const week = document.getElementById('week-select').value;

    const messageEl = document.getElementById('my-bets-message');
    const listEl = document.getElementById('my-bets-list');
    const summaryEl = document.getElementById('my-bets-summary');

    const formatMoney = (n) => {
        const num = Number(n || 0);
        if (num === 0) return '$0.00';
        const abs = Math.abs(num).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        return num > 0 ? `+$${abs}` : `-$${abs}`;
    };

    if (!getCurrentUsername()) {
        if (summaryEl) summaryEl.innerHTML = '';
        messageEl.textContent = 'Log in to see your bets.';
        messageEl.className = 'my-bets-message prompt';
        listEl.innerHTML = '';
        return;
    }

    messageEl.textContent = '';
    messageEl.className = 'my-bets-message';
    summaryEl.innerHTML = '';
    listEl.innerHTML = '<div class="loader">Loading your bets...</div>';

    const params = new URLSearchParams();
    if (season) params.append('season', season);
    if (week) params.append('week', week);

    fetch(`/get_my_bets?${params.toString()}`, { credentials: 'same-origin' })
        .then(res => res.json())
        .then(bets => {
            if (!bets || bets.length === 0) {
                listEl.innerHTML = '<div class="my-bets-empty">No bets yet for this week. Place picks in the AI Model tab first.</div>';
                return;
            }

            let wins = 0;
            let losses = 0;
            let pending = 0;
            let pushes = 0;
            let totalProfit = 0;

            bets.forEach(b => {
                totalProfit += Number(b.profit || 0);
                if (b.outcome === 'Win') wins++;
                else if (b.outcome === 'Loss') losses++;
                else if (b.outcome === 'Pending') pending++;
                else if (b.outcome === 'Push') pushes++;
            });

            const record = `${wins}-${losses}`;
            const profitText = formatMoney(totalProfit);

            summaryEl.innerHTML = `
                <div class="my-bets-summary-stats">
                    <div class="my-bets-stat">
                        <div class="my-bets-stat-value">${record}</div>
                        <div class="my-bets-stat-label">Record</div>
                    </div>
                    <div class="my-bets-stat">
                        <div class="my-bets-stat-value">${profitText}</div>
                        <div class="my-bets-stat-label">Profit</div>
                    </div>
                    <div class="my-bets-stat">
                        <div class="my-bets-stat-value">${pending}</div>
                        <div class="my-bets-stat-label">Pending</div>
                    </div>
                </div>
            `;

            const byGroup = {};
            bets.forEach(b => {
                const key = `${b.season}-${b.week}`;
                if (!byGroup[key]) byGroup[key] = { season: b.season, week: b.week, bets: [] };
                byGroup[key].bets.push(b);
            });

            const groups = Object.values(byGroup);
            let html = '';
            groups.forEach(group => {
                html += `<div class="my-bets-group">
                    <h3 class="my-bets-group-title">${group.season} Season — Week ${group.week}</h3>
                    <div class="my-bets-cards">`;

                group.bets.forEach(b => {
                    const outcome = b.outcome || 'Pending';
                    const profitTextForRow = outcome === 'Pending' ? '—' : formatMoney(b.profit);

                    const awayPicked = b.pick === b.away_team;
                    const homePicked = b.pick === b.home_team;

                    html += `
                        <div class="my-bets-card">
                            <div class="my-bets-pill-wrap">
                                <div class="my-bets-matchup">
                                    <span class="my-bets-team ${awayPicked ? 'picked' : ''}">${b.away_team}</span>
                                    <span class="my-bets-vs">@</span>
                                    <span class="my-bets-team ${homePicked ? 'picked' : ''}">${b.home_team}</span>
                                </div>
                            </div>
                            <div class="my-bets-pill-wrap" style="justify-content:flex-end;">
                                <div class="my-bets-badge">Bet: <strong>${b.pick}</strong></div>
                                <div class="my-bets-outcome ${outcome.toLowerCase()}">${outcome}</div>
                                <div class="my-bets-profit">${profitTextForRow}</div>
                            </div>
                        </div>
                    `;
                });

                html += '</div></div>';
            });

            listEl.innerHTML = html;
        })
        .catch(err => {
            console.error('Error loading my bets:', err);
            messageEl.textContent = 'Could not load your bets. Check your connection.';
            messageEl.className = 'my-bets-message error';
            listEl.innerHTML = '';
        });
};

const loadLeaderboard = () => {
    const tbody = document.getElementById('leaderboard-body');
    tbody.innerHTML = '<tr><td colspan="5" class="loader">Loading stats...</td></tr>';
    
    fetch('/leaderboard')
        .then(res => res.json())
        .then(data => {
            tbody.innerHTML = '';
            if (data.length === 0) { 
                tbody.innerHTML = '<tr><td colspan="5">No picks recorded yet.</td></tr>'; 
                return; 
            }
            
            data.forEach((entry, index) => {
                const profitClass = entry.raw_profit > 0 ? 'correct' : (entry.raw_profit < 0 ? 'incorrect' : '');
                tbody.innerHTML += `
                    <tr>
                        <td>${index + 1}</td>
                        <td>${entry.user}</td>
                        <td>${entry.record}</td>
                        <td>${entry.pct}</td>
                        <td class="${profitClass}">${entry.profit}</td>
                    </tr>`;
            });
        })
        .catch(err => {
            console.error("Error loading leaderboard:", err);
            tbody.innerHTML = '<tr><td colspan="5" style="color: var(--incorrect-color);">Network error: Failed to fetch leaderboard data.</td></tr>';
        });
};

const openModal = () => modal.style.display = 'block';
const closeModal = () => modal.style.display = 'none';

window.onclick = (event) => { 
    if (event.target == modal) closeModal(); 
};

const showAIDetails = (game) => {
    let breakdownHtml = '';
    if (game.prediction_breakdown) {
        breakdownHtml = '<div class="breakdown-container">';
        for (const [key, value] of Object.entries(game.prediction_breakdown)) {
            breakdownHtml += `<p><strong>${key}:</strong> ${value}</p>`;
        }
        breakdownHtml += '</div>';
    } else {
        breakdownHtml = `<p>Spread Line: ${game.spread_line}</p><p>Confidence: ${(game.confidence * 100).toFixed(1)}%</p>`;
    }

    let actualWinnerHtml = '';
    if (game.actual_winner && game.actual_winner !== 'null') {
        const isCorrect = game.predicted_winner === game.actual_winner;
        const icon = isCorrect ? '<span class="prediction-icon correct">✓</span>' : '<span class="prediction-icon incorrect">✗</span>';
        actualWinnerHtml = `<h4>${icon}Actual Winner: <span class="actual-winner-text ${isCorrect ? 'correct' : 'incorrect'}">${game.actual_winner}</span></h4>`;
    }

    modalBody.innerHTML = `
        <h3>AI Prediction Details</h3>
        <div class="teams">
            <div class="team">
                <img src="${game.away_logo}" alt="${game.away_team} logo" onerror="this.style.display='none'">
                <span>${game.away_team}</span>
            </div>
            <span class="vs">@</span>
            <div class="team">
                <img src="${game.home_logo}" alt="${game.home_team} logo" onerror="this.style.display='none'">
                <span>${game.home_team}</span>
            </div>
        </div>
        <hr>
        <h4>Predicted Winner: <span style="color:var(--accent-color)">${game.predicted_winner}</span></h4>
        ${actualWinnerHtml}
        <h4>Prediction Breakdown:</h4>
        ${breakdownHtml}
    `;
    openModal();
};

const onWeekChange = () => {
    if (document.getElementById('ai-model').classList.contains('active')) fetchAIPredictions();
    else if (document.getElementById('custom-engine').classList.contains('active')) fetchAIPredictions(); /* loads weeklyMatchups then populateCustomGames() */
    else if (document.getElementById('sos-analysis').classList.contains('active')) fetchSoSAnalysis();
    else if (document.getElementById('leaderboard').classList.contains('active')) loadLeaderboard();
};

const handleSeasonChange = () => {
    const season = document.getElementById('season-select').value;
    const weekSelect = document.getElementById('week-select');
    
    weekSelect.innerHTML = '';
    
    if (seasonsData[season]) {
        seasonsData[season].forEach(week => { 
            const option = document.createElement('option'); 
            option.value = week; 
            option.textContent = `Week ${week}`; 
            weekSelect.appendChild(option); 
        });
    }
    onWeekChange();
};

document.addEventListener('DOMContentLoaded', async () => {
    updateAuthUI();
    
    fetch('/get_performance_stats')
        .then(res => res.json())
        .then(stats => { 
            const el = document.getElementById('performance-summary');
            if (stats.error && el) {
                el.innerHTML = `<p style="color: var(--incorrect-color); text-align: center;">${stats.error}</p>`;
                return;
            }
            if (el) {
                el.innerHTML = `<h2>Model Performance (Overall)</h2><div class="stats-container"><div class="stat"><span class="stat-value">${stats.accuracy}</span><span class="stat-label">Accuracy</span></div><div class="stat"><span class="stat-value">${stats.simulated_roi}</span><span class="stat-label">ROI</span></div><div class="stat"><span class="stat-value">${stats.total_games_tested}</span><span class="stat-label">Games Tested</span></div></div>`; 
            }
        })
        .catch(err => {
            console.error("Error loading performance stats:", err);
            const el = document.getElementById('performance-summary');
            if (el) el.innerHTML = `<p style="color: var(--incorrect-color); text-align: center;">Error loading model metrics. Check server connection.</p>`;
        });

    // Login/register (and other minimal pages) extend base but have no schedule UI — skip NFL init.
    if (!document.getElementById('season-select')) {
        return;
    }

    try {
        const [currentWeekInfo, allSeasonsData, teamsData] = await Promise.all([ 
            fetch('/get_current_week_info').then(res => res.json()), 
            fetch('/get_seasons_weeks').then(res => res.json()),
            fetch('/get_teams').then(res => res.json())
        ]);
        
        seasonsData = allSeasonsData;
        allTeams = teamsData;
        
        const teamSelect = document.getElementById('sos-team-select');
        teamSelect.innerHTML = '<option value="">-- Select Team --</option>';
        allTeams.forEach(team => { 
            const option = document.createElement('option'); 
            option.value = team; 
            option.textContent = team; 
            teamSelect.appendChild(option); 
        });

        const compareSelect = document.getElementById('sos-compare-team-select');
        if (compareSelect) {
            compareSelect.innerHTML = '<option value="">— None —</option>';
            allTeams.forEach(team => {
                const option = document.createElement('option');
                option.value = team;
                option.textContent = team;
                compareSelect.appendChild(option);
            });
        }

        const seasonSelect = document.getElementById('season-select');
        seasonSelect.innerHTML = '';
        
        Object.keys(seasonsData).forEach(season => { 
            const option = document.createElement('option'); 
            option.value = season; 
            option.textContent = `${season} Season`; 
            seasonSelect.appendChild(option); 
        });

        if (currentWeekInfo && !currentWeekInfo.error) {
            seasonSelect.value = currentWeekInfo.season;
            handleSeasonChange(); 
            document.getElementById('week-select').value = currentWeekInfo.week;
        } else { 
            handleSeasonChange(); 
        }
        
        onWeekChange(); 
    } catch (e) {
        console.error("Initialization error:", e);
        document.querySelector('.container').insertAdjacentHTML('afterbegin', `<div class="dashboard" style="border-color: var(--incorrect-color);"><h3 style="color: var(--incorrect-color); text-align: center;">Connection Error</h3><p style="text-align: center;">Could not reach the server to load NFL data. Please verify the Flask backend is running.</p></div>`);
    }
});