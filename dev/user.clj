(ns user
  (:require [clojure.tools.namespace.repl :refer [refresh refresh-all]]
            [dashboard-light.core :as app]
            [mount.core :as mount]))

(defn start
  "Запуск системы для разработки"
  []
  (app/start-app))

(defn stop
  "Остановка системы"
  []
  (app/stop-app))

(defn restart
  "Перезапуск системы с перезагрузкой измененных файлов"
  []
  (stop)
  (refresh :after 'user/start))


(comment
  (start)    ;; Запуск системы
  (stop)     ;; Остановка системы
  (restart)  ;; Перезапуск с обновлением кода
  (refresh)  ;; Только перезагрузка кода
  (refresh-all) ;; Полная перезагрузка всех неймспейсов
  )
