from airflow import DAG
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.utils.dates import days_ago
import json

with DAG(
    dag_id='nasa_apod_postgres', start_date=days_ago(1), schedule_interval='@daily', catchup=False
) as dag:
    #step 1: create the table if it does not exists
    @task
    def create_table():
        postgres_hook=PostgresHook(postgres_conn_id="my_postgres_connection")
        create_table_query = """CREATE TABLE IF NOT EXISTS apod_data(
            id SERIAL PRIMARY KEY,
            title VARCHAR(255),
            explanation TEXT,
            url TEXT,
            date DATE,
            media_type VARCHAR(50)
        );
        """
        postgres_hook.run(create_table_query)
    #step 2: extract the nasa api data(APOD) - extract pipeline
    extract_apod=SimpleHttpOperator(
        task_id='extract_apod',
        http_conn_id='nasa_api',  ## Connection ID Defined In Airflow For NASA API
        endpoint='planetary/apod', ## NASA API enpoint for APOD
        method='GET',
        data={"api_key":"{{ conn.nasa_api.extra_dejson.api_key}}"}, ## USe the API Key from the connection
        response_filter=lambda response:response.json(), ## Convert response to json
    )

    #step 3: transform the data(pick info that needed)
    @task
    def transform_apod_data(response):
        apod_data={
            'title': response.get('title', ''),
            'explanation': response.get('explanation', ''),
            'url': response.get('url', ''),
            'date': response.get('date', ''),
            'media_type': response.get('media_type', '')
        }
        return apod_data
    #step 4: load the data into postgres sql
    @task
    def load_data_to_postgres(apod_data):
        postgres_hook= PostgresHook(postgres_conn_id='my_postgres_connection')
        insert_query = """
        INSERT INTO apod_data (title, explanation, url, data, media_type)
        VALUES (%s, %s, %s, %s, %s);
        """
        postgres_hook.run(insert_query, parameters=(
            apod_data['title'], apod_data['explanation'], apod_data['url'], apod_data['date'], apod_data['media_type']
        ))

    #step 5: verify  the data dbviewer

    #step 6: define the task dependincies
    

    create_table() >> extract_apod
    api_response =extract_apod.output
    transformed_data=transform_apod_data(api_response)
    load_data_to_postgres(transformed_data)