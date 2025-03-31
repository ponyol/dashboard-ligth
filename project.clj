(defproject dashboard-light "0.1.0-SNAPSHOT"
  :description "Система мониторинга EKS Deployments & Pods"
  :url "http://example.com/dashboard-light"
  :license {:name "Eclipse Public License"
            :url "http://www.eclipse.org/legal/epl-v10.html"}
  :dependencies [[org.clojure/clojure "1.11.1"]

                 [ring "1.10.0"]
                 [compojure "1.7.0"]
                 [ring/ring-json "0.5.1"]
                 [ring/ring-defaults "0.4.0"]
                 [hiccup "1.0.5"]


                 [io.kubernetes/client-java "19.0.0"]


                 [aero "1.1.6"]
                 [clj-yaml "0.4.0"]


                 [ring-oauth2 "0.1.5"]
                 [buddy/buddy-auth "3.0.323"]
                 [buddy/buddy-sign "3.5.346"]


                 [org.clojure/tools.logging "1.2.4"]
                 [ch.qos.logback/logback-classic "1.4.11"]
                 [org.clojure/tools.namespace "1.4.4"]
                 [mount "0.1.17"]
                 [clj-time "0.15.2"]


                 [clj-http "3.12.3"]


                 [org.clojure/data.json "2.4.0"]
                 [metosin/jsonista "0.3.8"]]

  :main ^:skip-aot dashboard-light.core
  :target-path "target/%s"
  :profiles {:uberjar {:aot :all
                        :jvm-opts ["-Dclojure.compiler.direct-linking=true"]}
             :dev {:dependencies [[org.clojure/tools.namespace "1.4.4"]]
                   :source-paths ["dev"]
                   :repl-options {:init-ns user}}})
