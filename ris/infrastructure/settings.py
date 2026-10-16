"""Explicit environment snapshot for web configuration; no import-time I/O."""
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class WebSettings:
    secret_key: str
    database_url: str
    session_cookie_samesite: str
    session_cookie_secure: bool

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]):
        public_url = environment.get('RIS_PUBLIC_URL', 'https://ris.dynuddns.net')
        return cls(
            secret_key=environment.get('SECRET_KEY', 'change-me-now'),
            database_url=environment.get('DATABASE_URL', 'sqlite:///ris.db'),
            session_cookie_samesite=environment.get('SESSION_COOKIE_SAMESITE', 'Lax'),
            session_cookie_secure=environment.get(
                'SESSION_COOKIE_SECURE', '1' if public_url.lower().startswith('https://') else '0'
            ) == '1',
        )

    def flask_config(self):
        return {
            'SECRET_KEY': self.secret_key,
            'SQLALCHEMY_DATABASE_URI': self.database_url,
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,
            'MAX_CONTENT_LENGTH': 30 * 1024 * 1024,
            'SESSION_COOKIE_HTTPONLY': True,
            'SESSION_COOKIE_SAMESITE': self.session_cookie_samesite,
            'SESSION_COOKIE_SECURE': self.session_cookie_secure,
        }
