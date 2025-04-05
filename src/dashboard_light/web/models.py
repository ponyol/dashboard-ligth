"""Модели данных для API."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Модель для ответа с ошибкой."""

    detail: str = Field(..., description="Подробное описание ошибки")
    status_code: int = Field(400, description="HTTP код ошибки")


class HealthResponse(BaseModel):
    """Модель для ответа о состоянии здоровья приложения."""

    status: str = Field(..., description="Статус приложения")
    version: str = Field(..., description="Версия приложения")
    kubernetes_connected: bool = Field(..., description="Подключение к Kubernetes API")


class UserInfo(BaseModel):
    """Модель для информации о пользователе."""

    id: int = Field(..., description="Уникальный идентификатор пользователя")
    username: str = Field(..., description="Имя пользователя")
    name: Optional[str] = Field(None, description="Полное имя пользователя")
    email: Optional[str] = Field(None, description="Email пользователя")
    roles: List[str] = Field(default_factory=list, description="Роли пользователя")


class ContainerInfo(BaseModel):
    """Модель для информации о контейнере."""

    name: str = Field(..., description="Имя контейнера")
    image: str = Field(..., description="Образ контейнера")
    image_tag: str = Field(..., description="Тег образа контейнера")


class ReplicaInfo(BaseModel):
    """Модель для информации о репликах Deployment."""

    desired: int = Field(..., description="Желаемое количество реплик")
    ready: int = Field(..., description="Готовое количество реплик")
    available: int = Field(..., description="Доступное количество реплик")
    updated: int = Field(..., description="Обновленное количество реплик")


class DeploymentInfo(BaseModel):
    """Модель для информации о Deployment."""

    name: str = Field(..., description="Имя Deployment")
    namespace: str = Field(..., description="Пространство имен")
    replicas: ReplicaInfo = Field(..., description="Информация о репликах")
    main_container: Optional[ContainerInfo] = Field(None, description="Информация о главном контейнере")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")
    status: Optional[str] = Field(None, description="Статус Deployment")


class ResourceUsage(BaseModel):
    """Модель для информации об использовании ресурсов."""

    cpu: Optional[str] = Field(None, description="Использование CPU")
    memory: Optional[str] = Field(None, description="Использование памяти")
    cpu_millicores: Optional[int] = Field(None, description="Использование CPU в миллиядрах")
    memory_mb: Optional[float] = Field(None, description="Использование памяти в МБ")


class ContainerMetrics(BaseModel):
    """Модель для метрик контейнера."""

    name: str = Field(..., description="Имя контейнера")
    resource_usage: ResourceUsage = Field(..., description="Использование ресурсов")


class PodMetrics(BaseModel):
    """Модель для метрик Pod."""

    name: str = Field(..., description="Имя Pod")
    namespace: str = Field(..., description="Пространство имен")
    containers: List[ContainerMetrics] = Field(..., description="Метрики контейнеров")
    timestamp: Optional[str] = Field(None, description="Временная метка")
    age_seconds: Optional[float] = Field(None, description="Возраст метрик в секундах")


class PodInfo(BaseModel):
    """Модель для информации о Pod."""

    name: str = Field(..., description="Имя Pod")
    namespace: str = Field(..., description="Пространство имен")
    phase: str = Field(..., description="Фаза Pod")
    containers: List[ContainerInfo] = Field(..., description="Информация о контейнерах")
    pod_ip: Optional[str] = Field(None, description="IP Pod")
    host_ip: Optional[str] = Field(None, description="IP хоста")
    started_at: Optional[datetime] = Field(None, description="Время запуска")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")
    metrics: Optional[PodMetrics] = Field(None, description="Метрики Pod")


class NamespaceInfo(BaseModel):
    """Модель для информации о Namespace."""

    name: str = Field(..., description="Имя пространства имен")
    phase: Optional[str] = Field(None, description="Фаза пространства имен")
    created: Optional[str] = Field(None, description="Время создания")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")


class DeploymentList(BaseModel):
    """Модель для списка Deployments."""

    items: List[DeploymentInfo] = Field(..., description="Список Deployments")


class PodList(BaseModel):
    """Модель для списка Pods."""

    items: List[PodInfo] = Field(..., description="Список Pods")


class NamespaceList(BaseModel):
    """Модель для списка Namespaces."""

    items: List[NamespaceInfo] = Field(..., description="Список Namespaces")
