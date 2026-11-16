function decodeUplink(input) {
  const bytes = input.bytes;
  if (!bytes || bytes.length < 7) {
    return {
      errors: ["Payload binaire incomplet : 7 octets attendus"]
    };
  }

  // Température en int16 big-endian (centièmes de °C)
  const rawTemp = (bytes[0] << 8) | bytes[1];
  const signedTemp = rawTemp > 32767 ? rawTemp - 65536 : rawTemp;
  const temperature_c = signedTemp / 100.0;

  // Humidité en uint16 big-endian (centièmes de %)
  const rawHum = (bytes[2] << 8) | bytes[3];
  const humidity_pct = rawHum / 100.0;

  // Pression en uint16 big-endian (dixièmes de hPa)
  const rawPress = (bytes[4] << 8) | bytes[5];
  const pressure_hpa = rawPress / 10.0;

  // Batterie en uint8 (%)
  const battery_pct = bytes[6];

  return {
    data: {
      temperature_c: temperature_c,
      humidity_pct: humidity_pct,
      pressure_hpa: pressure_hpa,
      battery_pct: battery_pct
    }
  };
}