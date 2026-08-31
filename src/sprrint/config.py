from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path

import tomli_w

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from sprrint.errors import AuthError, ConfigError

SITE_URL = 'https://sprrint.run'


def config_dir() -> Path:
    if home := os.environ.get('SPRRINT_HOME'):
        return Path(home)
    xdg = os.environ.get('XDG_CONFIG_HOME')
    root = Path(xdg) if xdg else Path.home() / '.config'
    return root / 'sprrint'


def config_path() -> Path:
    return config_dir() / 'config.toml'


@dataclass
class Settings:
    api_url: str = SITE_URL
    api_key: str = ''
    project: str = ''

    def host(self) -> str:
        return self.api_url.rstrip('/')


def load() -> Settings:
    data = {}
    path = config_path()
    if path.exists():
        data = tomllib.loads(path.read_text()) or {}
    return Settings(
        api_url=SITE_URL,
        api_key=os.environ.get('SPRRINT_API_KEY') or data.get('api_key') or '',
        project=os.environ.get('SPRRINT_PROJECT') or data.get('project') or '',
    )


def save(settings: Settings) -> Path:
    settings.api_url = SITE_URL
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomli_w.dumps(asdict(settings)))
    path.chmod(0o600)
    return path


def update(**changes) -> Settings:
    settings = load()
    for key, value in changes.items():
        if value is None:
            continue
        if key == 'api_url':
            continue
        if not hasattr(settings, key):
            raise ConfigError(f'Unknown setting: {key}')
        setattr(settings, key, value)
    settings.api_url = SITE_URL
    save(settings)
    return settings


def require_key(settings: Settings | None = None) -> Settings:
    settings = settings or load()
    if not settings.api_key:
        raise AuthError('Not signed in. Run `sprrint login` or set SPRRINT_API_KEY.')
    return settings
