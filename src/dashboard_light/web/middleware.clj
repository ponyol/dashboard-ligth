(ns dashboard-light.web.middleware
  (:require [clojure.tools.logging :as log]
            [dashboard-light.auth.core :as auth]
            [dashboard-light.config.core :as config]))


(defn auth-disabled?
  "Проверяет, отключена ли авторизация в режиме разработки"
  []
  (or

   (Boolean/parseBoolean (or (System/getenv "DISABLE_AUTH") "false"))

   (Boolean/parseBoolean (or (System/getProperty "DISABLE_AUTH") "false"))))


(def ^:dynamic *disable-auth* (auth-disabled?))

(defn wrap-auth
  "Middleware для проверки аутентификации пользователя"
  [handler]
  (fn [req]
    (let [uri (:uri req)

          public-paths ["/api/health" "/api/auth/login" "/api/auth/callback"]]

      (log/debug "Запрос:" uri "Авторизация отключена:" *disable-auth*)

      (if (or *disable-auth*                    ;; Режим разработки
              (some #(= uri %) public-paths)    ;; Публичные пути
              (auth/authenticated? req))        ;; Аутентифицированный пользователь
        (handler req)

        {:status 401
         :headers {"Content-Type" "application/json"}
         :body {:error "Unauthorized"}}))))

(defn wrap-logging
  "Middleware для логирования запросов"
  [handler]
  (fn [req]
    (let [method (:request-method req)
          uri (:uri req)]
      (log/debug "Request:" method uri)
      (let [response (handler req)]
        (log/debug "Response:" (:status response))
        response))))
