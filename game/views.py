import json
import secrets
import string
from functools import wraps

from django.db import OperationalError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from . import engine
from .models import Member, Room


def api_errors(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except (engine.RuleError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return JsonResponse({'error': str(exc) if isinstance(exc, engine.RuleError) else 'Invalid JSON.'}, status=400)
        except OperationalError:
            return JsonResponse({'error': 'The room is busy. Please retry in a moment.'}, status=503)
    return wrapped


def payload(request):
    engine.require(len(request.body) <= 4096, 'Request is too large.')
    data = json.loads(request.body or b'{}')
    engine.require(isinstance(data, dict), 'Expected a JSON object.')
    return data


def guest_key(request):
    if not request.session.get('guest_key'):
        request.session['guest_key'] = secrets.token_hex(24)
    return request.session['guest_key']


def nickname(data):
    name = data.get('name', '')
    engine.require(isinstance(name, str), 'Enter a nickname.')
    name = ' '.join(name.split())
    engine.require(2 <= len(name) <= 20, 'Use a nickname with 2–20 characters.')
    engine.require(not any(ord(c) < 32 for c in name), 'Use a plain-text nickname.')
    return name


def member_for(request, room):
    return room.members.filter(guest_key=request.session.get('guest_key', '')).first()


def snapshot(room, member):
    return {**engine.player_view(room.state, str(member.id)), 'code': room.code, 'version': room.version}


@ensure_csrf_cookie
@never_cache
def home(request):
    return render(request, 'index.html')


@ensure_csrf_cookie
@never_cache
def room_page(request, code):
    room = get_object_or_404(Room, code=code.upper())
    return render(request, 'index.html', {'room_code': room.code})


@require_POST
@api_errors
def create_room(request):
    data = payload(request)
    name = nickname(data)
    key = guest_key(request)
    with transaction.atomic():
        while True:
            code = ''.join(secrets.choice(string.ascii_uppercase.replace('I', '').replace('O', '')) for _ in range(6))
            if not Room.objects.filter(code=code).exists():
                break
        room = Room.objects.create(code=code)
        member = Member.objects.create(room=room, guest_key=key)
        ruleset = data.get('ruleset', 'quest')
        engine.require(ruleset in ('quest', 'resistance'), 'Choose a valid ruleset.')
        room.state = engine.lobby([{'id': str(member.id), 'name': name}], str(member.id), ruleset)
        room.save(update_fields=['state'])
    return JsonResponse({'url': f'/room/{code}/'}, status=201)


@require_POST
@api_errors
def join_room(request, code):
    data = payload(request)
    key = guest_key(request)
    with transaction.atomic():
        room = get_object_or_404(Room, code=code.upper())
        member = room.members.filter(guest_key=key).first()
        if member:
            return JsonResponse({'url': f'/room/{room.code}/'})
        name = nickname(data)
        engine.require(room.state['phase'] == 'lobby', 'This game has started. Join the next lobby.')
        engine.require(len(room.state['players']) < 10, 'This room is full.')
        engine.require(all(p['name'].casefold() != name.casefold() for p in room.state['players']), 'That nickname is already in use here.')
        member = Member.objects.create(room=room, guest_key=key)
        room.state['players'].append({'id': str(member.id), 'name': name})
        room.version += 1
        room.save(update_fields=['state', 'version'])
    return JsonResponse({'url': f'/room/{room.code}/'})


@require_GET
@never_cache
def room_state(request, code):
    room = get_object_or_404(Room, code=code.upper())
    member = member_for(request, room)
    if not member:
        return JsonResponse({'error': 'Join this room to take a seat.', 'join_required': True}, status=403)
    return JsonResponse(snapshot(room, member))


@require_POST
@never_cache
@api_errors
def room_action(request, code):
    data = payload(request)
    with transaction.atomic():
        room = get_object_or_404(Room, code=code.upper())
        member = member_for(request, room)
        if not member:
            return JsonResponse({'error': 'Join this room first.'}, status=403)
        if type(data.get('version')) is not int or data['version'] != room.version:
            return JsonResponse({'error': 'The room changed. Review the latest state and try again.'}, status=409)
        actor = str(member.id)
        if data.get('type') == 'leave':
            engine.require(room.state['phase'] == 'lobby', 'You can leave your seat between games.')
            room.state['players'] = [p for p in room.state['players'] if p['id'] != actor]
            member.delete()
            if not room.state['players']:
                room.delete()
            else:
                if room.state['host'] == actor:
                    room.state['host'] = room.state['players'][0]['id']
                room.version += 1
                room.save(update_fields=['state', 'version'])
            return JsonResponse({'url': '/'})
        room.state = engine.apply_action(room.state, actor, data)
        room.version += 1
        room.save(update_fields=['state', 'version'])
        result = snapshot(room, member)
    return JsonResponse(result)
