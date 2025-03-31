(ns dashboard-light.utils.core
  (:require [clojure.string :as str]
            [clojure.java.io :as io]
            [clojure.tools.logging :as log]))

(defn deep-merge
  "Глубокое объединение вложенных карт.
   Если ключи имеют карты в качестве значений, они рекурсивно объединяются.
   В противном случае значение из второй карты перезаписывает значение из первой."
  [& maps]
  (if (every? map? maps)
    (apply merge-with deep-merge maps)
    (last maps)))

(defn dissoc-in
  "Удаляет значение по пути ключей в карте."
  [m ks]
  (if (seq (butlast ks))
    (update-in m (vec (butlast ks)) dissoc (last ks))
    (dissoc m (first ks))))

(defn format-error
  "Форматирование информации об ошибке для логирования"
  [e context]
  (merge
   {:error-message (.getMessage e)
    :error-type (-> e class .getName)
    :stacktrace (->> (.getStackTrace e)
                     (map str)
                     (take 10)
                     (str/join "\n"))}
   context))

(defn parse-int
  "Безопасное преобразование строки в целое число"
  [s]
  (try
    (Integer/parseInt (str/trim s))
    (catch Exception _
      nil)))

(defn env-value
  "Получение значение из переменной окружения с поддержкой значения по умолчанию"
  ([env-name] (env-value env-name nil))
  ([env-name default]
   (or (System/getenv env-name) default)))

(defn parse-boolean
  "Преобразование строки в булево значение"
  [s]
  (when (string? s)
    (contains? #{"true" "yes" "1" "y" "t"} (str/lower-case (str/trim s)))))

(defn sanitize-filename
  "Очистка имени файла от недопустимых символов"
  [filename]
  (-> filename
      (str/replace #"[^a-zA-Z0-9\-_.]" "_")
      (str/replace #"_{2,}" "_")))

(defn human-readable-size
  "Преобразование размера в байтах в человеко-читаемый формат"
  [size]
  (let [units ["B" "KB" "MB" "GB" "TB"]
        unit (loop [n size
                    i 0]
               (if (or (< n 1024) (>= i (dec (count units))))
                 [n (nth units i)]
                 (recur (/ n 1024) (inc i))))]
    (format "%.2f %s" (first unit) (second unit))))
