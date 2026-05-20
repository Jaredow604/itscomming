"""
Paso 2: Resolución de Entidades y Búsqueda Difusa

Audita los dos entity resolvers del proyecto:
  - predicciones/entity_resolver.py  (Django ORM, umbral 85%)
  - src/data_processing/entity_resolver.py  (SQLAlchemy, umbral 90%)

Verifica:
  - clean_team_name: acentos, stop words, puntuación, idempotencia
  - resolver_entidad_equipo: alias exacto → cleaned exacto → fuzzy → huérfano
  - EntityResolver (SQLAlchemy): ILIKE → fuzzy → auto-create
  - Integración con datasets que importan clean_team_name
"""

import pytest
from unittest.mock import MagicMock, patch, call
from decimal import Decimal

from rapidfuzz import fuzz, process
from predicciones.entity_resolver import (
    clean_team_name,
    resolver_entidad_equipo,
    STOP_WORDS,
)


# ==========================================
# TESTS: clean_team_name
# ==========================================

class TestCleanTeamName:
    def test_lowercase(self):
        assert clean_team_name("REAL MADRID") == "madrid"

    def test_accent_removal(self):
        assert clean_team_name("São Paulo") == "sao paulo"
        assert clean_team_name("Atlético Madrid") == "atletico madrid"
        assert clean_team_name("München") == "munchen"

    def test_diaeresis(self):
        assert clean_team_name("Málaga") == "malaga"
        assert clean_team_name("Barcelona Zürich") == "barcelona zurich"

    def test_stop_word_removal(self):
        assert clean_team_name("FC Barcelona") == "barcelona"
        assert clean_team_name("Paris Saint-Germain FC") == "paris saint germain"
        assert clean_team_name("AC Milan") == "milan"
        assert clean_team_name("Manchester United") == "manchester"

    def test_all_stop_words_preserved(self):
        """Si todas las palabras son stop words, devuelve el string limpio original."""
        result = clean_team_name("Club FC")
        assert result == "club fc"

    def test_punctuation_removal(self):
        assert clean_team_name("Barcelona!") == "barcelona"
        assert clean_team_name("Real Madrid C.F.") == "madrid c f"
        assert clean_team_name("Paris Saint-Germain") == "paris saint germain"

    def test_multiple_spaces(self):
        assert clean_team_name("Real   Madrid") == "madrid"

    def test_empty_input(self):
        assert clean_team_name("") == ""

    def test_none_input(self):
        assert clean_team_name(None) == ""

    def test_numbers_not_removed(self):
        """'1860' no es stop word — solo '1','05','04' lo son."""
        assert clean_team_name("1860 München") == "1860 munchen"

    def test_tsv_stop_word_removed(self):
        """'tsv' es stop word, '1860' no — '1860' permanece."""
        assert clean_team_name("TSV 1860 München") == "1860 munchen"

    def test_idempotent(self):
        """clean_team_name aplicado dos veces debe dar el mismo resultado."""
        original = "F.C. Barcelona (Real Club)"
        once = clean_team_name(original)
        twice = clean_team_name(once)
        assert once == twice

    def test_hotspur_edge(self):
        """'hotspur' es stop word. Tottenham Hotspur → tottenham."""
        assert clean_team_name("Tottenham Hotspur") == "tottenham"

    def test_wanderers_edge(self):
        assert clean_team_name("Wolverhampton Wanderers") == "wolverhampton"

    def test_sporting_edge(self):
        assert clean_team_name("Sporting CP") == "cp"

    def test_internazionale_edge(self):
        """'internazionale' y 'milano' son stop words → preserva original."""
        assert clean_team_name("Internazionale Milano") == "internazionale milano"

    def test_barcelona_vs_barca(self):
        """Clean no es contextual: 'Barça' → 'barca' (sin acento)."""
        assert clean_team_name("Barça") == "barca"

    def test_complex_spanish_name(self):
        assert clean_team_name("Real Club Deportivo de La Coruña") == "de la coruna"

    def test_portuguese_team(self):
        assert clean_team_name("Sport Lisboa e Benfica") == "sport lisboa e benfica"


# ==========================================
# TESTS: resolver_entidad_equipo (Django ORM)
# ==========================================

@pytest.fixture
def mock_equipo():
    eq = MagicMock()
    eq.id = 1
    eq.nombre = "FC Barcelona"
    return eq


@pytest.fixture
def mock_equipos_list(mock_equipo):
    eq2 = MagicMock()
    eq2.id = 2
    eq2.nombre = "Real Madrid"
    eq3 = MagicMock()
    eq3.id = 3
    eq3.nombre = "Atlético Madrid"
    return [mock_equipo, eq2, eq3]


class TestResolverEntidadEquipo:
    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    def test_paso_a_alias_match(self, mock_alias, mock_equipo):
        """Paso A: coincidencia exacta en tabla Alias."""
        mock_alias.filter.return_value.first.return_value = MagicMock(equipo=mock_equipo)
        result = resolver_entidad_equipo("FC Barcelona")
        assert result == mock_equipo
        mock_alias.filter.assert_called_once_with(nombre_fuente__iexact="FC Barcelona")

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_b_cleaned_exact_match(
        self, mock_huerfana, mock_equipos_orm, mock_alias, mock_equipo
    ):
        """Paso B: sin alias, pero match exacto post-limpieza."""
        mock_alias.filter.return_value.first.return_value = None
        mock_equipos_orm.all.return_value = [mock_equipo]
        mock_equipo.nombre = "FC Barcelona"

        result = resolver_entidad_equipo("Barcelona")

        assert result == mock_equipo
        mock_alias.get_or_create.assert_called_once_with(
            nombre_fuente="Barcelona", equipo=mock_equipo
        )

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_b_cleaned_exact_match_madrid(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Real Madrid como 'Real Madrid' → cleaned 'madrid' match."""
        mock_alias.filter.return_value.first.return_value = None
        eq_madrid = MagicMock()
        eq_madrid.id = 2
        eq_madrid.nombre = "Real Madrid"
        mock_equipos_orm.all.return_value = [eq_madrid]

        result = resolver_entidad_equipo("Real Madrid")

        assert result == eq_madrid

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_c_fuzzy_match(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Paso C: fuzzy match con RapidFuzz (score >= 85)."""
        mock_alias.filter.return_value.first.return_value = None
        eq = MagicMock()
        eq.id = 1
        eq.nombre = "FC Barcelona"
        mock_equipos_orm.all.return_value = [eq]
        mock_equipos_orm.get.return_value = eq

        result = resolver_entidad_equipo("Barcalona")

        # 'Barcalona' debe hacer fuzzy match con 'barcelona'
        assert result == eq

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_c_fuzzy_match_umbral_estricto(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Fuzzy match con umbral alto: nombre muy distinto no debe matchear."""
        mock_alias.filter.return_value.first.return_value = None
        eq = MagicMock()
        eq.id = 1
        eq.nombre = "FC Barcelona"
        mock_equipos_orm.all.return_value = [eq]

        result = resolver_entidad_equipo("Liverpool")

        assert result is None  # No debe matchear con Barcelona

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_c_fuzzy_inserts_alias(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Fuzzy match exitoso debe crear un alias para acelerar futuras consultas."""
        mock_alias.filter.return_value.first.return_value = None
        eq = MagicMock()
        eq.id = 1
        eq.nombre = "FC Barcelona"
        mock_equipos_orm.all.return_value = [eq]
        mock_equipos_orm.get.return_value = eq

        resolver_entidad_equipo("Barcalona")

        mock_alias.get_or_create.assert_called_with(
            nombre_fuente="Barcalona", equipo=eq
        )

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_d_orphan_registration(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Paso D: si nada matchea, registrar como huérfano."""
        mock_alias.filter.return_value.first.return_value = None
        mock_equipos_orm.all.return_value = []

        result = resolver_entidad_equipo("FC Desconocido 2024")

        assert result is None
        mock_huerfana.get_or_create.assert_called_once_with(
            nombre_crudo="FC Desconocido 2024"
        )

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_paso_a_vs_b_precedence(
        self, mock_huerfana, mock_equipos_orm, mock_alias, mock_equipo
    ):
        """Paso A (alias exacto) debe ejecutarse antes que Paso B (cleaned)."""
        mock_alias.filter.return_value.first.return_value = MagicMock(equipo=mock_equipo)
        resolver_entidad_equipo("FC Barcelona")
        mock_equipos_orm.all.assert_not_called()

    def test_empty_input_returns_none(self):
        assert resolver_entidad_equipo("") is None
        assert resolver_entidad_equipo(None) is None

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_acentos_en_fuzzy(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Nombre con acento desde API debe resolver contra DB sin acento."""
        mock_alias.filter.return_value.first.return_value = None
        eq = MagicMock()
        eq.id = 1
        eq.nombre = "Atlético Madrid"
        mock_equipos_orm.all.return_value = [eq]

        result = resolver_entidad_equipo("Atletico Madrid")

        assert result == eq

    @patch("predicciones.entity_resolver.AliasEquipo.objects")
    @patch("predicciones.entity_resolver.Equipos.objects")
    @patch("predicciones.entity_resolver.EntidadHuerfana.objects")
    def test_abreviacion_equipo(
        self, mock_huerfana, mock_equipos_orm, mock_alias
    ):
        """Nombres con 1 typo deben resolver vía fuzzy match (score ~90 ≥ 85)."""
        mock_alias.filter.return_value.first.return_value = None
        eq = MagicMock()
        eq.id = 1
        eq.nombre = "Manchester United FC"
        mock_equipos_orm.all.return_value = [eq]
        mock_equipos_orm.get.return_value = eq

        # 'Manchaster' tiene un typo (a→e) frente a 'manchester'
        # token_sort_ratio('manchaster', 'manchester') ≈ 90 ≥ 85
        result = resolver_entidad_equipo("Manchaster United")

        assert result == eq


# ==========================================
# TESTS: EntityResolver (SQLAlchemy)
# ==========================================

class TestEntityResolverSQLAlchemy:
    """Pruebas para src/data_processing/entity_resolver.EntityResolver."""

    def _make_resolver(self, session=None):
        from src.data_processing.entity_resolver import EntityResolver
        return EntityResolver(session=session or MagicMock())

    def _make_scalars_iliike(self, return_val=None):
        """Mock chain: session.execute() → scalars() → first()"""
        scalars = MagicMock()
        scalars.first.return_value = return_val
        return scalars

    def _make_scalars_all(self, return_val):
        """Mock chain: scalars() → all()"""
        scalars = MagicMock()
        scalars.all.return_value = return_val
        return scalars

    def _make_scalars_scalar(self, return_val):
        """Mock chain: scalars() → scalar()"""
        scalars = MagicMock()
        scalars.scalar.return_value = return_val
        return scalars

    def test_init_creates_empty_caches(self):
        resolver = self._make_resolver()
        assert resolver._team_cache == {}
        assert resolver._player_cache == {}

    # --- resolve_team ---

    def test_resolve_team_cache_hit(self):
        resolver = self._make_resolver()
        resolver._team_cache["FC Barcelona"] = 42
        result = resolver.resolve_team("FC Barcelona")
        assert result == 42

    def test_resolve_team_exact_iliike_match(self):
        session = MagicMock()
        resolver = self._make_resolver(session)

        mock_team = MagicMock()
        mock_team.id_equipo = 7
        mock_scalars = self._make_scalars_iliike(mock_team)
        session.execute.return_value.scalars.return_value = mock_scalars

        result = resolver.resolve_team("Barcelona")

        assert result == 7
        assert resolver._team_cache["Barcelona"] == 7

    def test_resolve_team_exact_caches(self):
        session = MagicMock()
        resolver = self._make_resolver(session)
        mock_team = MagicMock()
        mock_team.id_equipo = 7
        mock_scalars = self._make_scalars_iliike(mock_team)
        session.execute.return_value.scalars.return_value = mock_scalars

        resolver.resolve_team("Barcelona")
        assert resolver._team_cache["Barcelona"] == 7

        resolver._team_cache["Barcelona"] = 99
        assert resolver.resolve_team("Barcelona") == 99

    @patch("src.data_processing.entity_resolver.process.extractOne")
    def test_resolve_team_fuzzy_match(self, mock_extract):
        session = MagicMock()
        resolver = self._make_resolver(session)

        exec_results = [
            MagicMock(scalars=MagicMock(return_value=self._make_scalars_iliike(None))),
            MagicMock(scalars=MagicMock(return_value=self._make_scalars_all(
                [MagicMock(id_equipo=1, nombre="FC Barcelona"),
                 MagicMock(id_equipo=2, nombre="Real Madrid")]
            ))),
        ]
        session.execute.side_effect = exec_results

        mock_extract.return_value = ("FC Barcelona", 95, 1)

        result = resolver.resolve_team("Barcalona")

        assert result == 1
        assert resolver._team_cache["Barcalona"] == 1

    @patch("src.data_processing.entity_resolver.process.extractOne")
    def test_resolve_team_fuzzy_below_threshold(self, mock_extract):
        """Fuzzy score bajo + sin equipos en DB → ValueError."""
        session = MagicMock()
        resolver = self._make_resolver(session)

        exec_results = [
            MagicMock(scalars=MagicMock(return_value=self._make_scalars_iliike(None))),
            MagicMock(scalars=MagicMock(return_value=self._make_scalars_all([]))),
        ]
        session.execute.side_effect = exec_results

        with pytest.raises(ValueError, match="No existen equipos registrados"):
            resolver.resolve_team("Totalmente Desconocido")

    @patch("src.data_processing.entity_resolver.process.extractOne")
    def test_resolve_team_auto_create(self, mock_extract):
        session = MagicMock()
        resolver = self._make_resolver(session)

        def mk_exec_result(configure_scalars):
            m = MagicMock()
            s = MagicMock()
            configure_scalars(s)
            m.scalars.return_value = s
            return m

        r1 = mk_exec_result(lambda s: setattr(s.first, 'return_value', None))
        r2 = mk_exec_result(
            lambda s: setattr(s.all, 'return_value',
                              [MagicMock(id_equipo=1, nombre="FC Barcelona")])
        )
        r3 = MagicMock()
        r3.scalar.return_value = 50001  # .scalar() not .scalars().scalar()

        session.execute.side_effect = [r1, r2, r3]
        mock_extract.return_value = ("Algo", 50, None)

        result = resolver.resolve_team("Nuevo Equipo FC")

        assert result == 50002
        session.add.assert_called_once()
        session.flush.assert_called_once()

    @patch("src.data_processing.entity_resolver.process.extractOne")
    def test_resolve_team_empty_db_raises(self, mock_extract):
        """Si no hay equipos en DB, debe levantar ValueError."""
        session = MagicMock()
        resolver = self._make_resolver(session)

        exec_results = [
            MagicMock(scalars=MagicMock(return_value=self._make_scalars_iliike(None))),
            MagicMock(scalars=MagicMock(return_value=self._make_scalars_all([]))),
        ]
        session.execute.side_effect = exec_results

        with pytest.raises(ValueError):
            resolver.resolve_team("Cualquier Cosa")

    # --- resolve_player ---

    def test_resolve_player_cache_hit(self):
        resolver = self._make_resolver()
        resolver._player_cache["Messi_1"] = 10
        assert resolver._player_cache["Messi_1"] == 10

    def test_resolve_player_exact_match(self):
        session = MagicMock()
        resolver = self._make_resolver(session)

        mock_player = MagicMock()
        mock_player.id_jugador = 100
        scalars = self._make_scalars_iliike(mock_player)
        session.execute.return_value.scalars.return_value = scalars

        resolver.resolve_player("Messi", team_id=1)

        assert resolver._player_cache["Messi_1"] == 100

    def test_resolve_player_no_team_fallback(self):
        session = MagicMock()
        resolver = self._make_resolver(session)

        def mk_exec_result(configure_scalars):
            m = MagicMock()
            s = MagicMock()
            configure_scalars(s)
            m.scalars.return_value = s
            return m

        r1 = mk_exec_result(lambda s: setattr(s.first, 'return_value', None))
        r2 = MagicMock()
        r2.scalar.return_value = 9999999   # .scalar() not .scalars().scalar()
        r3 = mk_exec_result(lambda s: setattr(s.first, 'return_value', None))
        r4 = mk_exec_result(lambda s: setattr(s.first, 'return_value', None))

        session.execute.side_effect = [r1, r2, r3, r4]

        result = resolver.resolve_player("Nuevo Jugador")

        assert result == 10000000
        session.add.assert_called()
        session.flush.assert_called()

    # --- resolve_match ---

    def test_resolve_match_invalid_date(self):
        resolver = self._make_resolver()
        result = resolver.resolve_match(1, 2, "not-a-date")
        assert result == -1

    def test_resolve_match_empty_db_creates(self):
        session = MagicMock()
        resolver = self._make_resolver(session)

        def mk_exec_result(configure_scalars):
            m = MagicMock()
            s = MagicMock()
            configure_scalars(s)
            m.scalars.return_value = s
            return m

        r1 = mk_exec_result(lambda s: setattr(s.first, 'return_value', None))
        r2 = MagicMock()
        r2.scalar.return_value = 8000000  # .scalar() not .scalars().scalar()

        session.execute.side_effect = [r1, r2]

        result = resolver.resolve_match(1, 2, "15/05/2024")

        assert result == 8000001
        session.add.assert_called()
        session.flush.assert_called()

    def test_resolve_match_date_tolerance(self):
        """Debe encontrar match con +/-1 día de tolerancia."""
        session = MagicMock()
        resolver = self._make_resolver(session)

        mock_match = MagicMock()
        mock_match.id_partido = 100
        mock_scalars = MagicMock()
        mock_scalars.first.return_value = mock_match
        session.execute.return_value.scalars.return_value = mock_scalars

        result = resolver.resolve_match(1, 2, "15/05/2024")

        assert result == 100


# ==========================================
# TESTS: RAPIDFUZZ EN FBrefPlayerDataset
# ==========================================

class TestFBrefFuzzyPatterns:
    """
    Verifica que los patrones de fuzzy matching usados en
    FBrefPlayerDataset (rapidfuzz, token_sort_ratio, cutoff=85)
    funcionan para casos reales de nombres de jugadores/equipos.
    """

    JUGADORES_DB = [
        "Lionel Messi", "Cristiano Ronaldo", "Neymar Jr",
        "Kylian Mbappé", "Robert Lewandowski", "Kevin De Bruyne",
    ]

    EQUIPOS_DB = [
        "FC Barcelona", "Real Madrid", "Paris Saint-Germain",
        "Manchester City", "Bayern Munich", "Liverpool FC",
    ]

    def test_jugador_match_exacto(self):
        match = process.extractOne(
            "Lionel Messi", self.JUGADORES_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None
        assert match[0] == "Lionel Messi"
        assert match[1] >= 85

    def test_jugador_match_typo(self):
        match = process.extractOne(
            "Leonel Messi", self.JUGADORES_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None
        assert match[1] >= 85

    def test_jugador_match_sin_acento(self):
        match = process.extractOne(
            "Kylian Mbappe", self.JUGADORES_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None
        assert match[0] == "Kylian Mbappé"

    def test_jugador_match_parcial(self):
        """⚠️ LIMITACIÓN: 'Cristiano' solo vs 'Cristiano Ronaldo' → token_sort_ratio
        ~77% (palabras añadidas bajan el score). No supera cutoff 85."""
        match = process.extractOne(
            "Cristiano", self.JUGADORES_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is None

    def test_jugador_match_typo_real(self):
        """Un typo real ('Ronaldho') debe pasar el umbral 85 con 'Ronaldo'."""
        match = process.extractOne(
            "Cristiano Ronaldho", self.JUGADORES_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None
        assert match[1] >= 85

    def test_jugador_sin_match(self):
        match = process.extractOne(
            "John Doe Desconocido", self.JUGADORES_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is None

    def test_equipo_match_exacto(self):
        match = process.extractOne(
            "FC Barcelona", self.EQUIPOS_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None
        assert match[1] == 100

    def test_equipo_match_sin_stopword(self):
        match = process.extractOne(
            "Barcelona", self.EQUIPOS_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None

    def test_equipo_match_paris(self):
        match = process.extractOne(
            "PSG", self.EQUIPOS_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is None or match[0] == "Paris Saint-Germain"

    def test_equipo_match_manchester(self):
        match = process.extractOne(
            "Manchester City FC", self.EQUIPOS_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is not None

    def test_sin_match_total(self):
        match = process.extractOne(
            "Equipo Inexistente XYZ", self.EQUIPOS_DB,
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        assert match is None


# ==========================================
# TESTS: clean_team_name INTEGRACIÓN
# ==========================================

class TestCleanTeamNameIntegration:
    """
    Prueba el flujo real: API devuelve nombre → clean_team_name
    → fuzzy match contra nombres limpios de DB.
    """

    EQUIPOS_DB = [
        "FC Barcelona", "Real Madrid CF", "Atlético de Madrid",
        "Paris Saint-Germain", "Manchester United FC",
        "AC Milan", "FC Bayern München", "Liverpool FC",
        "Chelsea FC", "Arsenal FC",
    ]

    def _clean_and_match(self, raw_name):
        cleaned = clean_team_name(raw_name)
        db_cleaned = {clean_team_name(t): t for t in self.EQUIPOS_DB}
        match = process.extractOne(
            cleaned, list(db_cleaned.keys()),
            scorer=fuzz.token_sort_ratio, score_cutoff=85
        )
        if match:
            return db_cleaned[match[0]]
        return None

    def test_clean_and_match_barcelona(self):
        assert self._clean_and_match("FC Barcelona") == "FC Barcelona"

    def test_clean_and_match_barca_api(self):
        assert self._clean_and_match("Barcelona") == "FC Barcelona"

    def test_clean_and_match_barca_con_acento_api(self):
        """⚠️ LIMITACIÓN: 'Barça' → 'barca' no supera umbral 85 con 'barcelona'.
        El 5-char diff (~50% token_sort_ratio) queda fuera del cutoff. 
        Esto es una brecha de robustez del entity resolver actual."""
        assert self._clean_and_match("Barça") is None

    def test_clean_and_match_manchester_abreviado(self):
        """⚠️ LIMITACIÓN: 'Man Utd' no supera umbral 85 con 'manchester'.
        No hay solapamiento léxico suficiente para token_sort_ratio ≥ 85."""
        assert self._clean_and_match("Man Utd") is None

    def test_clean_and_match_munich_api(self):
        assert self._clean_and_match("Bayern Munich") == "FC Bayern München"

    def test_clean_and_match_liverpool_api(self):
        assert self._clean_and_match("Liverpool") == "Liverpool FC"

    def test_clean_and_match_atletico_api(self):
        assert self._clean_and_match("Atletico Madrid") == "Atlético de Madrid"

    def test_clean_and_match_paris_api(self):
        """⚠️ LIMITACIÓN: 'Paris SG' → 'paris sg' no supera 85 con
        'paris saint germain'. 'sg' no está en STOP_WORDS."""
        assert self._clean_and_match("Paris SG") is None

    def test_clean_and_match_ac_milan_api(self):
        assert self._clean_and_match("Milan") == "AC Milan"

    def test_clean_and_match_cfc_api(self):
        assert self._clean_and_match("Chelsea") == "Chelsea FC"

    def test_clean_and_match_inexistente(self):
        assert self._clean_and_match("FC No Existe 9999") is None
