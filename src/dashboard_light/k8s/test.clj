(ns dashboard-light.k8s.test
  (:require [clojure.tools.logging :as log]
            [dashboard-light.k8s.namespaces :as namespaces]
            [dashboard-light.k8s.deployments :as deployments]
            [dashboard-light.k8s.pods :as pods]
            [dashboard-light.k8s.metrics :as metrics]
            [dashboard-light.config.core :as config]
            [dashboard-light.utils.logging :refer [with-timing-info]]))

(defn test-k8s-api
  "Тестирование работы Kubernetes API"
  []
  (with-timing-info "Тестирование Kubernetes API"
    (try
      (log/info "Начало тестирования Kubernetes API...")


      (let [all-namespaces (namespaces/list-namespaces)]
        (log/info "Получено неймспейсов:" (count all-namespaces))


        (let [patterns (config/get-in-config [:test :namespace_patterns] ["default" "kube-system"])
              filtered-namespaces (namespaces/filter-namespaces-by-pattern all-namespaces patterns)

              test-namespaces (take 2 filtered-namespaces)]
          (log/info "Тестируем неймспейсы:" (map :name test-namespaces))


          (doseq [ns test-namespaces]
            (let [ns-name (:name ns)
                  deployments (deployments/list-deployments-for-namespace ns-name)
                  pods (pods/list-pods-for-namespace ns-name)]
              (log/info "Неймспейс:" ns-name
                       "Deployments:" (count deployments)
                       "Pods:" (count pods))


              (when-let [first-deployment (first deployments)]
                (let [deployment-name (:name first-deployment)
                      deployment-pods (pods/list-deployment-pods ns-name deployment-name)]
                  (log/info "Деплоймент:" deployment-name
                           "Поды:" (count deployment-pods))


                  (doseq [pod (take 2 deployment-pods)]
                    (let [pod-name (:name pod)
                          pod-metrics (metrics/get-pod-metrics-by-name ns-name pod-name)]
                      (if pod-metrics
                        (let [usage (metrics/get-total-pod-resource-usage pod-metrics)]
                          (log/info "Под:" pod-name
                                   "CPU:" (:cpu-millicores usage) "millicores"
                                   "Memory:" (:memory-mb usage) "MB"))
                        (log/warn "Для пода" pod-name "метрики не найдены")))))))))

        (log/info "Тестирование Kubernetes API завершено успешно"))

      (catch Exception e
        (log/error e "Ошибка при тестировании Kubernetes API")))))

(defn test-k8s-caching
  "Тестирование кэширования API запросов"
  []
  (with-timing-info "Тестирование кэширования"
    (try
      (log/info "Начало тестирования кэширования...")


      (log/info "Первый запрос неймспейсов (данные из API)...")
      (let [first-call-start (System/currentTimeMillis)
            namespaces1 (namespaces/list-namespaces)
            first-call-time (- (System/currentTimeMillis) first-call-start)]
        (log/info "Первый запрос выполнен за" first-call-time "мс, получено" (count namespaces1) "неймспейсов")


        (log/info "Второй запрос неймспейсов (данные из кэша)...")
        (let [second-call-start (System/currentTimeMillis)
              namespaces2 (namespaces/list-namespaces)
              second-call-time (- (System/currentTimeMillis) second-call-start)]
          (log/info "Второй запрос выполнен за" second-call-time "мс, получено" (count namespaces2) "неймспейсов")


          (if (< second-call-time first-call-time)
            (log/info "Кэширование работает корректно! Ускорение:" (format "%.2f" (float (/ first-call-time second-call-time))) "раз")
            (log/warn "Кэширование возможно не работает, второй запрос не быстрее первого"))))

      (catch Exception e
        (log/error e "Ошибка при тестировании кэширования"))

      (finally
        (log/info "Тестирование кэширования завершено")))))
