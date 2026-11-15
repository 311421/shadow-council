import copy
import json
from unittest import TestCase as PlainTestCase
from unittest.mock import patch

from django.test import Client, TestCase
from . import engine, quest


def setup(count=6, variant='youth', board='A'):
    players = [{'id': str(i), 'name': f'Player {i}'} for i in range(count)]
    state = quest.lobby(players, '0', {'variant': variant, 'board': board})
    state = quest.apply_action(state, '0', {'type': 'start'})
    # Fixed deck and leader for isolated rules tests, retaining small-game hidden card.
    deck = quest.role_pool(count, variant)
    if count <= 5:
        state['hidden_role'] = 'servant'
        deck.remove('servant')
    state['roles'] = dict(zip([str(i) for i in range(count)], deck))
    state['leader'] = 0
    state['veterans'] = ['0']
    state['checks'] = {'0': [{'source': 'Cleric', 'target': '0', 'allegiance': 'good'}]}
    return state


def role_id(state, role):
    return next(pid for pid, r in state['roles'].items() if r == role)


def expedition(state, fail=False):
    ids = list(state['roles'])
    count = quest.sizes(state)[state['round']]
    if fail:
        evil = role_id(state, 'morgan')
        team = [evil] + [pid for pid in ids if pid != evil][:count-1]
        magic = next(pid for pid in team if state['roles'][pid] != 'youth' and pid != evil)
    else:
        team = ids[:count]
        magic = next(pid for pid in team if state['roles'][pid] != 'youth')
    state = quest.apply_action(state, quest.leader_id(state), {'type': 'propose', 'team': team, 'magic': magic})
    for actor in team:
        state = quest.apply_action(state, actor, {'type': 'mission', 'sabotage': fail and state['roles'][actor] == 'morgan'}, now=1000)
    return state


def transition(state):
    eligible = quest.eligible_leaders(state)
    due = quest.amulet_due(state)
    state = quest.apply_action(state, quest.leader_id(state), {'type': 'transition', 'leader': eligible[0], 'holder': eligible[1] if due else None})
    if state['phase'] == 'amulet':
        state = quest.apply_action(state, state['amulets'][-1]['holder'], {'type': 'investigate', 'target': quest.amulet_targets(state)[0]})
    return state


class QuestRulesTests(PlainTestCase):
    def test_all_decks_and_both_four_player_boards(self):
        for n in range(4, 11):
            for variant in ('youth', 'troublemaker'):
                state = setup(n, variant)
                self.assertEqual(len(state['roles']), n)
                self.assertIn('morgan', state['roles'].values())
                self.assertIn('hunter', state['roles'].values())
                if n >= 6:
                    self.assertIn('cleric', state['roles'].values())
                    self.assertIn(variant, state['roles'].values())
                self.assertEqual(sum(r in quest.EVIL_ROLES for r in state['roles'].values()), {4:2,5:3,6:3,7:4,8:4,9:5,10:5}[n])
        self.assertEqual(quest.sizes(setup(4,board='A')), [3,2,3,2])
        self.assertEqual(quest.sizes(setup(4,board='B')), [3,2,2,3])
        self.assertEqual(quest.sizes(setup(8)), [4,3,4,5,4])

    def test_no_voting_and_magic_must_be_on_party(self):
        state=setup()
        with self.assertRaises(quest.RuleError):
            quest.apply_action(state,'0',{'type':'propose','team':['0','1','2'],'magic':'3'})
        state=quest.apply_action(state,'0',{'type':'propose','team':['0','1','2'],'magic':'0'})
        self.assertEqual(state['phase'],'mission')
        with self.assertRaises(quest.RuleError):
            quest.apply_action(state,'1',{'type':'vote','approve':True})

    def test_magic_and_every_character_card_restriction(self):
        for role in quest.GOOD_ROLES | quest.EVIL_ROLES:
            for magic in (False,True):
                state=setup()
                state.update(phase='mission',team=['0','1','2'],magic='0' if magic else '1')
                state['roles']['0']=role
                expected=[True] if magic and role=='youth' else [False,True] if role=='morgan' or (role in quest.EVIL_ROLES and not magic) else [False]
                self.assertEqual(quest.mission_options(state,'0'), expected)
                for value in (True,False):
                    if value in expected:
                        self.assertEqual(quest.apply_action(state,'0',{'type':'mission','sabotage':value})['submissions']['0'],value)
                    else:
                        with self.assertRaises(quest.RuleError): quest.apply_action(state,'0',{'type':'mission','sabotage':value})

    def test_duplicate_and_non_party_submissions(self):
        state=quest.apply_action(setup(),'0',{'type':'propose','team':['0','1','2'],'magic':'0'})
        with self.assertRaises(quest.RuleError): quest.apply_action(state,'5',{'type':'mission','sabotage':False})
        state=quest.apply_action(state,'0',{'type':'mission','sabotage':False})
        with self.assertRaises(quest.RuleError): quest.apply_action(state,'0',{'type':'mission','sabotage':False})

    def test_two_failure_thresholds(self):
        for n in range(4,11):
            state=setup(n)
            for index in range(len(quest.sizes(state))):
                state['round']=index
                self.assertEqual(quest.fail_threshold(state), 2 if (n>=7 and index==3) or (n>=8 and index==2) else 1)

    def test_leader_restrictions_and_amulet_schedule(self):
        for n,rounds in [(5,set()),(6,{4}),(7,{3,4}),(8,{2,3,4}),(10,{2,3,4})]:
            state=setup(n)
            for completed in range(1,5):
                state['missions']=[{}]*completed
                self.assertEqual(quest.amulet_due(state),completed in rounds)
        state=expedition(setup())
        self.assertEqual(state['phase'],'transition')
        with self.assertRaises(quest.RuleError): quest.apply_action(state,'0',{'type':'transition','leader':'0'})
        state['amulets']=[{'holder':'1','target':'0','after_round':2}]
        with self.assertRaises(quest.RuleError): quest.apply_action(state,'0',{'type':'transition','leader':'1'})

    def test_amulet_requires_distinct_eligible_holder_and_private_truth(self):
        state=setup(8,'troublemaker')
        state.update(phase='transition',missions=[{'success':True}]*2,round=1)
        with self.assertRaises(quest.RuleError): quest.apply_action(state,'0',{'type':'transition','leader':'2','holder':'2'})
        state=quest.apply_action(state,'0',{'type':'transition','leader':'2','holder':'3'})
        self.assertEqual(state['phase'],'amulet')
        self.assertNotIn('3',quest.amulet_targets(state))
        trouble=role_id(state,'troublemaker')
        state=quest.apply_action(state,'3',{'type':'investigate','target':trouble})
        self.assertEqual(state['checks']['3'][-1]['allegiance'],'evil')
        self.assertEqual(quest.player_view(state,'4')['your_checks'],[])
        self.assertNotIn('checks',quest.player_view(state,'4'))
        self.assertNotIn(trouble,quest.amulet_targets(state))

    def test_cleric_sees_apparent_first_leader_allegiance(self):
        for variant in ('youth','troublemaker'):
            for _ in range(12):
                players=[{'id':str(i),'name':str(i)} for i in range(6)]
                state=quest.apply_action(quest.lobby(players,'0',{'variant':variant,'board':'A'}),'0',{'type':'start'})
                cleric=role_id(state,'cleric')
                check=state['checks'][cleric][0]
                self.assertEqual(check['target'],quest.leader_id(state))
                self.assertEqual(check['allegiance'],quest.apparent_allegiance(state['roles'][check['target']]))

    def test_evil_knowledge_and_hidden_card_privacy(self):
        for n in (4,5,6,10):
            state=setup(n);hunter=role_id(state,'hunter');morgan=role_id(state,'morgan')
            self.assertEqual(quest.player_view(state,hunter)['allies'],[])
            self.assertEqual(hunter in quest.player_view(state,morgan)['allies'],n<=5)
            view=quest.player_view(state,'0')
            self.assertIsNone(view['hidden_role'])
            self.assertEqual(view['revealed_roles'],{})
            for secret in ('roles','checks','submissions'):
                self.assertNotIn(secret,view)

    def test_good_wins_three_successes_and_input_not_mutated(self):
        state=setup();original=copy.deepcopy(state)
        for i in range(3):
            state=expedition(state)
            if i<2: state=transition(state)
        self.assertEqual(state['winner'],'good')
        self.assertEqual(state['phase'],'finished')
        self.assertEqual(state['submissions'],{})
        self.assertEqual(original['missions'],[])

    def test_failures_start_final_discussion_not_evil_victory(self):
        for n,total in ((4,2),(6,3)):
            state=setup(n)
            for i in range(total):
                state=expedition(state,True)
                if i<total-1: state=transition(state)
            self.assertEqual(state['phase'],'discussion')
            self.assertIsNone(state['winner'])
            self.assertEqual(state['discussion_until'],1300)
            hunter=role_id(state,'hunter')
            with self.assertRaises(quest.RuleError): quest.apply_action(state,hunter,{'type':'hunt_decision','hunt':True},now=1299)
            with self.assertRaises(quest.RuleError): quest.apply_action(state,'0',{'type':'hunt_decision','hunt':True},now=1400)
            self.assertEqual(quest.apply_action(state,hunter,{'type':'hunt_decision','hunt':True},now=1300)['phase'],'hunt')

    def test_hunt_correct_wrong_hidden_card_and_leadership_exception(self):
        for n in (4,6,10):
            for correct in (True,False):
                state=setup(n);hunter=role_id(state,'hunter')
                state.update(phase='hunt',hunter_revealed=hunter)
                guesses=[{'target':role_id(state,'cleric'),'role':'cleric'},
                         {'target':'hidden' if n<=5 else role_id(state,'duke'),'role':'servant' if correct else 'troublemaker'}]
                result=quest.apply_action(state,hunter,{'type':'hunt','guesses':guesses})
                self.assertEqual(result['winner'],'evil' if correct else 'good')
                if correct:
                    state['veterans']=[hunter,role_id(state,'morgan')]
                    self.assertEqual(quest.apply_action(state,hunter,{'type':'hunt','guesses':guesses})['winner'],'good')

    def test_last_chance_requires_exact_union_and_no_premature_reveal(self):
        for extra_good in (False,True):
            state=setup(5);state['phase']='accusation'
            evil=[p for p,r in state['roles'].items() if r in quest.EVIL_ROLES]
            ids=list(state['roles'])
            for i,pid in enumerate(ids):
                targets=[evil[i%len(evil)],evil[(i+1)%len(evil)]]
                if extra_good and pid=='0': targets[0]='0'
                if i==len(ids)-1:
                    view=quest.player_view(state,pid)
                    self.assertEqual(view['accusations'],{})
                    self.assertEqual(view['revealed_roles'],{})
                state=quest.apply_action(state,pid,{'type':'accuse','targets':targets})
            self.assertEqual(state['winner'],'evil' if extra_good else 'good')

    def test_duke_and_archduke_adjustments_once_in_order(self):
        state=setup(10);state['phase']='accusation'
        evil=[p for p,r in state['roles'].items() if r in quest.EVIL_ROLES]
        good=[p for p,r in state['roles'].items() if r in quest.GOOD_ROLES]
        for i,pid in enumerate(state['roles']):
            state=quest.apply_action(state,pid,{'type':'accuse','targets':[evil[i%len(evil)],evil[(i+1)%len(evil)]]})
        self.assertEqual(state['phase'],'duke')
        self.assertEqual(len(quest.player_view(state,'0')['revealed_roles']),10)
        self.assertTrue(all(state['roles'][p] in quest.GOOD_ROLES for p in state['accusations']))
        duke,arch=role_id(state,'duke'),role_id(state,'archduke')
        with self.assertRaises(quest.RuleError): quest.apply_action(state,arch,{'type':'archduke','skip':True})
        state=quest.apply_action(state,duke,{'type':'duke','source':good[0],'hand':0})
        self.assertEqual(len(state['accusations'][good[0]]),1)
        self.assertEqual(state['phase'],'archduke')
        with self.assertRaises(quest.RuleError): quest.apply_action(state,duke,{'type':'duke','skip':True})
        state=quest.apply_action(state,arch,{'type':'archduke','source':good[1],'hand':0,'target':good[0]})
        self.assertEqual(state['phase'],'finished')
        self.assertEqual(state['winner'],'evil')

    def test_all_counts_can_complete_leadership_and_amulet_transitions(self):
        for count in range(4,11):
            for variant in ('youth','troublemaker'):
                state=setup(count,variant)
                for fail in (False,True,False,True,False):
                    ids=list(state['roles']);threshold=quest.fail_threshold(state)
                    good_magic=next(pid for pid,r in state['roles'].items() if r in quest.GOOD_ROLES and r!='youth')
                    failing=[pid for pid,r in state['roles'].items() if r in quest.EVIL_ROLES][:threshold] if fail else []
                    team=failing+[good_magic]
                    team += [pid for pid in ids if pid not in team][:quest.sizes(state)[state['round']]-len(team)]
                    state=quest.apply_action(state,quest.leader_id(state),{'type':'propose','team':team,'magic':good_magic})
                    for pid in team:state=quest.apply_action(state,pid,{'type':'mission','sabotage':pid in failing})
                    if state['phase'] in ('finished','discussion'):break
                    state=transition(state)
                self.assertIn(state['phase'],('finished','discussion'))
                self.assertEqual(len(state['veterans']),len(set(state['veterans'])))
                self.assertFalse(set(state['veterans']) & {a['holder'] for a in state['amulets']})

    def test_last_chance_leadership_exception_and_hidden_cleric_hunt(self):
        state=setup(5);state['phase']='accusation'
        evil=[pid for pid,r in state['roles'].items() if r in quest.EVIL_ROLES]
        state['veterans']=evil[:]
        for pid in state['roles']:
            state=quest.apply_action(state,pid,{'type':'accuse','targets':['0','1']})
        self.assertEqual(state['winner'],'good')
        state=setup(4)
        cleric=role_id(state,'cleric');state['roles'][cleric]='servant';state['hidden_role']='cleric'
        hunter=role_id(state,'hunter');state.update(phase='hunt',hunter_revealed=hunter)
        state=quest.apply_action(state,hunter,{'type':'hunt','guesses':[{'target':'hidden','role':'cleric'},{'target':cleric,'role':'servant'}]})
        self.assertEqual(state['winner'],'evil')


class QuestHTTPTests(TestCase):
    def post(self,client,url,data): return client.post(url,json.dumps(data),content_type='application/json')
    def setUp(self):
        self.clients=[Client() for _ in range(6)]
        response=self.post(self.clients[0],'/api/rooms/',{'name':'Player 0'})
        self.root='/api/rooms/'+response.json()['url'].split('/')[2]+'/'
        for i,c in enumerate(self.clients[1:],1):self.post(c,self.root+'join/',{'name':f'Player {i}'})
    def state(self,c=None):return (c or self.clients[0]).get(self.root+'state/').json()
    def act(self,c,**data):
        response=self.post(c,self.root+'action/',{'version':self.state(c)['version'],**data})
        self.assertEqual(response.status_code,200,response.content)
        return response.json()
    def test_new_room_defaults_to_quest_and_complete_game(self):
        self.assertEqual(self.state()['ruleset'],'quest')
        self.act(self.clients[0],type='configure',variant='troublemaker',board='B')
        self.act(self.clients[0],type='start')
        mapping={self.state(c)['you']:c for c in self.clients}
        for i in range(3):
            state=self.state();team=[p['id'] for p in state['players'][:state['team_size']]]
            self.act(mapping[state['leader']],type='propose',team=team,magic=team[0])
            for pid in team:self.act(mapping[pid],type='mission',sabotage=False)
            state=self.state()
            if i<2:self.act(mapping[state['leader']],type='transition',leader=state['eligible_leaders'][0])
        self.assertEqual(self.state()['winner'],'good')
        self.act(self.clients[0],type='rematch')
        self.assertEqual(self.state()['settings']['variant'],'troublemaker')
        self.assertEqual(self.state()['phase'],'lobby')
    def test_four_guest_start_and_stale_action(self):
        response=self.post(Client(),'/api/rooms/',{'name':'Host Four'})
        root='/api/rooms/'+response.json()['url'].split('/')[2]+'/'
        host=Client();response=self.post(host,'/api/rooms/',{'name':'Four Host'})
        root='/api/rooms/'+response.json()['url'].split('/')[2]+'/'
        for i in range(3):self.post(Client(),root+'join/',{'name':f'Guest {i}'})
        version=host.get(root+'state/').json()['version']
        self.assertEqual(self.post(host,root+'action/',{'type':'start','version':version}).status_code,200)
        self.assertEqual(self.post(host,root+'action/',{'type':'start','version':version}).status_code,409)

    def reach_final(self, count=10):
        for i in range(len(self.clients),count):
            c=Client();self.clients.append(c)
            self.assertEqual(self.post(c,self.root+'join/',{'name':f'Player {i}'}).status_code,200)
        self.act(self.clients[0],type='configure',variant='troublemaker',board='A')
        self.act(self.clients[0],type='start')
        mapping={self.state(c)['you']:c for c in self.clients}
        roles={pid:self.state(c)['your_role'] for pid,c in mapping.items()}
        for i in range(3):
            state=self.state();evil=[pid for pid,r in roles.items() if r in quest.EVIL_ROLES]
            good=[pid for pid,r in roles.items() if r in quest.GOOD_ROLES]
            threshold=state['fail_threshold']
            team=evil[:threshold]+[good[0]]
            team += [pid for pid in roles if pid not in team][:state['team_size']-len(team)]
            self.act(mapping[state['leader']],type='propose',team=team,magic=good[0])
            for pid in team:
                with patch('game.quest.time.time',return_value=1000):
                    self.act(mapping[pid],type='mission',sabotage=pid in evil[:threshold])
            state=self.state()
            if i<2:
                holder=state['eligible_leaders'][1] if state['amulet_due'] else None
                self.act(mapping[state['leader']],type='transition',leader=state['eligible_leaders'][0],holder=holder)
                if holder:
                    private=self.state(mapping[holder])
                    checked=private['amulet_targets'][0]
                    self.act(mapping[holder],type='investigate',target=checked)
                    self.assertTrue(self.state(mapping[holder])['your_checks'])
                    self.assertFalse(any(e.get('allegiance') for e in self.state()['history']))
        self.assertEqual(self.state()['phase'],'discussion')
        self.assertIsNone(self.state()['winner'])
        return mapping,roles

    def test_complete_ten_player_last_chance_through_guest_endpoints(self):
        mapping,roles=self.reach_final()
        hunter=next(pid for pid,r in roles.items() if r=='hunter')
        with patch('game.quest.time.time',return_value=1300):
            self.act(mapping[hunter],type='hunt_decision',hunt=False)
        evil=[pid for pid,r in roles.items() if r in quest.EVIL_ROLES]
        good=[pid for pid,r in roles.items() if r in quest.GOOD_ROLES]
        for pid in mapping:
            index=good.index(pid) if pid in good else 0
            self.act(mapping[pid],type='accuse',targets=[evil[index%len(evil)],evil[(index+1)%len(evil)]])
        self.assertEqual(self.state()['phase'],'duke')
        self.assertEqual(len(self.state()['revealed_roles']),10)
        for role in ('duke','archduke'):
            pid=next(pid for pid,r in roles.items() if r==role)
            self.act(mapping[pid],type=role,skip=True)
        self.assertEqual(self.state()['winner'],'good')

    def test_complete_eight_player_hunt_through_guest_endpoints(self):
        mapping,roles=self.reach_final(8)
        hunter=next(pid for pid,r in roles.items() if r=='hunter')
        with patch('game.quest.time.time',return_value=1300):
            self.act(mapping[hunter],type='hunt_decision',hunt=True)
        self.assertEqual(self.state()['revealed_roles'],{})
        self.assertEqual(self.state()['hunter_revealed'],hunter)
        self.act(mapping[hunter],type='hunt',guesses=[{'target':next(pid for pid,r in roles.items() if r=='cleric'),'role':'cleric'},
            {'target':next(pid for pid,r in roles.items() if r=='duke'),'role':'servant'}])
        self.assertIn(self.state()['winner'],('good','evil'))
        self.assertEqual(self.state()['phase'],'finished')
