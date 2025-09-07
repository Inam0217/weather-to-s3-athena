# Weather → S3 → Athena (Serverless ETL)

Serverless data pipeline on AWS:
EventBridge (schedule) → Lambda (OpenWeather) → S3 (partitioned) → Glue Crawler (catalog) → Athena (SQL). Optional QuickSight.

## Architecture
```mermaid
flowchart LR
    EB[EventBridge Scheduler (hourly)] --> L[Lambda weather_ingest]
    L -->|JSON per city/hour| S3[(Amazon S3 raw/city=.../dt=.../hour=.../)]
    S3 --> GC[Glue Crawler (hourly/daily)]
    GC --> DC[Glue Data Catalog weather_data.inam_weather_data]
    DC --> A[Athena SQL queries]
    A --> QS[QuickSight (optional dashboard)]

```

## What it does
- Ingests weather for Riyadh/Jeddah/Mecca hourly (EventBridge → Lambda).
- Stores JSON to S3 with partitions: `raw/city=.../dt=YYYY-MM-DD/hour=HH/...`
- Glue Crawler updates a table in **Glue Data Catalog**.
- Query with **Athena** using standard SQL.

## Quickstart (what I did)
1. S3 bucket (encrypted, public-blocked).  
2. Secrets Manager: `openweather/api` with `{"OPENWEATHER_API_KEY":"..."}`.  
3. IAM role `lambda-weather-ingest-role` with:
   - `AWSLambdaBasicExecutionRole`
   - Inline allow: `secretsmanager:GetSecretValue`, `s3:PutObject`, `s3:ListBucket` on the bucket.
4. Lambda `weather_ingest` (Python 3.12) env:
   - `BUCKET`, `SECRET_NAME=openweather/api`, `CITIES=Riyadh,Jeddah,Mecca`, `BASE_PATH=raw`
5. EventBridge schedule: `rate(1 hour)`.  
6. Glue Crawler → DB `weather_data` → table `inam_weather_data` (hourly/daily schedule).  
7. Athena: set results folder, run queries.

## Example queries (Athena)
```sql
-- Daily average temperature per city
SELECT city, dt, ROUND(AVG(CAST(temp_c AS double)), 2) AS avg_temp_c
FROM "weather_data"."inam_weather_data"
GROUP BY city, dt
ORDER BY dt DESC, city;
```

```sql
-- Hottest city per day (top 10)
SELECT dt, city, MAX(CAST(temp_c AS double)) AS max_temp_c
FROM "weather_data"."inam_weather_data"
GROUP BY dt, city
ORDER BY dt DESC, max_temp_c DESC
LIMIT 10;
```

```sql
-- Hourly trend today for Riyadh
SELECT hour, ROUND(AVG(CAST(temp_c AS double)), 2) AS avg_temp_c
FROM "weather_data"."inam_weather_data"
WHERE city = 'Riyadh' AND dt = current_date
GROUP BY hour
ORDER BY hour;
```

## Lambda handler (snippet)
See [`lambda/handler.py`](lambda/handler.py). Writes JSONL with `city_name`, `ts_utc`, `temp_c`, etc.

## Costs
Near-zero at this scale (S3 MBs, Lambda ms, Glue short crawls, Athena cents/query). Free Tier friendly.

## What I learned
Serverless ETL, S3 partitioning, Glue Data Catalog, Athena SQL, IAM least-privilege, Secrets Manager, scheduled data pipelines.
