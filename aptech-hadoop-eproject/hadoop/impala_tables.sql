-- EarthScape: Impala (or Hive) external tables over the data stored in HDFS.
-- The tables read the files in place; nothing is copied. Run in impala-shell or Hue:
--   impala-shell -f hadoop/impala_tables.sql
-- (Hive: the same statements work in beeline; use MSCK REPAIR TABLE instead of ALTER ... RECOVER PARTITIONS.)

CREATE DATABASE IF NOT EXISTS earthscape;
USE earthscape;

-- Raw FAO temperature-change file (wide format: one column per year) as uploaded by start_hdfs.cmd
CREATE EXTERNAL TABLE IF NOT EXISTS temperature_raw (
  objectid INT, country STRING, iso2 STRING, iso3 STRING, indicator STRING, unit STRING, source STRING,
  cts_code STRING, cts_name STRING, cts_full_descriptor STRING
  -- plus one DOUBLE column per year 1961..2023; list them if you need SQL access to every year
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/climate/raw/historical'
TBLPROPERTIES ('skip.header.line.count'='1');

-- Output of the Hadoop Streaming MapReduce job (hadoop/run_mapreduce.cmd)
CREATE EXTERNAL TABLE IF NOT EXISTS disasters_per_year (
  year INT,
  disasters INT
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY '\t'
STORED AS TEXTFILE
LOCATION '/climate/output/disasters_per_year';

-- Cleaned station readings uploaded through the console, partitioned like the HDFS layout
--   /climate/clean/station/year=YYYY/month=MM/*.csv
CREATE EXTERNAL TABLE IF NOT EXISTS station_readings (
  station STRING, country STRING, region STRING, latitude DOUBLE, longitude DOUBLE,
  `date` STRING, temperature DOUBLE, rainfall DOUBLE, humidity DOUBLE
)
PARTITIONED BY (year INT, month INT)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
STORED AS TEXTFILE
LOCATION '/climate/clean/station'
TBLPROPERTIES ('skip.header.line.count'='1');

ALTER TABLE station_readings RECOVER PARTITIONS;
COMPUTE STATS disasters_per_year;

-- Example analytical queries ------------------------------------------------------

-- Decades with the most climate disasters
SELECT FLOOR(year / 10) * 10 AS decade, SUM(disasters) AS total
FROM disasters_per_year GROUP BY 1 ORDER BY 1;

-- Year-on-year change
SELECT year, disasters,
       disasters - LAG(disasters) OVER (ORDER BY year) AS change_vs_previous_year
FROM disasters_per_year ORDER BY year;

-- Monthly averages per station (only reads the partitions it needs)
SELECT station, year, month, AVG(temperature) AS avg_temp_c, SUM(rainfall) AS rain_mm, AVG(humidity) AS humidity_pct
FROM station_readings
WHERE year >= 2024
GROUP BY station, year, month
ORDER BY station, year, month;

-- Production note (Data Security): put /climate in an HDFS encryption zone so blocks are encrypted at rest:
--   hadoop key create earthscape_key
--   hdfs crypto -createZone -keyName earthscape_key -path /climate
