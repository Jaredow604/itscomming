from django.db import models

# ==========================================
# 1. ENTIDAD: Equipos
# ==========================================
class Equipos(models.Model):
    # Clave primaria explícita como en el diagrama
    id_equipo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, help_text="Nombre del equipo")
    
    # Atributos estadísticos: usamos DecimalField para promedios con precisión
    prom_corners = models.DecimalField(max_digits=5, decimal_places=2, help_text="Promedio de córners por partido")
    prom_tiros_puerta = models.DecimalField(max_digits=5, decimal_places=2, help_text="Promedio de tiros a puerta por partido")
    prom_goles = models.DecimalField(max_digits=5, decimal_places=2, help_text="Promedio de goles por partido")

    def __str__(self):
        return self.nombre

# ==========================================
# 2. ENTIDAD: jugador
# ==========================================
class jugador(models.Model):
    # Clave primaria
    id_jugador = models.AutoField(primary_key=True)
    
    # RELACIÓN: Un Equipo tiene N jugadores (Diagrama: tiene [1 Equipo-N jugador])
    equipo = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='jugadores', verbose_name="Equipo actual")
    
    nombre = models.CharField(max_length=100)
    posicion = models.CharField(max_length=50, help_text="Ej: Defensa, Delantero")
    num_camiseta = models.IntegerField(help_text="Número de camiseta")
    
    # Atributos de conteo directo
    asistencias = models.IntegerField(default=0, help_text="Total asistencias en temporada")
    goles = models.IntegerField(default=0, help_text="Total goles en temporada")
    
    # Atributos estadísticos (Promedios)
    prom_faltas = models.DecimalField(max_digits=5, decimal_places=2, help_text="Promedio de faltas")
    prom_tarjetas_x_partido = models.DecimalField(max_digits=5, decimal_places=2, help_text="Promedio tarjetas/partido")
    
    # Atributos específicos del diagrama
    tar_amarilla = models.IntegerField(default=0, help_text="Total tarjetas amarillas")
    tar_roja = models.IntegerField(default=0, help_text="Total tarjetas rojas")

    def __str__(self):
        return self.nombre

# ==========================================
# 3. ENTIDAD: Chatbot
# ==========================================
class Chatbot(models.Model):
    # Clave primaria explícita
    id_chatbot = models.AutoField(primary_key=True)
    
    # El diagrama tiene un campo 'Consultas' que parece un contador
    consultas_totales = models.IntegerField(default=0)
    
    def __str__(self):
        return f"Chatbot #{self.id_chatbot}"

# ==========================================
# 4. ENTIDAD: Partido
# ==========================================
class Partido(models.Model):
    # Clave primaria
    id_partido = models.AutoField(primary_key=True)
    
    # RELACIÓN: Un Chatbot predice N Partidos (Diagrama: Predice [1 Chatbot-N Partido])
    # Usamos on_delete=models.SET_NULL para que si se borra el chatbot, no se borren las predicciones de partidos pasados.
    chatbot = models.ForeignKey(Chatbot, on_delete=models.SET_NULL, null=True, blank=True, related_name='predicciones')
    
    # RELACIONES DIRECTAS: El diagrama especifica ID_local e ID_visitante
    # Esto es más claro y directo que usar el rombo 'juegan' como una relación M:N compleja.
    local = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='partidos_local', verbose_name="Equipo Local")
    visitante = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='partidos_visitante', verbose_name="Equipo Visitante")
    
    # Atributos del diagrama
    fecha = models.DateTimeField()
    # Fstatus: podría ser 'Programado', 'En juego', 'Terminado', etc.
    fstatus = models.CharField(max_length=50, help_text="Estado del partido")
    
    # Nota sobre el rombo 'juegan':
    # El diagrama tiene un rombo 'juegan' que conecta Partido(1) a Equipos(M).
    # Esto contradice los campos 'ID_local' e 'ID_visitante'. He optado por usar las claves 
    # foráneas directas (local, visitante) porque son mucho más claras para representar un único partido entre dos equipos.

    def __str__(self):
        return f"{self.local.nombre} vs {self.visitante.nombre} - {self.fecha.strftime('%d/%m/%Y')}"

# ==========================================
# 5. ENTIDAD: Tabla general (Tabla de Clasificación)
# ==========================================
class TablaGeneral(models.Model):
    # Clave primaria explícita
    id_clasificacion = models.AutoField(primary_key=True)
    
    # RELACIÓN: Una Tabla General posiciona M Equipos (Diagrama: Posiciona [1 Tabla Gral-M Equipos])
    equipo = models.ForeignKey(Equipos, on_delete=models.CASCADE, related_name='posiciones_en_tabla')
    
    # Atributos del diagrama (campos estadísticos de la tabla)
    puntos = models.IntegerField(default=0)
    goles_diferencia = models.IntegerField(default=0)
    partidos_jugados = models.IntegerField(default=0)

    # El campo 'consultas' del diagrama
    consultas = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.equipo.nombre} ({self.puntos} pts)"