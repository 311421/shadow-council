/* Each action has its own editable selection and explicit acceptance. */
const QuestChoices = (() => {
  const initial = () => ({accepted:[], selected:[]});
  const evil = new Set(['morgan','hunter','minion']);
  function flow(game, state=initial(), configuring=false) {
    const ids=game.players.map(p=>p.id), picks=state.accepted;
    if(!ids.includes(game.you)) return null;
    const player=(name,label,eligible,count=1,accept='Accept choice')=>({kind:'player',name,label,eligible,count,accept});
    const card=(kind,name,label,eligible,accept)=>({kind,name,label,eligible,count:1,accept});
    let steps=[],payload;
    switch(game.phase) {
      case 'lobby':
        if(!configuring||game.host!==game.you)return null;
        steps=[card('variant','variant','Choose the Good special character.',['youth','troublemaker'],'Accept character'),card('board','board','Choose the four-player board.',['A','B'],'Accept board & save settings')];
        payload={type:'configure',variant:picks[0],board:picks[1]};break;
      case 'proposal':
        if(game.leader!==game.you)return null;
        steps=[player('party',`Choose your party: ${game.team_size} players.`,ids,game.team_size,'Accept party'),player('magic','Choose the Magic holder.',picks[0]||[],1,'Accept Magic & send party')];
        payload={type:'propose',team:picks[0],magic:picks[1]};break;
      case 'transition':
        if(game.leader!==game.you)return null;
        steps=[player('leader','Choose the next leader.',game.eligible_leaders,1,'Accept leader')];
        if(game.amulet_due)steps.push(player('holder','Choose the amulet holder.',game.eligible_leaders.filter(id=>id!==picks[0]),1,'Accept amulet holder'));
        payload={type:'transition',leader:picks[0],holder:game.amulet_due?picks[1]:null};break;
      case 'amulet':
        if(game.amulet_holder!==game.you)return null;
        steps=[player('target','Choose a player to check with your amulet.',game.amulet_targets,1,'Accept target & investigate')];
        payload={type:'investigate',target:picks[0]};break;
      case 'hunt': {
        if(game.hunter_revealed!==game.you)return null;
        const targets=ids.concat(game.players.length<=5?['hidden']:[]);
        const roles=[...new Set(game.role_pool.filter(r=>!evil.has(r)))];
        if((roles.includes('duke')||roles.includes('archduke'))&&!roles.includes('servant'))roles.unshift('servant');
        steps=[player('target1','Choose your first Hunt target.',targets,1,'Accept first target'),card('role','role1','Name the first target’s character.',roles,'Accept first role'),player('target2','Choose your second Hunt target.',targets.filter(id=>id!==picks[0]),1,'Accept second target'),card('role','role2','Name the second target’s character.',picks[1]==='cleric'?roles.filter(r=>r!=='cleric'):['cleric'],'Accept role & lock Hunt')];
        payload={type:'hunt',guesses:[{target:picks[0],role:picks[1]},{target:picks[2],role:picks[3]}]};break;
      }
      case 'accusation':
        if(game.you_accused)return null;
        steps=[player('targets','Choose two players to accuse.',ids,2,'Accept accusations')];
        payload={type:'accuse',targets:picks[0]};break;
      case 'duke':case 'archduke': {
        if(game.your_role!==game.phase)return null;
        const sources=Object.entries(game.accusations).filter(([,t])=>t.length).map(([id])=>id);
        const targets=game.accusations[picks[0]]||[];
        steps=[player('source','Choose whose accusation to change.',sources,1,'Accept player'),player('hand','Choose the player their hand points at.',[...new Set(targets)],1,game.phase==='duke'?'Accept hand & lower it':'Accept hand')];
        if(game.phase==='archduke')steps.push(player('target','Choose where to redirect that hand.',ids,1,'Accept target & redirect'));
        payload={type:game.phase,source:picks[0],hand:targets.indexOf(picks[1]),...(game.phase==='archduke'?{target:picks[2]}:{})};break;
      }
      default:return null;
    }
    const step=steps[picks.length]||null, selected=state.selected;
    return {steps,step,index:picks.length,total:steps.length,payload,complete:!step,
      canAccept:!!step&&selected.length===step.count&&new Set(selected).size===selected.length&&selected.every(v=>step.eligible.includes(v))};
  }
  function toggle(game,state,value,configuring=false) {
    const current=flow(game,state,configuring),step=current?.step;
    if(!step||!step.eligible.includes(value))throw new Error('That choice is not available for this action.');
    if(state.selected.includes(value))return {...state,selected:state.selected.filter(v=>v!==value)};
    if(step.count===1)return {...state,selected:[value]};
    if(state.selected.length>=step.count)throw new Error(`Choose ${step.count} players. Click a selected portrait to deselect it first.`);
    return {...state,selected:[...state.selected,value]};
  }
  function accept(game,state,configuring=false) {
    const current=flow(game,state,configuring);
    if(!current?.canAccept)throw new Error('Complete this selection before accepting.');
    const value=current.step.count===1?state.selected[0]:[...state.selected];
    return {accepted:[...state.accepted,value],selected:[]};
  }
  function back(state) {
    if(!state.accepted.length)return {...state,selected:[]};
    const previous=state.accepted.at(-1);
    return {accepted:state.accepted.slice(0,-1),selected:Array.isArray(previous)?[...previous]:[previous]};
  }
  function reconcile(game,state,configuring=false) {
    let valid=initial();
    for(const value of state.accepted) {
      const values=Array.isArray(value)?value:[value],step=flow(game,valid,configuring)?.step;
      if(!step||values.length!==step.count||new Set(values).size!==values.length||!values.every(v=>step.eligible.includes(v)))return valid;
      valid={accepted:[...valid.accepted,Array.isArray(value)?[...value]:value],selected:[]};
    }
    const step=flow(game,valid,configuring)?.step;
    return {...valid,selected:step?state.selected.filter(v=>step.eligible.includes(v)).slice(0,step.count):[]};
  }
  return {initial,flow,toggle,accept,back,reconcile};
})();
if(typeof module!=='undefined')module.exports=QuestChoices;
