(ns dashboard-light.config.schema
  (:require [clojure.spec.alpha :as s]))




(s/def ::client-id string?)
(s/def ::client-secret-env string?)
(s/def ::redirect-uri string?)
(s/def ::gitlab-url string?)

(s/def ::gitlab-group string?)
(s/def ::gitlab-groups (s/coll-of ::gitlab-group))

(s/def ::menu-item string?)
(s/def ::menu-items (s/coll-of ::menu-item))
(s/def ::allowed-namespace-pattern string?)
(s/def ::allowed-namespace-patterns (s/coll-of ::allowed-namespace-pattern))
(s/def ::allowed-cluster string?)
(s/def ::allowed-clusters (s/coll-of ::allowed-cluster))

(s/def ::role-permissions
  (s/keys :req-un [::menu-items ::allowed-namespace-patterns ::allowed-clusters]))

(s/def ::role-name keyword?)
(s/def ::permissions (s/map-of ::role-name ::role-permissions))

(s/def ::role-gitlab-groups
  (s/keys :req-un [::gitlab-groups]))

(s/def ::roles (s/map-of ::role-name ::role-gitlab-groups))

(s/def ::allow-anonymous-access boolean?)
(s/def ::anonymous-role string?)

(s/def ::auth
  (s/keys :req-un [::provider ::gitlab-url ::client-id ::client-secret-env ::redirect-uri ::roles ::permissions]
          :opt-un [::allow-anonymous-access ::anonymous-role]))

(s/def ::config
  (s/keys :req-un [::auth]
          :opt-un [;; Другие секции конфигурации
                   ]))

(defn validate-config
  "Валидация конфигурации по схеме"
  [config]
  (when-not (s/valid? ::config config)
    (throw (ex-info "Некорректная конфигурация"
                    {:explain (s/explain-str ::config config)})))
  config)
