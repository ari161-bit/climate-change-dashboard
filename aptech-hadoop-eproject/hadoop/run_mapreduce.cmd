@echo off
rem Runs the "climate disasters per year" MapReduce job on Hadoop (Hadoop Streaming + Python).
rem Needs HDFS running first (start_hdfs.cmd). Reads /climate/Disaster.csv, writes /climate/output/disasters_per_year
set JAVA_HOME=C:\PROGRA~1\Java\jdk1.8.0_202
set HADOOP_HOME=C:\hadoop\hadoop-2.9.2
set PATH=%HADOOP_HOME%\bin;%HADOOP_HOME%\sbin;%PATH%
cd /d "%~dp0"

call hdfs dfs -rm -r -f /climate/output/disasters_per_year
call hadoop jar %HADOOP_HOME%\share\hadoop\tools\lib\hadoop-streaming-2.9.2.jar -files "mapper.py,reducer.py" -mapper "python mapper.py" -reducer "python reducer.py" -input /climate/Disaster.csv -output /climate/output/disasters_per_year
echo.
echo ===== Result (year, disasters) =====
call hdfs dfs -cat /climate/output/disasters_per_year/part-00000
if not "%1"=="--no-pause" pause
