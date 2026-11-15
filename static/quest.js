/* Quest interface. All role restrictions and phase transitions are server-owned. */
const QuestUI = (() => {
  const roleText = {
    servant:'Complete three expeditions, or expose every Evil player in the Final Quest.',
    cleric:'You privately know the first leader’s apparent allegiance. Hide your identity from the Hunter.',
    youth:'Normally play Success. If you receive Magic, you MUST play Failure.',
    troublemaker:'You are Good, but every allegiance check reports you as Evil.',
    duke:'During Good’s Last Chance, you may remove one remaining accusation.',
    archduke:'During Good’s Last Chance, you may redirect one remaining accusation.',
    morgan:'You are Evil. You may ignore Magic and play either expedition card.',
    hunter:'You are Evil but do not know your teammates. After the final discussion, choose whether to Hunt.',
    minion:'Help fail expeditions. Magic forces you to play Success.'
  };
  let choices = QuestChoices.initial(), configuring = false, draftPhase = null;
  const roleName = role => game.role_names[role] || role;
  const currentFlow = () => QuestChoices.flow(game, choices, configuring);
  const targetName = id => id === 'hidden' ? 'Undealt Good card' : nameOf(id);
  const stepNames = {variant:'Character',board:'Board',magic:'Magic',leader:'Next leader',holder:'Amulet holder',target:'Target',target1:'First target',target2:'Second target',role1:'First role',role2:'Second role',source:'Whose hand',hand:'Current target'};
  function pickLabel(value, step) {
    if (step.kind === 'role' || step.kind === 'variant') return roleName(value);
    if (step.kind === 'board') return `Board ${value} · ${value === 'A' ? '3 / 2 / 3 / 2' : '3 / 2 / 2 / 3'}`;
    return targetName(value);
  }
  function choiceGuide() {
    const flow=currentFlow();if(!flow)return '';
    return `<section class="choice-guide" aria-live="polite"><span class="eyebrow">ACTION ${flow.index+1} OF ${flow.total}</span><h3 id="choice-title" tabindex="-1">${esc(flow.step.label)}</h3><p class="muted">${flow.step.kind==='player'?'Click portraits to select. Click a selected portrait again to deselect.':'Click a card to select it, or click it again to deselect.'} Accept this action when ready.</p><p class="selection-count">${choices.selected.length} / ${flow.step.count} selected</p>${choices.accepted.length?`<div class="choice-trail">${choices.accepted.map((value,index)=>{const step=flow.steps[index],values=Array.isArray(value)?value:[value];return `<span class="choice-chip accepted-choice"><span aria-hidden="true">✓</span><span><small>${esc(stepNames[step.name]||'Party')}</small>${values.map(v=>esc(pickLabel(v,step))).join(', ')}</span></span>`;}).join('')}</div>`:''}</section>`;
  }
  function choiceControls() {
    const flow=currentFlow(),kind=flow.step.kind;let cards='';
    if(kind!=='player')cards=`<div class="role-choice-grid">${flow.step.eligible.map(value=>`<button type="button" class="role-choice ${choices.selected.includes(value)?'selected':''}" data-qvalue="${value}" aria-pressed="${choices.selected.includes(value)}" ${busy?'disabled':''}><span class="role-choice-symbol" aria-hidden="true">${kind==='board'?'▦':'◇'}</span><b>${esc(pickLabel(value,flow.step))}</b><span class="muted">${kind==='board'?'Four-player expedition sizes':esc(roleText[value]||'')}</span></button>`).join('')}</div>`;
    return `${cards}<div class="action-row choice-controls"><button type="button" class="primary" data-qconfirm="true" ${busy||!flow.canAccept?'disabled':''}>${esc(flow.step.accept)}</button>${choices.accepted.length?`<button type="button" class="secondary" data-qnav="back" ${busy?'disabled':''}>← Back</button>`:''}${configuring?`<button type="button" class="ghost" data-qnav="cancel" ${busy?'disabled':''}>Cancel</button>`:''}${game.phase==='duke'||game.phase==='archduke'?`<button type="button" class="secondary" data-qskip="${game.phase}" ${busy?'disabled':''}>Pass</button>`:''}</div>${game.phase==='hunt'?'<p class="muted choice-note">One guess must name the Cleric. Duke and Archduke may be named as Loyal Servant.</p>':''}${game.phase==='accusation'?'<p class="muted choice-note">No further discussion. Accusations stay private until everyone accepts theirs.</p>':''}`;
  }
  function rolePanel() {
    if (game.phase === 'lobby') return `<section class="panel private-card"><span class="eyebrow">QUEST / DIRECTOR’S CUT</span><h2>A familiar face.<br>A hidden allegiance.</h2><p>Your character and private knowledge appear here once the game begins.</p></section>`;
    return `<section class="panel private-card ${game.your_allegiance === 'evil' ? 'saboteur' : ''}"><span class="eyebrow">YOUR CLASSIFIED IDENTITY</span><h2>${roleVisible ? esc(roleName(game.your_role)) : 'Loyalty: classified.'}</h2><p>${roleVisible ? `<b>${game.your_allegiance.toUpperCase()}</b> · ${roleText[game.your_role]}${game.allies.length ? '<br><b>Known Evil:</b> ' + game.allies.map(id=>esc(nameOf(id))).join(', ') : ''}` : 'Reveal your character privately. Keep your screen away from other players.'}</p><button class="role-button" data-command="role">${roleVisible ? 'Hide my role' : 'Reveal my role'}</button></section>
    ${roleVisible && game.your_checks.length ? `<section class="panel private-checks"><span class="eyebrow">PRIVATE INTELLIGENCE</span>${game.your_checks.map(check=>`<p><b>${esc(nameOf(check.target))}</b> appeared <strong class="${check.allegiance}">${check.allegiance.toUpperCase()}</strong><br><span class="muted">${esc(check.source)} check. Troublemaker appears Evil.</span></p>`).join('')}</section>` : ''}`;
  }
  function playerCard(p) {
    const flow=currentFlow(), choosing=flow?.step.kind==='player';
    const eligible=choosing && flow.step.eligible.includes(p.id);
    const chosen=choices.selected.includes(p.id);
    const tags = [p.id === game.you ? 'You' : '', p.id === game.host ? 'Host' : '', p.id === game.leader && game.phase !== 'lobby' ? 'Leader' : '',
      game.veterans.includes(p.id) ? 'Veteran' : '', game.amulets.some(a=>a.holder === p.id) ? 'Amulet' : '',
      game.magic === p.id ? 'Magic' : '', game.revealed_roles[p.id] ? roleName(game.revealed_roles[p.id]) : ''].filter(Boolean);
    const onParty = game.team.includes(p.id) || (game.phase==='proposal' && (choices.accepted[0]||[]).includes(p.id));
    const detail=p.id==='hidden'?'A possible Hunt target':tags.join(' · ') || 'Council member';
    return `<${choosing?'button type="button"':'div'} class="player quest-portrait ${chosen?'selected':''} ${onParty?'party-context':''} ${eligible?'pick-eligible':''}" data-qseat="${p.id}" ${choosing?`data-qpick="${p.id}" aria-label="Choose ${esc(p.name)}" aria-pressed="${chosen}" ${eligible&&!busy?'':'disabled'}`:''}><span class="avatar" aria-hidden="true">${p.id==='hidden'?'?':esc(p.name.slice(0,2).toUpperCase())}</span><div class="player-info"><div class="player-name">${esc(p.name)}</div><div class="player-detail">${esc(detail)}</div></div>${game.magic === p.id ? '<span class="magic-badge" title="Magic">✦</span>' : chosen?'<span class="picked-mark" aria-hidden="true">✓</span>':''}</${choosing?'button':'div'}>`;
  }
  function missions() {
    return `<div class="mission-track quest-track" style="--quest-count:${game.team_sizes.length}" aria-label="Expedition results">${game.team_sizes.map((size,i)=>{
      const m=game.missions[i];
      return `<div class="mission-slot ${m ? m.success ? 'success' : 'failed' : i === game.round-1 ? 'active' : ''}"><div class="number">EXPEDITION ${i+1}</div><div class="mission-icon">${m ? m.success ? '✓' : '×' : '◇'}</div><div class="mission-size">${m ? `${m.fails} Failure · ${m.success ? 'SUCCESS' : 'FAILED'}` : `${size} players`}</div>${(game.players.length >= 7 && i === 3)||(game.players.length >= 8 && i === 2) ? '<div class="threshold-note">2 Failures needed</div>' : ''}</div>`;
    }).join('')}</div>`;
  }
  function lobby() {
    const needed=Math.max(0,4-game.players.length);
    const host=game.host===game.you;
    return `<section class="panel"><div class="panel-title"><h3>Quest Director’s Cut</h3><span class="counter">${game.players.length} / 10 SEATED</span></div><div class="player-grid">${game.players.map(playerCard).join('')}</div>
    <p class="muted" style="margin-top:18px">No party votes. Every leader serves once. Magic and hidden characters change who you can trust.</p>
    <div class="lobby-settings"><span class="eyebrow">LOBBY SETTINGS</span><p><b>${esc(roleName(game.settings.variant))}</b> for 6+ players · <b>Board ${game.settings.board}</b> for 4 players</p>${host ? (configuring?choiceGuide()+choiceControls():`<button type="button" class="secondary" data-qnav="configure" ${busy?'disabled':''}>Change settings</button>`) : ''}</div>
    <div class="lobby-bottom"><p class="muted">${configuring?'Save or cancel your settings before starting.':needed?`Invite ${needed} more player${needed===1?'':'s'} to begin.`:'Ready to begin. Use a voice call or play together in person.'}</p>${host?`<button class="primary" data-command="start" ${needed||busy||configuring?'disabled':''}>Begin Quest →</button>`:'<span class="muted">Waiting for the host…</span>'}</div></section>`;
  }
  function actions() {
    if(currentFlow()) return choiceControls();
    const phase=game.phase;
    if(phase==='proposal') return `<div class="waiting">${esc(nameOf(game.leader))} is choosing ${game.team_size} players and assigning Magic. The party goes directly on the expedition.</div>`;
    if(phase==='mission') {
      if(!game.team.includes(game.you)) return `<div class="waiting">${game.submitted_count} / ${game.team.length} expedition cards submitted.</div>`;
      if(game.you_submitted) return '<div class="waiting">Your card is locked. Waiting for the other party members.</div>';
      return `<div class="action-row">${game.mission_options.map(fail=>`<button class="${fail?'danger':'primary'}" data-qcard="${fail}" ${busy?'disabled':''}>${fail?'Play Failure':'Play Success'}</button>`).join('')}</div><p class="muted" style="margin-top:12px">${game.magic===game.you ? 'You hold Magic. Your character determines which cards are available.' : 'Your character determines which cards are available.'} Cards remain anonymous. ${game.fail_threshold} Failure${game.fail_threshold===1?'':'s'} needed.</p>`;
    }
    if(phase==='transition') return `<div class="waiting">${esc(nameOf(game.leader))} must choose a new leader${game.amulet_due?' and an amulet holder':''}.</div>`;
    if(phase==='amulet') return `<div class="waiting">${esc(nameOf(game.amulet_holder))} is using the amulet. The result is private.</div>`;
    if(phase==='discussion') return `<div class="discussion-clock" id="discussion-clock" data-until="${game.discussion_until}"></div><p class="muted">Discuss who is Evil for five minutes. Once the timer ends, all discussion must stop. The Blind Hunter privately chooses the next phase.</p>${game.your_role==='hunter' ? '<div class="action-row" style="margin-top:18px"><button class="danger" data-qdecision="true">Reveal myself and Hunt</button><button class="secondary" data-qdecision="false">Allow Good’s Last Chance</button></div>' : '<div class="waiting" style="margin-top:16px">After discussion, wait for the Hunt or Good’s Last Chance.</div>'}`;
    if(phase==='hunt') return `<div class="waiting">${esc(nameOf(game.hunter_revealed))} is the Blind Hunter. Only the Hunter may speak now.</div>`;
    if(phase==='accusation') return `<div class="waiting">Your two accusations are locked. ${game.accused_count} / ${game.players.length} players ready.</div>`;
    if(phase==='duke'||phase==='archduke') return `<div class="waiting">The ${roleName(phase)} may ${phase==='duke'?'remove':'redirect'} one accusation or pass.</div>`;
    return `${game.hidden_role?`<p class="muted">The undealt Good card was <b>${esc(roleName(game.hidden_role))}</b>.</p>`:''}${game.host===game.you?'<button class="primary" data-command="rematch">Open rematch lobby →</button>':'<div class="waiting">The host can open a rematch lobby.</div>'}`;
  }
  function accusations() {
    if(!Object.keys(game.accusations).length) return '';
    return `<section class="panel"><h3>Good’s Last Chance</h3><p class="muted" style="margin:10px 0">Evil’s hands are down. Good must collectively point at every Evil player and no Good players.</p>${Object.entries(game.accusations).map(([source,targets])=>`<p class="accusation-line"><b>${esc(nameOf(source))}</b> → ${targets.length?targets.map(t=>esc(nameOf(t))).join(', '):'No remaining accusations'}</p>`).join('')}</section>`;
  }
  function record() {
    const parties=game.history.filter(e=>e.type==='party');
    const expeditions=game.team_sizes.map((_,index)=>({round:index+1,party:parties.find(p=>p.round===index+1),result:game.missions.find(m=>m.round===index+1)}));
    return `<section class="panel quest-party-record"><div class="panel-title"><h3>Expedition history</h3><span class="counter">NO PARTY VOTES</span></div><p class="muted vote-legend">Players in rows, expeditions in columns. ● Party member · L Leader · ✦ Magic holder</p><div class="vote-table-scroll" role="region" aria-label="Player expedition history" tabindex="0"><table class="vote-table expedition-matrix"><caption class="sr-only">Each player's party membership, leadership, and Magic across expeditions.</caption><thead><tr><th scope="col">Player</th>${expeditions.map(e=>`<th scope="col">Expedition ${e.round}<span class="expedition-result ${e.result?e.result.success?'vote-yes':'vote-no':''}">${e.result?`${e.result.success?'Success':'Failed'} · ${e.result.fails} Failure${e.result.fails===1?'':'s'}`:e.party?'In progress':'Not started'}</span></th>`).join('')}</tr></thead><tbody>${game.players.map(player=>`<tr><th scope="row">${esc(player.name)}</th>${expeditions.map(e=>{
      const party=e.party,onTeam=party?.team.includes(player.id),leader=party?.leader===player.id,magic=party?.magic===player.id;
      const marks=[onTeam?'● Party':'',leader?'L Leader':'',magic?'✦ Magic':''].filter(Boolean);
      return `<td class="expedition-player-cell ${onTeam?'party-member':''}" aria-label="${esc(player.name)}, expedition ${e.round}: ${marks.length?marks.join(', '):party?'Not on the party':'Not started'}">${marks.length?marks.map(mark=>`<span>${mark}</span>`).join(''):'—'}</td>`;
    }).join('')}</tr>`).join('')}</tbody></table></div></section>`;
  }
  function log() {
    return `<section class="panel"><span class="eyebrow">PUBLIC RECORD</span><div class="log">${[...game.history].reverse().map(e=>`<div class="log-entry">${e.type==='party'?`<b>Expedition ${e.round}</b> · ${e.team.map(id=>esc(nameOf(id))).join(', ')}<br>Magic: ${esc(nameOf(e.magic))}`:e.type==='mission'?`<b>Expedition ${e.round} ${e.success?'succeeded':'failed'}</b><br>${e.fails} Failure card(s). ${e.threshold} needed.`:e.type==='transition'?`Next leader: ${esc(nameOf(e.leader))}${e.holder?'<br>Amulet: '+esc(nameOf(e.holder)):''}`:e.type==='investigation'?`${esc(nameOf(e.holder))} checked ${esc(nameOf(e.target))}. Result private.`:esc(e.text||'')}</div>`).join('')||'<p class="muted">The record begins when Quest starts.</p>'}</div></section>`;
  }
  function board() {
    const labels={proposal:['◇','Choose the expedition party.'],mission:['✦','The expedition is underway.'],transition:['↗','Pass on the leadership.'],amulet:['◈','An allegiance will be checked.'],discussion:['◷','The Final Quest begins.'],hunt:['◎','The Blind Hunter is hunting.'],accusation:['↗','Good’s Last Chance.'],duke:['◇','The Duke may lower one hand.'],archduke:['◇','The Archduke may redirect one hand.'],finished:['✓','Every secret has a story.']};
    const [icon,title]=labels[game.phase];
    return `${missions()}${game.phase==='finished'?`<div class="finished-banner ${game.winner==='evil'?'saboteur':''}"><span class="eyebrow">QUEST COMPLETE</span><h2>${game.winner==='good'?'Good prevails.':'Evil prevails.'}</h2><p class="muted">${esc(game.end_reason)}</p></div>`:''}<section class="panel"><div class="phase-banner"><span class="phase-marker">${icon}</span><div><h2>${title}</h2><p>${game.phase==='finished'?'All characters are now revealed.':`Leader: ${esc(nameOf(game.leader))} · Expedition ${game.round}`}</p></div></div>${choiceGuide()}<div class="player-grid">${game.players.map(playerCard).join('')}${game.phase==='hunt'&&game.players.length<=5?playerCard({id:'hidden',name:'Undealt Good card'}):''}</div><div class="action-area">${actions()}</div></section>${accusations()}${record()}`;
  }
  function renderRoom(focusStep=false) {
    const key=roomCode+':'+game.phase+':'+game.round;
    if(draftPhase!==key) {choices=QuestChoices.initial();configuring=false;draftPhase=key;}
    choices=QuestChoices.reconcile(game,choices,configuring);
    const active=document.activeElement;
    const focusTitle=active?.id==='choice-title';
    const focusAttr=['data-qpick','data-qvalue','data-qnav','data-qconfirm','data-command'].find(attr=>active?.hasAttribute(attr));
    const focusValue=focusAttr?active.getAttribute(focusAttr):null;
    const scroll=document.querySelector('.vote-table-scroll')?.scrollLeft||0;
    app.innerHTML=`<div class="room-top"><div><span class="eyebrow">QUEST / DIRECTOR’S CUT</span><h1>${game.phase==='lobby'?'A seat at the table.':'Trust is a dangerous game.'}</h1></div><div class="room-tools"><span class="room-code">${esc(roomCode)}</span><button class="secondary" data-command="invite">Copy invite ↗</button><span class="connection" id="connection">LIVE</span></div></div><div class="room-layout"><div>${game.phase==='lobby'?lobby():board()}</div><aside class="sidebar">${rolePanel()}<section class="panel"><span class="eyebrow">CHARACTERS IN PLAY</span><p class="muted">${game.role_pool.length?game.role_pool.map(r=>esc(roleName(r))).join(' · '):'Seat 4–10 players to see the character pool.'}${game.players.length<=5&&game.role_pool.length?'<br>One of these Good cards stays undealt and hidden.':''}</p></section>${log()}<div class="room-help">${rulesButton()}${game.phase==='lobby'?'<br><button class="ghost" data-command="leave">Leave my seat</button>':''}</div></aside></div>`;
    if(focusStep||focusTitle) document.querySelector('#choice-title')?.focus({preventScroll:true});
    else if(focusAttr) document.querySelector(`[${focusAttr}="${CSS.escape(focusValue)}"]:not(:disabled)`)?.focus({preventScroll:true});
    const table=document.querySelector('.vote-table-scroll');if(table)table.scrollLeft=scroll;
    tick();
  }
  function tick() {
    const clock=document.querySelector('#discussion-clock');
    if(!clock)return;
    const left=Math.max(0,Math.ceil(Number(clock.dataset.until)-Date.now()/1000));
    clock.textContent=left?`${Math.floor(left/60)}:${String(left%60).padStart(2,'0')} discussion remaining`:'Discussion is over. No further talking.';
    document.querySelectorAll('[data-qdecision]').forEach(button=>button.disabled=left>0||busy);
  }
  document.addEventListener('click',async event=>{
    const button=event.target.closest('button');
    if(!button||button.disabled||busy||!game||game.ruleset!=='quest')return;
    if(button.hasAttribute('data-qpick')||button.hasAttribute('data-qvalue')) {
      try {choices=QuestChoices.toggle(game,choices,button.dataset.qpick??button.dataset.qvalue,configuring);renderRoom();}
      catch(error) {toast(error.message);}
      return;
    }
    if(button.dataset.qnav) {
      if(button.dataset.qnav==='configure') {configuring=true;choices=QuestChoices.initial();}
      if(button.dataset.qnav==='cancel') {configuring=false;choices=QuestChoices.initial();}
      if(button.dataset.qnav==='back') choices=QuestChoices.back(choices);
      renderRoom(true);return;
    }
    if(button.hasAttribute('data-qconfirm')) {
      const flow=currentFlow();if(!flow?.canAccept)return;
      const accepted=QuestChoices.accept(game,choices,configuring);
      const next=QuestChoices.flow(game,accepted,configuring);
      if(next.complete) {
        if(await act(next.payload)) {choices=QuestChoices.initial();configuring=false;renderRoom(true);}
      } else {choices=accepted;renderRoom(true);}
      return;
    }
    if(button.hasAttribute('data-qcard'))await act({type:'mission',sabotage:button.dataset.qcard==='true'});
    if(button.hasAttribute('data-qdecision'))await act({type:'hunt_decision',hunt:button.dataset.qdecision==='true'});
    if(button.hasAttribute('data-qskip'))await act({type:button.dataset.qskip,skip:true});
  });
  setInterval(tick,1000);
  return {renderRoom};
})();
