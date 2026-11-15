/* Build the record only from the server's public snapshot, including old games. */
const VoteHistory = (() => {
  function attemptsFor(snapshot) {
    const counts = new Map();
    const attempts = snapshot.history.filter(event => event.type === 'vote').map(event => {
      const number = (counts.get(event.round) || 0) + 1;
      counts.set(event.round, number);
      return {...event, number, key: `${event.round}-${number}`, pending: false};
    });
    if (snapshot.phase === 'vote') {
      const number = (counts.get(snapshot.round) || 0) + 1;
      attempts.push({round: snapshot.round, number, key: `${snapshot.round}-${number}`,
        team: snapshot.team, votes: null, approved: null, pending: true});
    }
    return attempts;
  }
  return {attemptsFor};
})();
if (typeof module !== 'undefined') module.exports = VoteHistory;
