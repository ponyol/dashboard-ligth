(ns dashboard-light.k8s.metrics
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.core :refer [k8s-client]])
  (:import [io.kubernetes.client.openapi.apis CustomObjectsApi]))

(defn get-api
  "Получение экземпляра CustomObjectsApi"
  []
  (CustomObjectsApi. k8s-client))

(defn list-pod-metrics-for-namespace
  "Получение метрик Pod из Metrics Server для указанного пространства имен"
  [namespace]
  (try
    (let [api (get-api)
          metrics-group "metrics.k8s.io"
          metrics-version "v1beta1"
          metrics-plural "pods"
          result (.listNamespacedCustomObject api metrics-group metrics-version namespace metrics-plural nil nil nil nil nil nil nil)]

      (let [items (get result "items")]
        (map (fn [item]
               (let [metadata (get item "metadata")
                     containers (get-in item ["containers"])
                     usage (get-in (first containers) ["usage"])]
                 {:name (get metadata "name")
                  :namespace (get metadata "namespace")
                  :resource-usage {:cpu (get usage "cpu")
                                   :memory (get usage "memory")}
                  :timestamp (get metadata "timestamp")}))
             items)))
    (catch Exception e
      (log/error e "Ошибка получения метрик Pod" {:namespace namespace})
      [])))

(defn get-pod-metrics-by-name
  "Получение метрик для конкретного Pod по имени"
  [namespace pod-name]
  (let [metrics (list-pod-metrics-for-namespace namespace)]
    (first (filter #(= (:name %) pod-name) metrics))))
