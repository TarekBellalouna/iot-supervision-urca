@echo off
echo === TEST SCENARIO : REJEU D'UNE TRAME LORAWAN (FCnt) ===
docker compose exec -T lorawan-sim python -c "import urllib.request; print(urllib.request.urlopen(urllib.request.Request('http://localhost:8091/control/lora-node-01/replay', method='POST')).read().decode())"
timeout /t 2 /nobreak > nul
echo.
echo === LOGS CHIRPSTACK (VERIFICATION DU REJET ANTI-REJEU) ===
docker compose logs --tail=15 chirpstack
pause