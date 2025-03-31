(ns dashboard-light.k8s.deployments
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.core :refer [k8s-client]])
  (:import [io.kubernetes.client.openapi.apis AppsV1Api]
           [io.kubernetes.client.openapi.models V1DeploymentList]))

(defn get-api
  "Получение экземпляра AppsV1Api"
  []
  (AppsV1Api. k8s-client))

(defn list-deployments-for-namespace
  "Получение списка Deployments в указанном пространстве имен"
  [namespace]
  (try
    (let [api (get-api)
          result (.listNamespacedDeployment api namespace nil nil nil nil nil nil nil nil nil)]
      (map (fn [item]
             (let [metadata (.getMetadata item)
                   spec (.getSpec item)
                   status (.getStatus item)
                   containers (-> spec .getTemplate .getSpec .getContainers)
                   main-container (first containers)]
               {:name (.getName metadata)
                :namespace (.getNamespace metadata)
                :replicas {:desired (-> spec .getReplicas)
                           :ready (-> status .getReadyReplicas)
                           :available (-> status .getAvailableReplicas)
                           :updated (-> status .getUpdatedReplicas)}
                :main-container {:name (-> main-container .getName)
                                 :image (-> main-container .getImage)
                                 :image-tag (last (clojure.string/split (-> main-container .getImage) #":"))}
                :labels (into {} (.getLabels metadata))}))
           (.getItems result)))
    (catch Exception e
      (log/error e "Ошибка получения списка Deployments" {:namespace namespace})
      [])))

(defn list-deployments-multi-ns
  "Получение списка Deployments для нескольких пространств имен"
  [namespaces]
  (mapcat list-deployments-for-namespace namespaces))

(defn get-deployment-status
  "Определение статуса Deployment на основе его параметров"
  [deployment]
  (let [desired (get-in deployment [:replicas :desired])
        ready (get-in deployment [:replicas :ready])]
    (cond
      (nil? desired) "error"
      (zero? desired) "scaled_zero"
      (= ready desired) "healthy"
      :else "progressing")))
