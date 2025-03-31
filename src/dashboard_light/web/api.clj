(ns dashboard-light.web.api
  (:require [ring.util.response :refer [response]]
            [dashboard-light.k8s.deployments :as k8s-deployments]
            [dashboard-light.k8s.pods :as k8s-pods]
            [dashboard-light.k8s.metrics :as k8s-metrics]
            [dashboard-light.auth.rbac :as rbac]
            [clojure.tools.logging :as log]))

(defn current-user
  "Получение информации о текущем пользователе"
  [req]
  (let [user (get-in req [:session :user])]
    (response {:user user})))

(defn filter-namespaces-by-access
  "Фильтрация неймспейсов по правам доступа пользователя"
  [req namespaces]
  (let [user (get-in req [:session :user])]
    (rbac/filter-allowed-namespaces user namespaces)))

(defn list-deployments
  "Получение списка Deployments с учетом фильтров"
  [req]
  (let [ns (get-in req [:params :namespace])]
    (if ns

      (let [deployments (k8s-deployments/list-deployments-for-namespace ns)]
        (response {:items deployments}))

      (let [namespaces ["default"] ;; TODO: Получать список всех неймспейсов
            allowed-ns (filter-namespaces-by-access req namespaces)
            deployments (k8s-deployments/list-deployments-multi-ns allowed-ns)]
        (response {:items deployments})))))

(defn get-deployment
  "Получение детальной информации о конкретном Deployment"
  [req namespace name]
  (let [deployments (k8s-deployments/list-deployments-for-namespace namespace)
        deployment (first (filter #(= (:name %) name) deployments))]
    (if deployment
      (let [pods (k8s-pods/list-deployment-pods namespace name)
            pod-metrics (mapv (fn [pod]
                               (assoc pod :metrics
                                      (k8s-metrics/get-pod-metrics-by-name namespace (:name pod))))
                             pods)]
        (response (assoc deployment :pods pod-metrics)))
      (response {:error "Deployment not found"} 404))))

(defn list-pods
  "Получение списка Pods с учетом фильтров"
  [req]
  (let [ns (get-in req [:params :namespace])]
    (if ns

      (let [pods (k8s-pods/list-pods-for-namespace ns)]
        (response {:items pods}))

      (let [namespaces ["default"] ;; TODO: Получать список всех неймспейсов
            allowed-ns (filter-namespaces-by-access req namespaces)
            pods (mapcat k8s-pods/list-pods-for-namespace allowed-ns)]
        (response {:items pods})))))
