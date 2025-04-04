(ns dashboard-light.k8s.cache
  (:require [clojure.tools.logging :as log]
            [dashboard-light.config.core :as config]
            [mount.core :refer [defstate]])
  (:import [java.util.concurrent ConcurrentHashMap]
           [java.time Instant]))


(defonce cache-store (ConcurrentHashMap.))


(def default-ttl-seconds 30)

(defn get-cache-ttl
  "Получение TTL для кэша из конфигурации или значения по умолчанию"
  [cache-key]
  (let [path [:cache :ttl (keyword cache-key)]]
    (or (config/get-in-config path)
        (config/get-in-config [:cache :default_ttl])
        default-ttl-seconds)))

(defn cache-get
  "Получение значения из кэша с проверкой его актуальности"
  [cache-key]
  (let [cached-item (.get cache-store cache-key)]
    (when cached-item
      (let [ttl (get-cache-ttl cache-key)
            current-time (Instant/now)
            update-time (:update-time cached-item)
            age-seconds (.getSeconds (java.time.Duration/between update-time current-time))]
        (if (< age-seconds ttl)
          (:value cached-item)
          (do
            (log/debug "Кэш устарел:" cache-key "возраст:" age-seconds "сек")
            nil))))))

(defn cache-put
  "Сохранение значения в кэше с текущим временем"
  [cache-key value]
  (.put cache-store cache-key {:value value
                               :update-time (Instant/now)})
  value)

(defmacro with-cache
  "Макрос для получения данных с использованием кэширования"
  [cache-key & body]
  `(let [key-str# (name ~cache-key)
         cached# (cache-get key-str#)]
     (if cached#
       (do
         (log/debug "Используются кэшированные данные для:" key-str#)
         cached#)
       (let [result# (do ~@body)]
         (log/debug "Обновление кэша для:" key-str#)
         (cache-put key-str# result#)))))

(defn invalidate-cache
  "Инвалидация кэша для указанного ключа"
  [cache-key]
  (.remove cache-store (name cache-key)))

(defn invalidate-all
  "Полная инвалидация кэша"
  []
  (.clear cache-store))


(defstate cache-config
  :start (do
           (log/info "Инициализация конфигурации кэша")
           (let [default-ttl (config/get-in-config [:cache :default_ttl] default-ttl-seconds)]
             (log/info "Время жизни кэша по умолчанию:" default-ttl "сек")
             {:default-ttl default-ttl}))
  :stop (do
          (log/info "Очистка кэша")
          (invalidate-all)))
