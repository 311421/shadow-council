"""Pure game rules. No HTTP, database, or session dependencies."""
import copy
import secrets

TEAM_SIZES = {
    5: [2, 3, 2, 3, 3], 6: [2, 3, 4, 3, 4], 7: [2, 3, 3, 4, 4],
    8: [3, 4, 4, 5, 5], 9: [3, 4, 4, 5, 5], 10: [3, 4, 4, 5, 5],
}
SABOTEURS = {5: 2, 6: 2, 7: 3, 8: 3, 9: 3, 10: 4}


class RuleError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RuleError(message)


def lobby(players, host):
    return {'phase': 'lobby', 'players': players, 'host': host, 'roles': {},
            'leader': 0, 'round': 0, 'team': [], 'votes': {}, 'submissions': {},
            'rejections': 0, 'missions': [], 'history': [], 'winner': None}


def team_size(state):
    return TEAM_SIZES[len(state['players'])][min(state['round'], 4)]


def fail_threshold(state):
    return 2 if len(state['players']) >= 7 and state['round'] == 3 else 1


def leader_id(state):
    return state['players'][state['leader']]['id']


def apply_action(original, actor, action):
    state = copy.deepcopy(original)
    ids = [p['id'] for p in state['players']]
    require(actor in ids, 'You are not seated in this room.')
    kind = action.get('type')
    phase = state['phase']
    if kind == 'start':
        require(actor == state['host'], 'Only the host can start the game.')
        require(phase == 'lobby', 'The game has already started.')
        require(5 <= len(ids) <= 10, 'You need 5–10 players to start.')
        shuffled = ids[:]
        secrets.SystemRandom().shuffle(shuffled)
        spies = set(shuffled[:SABOTEURS[len(ids)]])
        state['roles'] = {pid: 'saboteur' if pid in spies else 'operative' for pid in ids}
        state['leader'] = secrets.randbelow(len(ids))
        state['phase'] = 'proposal'
        state['history'].append({'type': 'start', 'text': 'Roles assigned. The council is in session.'})
    elif kind == 'propose':
        require(phase == 'proposal', 'It is not time to propose a team.')
        require(actor == leader_id(state), 'Only the current leader can propose a team.')
        team = action.get('team')
        require(isinstance(team, list) and all(isinstance(x, str) for x in team), 'Choose a team.')
        require(len(team) == team_size(state) and len(set(team)) == len(team),
                f'Choose exactly {team_size(state)} different players.')
        require(all(pid in ids for pid in team), 'Unknown player in team.')
        state.update(team=team, votes={}, submissions={}, phase='vote')
    elif kind == 'vote':
        require(phase == 'vote', 'Team voting is closed.')
        require(actor not in state['votes'], 'Your vote is already locked in.')
        value = action.get('approve')
        require(type(value) is bool, 'Choose approve or reject.')
        state['votes'][actor] = value
        if len(state['votes']) == len(ids):
            approved = sum(state['votes'].values()) > len(ids) / 2
            state['history'].append({'type': 'vote', 'round': state['round'] + 1,
                'team': state['team'][:], 'votes': dict(state['votes']), 'approved': approved})
            if approved:
                state['phase'] = 'mission'
                state['rejections'] = 0
            else:
                state['rejections'] += 1
                state['leader'] = (state['leader'] + 1) % len(ids)
                state.update(phase='proposal', team=[], votes={})
                if state['rejections'] == 5:
                    state.update(phase='finished', winner='saboteur')
                    state['history'].append({'type': 'end', 'text': 'Five teams rejected. Saboteurs win.'})
    elif kind == 'mission':
        require(phase == 'mission', 'No mission is in progress.')
        require(actor in state['team'], 'Only the mission team may submit an action.')
        require(actor not in state['submissions'], 'Your mission action is already locked in.')
        value = action.get('sabotage')
        require(type(value) is bool, 'Choose support or sabotage.')
        require(not value or state['roles'][actor] == 'saboteur', 'Operatives must support the mission.')
        state['submissions'][actor] = value
        if len(state['submissions']) == len(state['team']):
            fails = sum(state['submissions'].values())
            result = {'round': state['round'] + 1, 'team': state['team'][:],
                      'fails': fails, 'threshold': fail_threshold(state),
                      'success': fails < fail_threshold(state)}
            state['missions'].append(result)
            state['history'].append({'type': 'mission', **result})
            successes = sum(m['success'] for m in state['missions'])
            failures = len(state['missions']) - successes
            # Erase the mapping between mission cards and individual players.
            state.update(submissions={}, votes={}, team=[])
            if successes == 3 or failures == 3:
                state.update(phase='finished', winner='operative' if successes == 3 else 'saboteur')
            else:
                state['round'] += 1
                state['leader'] = (state['leader'] + 1) % len(ids)
                state['phase'] = 'proposal'
    elif kind == 'rematch':
        require(actor == state['host'], 'Only the host can open a rematch.')
        require(phase == 'finished', 'Finish this game first.')
        return lobby(state['players'], state['host'])
    else:
        raise RuleError('Unknown action.')
    return state


def player_view(state, actor):
    """Allowlist public fields; never serialize the internal state wholesale."""
    phase = state['phase']
    role = state['roles'].get(actor)
    return {
        'phase': phase, 'players': state['players'], 'host': state['host'],
        'you': actor, 'leader': leader_id(state), 'round': state['round'] + 1,
        'team': state['team'], 'rejections': state['rejections'],
        'missions': state['missions'], 'history': state['history'], 'winner': state['winner'],
        'team_sizes': TEAM_SIZES.get(len(state['players']), []),
        'team_size': team_size(state) if phase != 'lobby' else None,
        'fail_threshold': fail_threshold(state), 'your_role': role,
        'allies': [pid for pid, r in state['roles'].items() if r == 'saboteur'] if role == 'saboteur' else [],
        'voted': list(state['votes']) if phase == 'vote' else [],
        # Only counts are public during secret mission submission.
        'submitted_count': len(state['submissions']) if phase == 'mission' else 0,
        'you_submitted': actor in state['submissions'] if phase == 'mission' else False,
        'revealed_roles': state['roles'] if phase == 'finished' else {},
    }
