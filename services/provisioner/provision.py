import json
import os
import secrets
import time
import grpc
from google.protobuf import empty_pb2
from chirpstack_api import api, common

CHIRPSTACK_SERVER = os.getenv("CHIRPSTACK_SERVER", "chirpstack:8080")
ADMIN_EMAIL = os.getenv("CHIRPSTACK_ADMIN_EMAIL", "admin@urca-iot.local")
ADMIN_PASSWORD = os.getenv("CHIRPSTACK_ADMIN_PASSWORD", "AdminUrca2026!Secure")
CODEC_PATH = os.getenv("CODEC_PATH", "/config/codec.js")
SHARED_DIR = os.getenv("SHARED_DIR", "/shared")

GATEWAYS = [
    {"id": "aa555a0000000101", "name": "gw-reims-nord"},
    {"id": "aa555a0000000102", "name": "gw-reims-sud"},
]

NODES = [
    {"node_id": "lora-node-01", "dev_eui": "0102030405060701", "dev_addr": "01020301"},
    {"node_id": "lora-node-02", "dev_eui": "0102030405060702", "dev_addr": "01020302"},
    {"node_id": "lora-node-03", "dev_eui": "0102030405060703", "dev_addr": "01020303"},
]


def wait_for_chirpstack(channel: grpc.Channel) -> str:
    internal = api.InternalServiceStub(channel)
    user_srv = api.UserServiceStub(channel)

    for attempt in range(30):
        try:
            # 1. Tente la connexion avec les identifiants par défaut
            resp = internal.Login(api.LoginRequest(email="admin", password="admin"))
            jwt = resp.jwt
            meta = [("authorization", f"Bearer {jwt}")]

            # 2. Remplace immédiatement le compte et le mot de passe par défaut via UserService
            profile = internal.Profile(empty_pb2.Empty(), metadata=meta)
            user_id = profile.user.id
            user_srv.Update(
                api.UpdateUserRequest(
                    user=api.User(
                        id=user_id,
                        email=ADMIN_EMAIL,
                        is_active=True,
                        is_admin=True,
                    )
                ),
                metadata=meta,
            )
            user_srv.UpdatePassword(
                api.UpdateUserPasswordRequest(user_id=user_id, password=ADMIN_PASSWORD),
                metadata=meta,
            )
            print(f"[Provisioner] Compte admin mis à jour vers {ADMIN_EMAIL}")
            resp = internal.Login(api.LoginRequest(email=ADMIN_EMAIL, password=ADMIN_PASSWORD))
            return resp.jwt
        except grpc.RpcError:
            try:
                # Si déjà provisionné lors d'un démarrage précédent
                resp = internal.Login(api.LoginRequest(email=ADMIN_EMAIL, password=ADMIN_PASSWORD))
                print("[Provisioner] Authentification réussie avec le compte admin sécurisé.")
                return resp.jwt
            except grpc.RpcError:
                print(f"[Provisioner] En attente de ChirpStack ({attempt + 1}/30)...")
                time.sleep(2)
    raise RuntimeError("Impossible de joindre ChirpStack gRPC.")

def main():
    channel = grpc.insecure_channel(CHIRPSTACK_SERVER)
    jwt = wait_for_chirpstack(channel)
    meta = [("authorization", f"Bearer {jwt}")]

    tenant_srv = api.TenantServiceStub(channel)
    gw_srv = api.GatewayServiceStub(channel)
    dp_srv = api.DeviceProfileServiceStub(channel)
    app_srv = api.ApplicationServiceStub(channel)
    dev_srv = api.DeviceServiceStub(channel)

    # Récupérer le tenant par défaut
    tenants = tenant_srv.List(api.ListTenantsRequest(limit=10), metadata=meta)
    tenant_id = tenants.result[0].id

    # Création des 2 passerelles LoRaWAN
    existing_gws = {
        g.gateway_id for g in gw_srv.List(api.ListGatewaysRequest(limit=50, tenant_id=tenant_id), metadata=meta).result
    }
    for gw in GATEWAYS:
        if gw["id"] not in existing_gws:
            gw_srv.Create(
                api.CreateGatewayRequest(
                    gateway=api.Gateway(
                        gateway_id=gw["id"],
                        name=gw["name"],
                        tenant_id=tenant_id,
                        stats_interval=30,
                    )
                ),
                metadata=meta,
            )
            print(f"[Provisioner] Passerelle créée : {gw['name']} ({gw['id']})")

    # Création du Device Profile avec le codec JS
    with open(CODEC_PATH, "r", encoding="utf-8") as f:
        codec_script = f.read()

    dps = dp_srv.List(api.ListDeviceProfilesRequest(limit=50, tenant_id=tenant_id), metadata=meta).result
    dp_id = next((d.id for d in dps if d.name == "URCA-LoRa-ClassA-EU868"), None)
    if not dp_id:
        dp_resp = dp_srv.Create(
            api.CreateDeviceProfileRequest(
                device_profile=api.DeviceProfile(
                    name="URCA-LoRa-ClassA-EU868",
                    tenant_id=tenant_id,
                    region=common.Region.EU868,
                    mac_version=common.MacVersion.LORAWAN_1_0_3,
                    reg_params_revision=common.RegParamsRevision.A,
                    adr_algorithm_id="default",
                    payload_codec_runtime=api.CodecRuntime.JS,
                    payload_codec_script=codec_script,
                    uplink_interval=20,
                    supports_otaa=False,
                )
            ),
            metadata=meta,
        )
        dp_id = dp_resp.id
        print(f"[Provisioner] Device Profile créé : {dp_id}")

    # Création de l'Application ChirpStack
    apps = app_srv.List(api.ListApplicationsRequest(limit=50, tenant_id=tenant_id), metadata=meta).result
    app_id = next((a.id for a in apps if a.name == "URCA-Supervision-IoT"), None)
    if not app_id:
        app_resp = app_srv.Create(
            api.CreateApplicationRequest(
                application=api.Application(
                    name="URCA-Supervision-IoT",
                    description="Supervision multi-réseaux Master 2 DAS",
                    tenant_id=tenant_id,
                )
            ),
            metadata=meta,
        )
        app_id = app_resp.id
        print(f"[Provisioner] Application créée : {app_id}")

    # Création et activation ABP des nœuds avec clés uniques
    existing_devs = {
        d.dev_eui for d in dev_srv.List(api.ListDevicesRequest(limit=50, application_id=app_id), metadata=meta).result
    }
    exported_nodes = []

    for node in NODES:
        nwk_s_key = secrets.token_hex(16)
        app_s_key = secrets.token_hex(16)

        if node["dev_eui"] not in existing_devs:
            dev_srv.Create(
                api.CreateDeviceRequest(
                    device=api.Device(
                        dev_eui=node["dev_eui"],
                        name=node["node_id"],
                        application_id=app_id,
                        device_profile_id=dp_id,
                        skip_fcnt_check=False,
                    )
                ),
                metadata=meta,
            )

        # Activation (ou réinitialisation propre des clés de session)
        dev_srv.Activate(
            api.ActivateDeviceRequest(
                device_activation=api.DeviceActivation(
                    dev_eui=node["dev_eui"],
                    dev_addr=node["dev_addr"],
                    app_s_key=app_s_key,
                    nwk_s_enc_key=nwk_s_key,
                    s_nwk_s_int_key=nwk_s_key,
                    f_nwk_s_int_key=nwk_s_key,
                    f_cnt_up=0,
                    n_f_cnt_down=0,
                    a_f_cnt_down=0,
                )
            ),
            metadata=meta,
        )
        print(f"[Provisioner] Nœud activé : {node['node_id']} (DevEUI={node['dev_eui']})")
        exported_nodes.append(
            {
                "node_id": node["node_id"],
                "dev_eui": node["dev_eui"],
                "dev_addr": node["dev_addr"],
                "nwk_s_key": nwk_s_key,
                "app_s_key": app_s_key,
            }
        )

    os.makedirs(SHARED_DIR, exist_ok=True)
    config_out = {
        "application_id": app_id,
        "gateways": GATEWAYS,
        "nodes": exported_nodes,
    }
    out_file = os.path.join(SHARED_DIR, "lorawan_devices.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(config_out, f, indent=2)

    print(f"[Provisioner] Configuration exportée dans {out_file}. Terminé.")


if __name__ == "__main__":
    main()