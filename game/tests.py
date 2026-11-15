import copy
import json
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase as PlainTestCase

from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase

from . import resistance as engine
from .models import Room


def setup_state(count=5):
    players = [{'id': str(i), 'name': f'Agent {i}'} for i in range(count)]
    state = engine.apply_action(engine.lobby(players, '0'), '0', {'type': 'start'})
    state['leader'] = 0
    # Deterministic assignments for tests only.
    state['roles'] = {str(i): 'saboteur' if i < engine.SABOTEURS[count] else 'operative' for i in range(count)}
    return state


def vote_team(state, team, approve=True):
    state = engine.apply_action(state, engine.leader_id(state), {'type': 'propose', 'team': team})
    for player in state['players']:
        state = engine.apply_action(state, player['id'], {'type': 'vote', 'approve': approve})
    return state


class EngineTests(PlainTestCase):
    def test_player_counts_and_roles(self):
        for count in range(5, 11):
            state = setup_state(count)
            self.assertEqual(sum(r == 'saboteur' for r in state['roles'].values()), engine.SABOTEURS[count])
            self.assertEqual(len(engine.TEAM_SIZES[count]), 5)
        with self.assertRaises(engine.RuleError):
            engine.apply_action(engine.lobby([{'id': '0', 'name': 'Solo'}], '0'), '0', {'type': 'start'})

    def test_only_host_and_leader_can_act(self):
        state = setup_state()
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '1', {'type': 'propose', 'team': ['0', '1']})
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '0', {'type': 'propose', 'team': ['0', '0']})
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '0', {'type': 'propose', 'team': ['0', 'stranger']})

    def test_tied_vote_rejects_and_rotates(self):
        state = setup_state(6)
        state = engine.apply_action(state, '0', {'type': 'propose', 'team': ['0', '1']})
        for i in range(6):
            state = engine.apply_action(state, str(i), {'type': 'vote', 'approve': i < 3})
        self.assertEqual(state['phase'], 'proposal')
        self.assertEqual(state['leader'], 1)
        self.assertEqual(state['rejections'], 1)
        self.assertEqual(len(state['history'][-1]['votes']), 6)

    def test_duplicate_vote_and_strict_boolean(self):
        state = engine.apply_action(setup_state(), '0', {'type': 'propose', 'team': ['0', '1']})
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '0', {'type': 'vote', 'approve': 'false'})
        state = engine.apply_action(state, '0', {'type': 'vote', 'approve': True})
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '0', {'type': 'vote', 'approve': False})

    def test_five_rejections_win(self):
        state = setup_state()
        for _ in range(5):
            state = vote_team(state, ['0', '1'], False)
        self.assertEqual(state['winner'], 'saboteur')
        self.assertEqual(state['phase'], 'finished')

    def test_only_team_can_submit_and_operatives_cannot_sabotage(self):
        state = vote_team(setup_state(), ['0', '2'])
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '3', {'type': 'mission', 'sabotage': False})
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '2', {'type': 'mission', 'sabotage': True})
        state = engine.apply_action(state, '0', {'type': 'mission', 'sabotage': False})
        with self.assertRaises(engine.RuleError):
            engine.apply_action(state, '0', {'type': 'mission', 'sabotage': True})

    def test_fourth_mission_requires_two_sabotages_with_seven_players(self):
        for fails, success in [(1, True), (2, False)]:
            state = setup_state(7)
            state['round'] = 3
            state = vote_team(state, ['0', '1', '3', '4'])
            for i, actor in enumerate(['0', '1', '3', '4']):
                state = engine.apply_action(state, actor, {'type': 'mission', 'sabotage': i < fails})
            self.assertEqual(state['missions'][0]['success'], success)

    def test_three_successes_and_three_failures(self):
        for sabotage, winner in [(False, 'operative'), (True, 'saboteur')]:
            state = setup_state()
            for _ in range(3):
                team = [str(i) for i in range(engine.team_size(state))]
                state = vote_team(state, team)
                for actor in team:
                    state = engine.apply_action(state, actor, {'type': 'mission', 'sabotage': sabotage and actor == '0'})
            self.assertEqual(state['phase'], 'finished')
            self.assertEqual(state['winner'], winner)
            self.assertEqual(len(engine.player_view(state, '2')['revealed_roles']), 5)
            reset = engine.apply_action(state, '0', {'type': 'rematch'})
            self.assertEqual(reset['phase'], 'lobby')
            self.assertEqual(reset['roles'], {})
            self.assertEqual(len(reset['players']), 5)

    def test_views_never_expose_secrets(self):
        state = vote_team(setup_state(), ['0', '2'])
        state = engine.apply_action(state, '0', {'type': 'mission', 'sabotage': True})
        operative = engine.player_view(state, '2')
        self.assertEqual(operative['allies'], [])
        self.assertEqual(operative['revealed_roles'], {})
        self.assertNotIn('roles', operative)
        self.assertNotIn('submissions', operative)
        self.assertNotIn('votes', operative)
        self.assertEqual(operative['submitted_count'], 1)
        self.assertFalse(operative['you_submitted'])
        self.assertEqual(engine.player_view(state, '0')['allies'], ['0', '1'])
        state = engine.apply_action(state, '2', {'type': 'mission', 'sabotage': False})
        self.assertEqual(state['submissions'], {})
        self.assertNotIn('submissions', state['history'][-1])

    def test_pending_vote_values_are_private_and_input_unchanged(self):
        state = engine.apply_action(setup_state(), '0', {'type': 'propose', 'team': ['0', '1']})
        original = copy.deepcopy(state)
        next_state = engine.apply_action(state, '0', {'type': 'vote', 'approve': False})
        self.assertEqual(state, original)
        view = engine.player_view(next_state, '2')
        self.assertEqual(view['voted'], ['0'])
        self.assertNotIn('votes', view)
        self.assertFalse(any(e['type'] == 'vote' for e in view['history']))


class RoomAPITests(TestCase):
    def setUp(self):
        self.clients = [Client() for _ in range(5)]
        response = self.post(self.clients[0], '/api/rooms/', {'name': 'Agent 0', 'ruleset': 'resistance'})
        self.assertEqual(response.status_code, 201)
        self.code = response.json()['url'].split('/')[2]
        self.root = f'/api/rooms/{self.code}/'
        for i, client in enumerate(self.clients[1:], 1):
            self.assertEqual(self.post(client, self.root + 'join/', {'name': f'Agent {i}'}).status_code, 200)

    def post(self, client, url, data):
        return client.post(url, json.dumps(data), content_type='application/json')

    def state(self, client=None):
        return (client or self.clients[0]).get(self.root + 'state/').json()

    def act(self, client, **data):
        return self.post(client, self.root + 'action/', {'version': self.state(client)['version'], **data})

    def test_guest_identity_reconnect_and_unauthorized_access(self):
        state = self.state()
        self.assertEqual(len(state['players']), 5)
        self.assertEqual(self.state()['you'], state['you'])
        self.assertNotIn('guest_key', json.dumps(state))
        self.assertEqual(Client().get(self.root + 'state/').status_code, 403)
        self.assertEqual(self.post(Client(), self.root + 'action/', {'type': 'start', 'version': 4}).status_code, 403)
        # Existing guests rejoin without adding another seat.
        self.assertEqual(self.post(self.clients[0], self.root + 'join/', {}).status_code, 200)
        self.assertEqual(len(self.state()['players']), 5)

    def test_full_game_over_http_and_rematch(self):
        self.assertEqual(self.act(self.clients[1], type='start').status_code, 400)
        self.assertEqual(self.act(self.clients[0], type='start').status_code, 200)
        mapping = {self.state(client)['you']: client for client in self.clients}
        self.assertEqual(self.post(Client(), self.root + 'join/', {'name': 'Latecomer'}).status_code, 400)
        for _ in range(3):
            state = self.state()
            team = [p['id'] for p in state['players'][:state['team_size']]]
            self.assertEqual(self.act(mapping[state['leader']], type='propose', team=team).status_code, 200)
            for client in self.clients:
                self.assertEqual(self.act(client, type='vote', approve=True).status_code, 200)
            for actor in team:
                self.assertEqual(self.act(mapping[actor], type='mission', sabotage=False).status_code, 200)
        self.assertEqual(self.state()['winner'], 'operative')
        self.assertEqual(self.act(self.clients[0], type='rematch').status_code, 200)
        self.assertEqual(self.state()['phase'], 'lobby')

    def test_stale_action_rejected_without_mutating_game(self):
        version = self.state()['version']
        self.assertEqual(self.act(self.clients[0], type='start').status_code, 200)
        response = self.post(self.clients[0], self.root + 'action/', {'type': 'start', 'version': version})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.state()['version'], version + 1)

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post(client, '/api/rooms/', {'name': 'Guest'}).status_code, 403)
        self.assertEqual(client.get('/').status_code, 200)
        token = client.cookies['csrftoken'].value
        response = client.post('/api/rooms/', json.dumps({'name': 'Guest'}), content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)

    def test_bad_payloads_and_duplicate_names(self):
        for data in [[], {'name': []}, {'name': 'a'}]:
            self.assertEqual(self.post(Client(), '/api/rooms/', data).status_code, 400)
        self.assertEqual(self.post(Client(), self.root + 'join/', {'name': 'aGeNt 0'}).status_code, 400)
        self.assertEqual(self.clients[0].post(self.root + 'action/', b'{bad', content_type='application/json').status_code, 400)

    def test_lobby_leave_transfers_host(self):
        old = self.state()['host']
        self.assertEqual(self.act(self.clients[0], type='leave').status_code, 200)
        state = self.state(self.clients[1])
        self.assertNotEqual(state['host'], old)
        self.assertEqual(state['host'], state['you'])
        self.assertEqual(len(state['players']), 4)

    def test_room_capacity(self):
        for i in range(5):
            self.assertEqual(self.post(Client(), self.root + 'join/', {'name': f'Extra {i}'}).status_code, 200)
        self.assertEqual(self.post(Client(), self.root + 'join/', {'name': 'Overflow'}).status_code, 400)

    def test_pages_and_private_response_cache(self):
        self.assertContains(self.clients[0].get('/'), 'Shadow Council')
        self.assertContains(self.clients[0].get(f'/room/{self.code}/'), self.code)
        self.assertIn('no-store', self.clients[0].get(self.root + 'state/')['Cache-Control'])


class ConcurrentActionTests(TransactionTestCase):
    # A file-backed database exercises actual SQLite locking across connections.
    def test_same_version_cannot_be_applied_twice(self):
        state = setup_state()
        state = engine.apply_action(state, '0', {'type': 'propose', 'team': ['0', '1']})
        room = Room.objects.create(code='LOCKED', state=state)

        def write_vote(actor):
            close_old_connections()
            try:
                from django.db import transaction
                with transaction.atomic():
                    current = Room.objects.get(pk=room.pk)
                    if current.version != 0:
                        return 'stale'
                    current.state = engine.apply_action(current.state, actor, {'type': 'vote', 'approve': True})
                    current.version += 1
                    current.save()
                    return 'saved'
            finally:
                close_old_connections()

        # SQLite's shared in-memory test DB reports locks immediately, unlike the
        # real file database configured in settings.TEST.
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(write_vote, ['0', '1']))
        self.assertCountEqual(outcomes, ['saved', 'stale'])
        room.refresh_from_db()
        self.assertEqual(len(room.state['votes']), 1)
