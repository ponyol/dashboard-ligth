(ns dashboard-light.auth.rbac
  (:require [clojure.tools.logging :as log]
            [dashboard-light.config.core :as config]))

(defn get-user-permissions
  "Получение прав доступа пользователя на основе его ролей"
  [user]
  (let [roles (set (:roles user))
        permissions-config (config/get-in-config [:auth :permissions])

        permissions (reduce (fn [acc role]
                              (let [role-perms (get permissions-config (keyword role))]
                                (if role-perms
                                  (merge-with concat acc role-perms)
                                  acc)))
                            {:menu_items []
                             :allowed_namespace_patterns []
                             :allowed_clusters []}
                            roles)]
    permissions))

(defn has-access-to-menu-item?
  "Проверка доступа пользователя к пункту меню"
  [user menu-item]
  (let [permissions (get-user-permissions user)
        allowed-items (set (:menu_items permissions))]
    (or (contains? allowed-items menu-item)
        (contains? allowed-items "*"))))

(defn has-access-to-namespace?
  "Проверка доступа пользователя к неймспейсу"
  [user namespace]
  (let [permissions (get-user-permissions user)
        patterns (:allowed_namespace_patterns permissions)]
    (some (fn [pattern]
            (re-matches (re-pattern pattern) namespace))
          patterns)))

(defn has-access-to-cluster?
  "Проверка доступа пользователя к кластеру"
  [user cluster]
  (let [permissions (get-user-permissions user)
        allowed-clusters (set (:allowed_clusters permissions))]
    (or (contains? allowed-clusters cluster)
        (contains? allowed-clusters "*"))))

(defn filter-allowed-namespaces
  "Фильтрация неймспейсов, к которым пользователь имеет доступ"
  [user namespaces]
  (filter (partial has-access-to-namespace? user) namespaces))

(defn filter-allowed-clusters
  "Фильтрация кластеров, к которым пользователь имеет доступ"
  [user clusters]
  (filter (partial has-access-to-cluster? user) clusters))
