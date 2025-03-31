(ns dashboard-light.ui.state
  (:require [clojure.tools.logging :as log]
            [dashboard-light.ui.focus :as focus]
            [dashboard-light.ui.compare :as compare]
            [dashboard-light.config.core :as config]))


(def initial-state
  {:selected-cluster nil
   :selected-namespaces []
   :sidebar-expanded true
   :theme "light"  ;; или "dark"
   :current-view "status"
   :deployments []
   :error nil
   :loading false
   :last-update-time nil
   :refresh-interval (config/get-in-config [:ui :refresh_interval_seconds] 15)
   :focus-mode-enabled false
   :focused-deployment-name nil
   :compare-mode-enabled false
   :compare-first-deployment nil
   :compare-second-deployment nil
   :comparison-result nil})

(defn update-theme
  "Обновление темы интерфейса"
  [state theme]
  (assoc state :theme theme))

(defn toggle-sidebar
  "Переключение состояния боковой панели"
  [state]
  (update state :sidebar-expanded not))

(defn set-view
  "Установка текущего вида"
  [state view]
  (assoc state :current-view view))

(defn set-loading
  "Установка состояния загрузки"
  [state loading?]
  (assoc state :loading loading?))

(defn set-error
  "Установка сообщения об ошибке"
  [state error]
  (assoc state :error error))

(defn update-deployments
  "Обновление списка Deployments"
  [state deployments]
  (-> state
      (assoc :deployments deployments)
      (assoc :last-update-time (java.util.Date.))
      (set-loading false)
      (set-error nil)))

(defn set-refresh-interval
  "Установка интервала обновления"
  [state interval]
  (assoc state :refresh-interval interval))

(defn select-cluster
  "Выбор кластера"
  [state cluster]
  (assoc state :selected-cluster cluster))

(defn select-namespaces
  "Выбор пространств имен"
  [state namespaces]
  (assoc state :selected-namespaces namespaces))

(defn toggle-deployment-focus
  "Переключение режима фокуса для Deployment"
  [state deployment-name]
  (focus/toggle-focus-mode state deployment-name))

(defn toggle-deployment-compare
  "Переключение режима сравнения для Deployment"
  [state deployment-name]
  (compare/toggle-compare-mode state deployment-name))

(defn update-comparison-result
  "Обновление результата сравнения"
  [state result]
  (assoc state :comparison-result result))
