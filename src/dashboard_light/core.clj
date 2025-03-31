(ns dashboard-light.core
  (:require [dashboard-light.config.core :as config]
            [dashboard-light.web.core :as web]
            [dashboard-light.k8s.core :as k8s]
            [dashboard-light.auth.core :as auth]
            [mount.core :as mount]
            [clojure.tools.logging :as log])
  (:gen-class))

(defn start-app
  "Запуск всех компонентов приложения"
  []
  (log/info "Запуск Dashboard-Light...")
  (let [components (if (System/getenv "SKIP_K8S")

                     (do
                       (log/info "K8s клиент пропущен (режим разработки)")
                       #{#'config/config #'web/http-server})

                     #{#'config/config #'k8s/k8s-client #'web/http-server})]
    (-> (mount/only components)
        (mount/start))))

(defn stop-app
  "Остановка всех компонентов приложения"
  []
  (log/info "Остановка Dashboard-Light...")
  (mount/stop))

(defn restart-app
  "Перезапуск приложения"
  []
  (stop-app)
  (start-app))

(defn -main
  "Точка входа для запуска приложения"
  [& args]
  (start-app)
  (.addShutdownHook (Runtime/getRuntime) (Thread. stop-app)))
