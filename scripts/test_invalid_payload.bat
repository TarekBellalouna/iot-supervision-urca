@echo off
echo === TEST VALIDATION : INJECTION DE MESURES HORS PLAGE ===
docker compose exec -T lorawan-sim python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8091/control/lora-node-02/invalid', method='POST')).read().decode())"
docker compose exec -T zigbee-sim python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8092/control/zb-node-01/invalid', method='POST')).read().decode())"
timeout /t 2 /nobreak > nul
echo.
echo === COMPTEURS DE LA PLATEFORME ===
docker compose exec -T core-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/counters').read().decode())"
pause