from django.contrib import admin
from .models import Equipos, Partido

@admin.register(Equipos)
class EquiposAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'prom_goles', 'prom_tiros_puerta')
    search_fields = ('nombre',)

@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ('local', 'visitante', 'fecha', 'jugado', 'goles_local', 'goles_visitante')
    list_filter = ('jugado', 'local', 'visitante')
    search_fields = ('local__nombre', 'visitante__nombre')
