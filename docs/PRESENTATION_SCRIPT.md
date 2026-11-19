# EarthScape: presentation script (about 4 minutes)

Do the **[actions in brackets]** while you speak. A recorded walkthrough is in the v1.0 release as `EarthScape_Demo.mp4`.

## 1. Opening (20 s)
**[Home page]** "This is **EarthScape**, a climate intelligence platform built for the EarthScape Climate Agency as an Aptech eProject. The agency collects huge amounts of data from satellites, weather stations and sensors. The challenge is turning that data into decisions. EarthScape does it with **Hadoop, MapReduce and machine learning**, behind a secure dashboard."

## 2. Architecture (30 s)
**[Architecture diagram in the PDF or README]** "Data comes in from the sources and goes through **ingestion**, where Django validates and cleans it. It's stored on **HDFS**, partitioned by date, then processed with **MapReduce** to find patterns and correlations. **Machine-learning models** predict trends and detect anomalies, and everything appears in the **console dashboard**. It's built with Python, Django, scikit-learn and Chart.js, and deployed live on Vercel."

## 3. Login and roles (30 s)
**[Login page, 'Try it instantly' card]** "Login is secure and role-based, with two roles: **Administrator** and **Climate Analyst**. Passwords are hashed and every page checks the role on the server. Reviewers can use the one-click demo logins. I'll sign in as the Administrator." **[Click Administrator]**

## 4. Dashboard tour (2 min)
- **[Overview]** "The Overview shows station temperature, CO2, rainfall and the global temperature anomaly at a glance, with filters by date, region, country and variable."
- **[Climate Analytics]** "Analysts explore trends and correlations across stations and variables."
- **[Data Management]** "Upload CSV or Excel files, or stream live readings through a secure API. The data is stored on HDFS."
- **[Data Processing]** "MapReduce jobs compute aggregates, patterns and correlations in parallel."
- **[Predictions, Anomaly Detection]** "Machine-learning forecasts of future trends, plus automatic flagging of unusual readings."
- **[Alerts]** "When a value crosses a threshold, an **alert** is raised automatically. The unread count shows in the sidebar and on the bell icon."
- **[Reports, Support, User Management]** "Reports produce downloadable summaries, and Support handles tickets and feedback. Admins manage users and roles here; analysts are blocked from this page, which is the role security working."

## 5. Design and non-functional requirements (20 s)
"The interface is a modern dark theme inspired by professional admin dashboards, and it works on phones. For security there's CSRF protection, HTTPS-only cookies, strict security headers and encrypted data. There are also backup and restore commands and performance monitoring."

## 6. Testing and closing (20 s)
"Every page and API route was tested with both roles. Analysts are blocked from admin pages, and logged-out users are redirected to login. Future work: streaming with Kafka or Spark, alerts by email and SMS, and map views. EarthScape takes raw climate data all the way to decisions: ingest, store, process, predict, visualise and alert. Thank you!"

## Likely questions
- **Why doesn't the live site run Hadoop?** Serverless hosting can't run a Hadoop cluster. The demo uses pre-built sample data; the full HDFS and MapReduce pipeline runs locally or on a cluster.
- **How are passwords stored?** Hashed with Django's password hasher, never as plain text.
- **Which ML models?** Trend prediction and statistical anomaly detection with scikit-learn and SciPy.
