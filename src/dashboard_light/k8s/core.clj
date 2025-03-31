(ns dashboard-light.k8s.core
  (:require [clojure.tools.logging :as log]
            [mount.core :refer [defstate]]
            [dashboard-light.config.core :as config])
  (:import [io.kubernetes.client.openapi ApiClient Configuration]
           [io.kubernetes.client.util Config]))

(defn create-mock-client
  "Создание мок-клиента для режима разработки"
  []
  (log/info "Используется MOCK-клиент Kubernetes")
  (let [client (ApiClient.)]
    (.setBasePath client "http://localhost:8080")
    client))

(defn create-k8s-client
  "Создание Kubernetes API клиента"
  []
  (try
    (log/info "Инициализация Kubernetes API клиента...")


    (let [client (if (System/getenv "K8S_MOCK")
                   (create-mock-client)
                   (do
                     (log/info "Подключение к реальному K8s кластеру...")
                     (Config/defaultClient)))]


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
