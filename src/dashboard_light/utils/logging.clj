(ns dashboard-light.utils.logging
  (:require [clojure.tools.logging :as log]
            [clojure.string :as str]
            [dashboard-light.config.core :as config])
  (:import [ch.qos.logback.classic Logger Level]
           [org.slf4j LoggerFactory]))

(defn set-root-logger-level!
  "Установка уровня логирования для корневого логгера"
  [level-name]
  (let [root-logger (LoggerFactory/getLogger Logger/ROOT_LOGGER_NAME)
        level (case (keyword (str/lower-case (name level-name)))
                :debug Level/DEBUG
                :info Level/INFO
                :warn Level/WARN
                :error Level/ERROR
                :trace Level/TRACE

                Level/INFO)]
    (.setLevel root-logger level)
    (log/info "Уровень логирования установлен:" (.toString level))))

(defn set-logger-level!
  "Установка уровня логирования для конкретного логгера"
  [logger-name level-name]
  (let [logger (LoggerFactory/getLogger logger-name)
        level (case (keyword (str/lower-case (name level-name)))
                :debug Level/DEBUG
                :info Level/INFO
                :warn Level/WARN
                :error Level/ERROR
                :trace Level/TRACE

                Level/INFO)]
    (.setLevel logger level)
    (log/info "Уровень логирования для" logger-name "установлен:" (.toString level))))

(defn configure-logging!
  "Настройка логирования на основе конфигурации"
  []
  (try
    (let [log-level (or (System/getenv "LOG_LEVEL")
                         (config/get-in-config [:logging :level] "info"))]
      (set-root-logger-level! log-level)


      (when-let [loggers (config/get-in-config [:logging :loggers])]
        (doseq [[logger-name level] loggers]
          (set-logger-level! (name logger-name) level))))
    (catch Exception e
      (log/error "Ошибка при настройке логирования:" (.getMessage e)))))

(defmacro with-timing
  "Макрос для измерения времени выполнения блока кода и логирования результата"
  [level msg & body]
  `(let [start# (System/currentTimeMillis)
         result# (do ~@body)
         duration# (- (System/currentTimeMillis) start#)]
     (log/log ~level (format "%s (выполнено за %d мс)" ~msg duration#))
     result#))


(defmacro with-timing-debug [msg & body] `(with-timing :debug ~msg ~@body))
(defmacro with-timing-info [msg & body] `(with-timing :info ~msg ~@body))

(defmacro with-error-logging
  "Макрос для выполнения кода с логированием возможных ошибок"
  [context & body]
  `(try
     ~@body
     (catch Exception e#
       (log/error e# (str "Ошибка: " ~context))
       (throw e#))))
