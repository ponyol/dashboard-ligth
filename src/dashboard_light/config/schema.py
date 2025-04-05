"""Схема валидации конфигурации приложения."""

import logging
import re
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)


class RoleGitlabGroups(BaseModel):
    """Модель для групп GitLab, связанных с ролью."""

    gitlab_groups: List[str] = Field(default_factory=list)


class RolePermissions(BaseModel):
    """Модель для прав доступа, связанных с ролью."""

    menu_items: List[str] = Field(default_factory=list)
    allowed_namespace_patterns: List[str] = Field(default_factory=list)
    allowed_clusters: List[str] = Field(default_factory=list)


class StatusColors(BaseModel):
    """Модель для цветов статусов."""

    class DeploymentColors(BaseModel):
        """Цвета для статусов деплойментов."""

        healthy: str = "#28a745"
        progressing: str = "#ffc107"
        scaled_zero: str = "#6c757d"
        error: str = "#dc3545"

    class PodColors(BaseModel):
        """Цвета для статусов подов."""

        running: str = "#28a745"
        succeeded: str = "#17a2b8"
        pending: str = "#ffc107"
        failed: str = "#dc3545"
        terminating: str = "#6c757d"

    deployment: DeploymentColors = Field(default_factory=DeploymentColors)
    pod: PodColors = Field(default_factory=PodColors)


class UIConfig(BaseModel):
    """Модель для конфигурации UI."""

    refresh_interval_seconds: int = 15
    status_colors: StatusColors = Field(default_factory=StatusColors)


class MenuItem(BaseModel):
    """Модель для пункта меню."""

    id: str
    title: str
    icon: str
    required_role: str


class AuthConfig(BaseModel):
    """Модель для конфигурации аутентификации."""

    provider: str
    gitlab_url: str
    client_id: str
    client_secret_env: str
    redirect_uri: str
    roles: Dict[str, RoleGitlabGroups]
    permissions: Dict[str, RolePermissions]
    allow_anonymous_access: bool = False
    anonymous_role: Optional[str] = None

    @model_validator(mode='after')
    def check_anonymous_role(self) -> 'AuthConfig':
        """Проверка, что анонимная роль существует, если включен анонимный доступ."""
        if self.allow_anonymous_access and not self.anonymous_role:
            raise ValueError("Если allow_anonymous_access=True, нужно указать anonymous_role")

        if self.allow_anonymous_access and self.anonymous_role not in self.roles:
            raise ValueError(f"Указанная anonymous_role '{self.anonymous_role}' не существует в списке ролей")

        return self


class CacheConfig(BaseModel):
    """Модель для конфигурации кэширования."""

    default_ttl: int = 30
    ttl: Dict[str, int] = Field(default_factory=dict)


class TestConfig(BaseModel):
    """Модель для конфигурации тестирования."""

    namespace_patterns: List[str] = Field(default_factory=lambda: ["default", "kube-system"])


class AppConfig(BaseModel):
    """Основная модель конфигурации приложения."""

    auth: AuthConfig
    ui: UIConfig = Field(default_factory=UIConfig)
    menu: List[MenuItem] = Field(default_factory=list)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    test: TestConfig = Field(default_factory=TestConfig)


def validate_config(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Валидация конфигурации по схеме.

    Args:
        config_data: Данные конфигурации для проверки

    Returns:
        Dict[str, Any]: Проверенные данные конфигурации

    Raises:
        ValueError: Если конфигурация не соответствует схеме
    """
    try:
        validated_config = AppConfig(**config_data)
        return validated_config.model_dump()
    except Exception as e:
        logger.error(f"Ошибка валидации конфигурации: {str(e)}")
        raise ValueError(f"Ошибка валидации конфигурации: {str(e)}")
