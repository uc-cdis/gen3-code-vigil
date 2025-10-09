# Setting up ci-metrics schema and grafana dashboard

## Creating ci-metrics schema

1. Connect to the database
   ```psql -h <hostname> -p 5432 -U <username> -d <dbname>```

2. Create the schema
   ```
   CREATE TABLE ci_metrics_data (
       run_date     DATE NOT NULL,
       repo_name    TEXT NOT NULL,
       pr_num       INTEGER NOT NULL,
       run_num      INTEGER NOT NULL,
       test_suite   TEXT NOT NULL,
       test_case    TEXT NOT NULL,
       result       TEXT NOT NULL,
       duration     INTERVAL NOT NULL,
       attempt_num  INTEGER NOT NULL
   );

3. Add a constraint to avoid duplicates
   ```
   ALTER TABLE ci_metrics_data
   ADD CONSTRAINT unique_test_run
   UNIQUE (run_date, repo_name, pr_num, run_num, attempt_num, test_suite, test_case);


## Connecting the database in grafana
1. In Grafana, goto **Connections** -> **Data sources** page and click on **Add new data source**.
![alt text](ci_metrics_images/connections.png)
2. Search for postgresql
![alt text](ci_metrics_images/db-search.png)
3. Fill in the details for the ci-metrics database
![alt text](ci_metrics_images/db-data-population.png)

## Creating charts in Dashboard
1. In Grafana, goto **Dashboard** page and click on **New** -> **New dashboard**.
![alt text](ci_metrics_images/dashboard.png)
2. On the top right tab, click on **Add** button -> **Visualization**.
![alt text](ci_metrics_images/add-chart.png)
3. In the **Query Panel** panel, select the datasource and database.
![alt text](ci_metrics_images/query-panel.png)
4. Build or code your sql query to retrieve relevant data to the chart being created.
![alt text](ci_metrics_images/query-code.png)
5. In the **Panel Options** panel, set the required properties pertaining to the chart.
![alt text](ci_metrics_images/panel-options.png)
