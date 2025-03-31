(ns dashboard-light.ui.focus
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.deployments :as deployments]
            [dashboard-light.k8s.pods :as pods]))

(defn focus-mode-data
  "Подготовка данных для режима фокуса
   В этом режиме выбранный Deployment выделяется,
   а другие становятся полупрозрачными"
  [namespace deployment-name]
  (let [all-deployments (deployments/list-deployments-for-namespace namespace)
        focused-deployment (first (filter #(= (:name %) deployment-name) all-deployments))
        pods (when focused-deployment
               (pods/list-deployment-pods namespace deployment-name))]
    {:focused-deployment focused-deployment
     :other-deployments (filter #(not= (:name %) deployment-name) all-deployments)
     :pods pods}))

(defn calculate-focus-opacity
  "Расчёт непрозрачности для элементов вне фокуса
   По умолчанию элементы вне фокуса показываются с непрозрачностью 0.3"
  [in-focus?]
  (if in-focus? 1.0 0.3))

(defn toggle-focus-mode
  "Переключение режима фокуса"
  [current-state deployment-name]
  (if (= (:focused-deployment-name current-state) deployment-name)

    (dissoc current-state :focused-deployment-name :focus-mode-enabled)

    (assoc current-state
           :focused-deployment-name deployment-name
           :focus-mode-enabled true)))
