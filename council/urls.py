from django.urls import path
from game import views

urlpatterns = [
    path('', views.home, name='home'),
    path('room/<str:code>/', views.room_page, name='room'),
    path('api/rooms/', views.create_room),
    path('api/rooms/<str:code>/join/', views.join_room),
    path('api/rooms/<str:code>/state/', views.room_state),
    path('api/rooms/<str:code>/action/', views.room_action),
]
