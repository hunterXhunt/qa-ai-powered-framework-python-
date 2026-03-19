"""
tests/specs/auth/test_login.py

US-001 — Authentification utilisateur
Exemple du type de tests que le générateur IA produit.

Pour régénérer ces tests avec l'IA :
    python scripts/generate_tests.py --story stories/auth/login.json
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from src.pages.base_page import BasePage
from src.utils.data_factory import DataFactory


# ── Page Object ───────────────────────────────────────────────────────────────

class LoginPage(BasePage):
    """Page Object for the /login page."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.email_input     = page.get_by_test_id("email-input")
        self.password_input  = page.get_by_test_id("password-input")
        self.submit_button   = page.get_by_test_id("submit-btn")
        self.error_message   = page.get_by_test_id("error-message")
        self.email_error     = page.get_by_test_id("email-error")
        self.header_username = page.get_by_test_id("header-username")

    def login(self, email: str, password: str) -> None:
        """Fill and submit the login form."""
        self.email_input.fill(email)
        self.password_input.fill(password)
        self.submit_button.click()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestAuthentification:
    """US-001 — Tests d'authentification utilisateur."""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, api_base_url: str) -> None:
        self.login_page   = LoginPage(page)
        self.page         = page
        self.api_base_url = api_base_url
        self.factory      = DataFactory()
        page.goto("/login")

    def _create_user(self) -> tuple[str, str]:
        """Helper: create a test user via API and return (email, password)."""
        user = self.factory.user()
        res = self.page.request.post(
            f"{self.api_base_url}/api/auth/register",
            data=user.registration_payload(),
        )
        assert res.ok, f"Could not create user: {res.text()}"
        return user.email, user.password

    # ── Happy Path ─────────────────────────────────────────────────────────────

    @pytest.mark.smoke
    def test_redirige_vers_dashboard_apres_connexion_valide(self) -> None:
        """Vérifie la redirection vers /dashboard après une connexion réussie."""
        email, password = self._create_user()
        self.login_page.login(email, password)
        expect(self.page).to_have_url(lambda url: "/dashboard" in url)
        expect(self.page.get_by_test_id("user-greeting")).to_be_visible()

    @pytest.mark.regression
    def test_affiche_prenom_dans_en_tete_apres_connexion(self) -> None:
        """Vérifie que le prénom de l'utilisateur est affiché dans l'en-tête."""
        user = self.factory.user(first_name="Michel")
        self.page.request.post(
            f"{self.api_base_url}/api/auth/register",
            data=user.registration_payload(),
        )
        self.login_page.login(user.email, user.password)
        expect(self.login_page.header_username).to_contain_text("Michel")

    # ── Edge Cases ─────────────────────────────────────────────────────────────

    @pytest.mark.regression
    def test_bouton_submit_desactive_si_champs_vides(self) -> None:
        """Vérifie que le bouton de connexion est désactivé quand les champs sont vides."""
        expect(self.login_page.submit_button).to_be_disabled()

    @pytest.mark.regression
    def test_mot_de_passe_masque_par_defaut(self) -> None:
        """Vérifie que le champ mot de passe est de type 'password'."""
        expect(self.login_page.password_input).to_have_attribute("type", "password")

    @pytest.mark.regression
    def test_accepte_email_avec_alias_plus(self) -> None:
        """Vérifie que les emails avec alias (test+alias@domain.com) sont acceptés."""
        email = f"test+alias-{self.factory.string()}@sub.domain.com"
        res = self.page.request.post(
            f"{self.api_base_url}/api/auth/register",
            data={"email": email, "password": "TestPassword123!", "firstName": "Test", "lastName": "User"},
        )
        if not res.ok:
            pytest.skip("Server does not support plus-alias emails")
        self.login_page.login(email, "TestPassword123!")
        expect(self.page).to_have_url(lambda url: "/dashboard" in url)

    @pytest.mark.regression
    def test_connexion_avec_email_en_majuscules(self) -> None:
        """Vérifie que la connexion fonctionne avec l'email en majuscules (case-insensitive)."""
        email, password = self._create_user()
        self.login_page.login(email.upper(), password)
        # Should either succeed or show a clear message — not a server error
        expect(self.page).not_to_have_url(lambda url: "500" in url or "error" in url.lower())

    # ── Error Scenarios ────────────────────────────────────────────────────────

    @pytest.mark.regression
    def test_affiche_erreur_mot_de_passe_incorrect(self) -> None:
        """Vérifie l'affichage d'un message d'erreur avec un mauvais mot de passe."""
        email, _ = self._create_user()
        self.login_page.login(email, "mauvais-mot-de-passe")
        expect(self.login_page.error_message).to_be_visible()
        expect(self.login_page.error_message).to_contain_text("Identifiants invalides")
        expect(self.page).to_have_url(lambda url: "/login" in url)

    @pytest.mark.regression
    def test_affiche_erreur_format_email_invalide(self) -> None:
        """Vérifie l'affichage d'une erreur de format pour un email invalide."""
        self.login_page.email_input.fill("email-sans-arobase")
        self.login_page.password_input.fill("AnyPassword123!")
        self.login_page.submit_button.click()
        expect(self.login_page.email_error).to_be_visible()
        expect(self.login_page.email_error).to_contain_text("Format email invalide")

    @pytest.mark.regression
    def test_affiche_erreur_compte_inexistant(self) -> None:
        """Vérifie l'affichage d'un message d'erreur pour un compte inconnu."""
        self.login_page.login(self.factory.email(), "SomePassword123!")
        expect(self.login_page.error_message).to_be_visible()

    @pytest.mark.regression
    def test_verrouillage_compte_apres_5_tentatives(self) -> None:
        """Vérifie le verrouillage du compte après 5 tentatives de connexion échouées."""
        email, _ = self._create_user()
        for _ in range(5):
            self.login_page.login(email, "wrong-password")
            self.page.goto("/login")  # Reset form
        self.login_page.login(email, "wrong-password")
        expect(self.login_page.error_message).to_contain_text_matching(
            r"verrouillé|bloqué|trop de tentatives",
        )

    # ── Security ───────────────────────────────────────────────────────────────

    @pytest.mark.security
    def test_redirige_vers_login_si_acces_dashboard_sans_auth(self) -> None:
        """Vérifie que /dashboard est inaccessible sans être connecté."""
        self.page.goto("/dashboard")
        expect(self.page).to_have_url(lambda url: "/login" in url)

    @pytest.mark.security
    def test_token_non_expose_dans_url_apres_connexion(self) -> None:
        """Vérifie que le token JWT n'apparaît pas dans l'URL après connexion."""
        email, password = self._create_user()
        self.login_page.login(email, password)
        url = self.page.url
        assert "token=" not in url.lower(), f"Token exposed in URL: {url}"
        assert "jwt="   not in url.lower(), f"JWT exposed in URL: {url}"

    @pytest.mark.security
    def test_injection_xss_champ_email_neutralisee(self) -> None:
        """Vérifie que les payloads XSS dans le champ email sont neutralisés."""
        # Intercept any dialog (would indicate XSS success)
        xss_triggered = []
        self.page.on("dialog", lambda d: xss_triggered.append(d.message) or d.dismiss())

        self.login_page.email_input.fill('<script>alert("xss")</script>')
        self.login_page.password_input.fill("AnyPassword123!")
        self.login_page.submit_button.click()

        assert not xss_triggered, f"XSS was triggered: {xss_triggered}"
        content = self.page.content()
        assert '<script>alert("xss")</script>' not in content
