"""Ruleset router: existing Resistance games remain playable."""
from . import quest, resistance
from .resistance import RuleError, require

def lobby(players, host, ruleset="quest"):
    if ruleset == "resistance":
        return {**resistance.lobby(players, host), "ruleset": "resistance"}
    return quest.lobby(players, host)

def apply_action(state, actor, action):
    if state.get("ruleset") == "quest":
        return quest.apply_action(state, actor, action)
    if action.get("type") == "rematch" and state["phase"] == "finished":
        require(actor == state["host"], "Only the host can open a rematch.")
        return quest.lobby(state["players"], state["host"])
    return resistance.apply_action(state, actor, action)

def player_view(state, actor):
    if state.get("ruleset") == "quest":
        return quest.player_view(state, actor)
    return {**resistance.player_view(state, actor), "ruleset": "resistance"}
