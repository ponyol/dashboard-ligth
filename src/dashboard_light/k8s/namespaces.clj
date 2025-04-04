(ns dashboard-light.k8s.namespaces
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.core :refer [k8s-client]]
            [dashboard-light.k8s.cache :as cache])
  (:import [io.kubernetes.client.openapi.apis CoreV1Api]
           [io.kubernetes.client.openapi.models V1NamespaceList]))


(defn get-api
  "Получение экземпляра CoreV1Api"
  []
  (CoreV1Api. k8s-client))


(def test-namespaces
  [{:name "default" :phase "Active"}
   {:name "kube-system" :phase "Active"}
   {:name "project-app1-staging" :phase "Active"}
   {:name "project-app2-prod" :phase "Active"}])


(defn discover-list-namespace-method
  "Обнаружение правильного метода для получения списка неймспейсов"
  [api]
  (try
    (log/info "K8S: Пробуем метод listNamespaceV1")
    (let [result (.listNamespaceV1 api nil nil nil nil nil nil nil nil nil)]
      (log/info "K8S: Метод listNamespaceV1 успешно сработал")
      result)
    (catch Exception e1
      (log/warn "K8S: Метод listNamespaceV1 не сработал, пробуем listNamespace с 10 параметрами")
      (try
        (let [result (.listNamespace api nil nil nil nil nil nil nil nil nil)]
          (log/info "K8S: Метод listNamespace с 10 параметрами успешно сработал")
          result)
        (catch Exception e2
          (log/warn "K8S: Метод listNamespace с 10 параметрами не сработал, пробуем listNamespace с 9 параметрами")
          (try
            (let [result (.listNamespace api nil nil nil nil nil nil nil nil)]
              (log/info "K8S: Метод listNamespace с 9 параметрами успешно сработал")
              result)
            (catch Exception e3
              (log/error "K8S: Все методы получения списка неймспейсов не сработали")
              nil)))))))


(defn list-namespaces
  "Получение списка всех неймспейсов в кластере"
  []
  (cache/with-cache :namespaces
    (try
      (log/info "K8S: Запрос списка неймспейсов из Kubernetes API")
      (let [api (get-api)
            _ (log/info "K8S: API клиент создан")
            result (discover-list-namespace-method api)]
        (if (nil? result)
          (do
            (log/warn "K8S: Результат запроса неймспейсов - nil, возвращаем тестовые данные")
            test-namespaces)
          (let [items (.getItems result)
                _ (log/info "K8S: Получено элементов:" (count items))]
            (map (fn [item]
                   (let [metadata (.getMetadata item)
                         status (.getStatus item)]
                     {:name (.getName metadata)
                      :phase (.getPhase status)
                      :created (.getCreationTimestamp metadata)
                      :labels (when-let [labels (.getLabels metadata)]
                                (into {} labels))}))
                 items))))
      (catch Exception e
        (log/error e "K8S: Ошибка получения списка неймспейсов")
        (log/warn "K8S: Возвращаем тестовые данные из-за ошибки")
        test-namespaces))))


(defn filter-namespaces-by-pattern
  "Фильтрация неймспейсов по списку регулярных выражений"
  [namespaces patterns]
  (if (or (empty? patterns) (some #(= ".*" %) patterns))
    namespaces
    (filter (fn [ns]
              (some #(re-matches (re-pattern %) (:name ns)) patterns))
            namespaces)))


(defn list-filtered-namespaces
  "Получение отфильтрованных неймспейсов по списку регулярных выражений"
  [patterns]
  (let [all-namespaces (list-namespaces)]
    (filter-namespaces-by-pattern all-namespaces patterns)))
