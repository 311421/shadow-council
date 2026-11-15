"""Quest Director's Cut rules, based on the supplied unofficial rulebook v2."""
import copy
import secrets
import time

from .resistance import RuleError, require

GOOD_ROLES = {'servant', 'cleric', 'youth', 'troublemaker', 'duke', 'archduke'}
EVIL_ROLES = {'minion', 'morgan', 'hunter'}
ROLE_NAMES = {'servant': 'Loyal Servant', 'cleric': 'Cleric', 'youth': 'Youth',
              'troublemaker': 'Troublemaker', 'duke': 'Duke', 'archduke': 'Archduke',
              'minion': 'Minion of Mordred', 'morgan': 'Morgan le Fay', 'hunter': 'Blind Hunter'}
TEAM_SIZES = {4: [3, 2, 3, 2], **{n: [3, 2, 3, 4, 3] for n in range(5, 8)},
              **{n: [4, 3, 4, 5, 4] for n in range(8, 11)}}


def lobby(players, host, settings=None):
    return {'ruleset': 'quest', 'phase': 'lobby', 'players': players, 'host': host,
            'settings': settings or {'variant': 'youth', 'board': 'A'}, 'roles': {},
            'leader': 0, 'round': 0, 'team': [], 'magic': None, 'missions': [],
            'history': [], 'submissions': {}, 'veterans': [], 'amulets': [],
            'checks': {}, 'accusations': {}, 'winner': None, 'end_reason': '',
            'discussion_until': None, 'hunter_revealed': None, 'hidden_role': None}


def leader_id(state):
    return state['players'][state['leader']]['id']


def sizes(state):
    if len(state['players']) == 4 and state['settings']['board'] == 'B':
        return [3, 2, 2, 3]
    return TEAM_SIZES.get(len(state['players']), [])


def fail_threshold(state):
    n = len(state['players'])
    return 2 if (n >= 7 and state['round'] == 3) or (n >= 8 and state['round'] == 2) else 1


def role_pool(count, variant='youth'):
    require(4 <= count <= 10, 'You need 4–10 players to start.')
    good = ['cleric', 'youth' if count <= 5 else variant]
    if count in (4, 5, 8, 9, 10):
        good.append('servant')
    if count in (6, 7, 8, 10):
        good.append('duke')
    if count in (9, 10):
        good.append('archduke')
    minions = {4: 0, 5: 1, 6: 1, 7: 2, 8: 2, 9: 3, 10: 3}[count]
    return good + ['morgan', 'hunter'] + ['minion'] * minions


def allegiance(role):
    return 'evil' if role in EVIL_ROLES else 'good'


def apparent_allegiance(role):
    return 'evil' if role == 'troublemaker' else allegiance(role)


def eligible_leaders(state):
    blocked = set(state['veterans']) | {a['holder'] for a in state['amulets']}
    return [p['id'] for p in state['players'] if p['id'] not in blocked]


def amulet_due(state):
    n, completed = len(state['players']), len(state['missions'])
    return completed in ({4} if n == 6 else {3, 4} if n == 7 else {2, 3, 4} if n >= 8 else set())


def amulet_targets(state):
    blocked = {a['holder'] for a in state['amulets']} | {a['target'] for a in state['amulets'] if a['target']}
    return [p['id'] for p in state['players'] if p['id'] not in blocked]


def mission_options(state, actor):
    if actor not in state['team'] or actor in state['submissions'] or state['phase'] != 'mission':
        return []
    role = state['roles'][actor]
    if state['magic'] == actor:
        if role == 'youth':
            return [True]
        if role != 'morgan':
            return [False]
    return [False, True] if role in EVIL_ROLES else [False]


def finish(state, winner, reason):
    state.update(phase='finished', winner=winner, end_reason=reason)
    state['history'].append({'type': 'end', 'text': reason})


def all_leaders_evil(state):
    return bool(state['veterans']) and all(state['roles'][pid] in EVIL_ROLES for pid in state['veterans'])


def finish_last_chance(state):
    pointed = {target for source, targets in state['accusations'].items()
               if state['roles'][source] in GOOD_ROLES for target in targets}
    evil = {pid for pid, role in state['roles'].items() if role in EVIL_ROLES}
    if pointed == evil:
        finish(state, 'good', 'Good’s Last Chance identified every Evil player and no Good players.')
    elif all_leaders_evil(state):
        finish(state, 'good', 'Every expedition leader was Evil: Good wins by the leadership exception.')
    else:
        finish(state, 'evil', 'Good’s Last Chance did not identify exactly the Evil players.')


def after_duke(state):
    if 'archduke' in state['roles'].values():
        state['phase'] = 'archduke'
    else:
        finish_last_chance(state)


def apply_action(original, actor, action, now=None):
    state = copy.deepcopy(original)
    now = time.time() if now is None else now
    ids = [p['id'] for p in state['players']]
    require(actor in ids, 'You are not seated in this room.')
    kind, phase = action.get('type'), state['phase']
    if kind == 'configure':
        require(phase == 'lobby' and actor == state['host'], 'Only the host can change lobby settings.')
        variant, board = action.get('variant'), action.get('board')
        require(variant in ('youth', 'troublemaker') and board in ('A', 'B'), 'Choose valid role and board options.')
        state['settings'] = {'variant': variant, 'board': board}
    elif kind == 'start':
        require(phase == 'lobby' and actor == state['host'], 'Only the host can start a lobby.')
        deck = role_pool(len(ids), state['settings']['variant'])
        if len(ids) <= 5:
            hidden = secrets.choice([r for r in deck if r in GOOD_ROLES])
            deck.remove(hidden)
            state['hidden_role'] = hidden
        secrets.SystemRandom().shuffle(deck)
        state['roles'] = dict(zip(ids, deck))
        state['leader'] = secrets.randbelow(len(ids))
        first = leader_id(state)
        state['veterans'] = [first]
        for pid, role in state['roles'].items():
            if role == 'cleric':
                state['checks'][pid] = [{'source': 'Cleric', 'target': first,
                    'allegiance': apparent_allegiance(state['roles'][first])}]
        state['phase'] = 'proposal'
        state['history'].append({'type': 'start', 'text': 'Quest Director’s Cut begins. The first leader has been chosen.'})
    elif kind == 'propose':
        require(phase == 'proposal' and actor == leader_id(state), 'Only the current leader can choose the party.')
        team = action.get('team')
        require(isinstance(team, list) and all(isinstance(pid, str) for pid in team), 'Choose a party.')
        required = sizes(state)[state['round']]
        require(len(team) == required and len(set(team)) == required and all(pid in ids for pid in team),
                f'Choose exactly {required} different players from this room.')
        magic = action.get('magic')
        require(isinstance(magic, str) and magic in team, 'Give Magic to one member of the chosen party.')
        state.update(team=team, magic=magic, submissions={}, phase='mission')
        state['history'].append({'type': 'party', 'round': state['round'] + 1,
                                 'team': team[:], 'magic': magic, 'leader': actor})
    elif kind == 'mission':
        require(phase == 'mission', 'No expedition is in progress.')
        value = action.get('sabotage')
        require(type(value) is bool and value in mission_options(state, actor), 'That expedition card is not allowed for you.')
        state['submissions'][actor] = value
        if len(state['submissions']) == len(state['team']):
            fails = sum(state['submissions'].values())
            result = {'type': 'mission', 'round': state['round'] + 1, 'team': state['team'][:],
                      'leader': leader_id(state), 'magic': state['magic'], 'fails': fails,
                      'threshold': fail_threshold(state), 'success': fails < fail_threshold(state)}
            state['missions'].append(result)
            state['history'].append(result)
            state.update(team=[], magic=None, submissions={})
            successes = sum(m['success'] for m in state['missions'])
            failures = len(state['missions']) - successes
            if successes == 3:
                finish(state, 'good', 'Three expeditions succeeded. Good wins.')
            elif failures >= (2 if len(ids) == 4 else 3):
                state.update(phase='discussion', discussion_until=now + 300)
                state['history'].append({'type': 'final', 'text': 'The Final Quest begins: five minutes of discussion.'})
            else:
                state['phase'] = 'transition'
    elif kind == 'transition':
        require(phase == 'transition' and actor == leader_id(state), 'The outgoing leader must choose the successors.')
        successor = action.get('leader')
        eligible = eligible_leaders(state)
        require(isinstance(successor, str) and successor in eligible, 'Choose a player who has not led or held an amulet.')
        due = amulet_due(state)
        holder = action.get('holder')
        if due:
            require(isinstance(holder, str) and holder in eligible and holder != successor,
                    'Choose a different eligible player to hold the amulet.')
            state['amulets'].append({'holder': holder, 'target': None, 'after_round': len(state['missions'])})
        state['leader'] = ids.index(successor)
        state['veterans'].append(successor)
        state['round'] += 1
        state['phase'] = 'amulet' if due else 'proposal'
        state['history'].append({'type': 'transition', 'leader': successor, 'holder': holder if due else None,
                                'text': 'The outgoing leader selected the next leader' + (' and an amulet holder.' if due else '.')})
    elif kind == 'investigate':
        require(phase == 'amulet' and actor == state['amulets'][-1]['holder'], 'Only the new amulet holder can investigate.')
        target = action.get('target')
        require(isinstance(target, str) and target in amulet_targets(state), 'That player cannot be checked by an amulet.')
        state['amulets'][-1]['target'] = target
        state['checks'].setdefault(actor, []).append({'source': 'Amulet', 'target': target,
            'allegiance': apparent_allegiance(state['roles'][target])})
        state['history'].append({'type': 'investigation', 'holder': actor, 'target': target,
                                'text': 'An amulet check was completed. Its result is private.'})
        state['phase'] = 'proposal'
    elif kind == 'hunt_decision':
        require(phase == 'discussion' and state['roles'][actor] == 'hunter', 'Only the Blind Hunter chooses whether to Hunt.')
        require(now >= state['discussion_until'], 'The five-minute discussion is still in progress.')
        require(type(action.get('hunt')) is bool, 'Choose Hunt or Last Chance.')
        if action['hunt']:
            state.update(phase='hunt', hunter_revealed=actor)
            state['history'].append({'type': 'hunt', 'text': 'The Blind Hunter revealed themself. Only the Hunter may speak.'})
        else:
            state['phase'] = 'accusation'
            state['history'].append({'type': 'last_chance', 'text': 'Good’s Last Chance: submit two accusations without further discussion.'})
    elif kind == 'hunt':
        require(phase == 'hunt' and actor == state['hunter_revealed'], 'Only the revealed Hunter may name targets.')
        guesses = action.get('guesses')
        require(isinstance(guesses, list) and len(guesses) == 2 and all(isinstance(g, dict) for g in guesses), 'Name two targets and their roles.')
        targets = [g.get('target') for g in guesses]
        valid_targets = ids + (['hidden'] if len(ids) <= 5 else [])
        require(all(isinstance(t, str) and t in valid_targets for t in targets) and targets[0] != targets[1], 'Choose two different targets.')
        require(all(isinstance(g.get('role'), str) and g['role'] in GOOD_ROLES for g in guesses), 'Guess a Good role for each target.')
        require(any(g['role'] == 'cleric' for g in guesses), 'One of your guesses must name the Cleric.')
        correct = True
        for guess in guesses:
            actual = state['hidden_role'] if guess['target'] == 'hidden' else state['roles'][guess['target']]
            correct &= guess['role'] == actual or (guess['role'] == 'servant' and actual in ('duke', 'archduke'))
        state['history'].append({'type': 'hunt_result', 'guesses': guesses, 'correct': correct,
                                'text': 'The Hunter named two roles. ' + ('Both guesses were correct.' if correct else 'At least one guess was incorrect.')})
        if correct and not all_leaders_evil(state):
            finish(state, 'evil', 'The Blind Hunter correctly identified both Good targets, including the Cleric.')
        else:
            finish(state, 'good', 'Every expedition leader was Evil: Good wins.' if correct else 'The Blind Hunter guessed incorrectly. Good wins.')
    elif kind == 'accuse':
        require(phase == 'accusation' and actor not in state['accusations'], 'Your accusations are already locked or this phase is closed.')
        targets = action.get('targets')
        require(isinstance(targets, list) and len(targets) == 2 and all(isinstance(t, str) and t in ids for t in targets)
                and targets[0] != targets[1], 'Accuse two different players.')
        state['accusations'][actor] = targets
        if len(state['accusations']) == len(ids):
            # Evil drops its hands before the Good characters adjust accusations.
            state['accusations'] = {pid: t for pid, t in state['accusations'].items() if state['roles'][pid] in GOOD_ROLES}
            if 'duke' in state['roles'].values():
                state['phase'] = 'duke'
            else:
                after_duke(state)
    elif kind in ('duke', 'archduke'):
        require(phase == kind and state['roles'][actor] == kind, 'Only that character may adjust accusations now.')
        if action.get('skip') is not True:
            source, hand = action.get('source'), action.get('hand')
            require(isinstance(source, str) and source in state['accusations'] and type(hand) is int
                    and 0 <= hand < len(state['accusations'][source]), 'Choose a remaining accusation to adjust.')
            if kind == 'duke':
                state['accusations'][source].pop(hand)
            else:
                target = action.get('target')
                require(isinstance(target, str) and target in ids, 'Choose a player for the redirected accusation.')
                state['accusations'][source][hand] = target
        state['history'].append({'type': 'adjustment', 'text': ROLE_NAMES[kind] + (' passed.' if action.get('skip') is True else ' adjusted one accusation.')})
        after_duke(state) if kind == 'duke' else finish_last_chance(state)
    elif kind == 'rematch':
        require(phase == 'finished' and actor == state['host'], 'Only the host can open a rematch after the game.')
        return lobby(state['players'], state['host'], state['settings'])
    else:
        raise RuleError('That action is not part of Quest Director’s Cut.')
    return state


def player_view(state, actor):
    phase, roles = state['phase'], state['roles']
    role = roles.get(actor)
    public_roles = phase in ('duke', 'archduke', 'finished')
    allies = []
    if role in ('morgan', 'minion'):
        allies = [pid for pid, r in roles.items() if r in EVIL_ROLES and (r != 'hunter' or len(state['players']) <= 5)]
    eligible = eligible_leaders(state)
    holder = state['amulets'][-1]['holder'] if phase == 'amulet' else None
    public_accusations = state['accusations'] if public_roles else {}
    return {'ruleset': 'quest', 'phase': phase, 'players': state['players'], 'host': state['host'],
        'you': actor, 'leader': leader_id(state), 'round': state['round'] + 1, 'settings': state['settings'],
        'team': state['team'], 'magic': state['magic'], 'missions': state['missions'], 'history': state['history'],
        'winner': state['winner'], 'end_reason': state['end_reason'], 'team_sizes': sizes(state),
        'team_size': sizes(state)[min(state['round'], len(sizes(state)) - 1)] if sizes(state) else None,
        'fail_threshold': fail_threshold(state), 'your_role': role, 'your_allegiance': allegiance(role) if role else None,
        'allies': allies, 'your_checks': state['checks'].get(actor, []), 'veterans': state['veterans'],
        'amulets': state['amulets'], 'eligible_leaders': eligible, 'amulet_due': amulet_due(state) if phase == 'transition' else False,
        'amulet_holder': holder, 'amulet_targets': amulet_targets(state) if phase == 'amulet' and actor == holder else [],
        'mission_options': mission_options(state, actor), 'submitted_count': len(state['submissions']) if phase == 'mission' else 0,
        'you_submitted': actor in state['submissions'] if phase == 'mission' else False,
        'discussion_until': state['discussion_until'], 'hunter_revealed': state['hunter_revealed'],
        'accused_count': len(state['accusations']) if phase == 'accusation' else 0,
        'you_accused': actor in state['accusations'], 'accusations': public_accusations,
        'revealed_roles': roles if public_roles else {}, 'hidden_role': state['hidden_role'] if phase == 'finished' else None,
        'role_pool': role_pool(len(state['players']), state['settings']['variant']) if 4 <= len(state['players']) <= 10 else [],
        'role_names': ROLE_NAMES}
