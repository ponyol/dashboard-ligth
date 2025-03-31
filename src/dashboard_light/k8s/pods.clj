(ns dashboard-light.k8s.pods
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.core :refer [k8s-client]])
  (:import [io.kubernetes.client.openapi.apis CoreV1Api]
           [io.kubernetes.client.openapi.models V1PodList]))

(defn get-api
  "Получение экземпляра CoreV1Api"
  []
  (CoreV1Api. k8s-client))

(defn list-pods-for-namespace
  "Получение списка Pods в указанном пространстве имен"
  [namespace]
  (try
    (let [api (get-api)
          result (.listNamespacedPod api namespace nil nil nil nil nil nil nil nil nil)]
      (map (fn [item]
             (let [metadata (.getMetadata item)
                   spec (.getSpec item)
                   status (.getStatus item)
                   containers (.getContainers spec)]
               {:name (.getName metadata)
                :namespace (.getNamespace metadata)
                :phase (.getPhase status)
                :containers (map (fn [container]
                                   {:name (.getName container)
                                    :image (.getImage container)
                                    :image-tag (last (clojure.string/split (.getImage container) #":"))})
                                 containers)
                :owner-references (when-let [refs (.getOwnerReferences metadata)]
                                    (map (fn [ref]
                                           {:name (.getName ref)
                                            :kind (.getKind ref)
                                            :uid (.getUid ref)})
                                         refs))
                :pod-ip (.getPodIP status)
                :host-ip (.getHostIP status)
                :started-at (.getStartTime status)
                :labels (into {} (.getLabels metadata))}))
           (.getItems result)))
    (catch Exception e
      (log/error e "Ошибка получения списка Pods" {:namespace namespace})
      [])))

(defn list-deployment-pods
  "Получение списка Pods, принадлежащих указанному Deployment"
  [namespace deployment-name]
  (let [pods (list-pods-for-namespace namespace)]
    (filter (fn [pod]
              (some (fn [ref]
                      (and (= (:kind ref) "ReplicaSet")
                           (re-matches (re-pattern (str deployment-name "-[a-z0-9]+"))
                                       (:name ref))))
                    (:owner-references pod)))
            pods)))

(defn get-pod-status
  "Получение статуса Pod"
  [pod]
  (let [phase (:phase pod)]
    (case phase
      "Running" "running"
      "Succeeded" "succeeded"
      "Pending" "pending"
      "Failed" "failed"
      "Terminating" "terminating"
      "error")))
