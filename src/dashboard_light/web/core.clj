(ns dashboard-light.web.core
  (:require [ring.adapter.jetty :as jetty]
            [ring.middleware.json :refer [wrap-json-response wrap-json-body]]
            [ring.middleware.params :refer [wrap-params]]
            [ring.middleware.keyword-params :refer [wrap-keyword-params]]
            [ring.middleware.session :refer [wrap-session]]
            [dashboard-light.web.routes :refer [app-routes]]
            [dashboard-light.web.middleware :as middleware]
            [dashboard-light.config.core :as config]
            [mount.core :refer [defstate]]
            [clojure.tools.logging :as log]))

(defn create-app
  "Создание Ring приложения с набором middleware"
  []
  (-> app-routes
      (middleware/wrap-auth)
      (wrap-json-body {:keywords? true})
      (wrap-json-response)
      (wrap-keyword-params)
      (wrap-params)
      (wrap-session)))

(defn start-server
  "Запуск HTTP сервера"
  []
  (let [port (Integer/parseInt (or (System/getenv "PORT") "3000"))]
    (log/info "Запуск HTTP сервера на порту" port)
    (jetty/run-jetty (create-app) {:port port
                                   :join? false})))

(defstate http-server
  :start (start-server)
  :stop (.stop http-server))
