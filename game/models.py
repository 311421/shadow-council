import uuid
from django.db import models


class Room(models.Model):
    code = models.CharField(max_length=6, unique=True)
    state = models.JSONField(default=dict)
    version = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Member(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='members')
    # This credential is never included in public game snapshots.
    guest_key = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['room', 'guest_key'], name='one_seat_per_guest')]
