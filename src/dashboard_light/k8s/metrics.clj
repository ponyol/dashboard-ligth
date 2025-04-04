(ns dashboard-light.k8s.metrics
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.core :refer [k8s-client]]
            [dashboard-light.k8s.cache :as cache])
  (:import [io.kubernetes.client.openapi.apis CustomObjectsApi]
           [java.time Instant]))

(defn get-api
  "Получение экземпляра CustomObjectsApi"
  []
  (CustomObjectsApi. k8s-client))

(defn parse-cpu-value
  "Преобразование значения CPU из формата Kubernetes (n, m, k, M, G)
   в миллиядра (millicores)"
  [cpu-str]
  (try
    (when cpu-str
      (cond

        (re-matches #"(\d+)m" cpu-str)
        (Integer/parseInt (second (re-matches #"(\d+)m" cpu-str)))


        (re-matches #"(\d+)" cpu-str)
        (* 1000 (Integer/parseInt (second (re-matches #"(\d+)" cpu-str))))


        (re-matches #"(\d+\.\d+)" cpu-str)
        (int (* 1000 (Double/parseDouble (second (re-matches #"(\d+\.\d+)" cpu-str)))))

        :else nil))
    (catch Exception e
      (log/warn "Не удалось преобразовать значение CPU:" cpu-str e)
      nil)))

(defn parse-memory-value
  "Преобразование значения памяти из формата Kubernetes (Ki, Mi, Gi)
   в мегабайты (MB)"
  [mem-str]
  (try
    (when mem-str
      (cond

        (re-matches #"(\d+)Mi" mem-str)
        (Integer/parseInt (second (re-matches #"(\d+)Mi" mem-str)))


        (re-matches #"(\d+)Gi" mem-str)
        (* 1024 (Integer/parseInt (second (re-matches #"(\d+)Gi" mem-str))))


        (re-matches #"(\d+)Ki" mem-str)
        (double (/ (Integer/parseInt (second (re-matches #"(\d+)Ki" mem-str))) 1024))


        (re-matches #"(\d+)M" mem-str)
        (Integer/parseInt (second (re-matches #"(\d+)M" mem-str)))


        (re-matches #"(\d+)G" mem-str)
        (* 1024 (Integer/parseInt (second (re-matches #"(\d+)G" mem-str))))


        (re-matches #"(\d+)" mem-str)
        (double (/ (Integer/parseInt (second (re-matches #"(\d+)" mem-str))) 1024 1024))

        :else nil))
    (catch Exception e
      (log/warn "Не удалось преобразовать значение памяти:" mem-str e)
      nil)))

(defn list-pod-metrics-for-namespace
  "Получение метрик Pod из Metrics Server для указанного пространства имен"
  [namespace]
  (cache/with-cache (str "metrics-" namespace)
    (try
      (log/debug (str "Получение метрик для неймспейса " namespace))
      (let [start-time (System/currentTimeMillis)
            api (get-api)
            metrics-group "metrics.k8s.io"
            metrics-version "v1beta1"
            metrics-plural "pods"
            result (.listNamespacedCustomObject api metrics-group metrics-version namespace metrics-plural
                                               nil nil nil nil nil nil nil)]

        (let [items (get result "items")
              metrics-data (map (fn [item]
                                 (let [metadata (get item "metadata")
                                       containers (get-in item ["containers"])]
                                   {:name (get metadata "name")
                                    :namespace (get metadata "namespace")
                                    :timestamp (get metadata "timestamp")
                                    :containers (map (fn [container]
                                                       (let [name (get container "name")
                                                             usage (get container "usage")]
                                                         {:name name
                                                          :resource-usage {:cpu (get usage "cpu")
                                                                           :memory (get usage "memory")
                                                                           :cpu-millicores (parse-cpu-value (get usage "cpu"))
                                                                           :memory-mb (parse-memory-value (get usage "memory"))}}))
                                                     containers)}))
                               items)
              duration (- (System/currentTimeMillis) start-time)]

          (log/debug (str "Получение метрик для неймспейса " namespace " выполнено за " duration " мс"))
          metrics-data))
      (catch Exception e
        (log/error e "Ошибка получения метрик Pod" {:namespace namespace})
        []))))

(defn get-pod-metrics-by-name
  "Получение метрик для конкретного Pod по имени"
  [namespace pod-name]
  (try
    (let [metrics (list-pod-metrics-for-namespace namespace)
          pod-metrics (first (filter #(= (:name %) pod-name) metrics))]
      (when pod-metrics
        (let [timestamp (:timestamp pod-metrics)
              now (str (Instant/now))
              age-seconds (when timestamp
                            (try
                              (/ (- (.toEpochMilli (Instant/parse now))
                                    (.toEpochMilli (Instant/parse timestamp)))
                                 1000)
                              (catch Exception _ nil)))]
          (cond-> pod-metrics
            age-seconds (assoc :age-seconds age-seconds)))))
    (catch Exception e
      (log/error e "Ошибка получения метрик для пода" {:namespace namespace :pod-name pod-name})
      nil)))

(defn get-total-pod-resource-usage
  "Получение суммарного использования ресурсов для пода"
  [pod-metrics]
  (when pod-metrics
    (let [containers (:containers pod-metrics)
          cpu-total (reduce + 0 (keep #(get-in % [:resource-usage :cpu-millicores]) containers))
          memory-total (reduce + 0 (keep #(get-in % [:resource-usage :memory-mb]) containers))]
      {:cpu-millicores cpu-total
       :memory-mb memory-total})))
