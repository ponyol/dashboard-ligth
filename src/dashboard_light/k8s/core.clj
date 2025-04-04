(ns dashboard-light.k8s.core
  (:require [clojure.tools.logging :as log]
            [mount.core :refer [defstate]]
            [dashboard-light.config.core :as config])
  (:import [io.kubernetes.client.openapi ApiClient Configuration]
           [io.kubernetes.client.util Config ClientBuilder]
           [io.kubernetes.client.openapi.apis CoreV1Api]
           [java.nio.file Paths Files]
           [java.nio.charset StandardCharsets]))

(defn verify-k8s-auth
  "Проверка аутентификации с Kubernetes API"
  [client]
  (try
    (let [api (CoreV1Api. client)
          namespaces (.listNamespace api nil nil nil nil nil nil nil nil nil nil)]
      (log/info "Kubernetes API аутентификация успешна. Найдено неймспейсов:" (count (.getItems namespaces)))
      true)
    (catch Exception e
      (log/error e "Ошибка аутентификации с Kubernetes API")
      false)))

(defn create-mock-client
  "Создание мок-клиента для режима разработки"
  []
  (log/info "Используется MOCK-клиент Kubernetes")
  (let [client (ApiClient.)]
    (.setBasePath client "http://localhost:8080")
    client))

(defn read-token-from-file
  "Чтение токена сервисного аккаунта из файла"
  [path]
  (try
    (String. (Files/readAllBytes (Paths/get path (into-array String []))) StandardCharsets/UTF_8)
    (catch Exception e
      (log/error e "Не удалось прочитать токен из файла" path)
      nil)))

(defn create-k8s-client
  "Создание Kubernetes API клиента
   При запуске внутри кластера будет использовать serviceAccount,
   при запуске вне кластера - kubeconfig или переменные окружения"
  []
  (try
    (log/info "Инициализация Kubernetes API клиента...")
    (let [use-mock (Boolean/parseBoolean (or (System/getenv "K8S_MOCK") "false"))
          client (cond

                   use-mock
                   (do
                     (log/info "Используется MOCK-клиент Kubernetes")
                     (create-mock-client))


                   :else
                   (do
                     (log/info "Подключение к кластеру Kubernetes...")
                     (try

                       (let [cluster-client (Config/fromCluster)]
                         (log/info "Успешно создан клиент внутри кластера")

                         (when-not (verify-k8s-auth cluster-client)
                           (log/warn "Клиент создан, но аутентификация не удалась. Проверяем токен...")

                           (let [token-paths ["/var/run/secrets/kubernetes.io/serviceaccount/token"
                                              "/var/run/secrets/tokens/token"]
                                 token (some read-token-from-file token-paths)]
                             (when token
                               (log/info "Найден токен, устанавливаем аутентификацию вручную")
                               (.setBearerToken cluster-client token))))
                         cluster-client)
                       (catch Exception e
                         (log/info "Не удалось подключиться изнутри кластера:" (.getMessage e)
                                  "Пробуем локальную конфигурацию")

                         (Config/defaultClient)))))]

      (Configuration/setDefaultApiClient client)
      (log/info "Kubernetes API клиент создан успешно")
      client)
    (catch Exception e
      (log/error e "Ошибка создания Kubernetes API клиента")

      (let [client (create-mock-client)]
        (Configuration/setDefaultApiClient client)
        client))))

(defstate k8s-client
  :start (create-k8s-client)
  :stop nil)
