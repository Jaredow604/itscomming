from django.db import models


class Equipos(models.Model):
    id_equipo = models.BigIntegerField(primary_key=True)
    nombre = models.CharField(max_length=100)
    liga = models.CharField(max_length=50, null=True, blank=True)
    logo_url = models.CharField(max_length=500, null=True, blank=True)
    prom_goles = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    prom_tiros_puerta = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    prom_corners = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    class Meta:
        db_table = 'equipos'

    def __str__(self):
        return self.nombre


class Partido(models.Model):
    id_partido = models.BigIntegerField(primary_key=True)
    local = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='partidos_local', db_column='id_local')
    visitante = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='partidos_visitante', db_column='id_visitante')
    fecha = models.DateTimeField()
    fecha_str = models.CharField(max_length=50, null=True, blank=True)
    goles_local = models.IntegerField(null=True, blank=True)
    goles_visitante = models.IntegerField(null=True, blank=True)
    jugado = models.BooleanField(default=False)
    fstatus = models.CharField(max_length=50, default='Fixture', null=True, blank=True)

    class Meta:
        db_table = 'partidos'
        unique_together = (('local', 'visitante', 'fecha'),)

    def __str__(self):
        return f"{self.local} vs {self.visitante}"


class DailySchedule(models.Model):
    sport = models.CharField(max_length=50)
    home_team = models.CharField(max_length=100)
    away_team = models.CharField(max_length=100)
    match_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    equipo_local = models.ForeignKey(
        Equipos, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='schedules_local', db_column='equipo_local_fk'
    )
    equipo_visitante = models.ForeignKey(
        Equipos, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='schedules_visitante', db_column='equipo_visitante_fk'
    )

    class Meta:
        db_table = 'dailyschedule'
        unique_together = (('sport', 'home_team', 'away_team', 'match_date'),)

    def __str__(self):
        return f"[{self.sport}] {self.home_team} vs {self.away_team}"


class AliasEquipo(models.Model):
    nombre_fuente = models.CharField(max_length=200, unique=True, help_text="Nombre tal como viene de la fuente externa")
    equipo = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='aliases', db_column='id_equipo')

    class Meta:
        db_table = 'alias_equipos'

    def __str__(self):
        return f"{self.nombre_fuente} -> {self.equipo.nombre}"


class EntidadHuerfana(models.Model):
    nombre_crudo = models.CharField(max_length=200, unique=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    resuelto = models.BooleanField(default=False)

    class Meta:
        db_table = 'entidadhuerfana'

    def __str__(self):
        return self.nombre_crudo
