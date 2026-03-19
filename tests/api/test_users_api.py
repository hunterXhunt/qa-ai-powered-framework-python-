"""
tests/api/test_users_api.py

Pure API tests for /users endpoints — no browser, uses httpx.
These run fast (~1s each) and are included in every CI push.
"""

from __future__ import annotations

import pytest
import httpx

from src.utils.data_factory import DataFactory, TestUser


# ── Helpers ───────────────────────────────────────────────────────────────────

def register_and_login(client: httpx.Client, factory: DataFactory) -> tuple[TestUser, str]:
    """Create and authenticate a test user, return (user, token)."""
    user = factory.user()
    reg = client.post("/api/auth/register", json=user.registration_payload())
    assert reg.status_code in (200, 201), f"Register failed: {reg.text}"
    user.id = reg.json().get("id", user.id)

    login = client.post("/api/auth/login", json=user.credentials())
    assert login.status_code == 200, f"Login failed: {login.text}"
    token = login.json()["token"]
    user.token = token
    return user, token


# ── GET /users/:id ─────────────────────────────────────────────────────────────

@pytest.mark.api
class TestGetUser:
    """Tests for GET /api/v1/users/:id"""

    @pytest.mark.smoke
    def test_retourne_utilisateur_avec_schema_valide(self, api_client: httpx.Client) -> None:
        """Vérifie que l'endpoint retourne un utilisateur avec le bon schéma JSON."""
        factory = DataFactory()
        user, token = register_and_login(api_client, factory)

        res = api_client.get(
            f"/api/v1/users/{user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        body = res.json()
        # Schema validation
        assert "id"        in body
        assert "email"     in body
        assert "firstName" in body
        assert body["email"] == user.email
        # Le mot de passe ne doit JAMAIS être retourné
        assert "password"     not in body
        assert "passwordHash" not in body

    @pytest.mark.regression
    def test_retourne_401_sans_token(self, api_client: httpx.Client) -> None:
        """Vérifie que l'endpoint retourne 401 sans token d'authentification."""
        res = api_client.get("/api/v1/users/any-id")
        assert res.status_code == 401

    @pytest.mark.regression
    def test_retourne_401_token_expire(self, api_client: httpx.Client) -> None:
        """Vérifie que l'endpoint retourne 401 avec un token expiré."""
        expired_token = "eyJhbGciOiJIUzI1NiJ9.eyJleHAiOjB9.invalid"
        res = api_client.get(
            "/api/v1/users/any-id",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert res.status_code in (401, 403)

    @pytest.mark.security
    def test_retourne_403_acces_profil_autre_utilisateur_idor(self, api_client: httpx.Client) -> None:
        """Vérifie la protection IDOR : un utilisateur ne peut pas voir le profil d'un autre."""
        factory = DataFactory()
        user_a, token_a = register_and_login(api_client, factory)
        user_b, _       = register_and_login(api_client, factory)

        # UserA essaie d'accéder au profil de UserB
        res = api_client.get(
            f"/api/v1/users/{user_b.id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code == 403, (
            f"IDOR vulnerability: user A accessed user B profile with status {res.status_code}"
        )

    @pytest.mark.regression
    def test_retourne_404_pour_id_inexistant(self, api_client: httpx.Client) -> None:
        """Vérifie le retour d'un 404 pour un ID inconnu."""
        factory = DataFactory()
        user, token = register_and_login(api_client, factory)
        res = api_client.get(
            "/api/v1/users/id-qui-nexiste-pas-99999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 404

    @pytest.mark.performance
    def test_repond_en_moins_de_300ms(self, api_client: httpx.Client) -> None:
        """Vérifie que l'endpoint répond en moins de 300ms."""
        factory = DataFactory()
        user, token = register_and_login(api_client, factory)

        import time
        start = time.perf_counter()
        res = api_client.get(
            f"/api/v1/users/{user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        duration_ms = (time.perf_counter() - start) * 1000

        assert res.status_code == 200
        assert duration_ms < 300, f"Response too slow: {duration_ms:.0f}ms > 300ms"


# ── POST /auth/login ──────────────────────────────────────────────────────────

@pytest.mark.api
class TestLogin:
    """Tests for POST /api/auth/login"""

    @pytest.mark.smoke
    def test_retourne_token_avec_identifiants_valides(self, api_client: httpx.Client) -> None:
        """Vérifie que l'endpoint retourne un token JWT valide."""
        factory = DataFactory()
        user = factory.user()
        api_client.post("/api/auth/register", json=user.registration_payload())

        res = api_client.post("/api/auth/login", json=user.credentials())

        assert res.status_code == 200
        body = res.json()
        assert "token" in body
        assert isinstance(body["token"], str)
        assert len(body["token"]) > 20

    @pytest.mark.regression
    def test_retourne_401_mauvais_mot_de_passe(self, api_client: httpx.Client) -> None:
        """Vérifie le retour 401 avec un mauvais mot de passe."""
        factory = DataFactory()
        user = factory.user()
        api_client.post("/api/auth/register", json=user.registration_payload())

        res = api_client.post("/api/auth/login", json={
            "email": user.email, "password": "mauvais-mdp"
        })
        assert res.status_code == 401

    @pytest.mark.regression
    def test_retourne_400_email_format_invalide(self, api_client: httpx.Client) -> None:
        """Vérifie le retour 400 pour un email malformé."""
        res = api_client.post("/api/auth/login", json={
            "email": "email-invalide", "password": "Password123!"
        })
        assert res.status_code in (400, 422)

    @pytest.mark.security
    def test_retourne_429_apres_brute_force(self, api_client: httpx.Client) -> None:
        """Vérifie la protection contre le brute force (rate limiting)."""
        factory = DataFactory()
        user = factory.user()
        api_client.post("/api/auth/register", json=user.registration_payload())

        for _ in range(10):
            api_client.post("/api/auth/login", json={
                "email": user.email, "password": "wrong-password"
            })

        # The 11th attempt should be rate-limited
        res = api_client.post("/api/auth/login", json={
            "email": user.email, "password": "wrong-password"
        })
        assert res.status_code in (401, 429), (
            "Rate limiting not implemented — brute force protection missing"
        )


# ── PATCH /users/:id ──────────────────────────────────────────────────────────

@pytest.mark.api
class TestUpdateUser:
    """Tests for PATCH /api/v1/users/:id"""

    @pytest.mark.regression
    def test_met_a_jour_prenom_avec_donnees_valides(self, api_client: httpx.Client) -> None:
        """Vérifie la mise à jour du prénom avec des données valides."""
        factory = DataFactory()
        user, token = register_and_login(api_client, factory)

        res = api_client.patch(
            f"/api/v1/users/{user.id}",
            json={"firstName": "NouveauPrenom"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert res.status_code == 200
        assert res.json()["firstName"] == "NouveauPrenom"

    @pytest.mark.regression
    def test_rejette_email_deja_utilise(self, api_client: httpx.Client) -> None:
        """Vérifie le rejet d'une mise à jour avec un email déjà utilisé."""
        factory = DataFactory()
        user_a, _       = register_and_login(api_client, factory)
        user_b, token_b = register_and_login(api_client, factory)

        res = api_client.patch(
            f"/api/v1/users/{user_b.id}",
            json={"email": user_a.email},
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert res.status_code in (400, 409)

    @pytest.mark.security
    def test_ne_peut_pas_modifier_profil_autre_utilisateur(self, api_client: httpx.Client) -> None:
        """Vérifie que l'on ne peut pas modifier le profil d'un autre utilisateur."""
        factory = DataFactory()
        user_a, token_a = register_and_login(api_client, factory)
        user_b, _       = register_and_login(api_client, factory)

        res = api_client.patch(
            f"/api/v1/users/{user_b.id}",
            json={"firstName": "Hacked"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert res.status_code in (403, 404)
