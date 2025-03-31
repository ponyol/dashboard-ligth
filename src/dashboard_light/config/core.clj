(ns dashboard-light.config.core
  (:require [aero.core :as aero]
            [clojure.java.io :as io]
            [mount.core :refer [defstate]]
            [clojure.tools.logging :as log]
            [dashboard-light.config.schema :as schema]
            [clj-yaml.core :as yaml]))

(defn load-config-file
  "Загрузка конфигурации из файла"
  [config-path]
  (try
    (let [file (io/file config-path)]
      (if (.exists file)
        (yaml/parse-string (slurp file))
        (throw (ex-info (str "Файл конфигурации не найден: " config-path)
                        {:path config-path}))))
    (catch Exception e
      (log/error e "Ошибка загрузки конфигурации")
      (throw e))))

(defn load-config
  "Загрузка конфигурации с учетом переменных окружения"
  []
  (let [config-path (or (System/getenv "CONFIG_PATH") "resources/config.yaml")
        config (load-config-file config-path)]


    (log/info "Конфигурация загружена")
    config))


(defstate config
  :start (load-config)
  :stop nil)

(defn get-in-config
  "Получение значения из конфигурации по пути ключей с поддержкой значения по умолчанию"
  ([path] (get-in-config path nil))
  ([path default]
   (get-in config path default)))
