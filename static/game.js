/* State comes from the server; local state contains presentation choices only. */
const app = document.querySelector('#app');
const roomCode = document.body.dataset.room;
let game = null, selected = new Set(), roleVisible = false, busy = false, polling = false, toastTimer;
let hoveredAttempt = null, focusedAttempt = null, pinnedAttempt = null;
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nameOf = id => game?.players.find(p => p.id === id)?.name || 'Unknown player';
const csrf = () => document.cookie.split('; ').find(c => c.startsWith('csrftoken='))?.split('=')[1] || '';
const base = () => `/api/rooms/${roomCode}/`;

function toast(message) {
  const el = document.querySelector('#toast'); el.textContent = message; el.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => {el.hidden = true;}, 5500);
}
async function request(url, data) {
  const response = await fetch(url, {method: data === undefined ? 'GET' : 'POST', credentials: 'same-origin',
    headers: data === undefined ? {} : {'Content-Type': 'application/json', 'X-CSRFToken': csrf()},
    body: data === undefined ? undefined : JSON.stringify(data), cache: 'no-store'});
  let result;
  try {result = await response.json();} catch {throw new Error(response.status === 404 ? 'Room not found. Check the invite code.' : 'The server could not complete this request.');}
  if (!response.ok) {const error = new Error(result.error || 'Something went wrong.'); error.status = response.status; error.data = result; throw error;}
  return result;
}

function savedName() {try {return localStorage.getItem('council-nickname') || '';} catch {return '';}}
function saveName(name) {try {localStorage.setItem('council-nickname', name);} catch { /* Cookies provide identity. */ }}
function rulesButton() {return '<button type="button" class="text-button" data-command="rules">Read the field manual ↗</button>';}
function renderHome() {
  app.innerHTML = `<div class="hero-grid"><section class="hero-copy"><span class="eyebrow">THE COUNCIL IS NOW IN SESSION</span>
    <h1>A familiar face.<br>A hidden <em>agenda.</em></h1>
    <p>Some of you are here to save the mission.<br>Some of you are here to ruin it.<br>Find out who you can trust.</p>
    <div class="tags"><span class="tag">4–10 friends</span><span class="tag">Quest Director’s Cut</span><span class="tag">Magic & hidden characters</span></div>
  </section><section class="entry-card" aria-label="Create or join a room"><div class="card-heading"><h2>Take your seat.</h2><span aria-hidden="true">↗</span></div>
    <form id="create-form"><label for="nickname">YOUR CALL SIGN</label><input id="nickname" name="name" autocomplete="nickname" placeholder="What should we call you?" minlength="2" maxlength="20" value="${esc(savedName())}" required>
    <button class="primary full" type="submit">Create a private room <span aria-hidden="true">→</span></button></form>
    <div class="divider">ALREADY HAVE AN INVITE?</div><form id="join-form"><label class="sr-only" for="code">Room code</label><div class="join-row"><input id="code" name="code" placeholder="ROOM CODE" pattern="[A-Za-z]{6}" maxlength="6" required><button class="secondary" type="submit">Join room</button></div></form>
    <p class="card-note">No account needed. Just a nickname and a little nerve.</p></section></div>
    <section class="briefing"><article><span class="step">01 /</span><div><h3>Keep your character close.</h3><p>Good or Evil? Special characters hold private knowledge and dangerous powers.</p></div></article>
    <article><span class="step">02 /</span><div><h3>Choose who to trust.</h3><p>Choose a party and assign Magic. Your successor will never lead twice.</p></div></article>
    <article><span class="step">03 /</span><div><h3>Face the Final Quest.</h3><p>Three successes save Good. If expeditions fail, the Hunt or Last Chance decides your fate.</p></div></article></section>
    <div style="margin-top:26px">${rulesButton()}</div>`;
  document.querySelector('#create-form').onsubmit = async e => {
    e.preventDefault(); const name = document.querySelector('#nickname').value.trim(); saveName(name);
    await entrySubmit(e.submitter, '/api/rooms/', {name});
  };
  document.querySelector('#join-form').onsubmit = e => {
    e.preventDefault(); saveName(document.querySelector('#nickname').value.trim());
    location.href = `/room/${document.querySelector('#code').value.trim().toUpperCase()}/`;
  };
}
async function entrySubmit(button, url, data) {
  button.disabled = true;
  try {const result = await request(url, data); location.href = result.url;} catch (error) {toast(error.message); button.disabled = false;}
}
function renderJoin() {
  app.innerHTML = `<section class="join-screen"><span class="eyebrow">PRIVATE INVITATION / ${esc(roomCode)}</span><h1>Your seat is waiting.</h1>
    <div class="entry-card"><h2>Join the council.</h2><form id="enter-form"><label for="nickname">YOUR CALL SIGN</label>
    <input id="nickname" name="name" autocomplete="nickname" value="${esc(savedName())}" placeholder="Choose a nickname" minlength="2" maxlength="20" required>
    <button class="primary full" type="submit">Enter room ${esc(roomCode)} →</button></form><p class="card-note">Your seat is saved in this browser. Keep your cookies to reconnect.</p></div><p style="margin-top:24px">${rulesButton()}</p></section>`;
  document.querySelector('#enter-form').onsubmit = async e => {
    e.preventDefault(); const name = document.querySelector('#nickname').value.trim(); saveName(name);
    await entrySubmit(e.submitter, base() + 'join/', {name});
  };
}
function renderRole() {
  if (game.phase === 'lobby') return `<section class="panel private-card"><span class="eyebrow">FOR YOUR EYES ONLY</span><h2>Everyone has<br>something to hide.</h2><p>Your secret role will appear here when the host starts the game.</p><span class="seal" aria-hidden="true">◈</span></section>`;
  const spy = game.your_role === 'saboteur';
  return `<section class="panel private-card ${spy ? 'saboteur' : ''}"><span class="eyebrow">YOUR CLASSIFIED IDENTITY</span>
    <h2>${roleVisible ? (spy ? 'The Saboteur' : 'The Operative') : 'Loyalty: classified.'}</h2>
    <p>${roleVisible ? (spy ? `Cause three failed missions. You may support to blend in.<br><b>Your faction:</b> ${game.allies.map(id => esc(nameOf(id))).join(', ')}.` : 'Complete three successful missions. You must support every mission you join. Trust carefully.') : 'Reveal your role privately. Make sure nobody is watching your screen.'}</p>
    <button class="role-button" data-command="role">${roleVisible ? 'Hide my role' : 'Reveal my role'}</button><span class="seal" aria-hidden="true">◈</span></section>`;
}
function playerCard(player, selectable = false) {
  const you = player.id === game.you, leader = player.id === game.leader, onTeam = game.team.includes(player.id);
  const chosen = selectable ? selected.has(player.id) : onTeam;
  const role = game.revealed_roles[player.id];
  const detail = [you ? 'You' : '', player.id === game.host ? 'Host' : '', game.phase !== 'lobby' && leader ? 'Leader' : '',
    game.phase === 'vote' && game.voted.includes(player.id) ? 'Vote locked' : '', role ? (role === 'saboteur' ? 'Saboteur' : 'Operative') : ''].filter(Boolean).join(' · ');
  return `<${selectable ? 'button type="button"' : 'div'} data-seat="${player.id}" class="player ${selectable ? 'selectable' : ''} ${chosen ? 'selected' : ''}" ${selectable ? `data-player="${player.id}" aria-pressed="${chosen}"` : ''}>
    <span class="avatar" aria-hidden="true">${esc(player.name.slice(0,2).toUpperCase())}</span><div class="player-info"><div class="player-name">${esc(player.name)}</div><div class="player-detail">${esc(detail || 'Council member')}</div></div>
    <span class="player-mark" aria-hidden="true">${chosen ? '✓' : (leader && game.phase !== 'lobby' ? '◇' : '')}</span><span class="historical-vote" hidden></span></${selectable ? 'button' : 'div'}>`;
}
function renderMissions() {
  const attempts = VoteHistory.attemptsFor(game);
  return `<div class="mission-track" aria-label="Mission results">${game.team_sizes.map((size, i) => {
    const mission = game.missions[i];
    const roundAttempts = attempts.filter(attempt => attempt.round === i + 1);
    return `<div class="mission-slot ${mission ? (mission.success ? 'success' : 'failed') : (i === game.round - 1 && game.phase !== 'finished' ? 'active' : '')}">
    <div class="number">EXPEDITION ${i + 1}</div><div class="mission-icon">${mission ? (mission.success ? '✓' : '×') : '◇'}</div><div class="mission-size">${mission ? (mission.success ? 'SUCCESS' : 'FAILED') : size + ' players'}</div>
    <div class="attempt-squares" aria-label="Expedition ${i + 1} party attempts">${Array.from({length:5}, (_, index) => {
      const attempt = roundAttempts[index];
      if (!attempt) return `<span class="attempt-square unused" aria-label="Attempt ${index + 1}: unused">${index + 1}</span>`;
      const status = attempt.pending ? 'pending' : attempt.approved ? 'approved' : 'rejected';
      const label = `Expedition ${i + 1}, attempt ${index + 1}: ${status}. Inspect party and votes`;
      return `<button type="button" class="attempt-square ${status}" data-attempt="${attempt.key}" aria-label="${label}" aria-pressed="false" title="${label}">${attempt.pending ? '…' : attempt.approved ? '✓' : '×'}</button>`;
    }).join('')}</div></div>`;
  }).join('')}</div><div class="attempt-inspector" id="attempt-inspector" aria-live="polite"><span class="muted">Hover an attempt to inspect its party and votes. Click to keep it open.</span></div>`;
}
function renderVoteTable() {
  const attempts=VoteHistory.attemptsFor(game);
  const expeditions=game.team_sizes.map((_,index)=>({round:index+1,attempts:attempts.filter(a=>a.round===index+1)}));
  return `<section class="panel vote-history"><div class="panel-title"><h3>Party vote history</h3><span class="counter">${attempts.filter(a=>!a.pending).length} COMPLETED</span></div><p class="muted vote-legend">Players in rows, expeditions in columns. Each numbered line is a party attempt. Shading marks party members. <span class="vote-yes">✓ Approve</span> · <span class="vote-no">× Reject</span> · — Unrevealed</p><div class="vote-table-scroll" role="region" aria-label="Votes by player and expedition" tabindex="0"><table class="vote-table expedition-matrix"><caption class="sr-only">Each player's votes, grouped by expedition and party attempt.</caption><thead><tr><th scope="col">Player</th>${expeditions.map(e=>`<th scope="col">Expedition ${e.round}${e.attempts.map(attempt=>`<button type="button" class="attempt-link attempt-column-button" data-attempt="${attempt.key}" aria-label="Inspect expedition ${e.round}, attempt ${attempt.number}" aria-pressed="false">${attempt.number} · ${attempt.pending?'Voting…':attempt.approved?'Approved':'Rejected'}</button>`).join('')}</th>`).join('')}</tr></thead><tbody>${game.players.map(player=>`<tr><th scope="row">${esc(player.name)}</th>${expeditions.map(e=>`<td class="player-votes">${e.attempts.length?e.attempts.map(attempt=>{
    const onTeam=attempt.team.includes(player.id),vote=attempt.votes?.[player.id];
    const label=attempt.pending?'Unrevealed':vote===true?'Approve':vote===false?'Reject':'Unavailable';
    return `<div class="vote-attempt ${onTeam?'party-member':''} ${attempt.pending?'':vote===true?'vote-yes':vote===false?'vote-no':''}" data-attempt="${attempt.key}" aria-label="${esc(player.name)}, expedition ${e.round}, attempt ${attempt.number}: ${label}${onTeam?', party member':''}"><small>${attempt.number}</small><span>${attempt.pending?'—':vote===true?'✓':vote===false?'×':'—'}</span>${onTeam?'<span class="party-dot" aria-hidden="true"></span>':''}</div>`;
  }).join(''):'—'}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`;
}
function updateAttemptPreview() {
  if (!game || game.phase === 'lobby' || game.ruleset === 'quest') return;
  const key = hoveredAttempt || focusedAttempt || pinnedAttempt;
  const attempt = VoteHistory.attemptsFor(game).find(item => item.key === key);
  document.querySelectorAll('[data-attempt]').forEach(el => {
    const active = !!attempt && el.dataset.attempt === key;
    el.classList.toggle('inspecting', active);
    if (el.tagName === 'BUTTON') el.setAttribute('aria-pressed', String(el.dataset.attempt === pinnedAttempt));
  });
  document.querySelectorAll('[data-seat]').forEach(card => {
    const id = card.dataset.seat, onTeam = !!attempt?.team.includes(id);
    card.classList.toggle('history-party', onTeam);
    card.classList.toggle('history-outside', !!attempt && !onTeam);
    const badge = card.querySelector('.historical-vote');
    badge.hidden = !attempt;
    const vote = attempt?.votes?.[id];
    badge.className = `historical-vote ${!attempt || attempt.pending ? 'vote-pending' : vote === true ? 'vote-yes' : vote === false ? 'vote-no' : 'vote-pending'}`;
    badge.textContent = !attempt ? '' : attempt.pending ? '— Unrevealed' : vote === true ? '✓ Approve' : vote === false ? '× Reject' : '— Unavailable';
  });
  const inspector = document.querySelector('#attempt-inspector');
  if (inspector) {
    const content = attempt ? `<div><strong>Expedition ${attempt.round} · Attempt ${attempt.number}</strong><span class="attempt-result ${attempt.pending ? 'pending' : attempt.approved ? 'approved' : 'rejected'}">${attempt.pending ? 'Voting in progress' : attempt.approved ? 'Party approved' : 'Party rejected'}</span><p>${attempt.team.map(id => esc(nameOf(id))).join(', ')}<span class="muted"> · ${attempt.pending ? 'Votes reveal together once everyone has voted.' : `${Object.values(attempt.votes).filter(Boolean).length} approve / ${Object.values(attempt.votes).filter(v => v === false).length} reject`}</span></p></div>${pinnedAttempt ? '<button class="text-button" data-command="clear-attempt">Clear</button>' : ''}` : '<span class="muted">Hover an attempt to inspect its party and votes. Click to keep it open.</span>';
    if (inspector.innerHTML !== content) inspector.innerHTML = content;
  }
}
function renderLog() {
  return `<section class="panel"><div class="panel-title"><span class="eyebrow">COUNCIL RECORD</span><span class="counter">PUBLIC</span></div><div class="log">${game.history.length ? [...game.history].reverse().map(event => {
    if (event.type === 'vote') return `<div class="log-entry"><strong>M${event.round} · Team ${event.approved ? 'approved' : 'rejected'}</strong>${event.team.map(id => esc(nameOf(id))).join(', ')}<div class="vote-breakdown">${Object.entries(event.votes).map(([id, yes]) => `${esc(nameOf(id))} ${yes ? '✓' : '×'}`).join(' · ')}</div></div>`;
    if (event.type === 'mission') return `<div class="log-entry"><strong>Mission ${event.round} ${event.success ? 'succeeded' : 'failed'}</strong>${event.fails} sabotage card${event.fails === 1 ? '' : 's'} revealed. ${event.threshold} needed to fail.</div>`;
    return `<div class="log-entry">${esc(event.text)}</div>`;
  }).join('') : '<p class="muted">Every vote tells a story.<br>The record begins with your first game.</p>'}</div></section>`;
}
function renderLobby() {
  const needed = Math.max(0, 5 - game.players.length);
  return `<section class="panel"><div class="panel-title"><h3>The waiting room</h3><span class="counter">${game.players.length} / 10 SEATED</span></div>
    <div class="player-grid">${game.players.map(p => playerCard(p)).join('')}${Array.from({length: Math.max(0, 5 - game.players.length)}, () => '<div class="player empty-seat"><span class="avatar">+</span><div class="player-info"><div class="player-name">An open seat</div><div class="player-detail">Invite a friend</div></div></div>').join('')}</div>
    <div class="lobby-bottom"><p class="muted">${needed ? `Waiting for ${needed} more player${needed === 1 ? '' : 's'}. Share the invite link to fill the table.` : 'The council is ready. Get everyone on a voice call before you begin.'}</p>
    ${game.host === game.you ? `<button class="primary" data-command="start" ${needed || busy ? 'disabled' : ''}>Begin the game →</button>` : '<span class="muted">Waiting for the host to start…</span>'}</div></section>`;
}
function renderActions() {
  if (game.phase === 'proposal') {
    if (game.you !== game.leader) return `<div class="waiting">${esc(nameOf(game.leader))} is choosing a team. Discuss who you trust while you wait.</div>`;
    return `<div class="action-row"><button class="primary" data-command="propose" ${selected.size !== game.team_size || busy ? 'disabled' : ''}>Propose team (${selected.size}/${game.team_size}) →</button></div><p class="muted">Select players above. You may include yourself.</p>`;
  }
  if (game.phase === 'vote') {
    if (game.voted.includes(game.you)) return `<div class="waiting">Your vote is locked. Waiting for ${game.players.length - game.voted.length} more vote${game.players.length - game.voted.length === 1 ? '' : 's'}.</div>`;
    return `<div class="action-row"><button class="primary" data-command="approve" ${busy ? 'disabled' : ''}>✓ Approve team</button><button class="secondary" data-command="reject" ${busy ? 'disabled' : ''}>× Reject team</button></div><p class="muted">Votes reveal together when everyone has voted. Your choice is final.</p>`;
  }
  if (game.phase === 'mission') {
    if (!game.team.includes(game.you)) return `<div class="waiting">The mission team is making its choice. ${game.submitted_count} / ${game.team.length} cards submitted.</div>`;
    if (game.you_submitted) return '<div class="waiting">Your card is locked. The outcome reveals when the whole team has submitted.</div>';
    return `<div class="action-row"><button class="primary" data-command="support" ${busy ? 'disabled' : ''}>Support mission</button>${game.your_role === 'saboteur' ? `<button class="danger" data-command="sabotage" ${busy ? 'disabled' : ''}>Sabotage mission</button>` : ''}</div><p class="muted">Your card stays anonymous. ${game.fail_threshold} sabotage card${game.fail_threshold === 1 ? '' : 's'} needed to fail this mission.</p>`;
  }
  return game.host === game.you ? '<button class="primary" data-command="rematch">Open rematch lobby →</button>' : '<div class="waiting">The host can open a new lobby for a rematch.</div>';
}
function renderBoard() {
  const labels = {
    proposal: ['◇', 'Who makes the team?', `${nameOf(game.leader)} leads mission ${game.round}. Choose ${game.team_size} players.`],
    vote: ['↗', 'Put your trust to a vote.', `${game.voted.length} of ${game.players.length} votes locked. A strict majority must approve.`],
    mission: ['◈', 'The mission is underway.', `${game.submitted_count} of ${game.team.length} secret cards submitted.`],
    finished: ['✓', 'Every secret has a story.', 'All roles are now revealed. Compare notes with the council.'],
  };
  const [icon, title, subtitle] = labels[game.phase];
  const selectable = game.phase === 'proposal' && game.leader === game.you;
  return `${renderMissions()}${game.phase === 'finished' ? `<div class="finished-banner ${game.winner}"><span class="eyebrow">OPERATION COMPLETE</span><h2>${game.winner === 'operative' ? 'The Operatives prevail.' : 'The Saboteurs prevail.'}</h2><p class="muted">${game.rejections === 5 ? 'Five consecutive teams rejected. The operation collapsed.' : 'Three missions decided the fate of the council.'}</p></div>` : ''}
    <section class="panel"><div class="phase-banner"><span class="phase-marker" aria-hidden="true">${icon}</span><div><h2>${title}</h2><p>${esc(subtitle)}</p></div></div>
    <div class="player-grid">${game.players.map(p => playerCard(p, selectable)).join('')}</div><div class="action-area">${renderActions()}</div></section>`;
}
function renderRoom() {
  if (game.ruleset === 'quest') {QuestUI.renderRoom(); return;}
  // Preserve keyboard focus and the public-log position across live updates.
  const focused = document.activeElement;
  const focusSelector = focused?.dataset.player ? `[data-player="${focused.dataset.player}"]` : focused?.dataset.command ? `[data-command="${focused.dataset.command}"]` : focused?.dataset.attempt ? `button[data-attempt="${focused.dataset.attempt}"]` : null;
  const logScroll = document.querySelector('.log')?.scrollTop || 0;
  const tableScroll = document.querySelector('.vote-table-scroll')?.scrollLeft || 0;
  app.innerHTML = `<div class="room-top"><div><span class="eyebrow">PRIVATE COUNCIL / ${game.phase === 'lobby' ? 'ASSEMBLING THE TEAM' : 'OPERATION IN PROGRESS'}</span><h1>${game.phase === 'lobby' ? 'A seat at the table.' : 'Trust is a dangerous game.'}</h1></div>
    <div class="room-tools"><span class="room-code">${esc(roomCode)}</span><button class="secondary" data-command="invite">Copy invite ↗</button><span class="connection" id="connection">LIVE</span></div></div>
    <div class="room-layout"><div>${game.phase === 'lobby' ? renderLobby() : renderBoard() + renderVoteTable()}</div><aside class="sidebar">${renderRole()}
    ${game.phase !== 'lobby' ? `<section class="panel"><span class="eyebrow">REJECTION PRESSURE</span><div class="rejection-track" aria-label="${game.rejections} of 5 rejections">${Array.from({length:5},(_,i)=>`<span class="rejection-pip ${i < game.rejections ? 'used' : ''}"></span>`).join('')}</div><p class="muted">${game.rejections} / 5 consecutive teams rejected.<br>Five rejections give saboteurs the win.</p></section>` : ''}
    ${renderLog()}<div class="room-help">${rulesButton()}${game.phase === 'lobby' ? '<br><button class="ghost" data-command="leave">Leave my seat</button>' : ''}</div></aside></div>`;
  if (focusSelector) document.querySelector(focusSelector)?.focus({preventScroll:true});
  const log = document.querySelector('.log'); if (log) log.scrollTop = logScroll;
  const table = document.querySelector('.vote-table-scroll'); if (table) table.scrollLeft = tableScroll;
  updateAttemptPreview();
}
function acceptState(next) {
  if (game && next.version < game.version) return;
  if (!game || game.phase !== next.phase || game.round !== next.round) selected.clear();
  if (game && next.phase === 'lobby' && game.phase !== 'lobby') {
    roleVisible = false;
    hoveredAttempt = focusedAttempt = pinnedAttempt = null;
  }
  game = next; renderRoom();
}
async function poll() {
  if (polling || busy || !roomCode) return;
  polling = true;
  try {
    const next = await request(base() + 'state/');
    if (!game || next.version > game.version) acceptState(next);
    const connection = document.querySelector('#connection'); if (connection) {connection.textContent = 'LIVE'; connection.classList.remove('offline');}
  } catch(error) {
    if (error.data?.join_required) {if (!document.querySelector('#enter-form')) renderJoin(); game = null;}
    else if (game) {const connection = document.querySelector('#connection'); if (connection) {connection.textContent = 'RECONNECTING'; connection.classList.add('offline');}}
    else if (!document.querySelector('#enter-form')) {app.innerHTML = '<section class="join-screen"><h2>Connection interrupted.</h2><p class="muted" style="margin-top:20px">Check your connection. We’ll keep trying to reconnect.</p><p style="margin-top:20px"><a href="/">Return home</a></p></section>';}
  } finally {polling = false;}
}
async function act(data) {
  if (busy || !game) return;
  busy = true; renderRoom();
  try {
    const next = await request(base() + 'action/', {...data, version: game.version});
    if (next.url) {location.href = next.url; return true;}
    acceptState(next);
    return true;
  } catch(error) {toast(error.message); return false;} finally {busy = false; if (game) renderRoom(); await poll();}
}
document.addEventListener('click', async event => {
  const attemptButton = event.target.closest('button[data-attempt]');
  if (attemptButton) {
    pinnedAttempt = pinnedAttempt === attemptButton.dataset.attempt ? null : attemptButton.dataset.attempt;
    updateAttemptPreview(); return;
  }
  const player = event.target.closest('[data-player]');
  if (player && !busy) {const id = player.dataset.player; if (selected.has(id)) selected.delete(id); else if (selected.size < game.team_size) selected.add(id); else toast(`Choose exactly ${game.team_size} players. Deselect someone first.`); renderRoom(); return;}
  const button = event.target.closest('[data-command]'); if (!button || button.disabled) return;
  switch(button.dataset.command) {
    case 'clear-attempt': hoveredAttempt = focusedAttempt = pinnedAttempt = null; updateAttemptPreview(); break;
    case 'rules': document.querySelector('#rules-dialog').showModal(); break;
    case 'role': roleVisible = !roleVisible; renderRoom(); break;
    case 'invite':
      try {await navigator.clipboard.writeText(location.origin + `/room/${roomCode}/`); toast('Invite link copied. Send it to your friends.');}
      catch {toast(`Room code: ${roomCode}. Share the URL in your address bar.`);} break;
    case 'propose': await act({type:'propose', team:[...selected]}); break;
    case 'approve': await act({type:'vote', approve:true}); break;
    case 'reject': await act({type:'vote', approve:false}); break;
    case 'support': await act({type:'mission', sabotage:false}); break;
    case 'sabotage': await act({type:'mission', sabotage:true}); break;
    case 'start': case 'rematch': case 'leave': await act({type:button.dataset.command}); break;
  }
});

// Inspect in place: rerendering the hovered button would cause pointer flicker.
document.addEventListener('pointerover', event => {
  const key = event.target.closest('[data-attempt]')?.dataset.attempt || null;
  if (hoveredAttempt !== key) {hoveredAttempt = key; updateAttemptPreview();}
});
document.addEventListener('pointerout', event => {
  const key = event.relatedTarget?.closest?.('[data-attempt]')?.dataset.attempt || null;
  if (hoveredAttempt !== key) {hoveredAttempt = key; updateAttemptPreview();}
});
document.addEventListener('focusin', event => {
  hoveredAttempt = null;
  focusedAttempt = event.target.closest('[data-attempt]')?.dataset.attempt || null;
  updateAttemptPreview();
});
document.addEventListener('focusout', event => {
  focusedAttempt = event.relatedTarget?.closest?.('[data-attempt]')?.dataset.attempt || null;
  updateAttemptPreview();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {hoveredAttempt = focusedAttempt = pinnedAttempt = null; updateAttemptPreview();}
});
document.querySelector('#close-rules').onclick = () => document.querySelector('#rules-dialog').close();
document.querySelector('#rules-dialog').addEventListener('click', event => {if (event.target === event.currentTarget) {const r = event.currentTarget.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) event.currentTarget.close();}});
document.addEventListener('visibilitychange', () => {if (!document.hidden && roomCode) poll();});
if (roomCode) {poll(); setInterval(() => {if (!document.hidden) poll();}, 1000);} else renderHome();
