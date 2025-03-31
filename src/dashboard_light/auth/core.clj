(ns dashboard-light.auth.core
  (:require [clojure.tools.logging :as log]
            [ring.util.response :refer [redirect]]
            [dashboard-light.config.core :as config]
            [dashboard-light.auth.gitlab :as gitlab]))


(def dev-user
  {:id 1
   :username "dev-user"
   :name "Developer"
   :email "dev@example.com"
   :roles #{"admin"}})


(defn auth-disabled?
  "Проверяет, отключена ли авторизация в режиме разработки"
  []
  (or

   (Boolean/parseBoolean (or (System/getenv "DISABLE_AUTH") "false"))

   (Boolean/parseBoolean (or (System/getProperty "DISABLE_AUTH") "false"))))

(defn authenticated?
  "Проверка, аутентифицирован ли пользователь"
  [req]
  (let [disable-auth (auth-disabled?)
        allow-anonymous (config/get-in-config [:auth :allow_anonymous_access] false)]
    (log/debug "Проверка аутентификации: disable-auth=" disable-auth
               ", allow-anonymous=" allow-anonymous
               ", session-user=" (get-in req [:session :user]))

    (or disable-auth
        allow-anonymous
        (some? (get-in req [:session :user])))))

(defn login-handler
  "Обработчик для перенаправления на страницу логина GitLab"
  []
  (let [disable-auth (auth-disabled?)]
    (if disable-auth

      (-> (redirect "/")
          (assoc :session {:user dev-user}))

      (let [auth-url (gitlab/get-authorization-url)]
        (redirect auth-url)))))

(defn callback-handler
  "Обработчик для OAuth callback от GitLab"
  [req]
  (let [disable-auth (auth-disabled?)
        code (get-in req [:params :code])
        session (:session req)]
    (if disable-auth

      (-> (redirect "/")
          (assoc :session {:user dev-user}))

      (if code
        (let [token (gitlab/exchange-code-for-token code)
              user-info (gitlab/get-user-info token)
              user-groups (gitlab/get-user-groups token)
              user-with-roles (gitlab/assign-roles user-info user-groups)
              session (assoc session :user user-with-roles :token token)]
          (-> (redirect "/")
              (assoc :session session)))
        (-> (redirect "/login?error=invalid_code")
            (assoc :session session))))))

(defn logout-handler
  "Обработчик для выхода из системы"
  []
  (-> (redirect "/")
      (assoc :session nil)))
