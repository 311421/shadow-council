const {test}=require('node:test');
const assert=require('node:assert/strict');
const {initial,flow,toggle,accept,back,reconcile}=require('../static/quest-choices.js');
const base=(phase,extra={})=>({phase,you:'a',host:'a',leader:'a',players:['a','b','c','d'].map(id=>({id,name:id})),team_size:3,eligible_leaders:['b','c','d'],amulet_due:true,amulet_holder:'a',amulet_targets:['b','c'],hunter_revealed:'a',role_pool:['servant','cleric','youth','morgan','hunter'],your_role:phase,you_accused:false,accusations:{b:['a','c'],c:['b','d']},...extra});
function stage(game,state,values,configuring=false) {
  for(const value of values)state=toggle(game,state,value,configuring);
  return accept(game,state,configuring);
}

test('selecting a full party does not advance until Accept party',()=>{
  const game=base('proposal');let state=initial();
  assert.equal(flow(game,state).canAccept,false);
  for(const id of ['a','b','c']) {
    state=toggle(game,state,id);
    assert.equal(flow(game,state).step.name,'party');
    assert.equal(state.accepted.length,0);
  }
  assert.equal(flow(game,state).canAccept,true);
  assert.throws(()=>toggle(game,state,'d'));
  state=accept(game,state);
  assert.deepEqual(state.accepted,[['a','b','c']]);
  assert.deepEqual(state.selected,[]);
  assert.equal(flow(game,state).step.name,'magic');
  assert.equal(flow(game,state).canAccept,false);
});

test('clicking a selected party portrait deselects it in the same stage',()=>{
  const game=base('proposal');let state=initial();
  for(const id of ['a','b','c'])state=toggle(game,state,id);
  state=toggle(game,state,'b');
  assert.deepEqual(state.selected,['a','c']);
  assert.equal(flow(game,state).step.name,'party');
  assert.equal(flow(game,state).canAccept,false);
  state=toggle(game,state,'d');
  assert.deepEqual(state.selected,['a','c','d']);
  assert.equal(flow(game,state).canAccept,true);
});

test('Magic is a separate editable selection with a separate acceptance',()=>{
  const game=base('proposal');let state=stage(game,initial(),['a','b','c']);
  assert.throws(()=>toggle(game,state,'d'));
  state=toggle(game,state,'b');
  assert.equal(flow(game,state).step.name,'magic');
  assert.equal(flow(game,state).complete,false);
  state=toggle(game,state,'b');
  assert.deepEqual(state.selected,[]);
  assert.equal(flow(game,state).canAccept,false);
  state=toggle(game,state,'a');state=toggle(game,state,'c');
  assert.deepEqual(state.selected,['c']);
  state=accept(game,state);
  assert.equal(flow(game,state).complete,true);
  assert.deepEqual(flow(game,state).payload,{type:'propose',team:['a','b','c'],magic:'c'});
});

test('Back restores the accepted party for direct portrait toggling',()=>{
  const game=base('proposal');let state=stage(game,initial(),['a','b','c']);
  state=toggle(game,state,'b');state=back(state);
  assert.deepEqual(state.accepted,[]);
  assert.deepEqual(state.selected,['a','b','c']);
  state=toggle(game,state,'a');
  assert.deepEqual(state.selected,['b','c']);
  state=toggle(game,state,'d');state=accept(game,state);
  assert.deepEqual(state.selected,[]);
  assert.deepEqual(flow(game,state).step.eligible,['b','c','d']);
});

test('incomplete selections cannot be accepted',()=>{
  const game=base('proposal');let state=toggle(game,initial(),'a');
  assert.throws(()=>accept(game,state));
  assert.throws(()=>accept(base('amulet'),initial()));
});

test('successor must be accepted before selecting the distinct amulet holder',()=>{
  const game=base('transition');let state=toggle(game,initial(),'b');
  assert.equal(flow(game,state).step.name,'leader');
  state=accept(game,state);
  assert.equal(flow(game,state).step.name,'holder');
  assert.throws(()=>toggle(game,state,'b'));
  state=stage(game,state,['c']);
  assert.deepEqual(flow(game,state).payload,{type:'transition',leader:'b',holder:'c'});
  const noAmulet=base('transition',{amulet_due:false});
  assert.equal(flow(noAmulet,stage(noAmulet,initial(),['b'])).complete,true);
});

test('amulet target remains deselectable until accepted',()=>{
  const game=base('amulet');assert.throws(()=>toggle(game,initial(),'a'));
  let state=toggle(game,initial(),'b');state=toggle(game,state,'b');
  assert.equal(flow(game,state).canAccept,false);
  state=stage(game,state,['c']);
  assert.deepEqual(flow(game,state).payload,{type:'investigate',target:'c'});
});

test('each Hunt target and role needs its own acceptance',()=>{
  const game=base('hunt');let state=initial();
  state=stage(game,state,['hidden']);
  assert.equal(flow(game,state).step.name,'role1');
  state=toggle(game,state,'servant');
  assert.equal(flow(game,state).step.name,'role1');
  state=accept(game,state);
  assert.throws(()=>toggle(game,state,'hidden'));
  state=stage(game,state,['b']);
  assert.deepEqual(flow(game,state).step.eligible,['cleric']);
  state=stage(game,state,['cleric']);
  assert.deepEqual(flow(game,state).payload,{type:'hunt',guesses:[{target:'hidden',role:'servant'},{target:'b',role:'cleric'}]});
});

test('Hunt retains role aliases and excludes hidden target with six players',()=>{
  const game=base('hunt',{players:['a','b','c','d','e','f'].map(id=>({id,name:id})),role_pool:['cleric','troublemaker','duke','morgan','hunter','minion']});
  assert.ok(!flow(game,initial()).step.eligible.includes('hidden'));
  let state=stage(game,initial(),['b']);
  assert.ok(flow(game,state).step.eligible.includes('servant'));
  assert.ok(!flow(game,state).step.eligible.includes('youth'));
});

test('the two accusations are selected together, toggled directly, and accepted once',()=>{
  const game=base('accusation');let state=toggle(game,initial(),'b');
  assert.equal(flow(game,state).canAccept,false);
  state=toggle(game,state,'d');assert.equal(flow(game,state).canAccept,true);
  state=toggle(game,state,'b');assert.equal(flow(game,state).canAccept,false);
  state=toggle(game,state,'a');state=accept(game,state);
  assert.deepEqual(flow(game,state).payload,{type:'accuse',targets:['d','a']});
  assert.equal(flow(base('accusation',{you_accused:true})),null);
});

test('Duke accepts the player, then accepts the selected hand',()=>{
  const game=base('duke');let state=stage(game,initial(),['b']);
  assert.deepEqual(flow(game,state).step.eligible,['a','c']);
  state=stage(game,state,['c']);
  assert.deepEqual(flow(game,state).payload,{type:'duke',source:'b',hand:1});
});

test('Archduke accepts source, hand, and new target separately',()=>{
  const game=base('archduke');let state=initial();
  for(const value of ['c','d','a'])state=stage(game,state,[value]);
  assert.deepEqual(flow(game,state).payload,{type:'archduke',source:'c',hand:1,target:'a'});
});

test('live updates keep accepted actions and valid active selections',()=>{
  const game=base('proposal');let state=stage(game,initial(),['a','b','c']);
  state=toggle(game,state,'b');
  assert.deepEqual(reconcile(game,state),state);
  const changed=base('proposal',{players:['a','c','d'].map(id=>({id,name:id}))});
  assert.deepEqual(reconcile(changed,state),initial());
});

test('settings require character acceptance then board acceptance',()=>{
  const game=base('lobby');assert.equal(flow(game),null);
  let state=toggle(game,initial(),'troublemaker',true);
  assert.equal(flow(game,state,true).step.name,'variant');
  state=accept(game,state,true);state=stage(game,state,['B'],true);
  assert.deepEqual(flow(game,state,true).payload,{type:'configure',variant:'troublemaker',board:'B'});
});

test('players cannot choose actions belonging to another actor',()=>{
  for(const phase of ['proposal','transition','amulet','hunt','duke','archduke'])assert.equal(flow(base(phase,{you:'spectator'})),null);
});
