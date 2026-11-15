@echo off
rem Starts HDFS and uploads the climate datasets to hdfs:///climate
rem Run from anywhere: E:\climatechanges\hadoop\start_hdfs.cmd

set JAVA_HOME=C:\PROGRA~1\Java\jdk1.8.0_202
set HADOOP_HOME=C:\hadoop\hadoop-2.9.2
set PATH=%HADOOP_HOME%\bin;%HADOOP_HOME%\sbin;%PATH%
set DATA=%~dp0..\data

rem Format the namenode only the first time (when its folder is empty)
dir /b "%HADOOP_HOME%\data\namenode" | findstr . >nul || (
  echo [1/4] First run: formatting the empty namenode...
  call hdfs namenode -format -force -nonInteractive
)

echo [2/4] Starting namenode and datanode (two new windows will open)...
call start-dfs.cmd

echo [3/4] Waiting for HDFS to come up...
:wait
timeout /t 5 /nobreak >nul
call hdfs dfsadmin -safemode wait >nul 2>&1 || goto wait

echo [4/4] Uploading datasets to /climate ...
call hdfs dfs -mkdir -p /climate
call hdfs dfs -put -f "%DATA%\Carbon.csv" /climate/
call hdfs dfs -put -f "%DATA%\Disaster.csv" /climate/
call hdfs dfs -ls /climate

echo.
echo Done. HDFS web UI: http://localhost:50070   Site page: http://127.0.0.1:8000/climatechanges/dataset/
pause
