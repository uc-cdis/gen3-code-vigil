# Setting up ci-metrics schema and grafana dashboard

## Creating ci-metrics schema

1. Connect to the database
   ```psql -h <hostname> -p 5432 -U <username> -d <dbname>```

2. Create the schema
   ```CREATE TABLE ci_metrics_data (
       run_date     DATE NOT NULL,
       repo_name    TEXT NOT NULL,
       pr_num       INTEGER NOT NULL,
       run_num      INTEGER NOT NULL,
       test_suite   TEXT NOT NULL,
       test_case    TEXT NOT NULL,
       result       TEXT NOT NULL,
       duration     INTERVAL NOT NULL,
       attempt_num  INTEGER NOT NULL
   );```

3. Add a constraint to avoid duplicates
   ```ALTER TABLE ci_metrics_data
   ADD CONSTRAINT unique_test_run
   UNIQUE (run_date, repo_name, pr_num, run_num, attempt_num, test_suite, test_case);```


## Connecting the database in grafana


## Creating charts in Dashboard
1. In Grafana, goto Dashboard page and Click on **New** dashboard.
2. On the top right tab, click on **Add** button -> **Visualization**.
3. In the **Query Panel** panel, select the datasource and database.
4. Build or code your sql query to retrieve relevant data to the chart being created.
5. In the **Panel Options** panel, set the required properties pertaining to the chart.
