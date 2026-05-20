# Scripts de Ingesta y Población de BD

## Scripts Principales

### `repoblar_bd.py` (Raiz del proyecto)
Script maestro que orquesta toda la re-población de la base de datos.

```bash
# Ejecutar todo
python repoblar_bd.py --todo

# Solo una fase especifica
python repoblar_bd.py --fase 1

# Reset destructivo + repoblar
python repoblar_bd.py --reset-db --todo

# Solo descargar logos
python repoblar_bd.py --solo-logos
```

**Fases:**
| Fase | Descripción |
|------|-------------|
| 0 | Reset destructivo de BD |
| 1 | Bootstrap equipos + logos (ESPN API) |
| 2 | Historico partidos futbol (football-data.co.uk) |
| 3 | Resolver FKs en match_history_stats |
| 4 | Feature engineering (anti-data-leakage) |
| 5 | Team rolling stats |
| 6 | Actualizar promedios UI |
| 7 | Entrenar scaler + inference data |
| 8 | Descargar logos de ligas |

---

### `scripts/ingesta_futbol.py`
Ingesta completa de futbol desde multiples fuentes.

```bash
python scripts/ingesta_futbol.py --todo
python scripts/ingesta_futbol.py --ligas PL SP1 --temporadas 2324 2425 2526
python scripts/ingesta_futbol.py --solo-csv
python scripts/ingesta_futbol.py --solo-fbref
python scripts/ingesta_futbol.py --solo-365scores --dias-atras 14
```

**Fuentes:**
- **ESPN API**: Equipos y logos
- **football-data.co.uk**: Historico de partidos (CSVs gratuitos)
- **FBref (soccerdata)**: Stats avanzados de jugadores (xG, tiros, pases)
- **365Scores**: Player props y stats en tiempo real

---

### `scripts/ingesta_nba.py`
Ingesta completa de NBA.

```bash
python scripts/ingesta_nba.py --todo
python scripts/ingesta_nba.py --temporadas 2023-24 2024-25 2025-26
python scripts/ingesta_nba.py --solo-equipos
python scripts/ingesta_nba.py --solo-backfill
```

**Fuentes:**
- **ESPN API**: Equipos y logos
- **NBA API (nba_api)**: Player game logs historicos

---

### `scripts/ingesta_mlb.py`
Ingesta completa de MLB.

```bash
python scripts/ingesta_mlb.py --todo
python scripts/ingesta_mlb.py --temporadas 2023 2024 2025
python scripts/ingesta_mlb.py --solo-equipos
python scripts/ingesta_mlb.py --solo-backfill
```

**Fuentes:**
- **ESPN API**: Equipos y logos
- **MLB statsapi**: Datos oficiales de juegos y jugadores

---

### `scripts/download_logos.py`
Descarga de logos de equipos y ligas.

```bash
python scripts/download_logos.py --todo
python scripts/download_logos.py --solo-equipos
python scripts/download_logos.py --solo-ligas
python scripts/download_logos.py --solo-bd
```

**Fuentes:**
- **ESPN API**: Logos de equipos
- **URLs publicas**: Logos de ligas

Los logos se guardan en `media/logos/equipos/` y `media/logos/ligas/`.

---

### `arrancar.py` (Raiz del proyecto)
Bootstrap rapido de equipos desde ESPN API.

```bash
python arrancar.py
```

---

## Dependencias

```bash
pip install soccerdata nba_api MLB-StatsAPI
```

## Temporadas Cubiertas

| Deporte | Temporadas |
|---------|------------|
| Futbol | 2324, 2425, 2526 |
| NBA | 2023-24, 2024-25, 2025-26 |
| MLB | 2023, 2024, 2025 |

## Ligas de Futbol

| Key | Liga |
|-----|------|
| PL | Premier League |
| SP1 | La Liga |
| D1 | Bundesliga |
| I1 | Serie A |
| F1 | Ligue 1 |
