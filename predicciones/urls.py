from django.urls import path
from . import views
urlpatterns = [
    path('', views.home, name='home'),
    path('api/predecir/<int:partido_id>/', views.chatbot_prediccion, name='predecir_id'),
    path('api/chatbot/<str:nombre_equipo>/', views.chatbot_prediccion, name='chatbot_query'),
    path('api/chatbot-web/', views.chatbot_web, name='chatbot_web'),
]