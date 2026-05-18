"""
Management Command: actualizar_todo.py
Pipeline completo de ingesta de datos para NBA, MLB y Soccer.
Actualiza equipos, estadísticas, partidos y schedule diario.
"""

import datetime
import logging
import os
import time

import pandas as pd
import requests
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from predicciones.models import DailySchedule, Equipos, Partido

logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURACION
# ============================================================
FOOTBALL_DATA_TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "3b78612c4bab4114abe352da00b7558d")
BASE_FD = "https://api.football-data.org/v4"

# Ligas soccer soportadas
SOCCER_LEAGUES = {
    "PL": "Premier League",
    "PD": "La Liga",
    "SA": "Serie A",
    "BL1": "Bundesliga",
    "FL1": "Ligue 1",
    "BSA": "Brasileirão",
    "CLI": "Copa Libertadores",
    "PPL": "Liga Portugal",
    "DED": "Eredivisie",
    "ELC": "Championship",
}

# Temporada soccer activa (2025-26)
CURRENT_SEASON = 2025

# Temporadas football-data.co.uk (formato YYYY)
FDUK_SEASONS = ["2425", "2526"]
FDUK_LEAGUES = {
    "E0": "Premier League",
    "D1": "Championship",
    "SP1": "La Liga",
    "I1": "Serie A",
    "F1": "Ligue 1",
    "D2": "2. Bundesliga",
}

# ============================================================
# COMANDO
# ============================================================
class Command(BaseCommand):
    help = "Actualiza TODO: equipos, stats, partidos y schedule para NBA, MLB y Soccer."

    def add_arguments(self, parser):
        parser.add_argument("--sport", choices=["all", "soccer", "nba", "mlb"], default="all")
        parser.add_argument("--skip-stats", action="store_true", help="Saltar descarga de stats")
        parser.add_argument("--skip-schedule", action="store_true", help="Saltar schedule diario")

    def handle(self, *args, **options):
        sport = options["sport"]
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  PIPELINE ACTUALIZAR_TODO"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        t0 = time.time()

        if sport in ("all", "soccer"):
            self._update_soccer_teams()
            if not options["skip_stats"]:
                self._update_soccer_stats_fudk()

        if sport in ("all", "nba"):
            self._update_nba_teams()

        if sport in ("all", "mlb"):
            self._update_mlb_teams()

        if not options["skip_schedule"]:
            self._fetch_daily_schedule()

        elapsed = time.time() - t0
        self.stdout.write(self.style.SUCCESS(f"\nPipeline completado en {elapsed:.1f}s"))

    # --------------------------------------------------------
    # SOCCER — Equipos
    # --------------------------------------------------------
    def _update_soccer_teams(self):
        self.stdout.write(self.style.WARNING("\n[Soccer] Descargando equipos desde football-data.org..."))
        headers = {"X-Auth-Token": FOOTBALL_DATA_TOKEN}

        equipos_creados = 0
        equipos_actualizados = 0

        for code, name in SOCCER_LEAGUES.items():
            self.stdout.write(f"  Liga: {name} ({code})")
            try:
                resp = requests.get(
                    f"{BASE_FD}/competitions/{code}/teams",
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code != 200:
                    self.stdout.write(self.style.ERROR(f"    Error {resp.status_code}: {resp.text[:120]}"))
                    continue

                data = resp.json()
                teams = data.get("teamCount", 0)
                self.stdout.write(f"    {teams} equipos encontrados")

                for item in data.get("teams", []):
                    nombre = item.get("name", "").strip()
                    if not nombre:
                        continue

                    defaults = {
                        "prom_goles": 0.0,
                        "prom_tiros_puerta": 0.0,
                        "prom_corners": 0.0,
                    }

                    try:
                        obj, created = Equipos.objects.update_or_create(
                            nombre=nombre, defaults=defaults,
                        )
                        if created:
                            equipos_creados += 1
                        else:
                            equipos_actualizados += 1
                    except Exception as e:
                        logger.warning("Error creando equipo %s: %s", nombre, e)

                time.sleep(1.2)

            except requests.RequestException as e:
                self.stdout.write(self.style.ERROR(f"    Error de red: {e}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"[Soccer] Equipos: {equipos_creados} creados, {equipos_actualizados} actualizados"
            )
        )

    # --------------------------------------------------------
    # SOCCER — Estadísticas desde football-data.co.uk (CSV)
    # --------------------------------------------------------
    def _update_soccer_stats_fudk(self):
        self.stdout.write(self.style.WARNING("\n[Soccer] Descargando stats desde football-data.co.uk..."))

        base_url = "https://www.football-data.co.uk/mmz4281"
        headers = {"X-Auth-Token": FOOTBALL_DATA_TOKEN}

        for season in FDUK_SEASONS:
            for code, liga_name in FDUK_LEAGUES.items():
                csv_url = f"{base_url}/{season}/{code}.csv"
                self.stdout.write(f"  {liga_name} ({season}) -> {csv_url}")
                try:
                    df = pd.read_csv(csv_url, encoding="latin-1")
                    if df.empty:
                        self.stdout.write("    CSV vacío, saltando...")
                        continue

                    self.stdout.write(f"    {len(df)} partidos leídos")

                    # Procesar todos los equipos del CSV
                    home_col, away_col = "HomeTeam", "AwayTeam"
                    if home_col not in df.columns:
                        alt_home = [c for c in df.columns if "home" in c.lower() and "team" in c.lower()]
                        if alt_home:
                            home_col = alt_home[0]
                            away_col = [c for c in df.columns if "away" in c.lower() and "team" in c.lower()][0]

                    unique_teams = set(df[home_col].dropna()) | set(df[away_col].dropna())
                    self.stdout.write(f"    {len(unique_teams)} equipos únicos")

                    for team in unique_teams:
                        df_h = df[df[home_col] == team]
                        df_a = df[df[away_col] == team]

                        total = len(df_h) + len(df_a)
                        if total == 0:
                            continue

                        goles = df_h.get("FTHG", pd.Series()).sum() + df_a.get("FTAG", pd.Series()).sum()
                        corners = df_h.get("HC", pd.Series()).sum() + df_a.get("AC", pd.Series()).sum()
                        tiros = df_h.get("HST", pd.Series()).sum() + df_a.get("AST", pd.Series()).sum()

                        prom_goles = round(goles / total, 2)
                        prom_corners = round(corners / total, 2)
                        prom_tiros = round(tiros / total, 2)

                        try:
                            obj, _ = Equipos.objects.update_or_create(
                                nombre=team,
                                defaults={
                                    "liga": liga_name,
                                    "prom_goles": prom_goles,
                                    "prom_tiros_puerta": prom_tiros,
                                    "prom_corners": prom_corners,
                                },
                            )
                        except Exception:
                            pass

                    time.sleep(0.8)

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"    Error: {e}"))

        # Verificar que todos los equipos tengan stats
        sin_stats = Equipos.objects.filter(prom_goles=0, prom_tiros_puerta=0, prom_corners=0).count()
        con_stats = Equipos.objects.exclude(prom_goles=0, prom_tiros_puerta=0, prom_corners=0).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"[Soccer] Stats: {con_stats} equipos con datos, {sin_stats} sin datos reales"
            )
        )

    # --------------------------------------------------------
    # NBA — Equipos
    # --------------------------------------------------------
    def _update_nba_teams(self):
        self.stdout.write(self.style.WARNING("\n[NBA] Registrando equipos..."))

        nba_teams = [
            "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
            "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
            "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
            "LA Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
            "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
            "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
            "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
            "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
            "Utah Jazz", "Washington Wizards",
        ]

        creados = 0
        for name in nba_teams:
            obj, created = Equipos.objects.update_or_create(
                nombre=name,
                defaults={"liga": "NBA"}
            )
            if created:
                creados += 1

        self.stdout.write(self.style.SUCCESS(f"[NBA] {creados} equipos nuevos registrados"))

    # --------------------------------------------------------
    # MLB — Equipos
    # --------------------------------------------------------
    def _update_mlb_teams(self):
        self.stdout.write(self.style.WARNING("\n[MLB] Registrando equipos..."))

        mlb_teams = [
            "Arizona Diamondbacks", "Atlanta Braves", "Baltimore Orioles",
            "Boston Red Sox", "Chicago Cubs", "Chicago White Sox",
            "Cincinnati Reds", "Cleveland Guardians", "Colorado Rockies",
            "Detroit Tigers", "Houston Astros", "Kansas City Royals",
            "Los Angeles Angels", "Los Angeles Dodgers", "Miami Marlins",
            "Milwaukee Brewers", "Minnesota Twins", "New York Mets",
            "New York Yankees", "Oakland Athletics", "Philadelphia Phillies",
            "Pittsburgh Pirates", "San Diego Padres", "San Francisco Giants",
            "Seattle Mariners", "St. Louis Cardinals", "Tampa Bay Rays",
            "Texas Rangers", "Toronto Blue Jays", "Washington Nationals",
        ]

        creados = 0
        for name in mlb_teams:
            obj, created = Equipos.objects.update_or_create(
                nombre=name,
                defaults={"liga": "MLB"}
            )
            if created:
                creados += 1

        self.stdout.write(self.style.SUCCESS(f"[MLB] {creados} equipos nuevos registrados"))

    # --------------------------------------------------------
    # SCHEDULE DIARIO — MLB, NBA, Soccer
    # --------------------------------------------------------
    def _fetch_daily_schedule(self):
        from django.core.management import call_command
        self.stdout.write(self.style.WARNING("\n[Schedule] Obteniendo partidos delegando a fetch_schedule..."))
        try:
            call_command("fetch_schedule")
            self.stdout.write(self.style.SUCCESS("[Schedule] Partidos actualizados correctamente vía The Odds API"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[Schedule] Error ejecutando fetch_schedule: {e}"))
