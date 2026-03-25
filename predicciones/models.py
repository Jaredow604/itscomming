from django.db import models

class Equipos(models.Model):
    nombre = models.CharField(max_length=100)
    prom_goles = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    prom_tiros_puerta = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    prom_corners = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    def __str__(self):
        return self.nombre

class Partido(models.Model):
    local = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='partidos_local')
    visitante = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='partidos_visitante')
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_str = models.CharField(max_length=50, null=True, blank=True)
    # Campos para H2H
    goles_local = models.IntegerField(null=True, blank=True)
    goles_visitante = models.IntegerField(null=True, blank=True)
    jugado = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.local} vs {self.visitante}"
