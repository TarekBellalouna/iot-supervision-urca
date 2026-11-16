#!/bin/sh
set -e

PASSWD_FILE="/mosquitto/config/passwd"
rm -f "$PASSWD_FILE"

mosquitto_passwd -b -c "$PASSWD_FILE" chirpstack "$MQTT_CHIRPSTACK_PASSWORD"
mosquitto_passwd -b "$PASSWD_FILE" zigbee_coord "$MQTT_ZIGBEE_PASSWORD"
mosquitto_passwd -b "$PASSWD_FILE" thread_bridge "$MQTT_THREAD_PASSWORD"
mosquitto_passwd -b "$PASSWD_FILE" core_backend "$MQTT_BACKEND_PASSWORD"

chown mosquitto:mosquitto "$PASSWD_FILE"
chmod 0700 "$PASSWD_FILE"

exec /usr/sbin/mosquitto -c /mosquitto/config/mosquitto.conf