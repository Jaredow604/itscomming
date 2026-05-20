"""
api_urls.py -- Rutas de la REST API v1 para predicciones deportivas.

Endpoints disponibles:
    POST /api/v1/chat/                   Chatbot conversacional con inferencia
    GET  /api/v1/predictions/nba/today/  Predicciones NBA del dia
    GET  /api/v1/predictions/mlb/today/  Predicciones MLB del dia
    GET  /api/v1/predictions/status/     Estado de salud de los modelos
    GET  /api/v1/today/                  Partidos del dia con predicciones
    GET  /api/v1/picks/                  Mejores picks del dia + historial
    GET  /api/v1/stats/                  Estadisticas de equipos

Uso:
    Incluir en core/urls.py:
        path('', include('predicciones.api_urls')),
"""

from django.urls import path
from predicciones.api_views import (
    DailyPredictionsAPIView,
    ModelHealthAPIView,
    TodayGamesAPIView,
    BestPicksAPIView,
    TeamStatsAPIView,
    PlayerPropsAPIView,
    StandingsAPIView,
)
from predicciones.chat_views import ChatAPIView

urlpatterns = [
    # Chatbot conversacional (POST)
    path(
        'api/v1/chat/',
        ChatAPIView.as_view(),
        name='chat-api',
    ),

    # Predicciones diarias por deporte
    path(
        'api/v1/predictions/<str:sport>/today/',
        DailyPredictionsAPIView.as_view(),
        name='daily-predictions',
    ),

    # Health check de los modelos
    path(
        'api/v1/predictions/status/',
        ModelHealthAPIView.as_view(),
        name='model-health',
    ),

    # Dashboard: Partidos del dia
    path(
        'api/v1/today/',
        TodayGamesAPIView.as_view(),
        name='today-games',
    ),

    # Dashboard: Mejores picks + historial
    path(
        'api/v1/picks/',
        BestPicksAPIView.as_view(),
        name='best-picks',
    ),

    # Estadisticas: Lista de equipos, detalle, comparacion
    path(
        'api/v1/stats/',
        TeamStatsAPIView.as_view(),
        name='team-stats',
    ),
    # Estadisticas: Player Props (nuevas rutas para props de jugadores)
    path(
        'api/v1/player-props/',
        PlayerPropsAPIView.as_view(),
        name='player-props',
    ),
    path(
        'api/v1/standings/',
        StandingsAPIView.as_view(),
        name='standings',
    ),
]

