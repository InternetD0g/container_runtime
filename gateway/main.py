from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
import httpx
import jwt
from jwt import PyJWKClient
import subprocess
import json
import time
import uuid

app = FastAPI(title="Containerd RBAC Gateway")

KEYCLOAK_URL = "http://192.168.56.10:8080"
REALM = "containerd-auth"
CLIENT_ID = "containerd-gateway"
CLIENT_SECRET = "MyNewGatewaySecret2026"
JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"

jwks_client = PyJWKClient(JWKS_URL)

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateContainerRequest(BaseModel):
    image: str

async def get_current_user(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")

    token = authorization.split(" ")[1]
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(token, signing_key.key, algorithms=["RS256"],
                             audience="account", options={"verify_aud": False},
                             issuer=f"{KEYCLOAK_URL}/realms/{REALM}")
        return {"username": payload.get("preferred_username"), "roles": payload.get("realm_access", {}).get("roles", [])}
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

@app.post("/login")
async def login(data: LoginRequest):
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/token", data={
            "grant_type": "password", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
            "username": data.username, "password": data.password
        })
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return response.json()

@app.get("/containers")
async def list_containers(user: dict = Depends(get_current_user)):
    is_admin = "admin" in user["roles"]
    cmd = ["sudo", "/usr/local/bin/crictl", "ps", "-o", "json"]
    if not is_admin:
        cmd += ["--label", f"owner={user['username']}"]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return {"user": user["username"], "is_admin": is_admin, "containers": json.loads(result.stdout).get("containers", [])}

@app.post("/containers")
async def create_container(data: CreateContainerRequest, user: dict = Depends(get_current_user)):
    username = user["username"]
    pod_name = f"pod-{username}-{int(time.time())}"

    pod_config = {
        "metadata": {
            "name": pod_name, 
            "namespace": "default",
            "uid": str(uuid.uuid4()),
            "attempt": 0
        },
        "log_directory": "/tmp"
    }
    ctr_config = {
        "metadata": {"name": f"ctr-{username}"},
        "image": {"image": data.image},
        "args": ["sleep", "3600"],
        "labels": {"owner": username}
    }

    with open("/tmp/pod.json", "w") as f: json.dump(pod_config, f)
    with open("/tmp/ctr.json", "w") as f: json.dump(ctr_config, f)

    try:
        subprocess.run(["sudo", "/usr/local/bin/crictl", "pull", data.image], check=True, capture_output=True)
        pod_id = subprocess.run(["sudo", "/usr/local/bin/crictl", "runp", "/tmp/pod.json"], capture_output=True, text=True, check=True).stdout.strip()
        ctr_id = subprocess.run(["sudo", "/usr/local/bin/crictl", "create", pod_id, "/tmp/ctr.json", "/tmp/pod.json"], capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["sudo", "/usr/local/bin/crictl", "start", ctr_id], check=True, capture_output=True)
        return {"status": "success", "pod_id": pod_id, "container_id": ctr_id, "owner": username}
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Crictl error: {e.stderr}")

@app.delete("/containers/{container_id}")
def delete_container(container_id: str, user: dict = Depends(get_current_user)):
    crictl = ["sudo", "/usr/local/bin/crictl"]

    if not container_id or not all(c in "0123456789abcdef" for c in container_id):
        raise HTTPException(status_code=400, detail="Invalid container id")

    inspect = subprocess.run(
        crictl + ["inspect", "-o", "json", container_id],
        capture_output=True, text=True
    )
    if inspect.returncode != 0:
        raise HTTPException(status_code=404, detail=f"Container not found: {inspect.stderr.strip()}")

    info = json.loads(inspect.stdout)
    labels = (info.get("status", {}).get("labels")
 i             or info.get("info", {}).get("config", {}).get("labels")
              or {})
    owner = labels.get("owner")

    if "admin" not in user["roles"] and owner != user["username"]:
        raise HTTPException(status_code=403, detail="You do not own this container")

    subprocess.run(crictl + ["stop", container_id], capture_output=True, text=True)

    rm_result = subprocess.run(
        crictl + ["rm", "-f", container_id], capture_output=True, text=True
    )
    if rm_result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Failed to remove container: {rm_result.stderr.strip()}")

    return {"status": "deleted", "container_id": container_id}
