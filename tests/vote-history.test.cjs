const {test} = require('node:test');
const assert = require('node:assert/strict');
const {attemptsFor} = require('../static/vote-history.js');

const vote = (round, approved, team = ['a', 'b']) => ({type:'vote', round, approved, team, votes:{a:true, b:false, c:approved}});

test('keeps every party, numbering attempts separately for each expedition', () => {
  const first = vote(1, false), second = vote(1, true, ['b', 'c']), third = vote(2, false);
  const attempts = attemptsFor({phase:'proposal', round:2, history:[{type:'start'}, first, second, {type:'mission', round:1}, third]});
  assert.deepEqual(attempts.map(a => a.key), ['1-1', '1-2', '2-1']);
  assert.deepEqual(attempts[1].team, ['b', 'c']);
  assert.deepEqual(attempts[1].votes, second.votes);
});

test('pending party shows no individual vote values, even after submissions', () => {
  const snapshot = {phase:'vote', round:1, history:[vote(1,false)], team:['a','c'], voted:['a','b']};
  const pending = attemptsFor(snapshot)[1];
  assert.equal(pending.key, '1-2');
  assert.equal(pending.pending, true);
  assert.equal(pending.votes, null);
  assert.equal(pending.approved, null);
});

test('completed fifth attempt has a stable key and no duplicate during a mission', () => {
  const history = Array.from({length:5}, (_,i) => vote(1, i === 4));
  for (const phase of ['mission','finished']) {
    const attempts = attemptsFor({phase, round:1, history, team:['a','b']});
    assert.equal(attempts.length, 5);
    assert.equal(attempts[4].key, '1-5');
    assert.equal(attempts[4].approved, true);
  }
});

test('pending key remains the same when its public vote result arrives', () => {
  const history = [vote(1,false)];
  const pending = attemptsFor({phase:'vote', round:1, history, team:['a','b']})[1];
  const resolved = attemptsFor({phase:'mission', round:1, history:[...history, vote(1,true)]})[1];
  assert.equal(pending.key, resolved.key);
  assert.equal(resolved.pending, false);
});

test('supports existing game records without an attempt field and resets in a rematch', () => {
  assert.equal(attemptsFor({phase:'proposal', round:2, history:[vote(1,true)]})[0].number, 1);
  assert.deepEqual(attemptsFor({phase:'lobby', round:1, history:[]}), []);
});
