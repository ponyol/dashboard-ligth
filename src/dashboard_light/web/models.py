"""Модели данных для API."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union, ForwardRef

from pydantic import BaseModel, Field, validator


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
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


class ReplicaInfo(BaseModel):
    """Модель для информации о репликах Deployment."""

    desired: int = Field(0, description="Желаемое количество реплик")
    ready: int = Field(0, description="Готовое количество реплик")
    available: int = Field(0, description="Доступное количество реплик")
    updated: int = Field(0, description="Обновленное количество реплик")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


# Определим полную модель PodInfo
class PodInfo(BaseModel):
    """Модель для информации о Pod."""

    name: str = Field(..., description="Имя Pod")
    namespace: str = Field(..., description="Пространство имен")
    phase: str = Field("Unknown", description="Фаза Pod")
    containers: List[ContainerInfo] = Field(default_factory=list, description="Информация о контейнерах")
    pod_ip: Optional[str] = Field(None, description="IP Pod")
    host_ip: Optional[str] = Field(None, description="IP хоста")
    started_at: Optional[Any] = Field(None, description="Время запуска")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")
    metrics: Optional["PodMetrics"] = Field(None, description="Метрики Pod")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных
        arbitrary_types_allowed = True  # Разрешаем произвольные типы

class DeploymentInfo(BaseModel):
    """Модель для информации о Deployment."""

    name: str = Field(..., description="Имя Deployment")
    namespace: str = Field(..., description="Пространство имен")
    replicas: ReplicaInfo = Field(..., description="Информация о репликах")
    main_container: Optional[ContainerInfo] = Field(None, description="Информация о главном контейнере")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")
    status: Optional[str] = Field(None, description="Статус Deployment")
    pods: Optional[List["PodInfo"]] = Field(None, description="Список подов deployment")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных
        arbitrary_types_allowed = True  # Разрешаем произвольные типы


class ResourceUsage(BaseModel):
    """Модель для информации об использовании ресурсов."""

    cpu: Optional[str] = Field(None, description="Использование CPU")
    memory: Optional[str] = Field(None, description="Использование памяти")
    cpu_millicores: Optional[int] = Field(0, description="Использование CPU в миллиядрах")
    memory_mb: Optional[float] = Field(0.0, description="Использование памяти в МБ")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


class ContainerMetrics(BaseModel):
    """Модель для метрик контейнера."""

    name: str = Field(..., description="Имя контейнера")
    resource_usage: ResourceUsage = Field(..., description="Использование ресурсов")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


class PodMetrics(BaseModel):
    """Модель для метрик Pod."""

    name: str = Field(..., description="Имя Pod")
    namespace: str = Field(..., description="Пространство имен")
    containers: List[ContainerMetrics] = Field(default_factory=list, description="Метрики контейнеров")
    timestamp: Optional[Any] = Field(None, description="Временная метка (может быть строкой или объектом datetime)")
    age_seconds: Optional[float] = Field(0, description="Возраст метрик в секундах")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных
        arbitrary_types_allowed = True  # Разрешаем произвольные типы


# Добавим вызов update_forward_refs() в конце файла


class NamespaceInfo(BaseModel):
    """Модель для информации о Namespace."""

    name: str = Field(..., description="Имя пространства имен")
    phase: Optional[str] = Field(None, description="Фаза пространства имен")
    created: Optional[str] = Field(None, description="Время создания")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


class DeploymentList(BaseModel):
    """Модель для списка Deployments."""

    items: List[DeploymentInfo] = Field(..., description="Список Deployments")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных

class ControllerInfo(BaseModel):
    """Модель для информации о контроллере (Deployment или StatefulSet)."""

    name: str = Field(..., description="Имя контроллера")
    namespace: str = Field(..., description="Пространство имен")
    controller_type: str = Field(..., description="Тип контроллера (deployment или statefulset)")
    replicas: ReplicaInfo = Field(..., description="Информация о репликах")
    main_container: Optional[ContainerInfo] = Field(None, description="Информация о главном контейнере")
    labels: Dict[str, str] = Field(default_factory=dict, description="Метки")
    status: Optional[str] = Field(None, description="Статус контроллера")
    pods: Optional[List["PodInfo"]] = Field(None, description="Список подов контроллера")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных
        arbitrary_types_allowed = True  # Разрешаем произвольные типы


class ControllerList(BaseModel):
    """Модель для списка контроллеров (Deployments и StatefulSets)."""

    items: List[ControllerInfo] = Field(..., description="Список контроллеров")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


class PodList(BaseModel):
    """Модель для списка Pods."""

    items: List[PodInfo] = Field(..., description="Список Pods")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


class NamespaceList(BaseModel):
    """Модель для списка Namespaces."""

    items: List[NamespaceInfo] = Field(..., description="Список Namespaces")
    
    class Config:
        """Конфигурация модели."""
        extra = "ignore"  # Игнорировать лишние поля в данных


# Разрешаем циклические зависимости между моделями
try:
    PodInfo.update_forward_refs()
    DeploymentInfo.update_forward_refs()
    ControllerInfo.update_forward_refs()
except Exception as e:
    # В Pydantic v2 иногда может потребоваться другой подход
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Не удалось обновить forward refs: {str(e)}")
    # Для Pydantic v2 можно использовать model_rebuild
    try:
        from pydantic import model_rebuild
        model_rebuild(PodInfo)
        model_rebuild(DeploymentInfo)
        model_rebuild(ControllerInfo)
    except ImportError:
        pass
