@echo off
echo.
echo === AMASCI Full Backend Pipeline ===
echo.

set EXEC=docker exec -w /app -e PYTHONPATH=/app amasci-api-dev

echo [0/7] Checking containers...
docker compose -f docker-compose.dev.yml up -d
echo Waiting 15s...
timeout /t 15 /nobreak >nul
echo.

echo [1/7] Initialization - data + graph + ML training (~4-5 min)...
%EXEC% python scripts/run_initialization.py --force
if %errorlevel% neq 0 goto error
echo.

echo [2/7] Ablation study...
%EXEC% python scripts/ablation.py
if %errorlevel% neq 0 goto error
echo.

echo [3/7] Drift experiment...
%EXEC% python scripts/run_drift_experiment.py
echo.

echo [4/7] Feature importance...
%EXEC% python scripts/report_feature_importance.py
if %errorlevel% neq 0 goto error
echo.

echo [5/7] Gate check...
%EXEC% python scripts/run_gate_check.py
if %errorlevel% neq 0 goto error
echo.

echo [6/7] Invariant check...
%EXEC% python scripts/invariant_check.py
echo.

echo [7/7] Neo4j probe...
%EXEC% python scripts/probe_neo4j.py
if %errorlevel% neq 0 goto error
echo.

echo === ALL STEPS COMPLETE ===
echo API:    http://localhost:8000
echo Docs:   http://localhost:8000/docs
echo Neo4j:  http://localhost:7474  (neo4j / neo4j_dev_pass)
goto end

:error
echo.
echo === PIPELINE HALTED - fix the error above and re-run ===
exit /b 1

:end
