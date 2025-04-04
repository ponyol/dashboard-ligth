(ns dashboard-light.web.routes
  (:require [compojure.core :refer :all]
            [compojure.route :as route]
            [ring.util.response :refer [response redirect content-type resource-response]]
            [dashboard-light.web.api :as api]
            [dashboard-light.auth.core :as auth]
            [dashboard-light.k8s.test :as k8s-test]
            [clojure.tools.logging :as log]))

(defroutes app-routes

  (context "/api" []
    (GET "/health" [] (response {:status "ok"}))

    (context "/auth" []
      (GET "/login" [] (auth/login-handler))
      (GET "/callback" req (auth/callback-handler req))
      (GET "/logout" [] (auth/logout-handler))
      (GET "/user" req (api/current-user req)))

    (context "/k8s" []
      (GET "/namespaces" req (api/list-namespaces req))
      (GET "/deployments" req (api/list-deployments req))
      (GET "/deployments/:namespace/:name" [namespace name :as req]
           (api/get-deployment req namespace name))
      (GET "/pods" req (api/list-pods req))
      (GET "/test" []
           (k8s-test/test-k8s-api)
           (response {:status "ok" :message "Тест выполнен, смотрите логи"}))
      (GET "/test-cache" req
           (api/test-cache req))))


  (GET "/" []
       (-> (resource-response "index.html" {:root "public"})
           (content-type "text/html")))


  (route/resources "/")


  (route/not-found (response {:error "Not Found"})))
