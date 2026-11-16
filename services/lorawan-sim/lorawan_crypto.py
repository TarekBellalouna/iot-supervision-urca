import struct
from Crypto.Cipher import AES
from Crypto.Hash import CMAC


def encrypt_frm_payload(payload: bytes, app_s_key_hex: str, dev_addr_hex: str, fcnt: int, direction: int = 0) -> bytes:
    """Chiffrement AES-128 conforme à la spécification LoRaWAN 1.0.3 (Section 4.3.3)."""
    key = bytes.fromhex(app_s_key_hex)
    dev_addr_le = bytes.fromhex(dev_addr_hex)[::-1]
    cipher = AES.new(key, AES.MODE_ECB)

    encrypted = bytearray()
    num_blocks = (len(payload) + 15) // 16

    for i in range(1, num_blocks + 1):
        block_a = (
            b"\x01\x00\x00\x00\x00"
            + bytes([direction])
            + dev_addr_le
            + struct.pack("<I", fcnt)
            + b"\x00"
            + bytes([i])
        )
        s_i = cipher.encrypt(block_a)
        chunk = payload[(i - 1) * 16 : i * 16]
        for b, s in zip(chunk, s_i):
            encrypted.append(b ^ s)

    return bytes(encrypted)


def compute_mic(mac_payload_with_mhdr: bytes, nwk_s_key_hex: str, dev_addr_hex: str, fcnt: int, direction: int = 0) -> bytes:
    """Calcul du Message Integrity Code (MIC) AES-128 CMAC sur 4 octets."""
    key = bytes.fromhex(nwk_s_key_hex)
    dev_addr_le = bytes.fromhex(dev_addr_hex)[::-1]

    block_b0 = (
        b"\x49\x00\x00\x00\x00"
        + bytes([direction])
        + dev_addr_le
        + struct.pack("<I", fcnt)
        + b"\x00"
        + bytes([len(mac_payload_with_mhdr)])
    )
    cobj = CMAC.new(key, ciphermod=AES)
    cobj.update(block_b0 + mac_payload_with_mhdr)
    return cobj.digest()[:4]


def build_uplink_phy_payload(
    dev_addr_hex: str,
    nwk_s_key_hex: str,
    app_s_key_hex: str,
    fcnt: int,
    temp_c: float,
    hum_pct: float,
    press_hpa: float,
    batt_pct: int,
    fport: int = 1,
) -> bytes:
    """Construit une trame PHY LoRaWAN UnconfirmedDataUp complète (MHDR + FHDR + FPort + FRMPayload + MIC)."""
    raw_payload = struct.pack(
        ">hHHB",
        int(round(temp_c * 100)),
        int(round(hum_pct * 100)),
        int(round(press_hpa * 10)),
        int(batt_pct),
    )
    frm_payload = encrypt_frm_payload(raw_payload, app_s_key_hex, dev_addr_hex, fcnt, direction=0)

    mhdr = b"\x40"  # Unconfirmed Data Up
    dev_addr_le = bytes.fromhex(dev_addr_hex)[::-1]
    fctrl = b"\x00"
    fcnt_le = struct.pack("<H", fcnt & 0xFFFF)
    fhdr = dev_addr_le + fctrl + fcnt_le

    mac_frame = mhdr + fhdr + bytes([fport]) + frm_payload
    mic = compute_mic(mac_frame, nwk_s_key_hex, dev_addr_hex, fcnt, direction=0)
    return mac_frame + mic