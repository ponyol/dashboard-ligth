(ns dashboard-light.ui.compare
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.deployments :as deployments]
            [dashboard-light.k8s.pods :as pods]
            [dashboard-light.k8s.metrics :as metrics]))

(defn get-deployment-details
  "Получение полной информации о Deployment для сравнения"
  [namespace deployment-name]
  (let [deployments (deployments/list-deployments-for-namespace namespace)
        deployment (first (filter #(= (:name %) deployment-name) deployments))]
    (when deployment
      (let [pods (pods/list-deployment-pods namespace deployment-name)
            pod-metrics (mapv (fn [pod]
                               (assoc pod :metrics
                                      (metrics/get-pod-metrics-by-name namespace (:name pod))))
                             pods)]
        (assoc deployment :pods pod-metrics)))))

(defn compare-deployments
  "Сравнение двух Deployment'ов и выявление различий"
  [deployment1 deployment2]
  (when (and deployment1 deployment2)
    {:replicas {:deployment1 (get-in deployment1 [:replicas])
                :deployment2 (get-in deployment2 [:replicas])
                :diff {:desired (not= (get-in deployment1 [:replicas :desired])
                                     (get-in deployment2 [:replicas :desired]))
                       :ready (not= (get-in deployment1 [:replicas :ready])
                                   (get-in deployment2 [:replicas :ready]))}}
     :containers {:deployment1 (get-in deployment1 [:main-container])
                  :deployment2 (get-in deployment2 [:main-container])
                  :diff {:image-tag (not= (get-in deployment1 [:main-container :image-tag])
                                         (get-in deployment2 [:main-container :image-tag]))}}
     :pods {:deployment1 (count (:pods deployment1))
            :deployment2 (count (:pods deployment2))}}))

(defn toggle-compare-mode
  "Переключение режима сравнения"
  [current-state deployment-name]
  (cond

    (not (:compare-mode-enabled current-state))
    (assoc current-state
           :compare-first-deployment deployment-name
           :compare-mode-enabled true
           :compare-second-deployment nil
           :comparison-result nil)


    (and (:compare-first-deployment current-state)
         (nil? (:compare-second-deployment current-state)))
    (if (= (:compare-first-deployment current-state) deployment-name)

      (dissoc current-state :compare-first-deployment :compare-mode-enabled)

      (assoc current-state :compare-second-deployment deployment-name))


    :else
    (if (= deployment-name
           (or (:compare-first-deployment current-state)
               (:compare-second-deployment current-state)))

      (dissoc current-state :compare-first-deployment
              :compare-second-deployment
              :compare-mode-enabled
              :comparison-result)

      (assoc current-state :compare-second-deployment deployment-name))))
