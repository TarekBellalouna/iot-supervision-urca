@echo off
echo ================================================================
echo DEMONSTRATION DES SCENARIOS DE ROBUSTESSE - TP IOT URCA
echo ================================================================
echo.
echo [1/3] Mise en veille de zb-node-03 et interrogation (attente expiration 8s)...
docker compose exec -T zigbee-sim python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8092/control/zb-node-03/sleep', method='POST')).read().decode())"
docker compose exec -T core-backend python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8000/api/nodes/zb-node-03/query', method='POST')).read().decode())"
timeout /t 10 /nobreak > nul
echo.
echo [2/3] Arret du noeud th-node-02 (observer passage a Perdu sur le dashboard)...
docker compose exec -T thread-sim python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8093/control/th-node-02/stop', method='POST')).read().decode())"
echo Attente 32 secondes pour le passage en etat PERDU...
timeout /t 32 /nobreak > nul
echo Redemarrage de th-node-02 (retour a En ligne)...
docker compose exec -T thread-sim python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8093/control/th-node-02/start', method='POST')).read().decode())"
timeout /t 12 /nobreak > nul
echo.
echo [3/3] Redemarrage du broker MQTT Mosquitto (reprise automatique sans intervention)...
docker compose restart mosquitto
timeout /t 8 /nobreak > nul
echo.
echo === ETAT FINAL DES COMPTEURS ===
docker compose exec -T core-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/counters').read().decode())"
pause