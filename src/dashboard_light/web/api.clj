(ns dashboard-light.web.api
  (:require [ring.util.response :refer [response]]
            [dashboard-light.k8s.deployments :as k8s-deployments]
            [dashboard-light.k8s.pods :as k8s-pods]
            [dashboard-light.k8s.metrics :as k8s-metrics]
            [dashboard-light.k8s.namespaces :as k8s-namespaces]
            [dashboard-light.k8s.cache :as k8s-cache]
            [dashboard-light.auth.rbac :as rbac]
            [dashboard-light.utils.logging :refer [with-timing-info]]
            [clojure.tools.logging :as log]))

(defn current-user
  "Получение информации о текущем пользователе"
  [req]
  (let [user (get-in req [:session :user])]
    (response {:user user})))

(defn filter-namespaces-by-access
  "Фильтрация неймспейсов по правам доступа пользователя"
  [req namespaces]
  (let [user (get-in req [:session :user])
        _ (log/info "RBAC: Пользователь:" (if user (str (:username user) ", роли: " (:roles user)) "не аутентифицирован"))
        _ (log/info "RBAC: Доступны неймспейсы до фильтрации:" (count namespaces) namespaces)
        allowed (if user
                  (rbac/filter-allowed-namespaces user namespaces)

                  namespaces)]
    (log/info "RBAC: Доступны неймспейсы после фильтрации:" (count allowed) allowed)
    allowed))

(defn list-deployments
  "Получение списка Deployments с учетом фильтров"
  [req]
  (let [ns (get-in req [:params :namespace])]
    (if ns
      (let [deployments (k8s-deployments/list-deployments-for-namespace ns)]
        (response {:items deployments}))
      (with-timing-info "Получение и фильтрация неймспейсов"
        (let [all-namespaces (k8s-namespaces/list-namespaces)
              namespaces (map :name all-namespaces)
              allowed-ns (filter-namespaces-by-access req namespaces)
              deployments (k8s-deployments/list-deployments-multi-ns allowed-ns)]
          (response {:items deployments}))))))

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
      (with-timing-info "Получение и фильтрация подов"
        (let [all-namespaces (k8s-namespaces/list-namespaces)
              namespaces (map :name all-namespaces)
              allowed-ns (filter-namespaces-by-access req namespaces)
              pods (mapcat k8s-pods/list-pods-for-namespace allowed-ns)]
          (response {:items pods}))))))

(defn list-namespaces
  "Получение списка доступных неймспейсов с учётом RBAC"
  [req]
  (with-timing-info "Получение доступных неймспейсов"
    (try
      (log/info "API: Получение списка неймспейсов")


      (k8s-cache/invalidate-cache "namespaces")
      (log/info "API: Кэш неймспейсов очищен")

      (let [all-namespaces (k8s-namespaces/list-namespaces)]
        (log/info "API: Получено неймспейсов из K8s:" (count all-namespaces))
        (if (empty? all-namespaces)
          (do
            (log/warn "API: Список неймспейсов пуст! Возможно проблема с подключением к Kubernetes API")

            (let [mock-namespaces [{:name "default" :phase "Active"}
                                   {:name "kube-system" :phase "Active"}
                                   {:name "project-app1-staging" :phase "Active"}
                                   {:name "project-app2-staging" :phase "Active"}]]
              (log/info "API: Возвращаем мок-данные для разработки:" (map :name mock-namespaces))
              (response {:items mock-namespaces})))

          (let [namespaces (map :name all-namespaces)
                _ (log/info "API: Имена неймспейсов:" namespaces)
                allowed-namespaces (filter-namespaces-by-access req namespaces)]
            (log/info "API: После фильтрации осталось:" (count allowed-namespaces))
            (response {:items (map (fn [ns-name]
                                     (let [ns-data (first (filter #(= (:name %) ns-name) all-namespaces))]
                                       (or ns-data {:name ns-name})))
                                   allowed-namespaces)}))))
      (catch Exception e
        (log/error e "API: Ошибка при получении списка неймспейсов")
        (let [mock-namespaces [{:name "default-mock" :phase "Active"}
                               {:name "kube-system-mock" :phase "Active"}
                               {:name "project-mock-staging" :phase "Active"}]]
          (log/info "API: Возвращаем мок-данные из-за ошибки")
          (response {:items mock-namespaces
                     :error (.getMessage e)}))))))

(defn test-cache
  "Тестирование работы кэша"
  [req]
  (try
    (k8s-cache/invalidate-all)
    (log/info "Кэш очищен")


    (let [start-time (System/currentTimeMillis)
          namespaces1 (k8s-namespaces/list-namespaces)
          first-call-time (- (System/currentTimeMillis) start-time)]
      (log/info "Первый вызов занял:" first-call-time "мс, получено:" (count namespaces1) "неймспейсов")


      (let [start-time2 (System/currentTimeMillis)
            namespaces2 (k8s-namespaces/list-namespaces)
            second-call-time (- (System/currentTimeMillis) start-time2)]
        (log/info "Второй вызов занял:" second-call-time "мс, получено:" (count namespaces2) "неймспейсов")

        (response {:status "ok"
                   :first_call_time_ms first-call-time
                   :second_call_time_ms second-call-time
                   :speed_improvement (format "%.2f" (float (/ first-call-time (max 1 second-call-time))))
                   :namespaces_count (count namespaces2)})))
    (catch Exception e
      (log/error e "Ошибка при тестировании кэша")
      (response {:status "error"
                 :message (.getMessage e)})
      )))
