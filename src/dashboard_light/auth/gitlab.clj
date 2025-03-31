(ns dashboard-light.auth.gitlab
  (:require [clojure.tools.logging :as log]
            [clj-http.client :as http]
            [clojure.data.json :as json]
            [ring.util.codec :as codec]
            [dashboard-light.config.core :as config]))

(defn get-oauth-config
  "Получение конфигурации OAuth для GitLab"
  []
  (let [gitlab-url (config/get-in-config [:auth :gitlab_url])
        client-id (config/get-in-config [:auth :client_id])
        client-secret-env (config/get-in-config [:auth :client_secret_env])
        client-secret (System/getenv client-secret-env)
        redirect-uri (config/get-in-config [:auth :redirect_uri])]
    {:authorization-uri (str gitlab-url "/oauth/authorize")
     :token-uri (str gitlab-url "/oauth/token")
     :client-id client-id
     :client-secret client-secret
     :redirect-uri redirect-uri
     :scope "read_user read_api"}))

(defn get-authorization-url
  "Получение URL для авторизации пользователя в GitLab"
  []
  (let [config (get-oauth-config)]
    (str (:authorization-uri config)
         "?client_id=" (codec/url-encode (:client-id config))
         "&redirect_uri=" (codec/url-encode (:redirect-uri config))
         "&response_type=code"
         "&scope=" (codec/url-encode (:scope config)))))

(defn exchange-code-for-token
  "Обмен кода авторизации на токен доступа"
  [code]
  (let [config (get-oauth-config)]
    (try
      (let [response (http/post (:token-uri config)
                              {:form-params {:client_id (:client-id config)
                                             :client_secret (:client-secret config)
                                             :code code
                                             :grant_type "authorization_code"
                                             :redirect_uri (:redirect-uri config)}
                               :as :json})]
        (:body response))
      (catch Exception e
        (log/error e "Ошибка получения токена доступа")
        nil))))

(defn get-user-info
  "Получение информации о пользователе из GitLab API"
  [token]
  (let [gitlab-url (config/get-in-config [:auth :gitlab_url])
        url (str gitlab-url "/api/v4/user")]
    (try
      (let [response (http/get url {:headers {"Authorization" (str "Bearer " (:access_token token))}
                                    :as :json})]
        (:body response))
      (catch Exception e
        (log/error e "Ошибка получения информации о пользователе")
        nil))))

(defn get-user-groups
  "Получение групп пользователя из GitLab API"
  [token]
  (let [gitlab-url (config/get-in-config [:auth :gitlab_url])
        url (str gitlab-url "/api/v4/groups")]
    (try
      (let [response (http/get url {:headers {"Authorization" (str "Bearer " (:access_token token))}
                                    :as :json})]
        (map :path (:body response)))
      (catch Exception e
        (log/error e "Ошибка получения групп пользователя")
        []))))

(defn assign-roles
  "Назначение ролей пользователю на основе его групп"
  [user-info user-groups]
  (let [roles-config (config/get-in-config [:auth :roles])
        user-roles (reduce (fn [acc [role-key role-config]]
                            (let [gitlab-groups (get role-config :gitlab_groups)
                                  has-any-group? (some #(contains? (set user-groups) %) gitlab-groups)]
                              (if has-any-group?
                                (conj acc (name role-key))
                                acc)))
                          #{}
                          roles-config)]
    (assoc user-info :roles user-roles)))
