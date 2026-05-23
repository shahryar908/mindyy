from fastapi.testclient import TestClient
from main import app

with TestClient(app) as client:
    r1 = client.post("/auth/signup", json={"email": "test@example.com", "password": "TestPass1!"})
    print("signup:", r1.status_code, r1.json())

    r2 = client.post("/auth/signin", json={"email": "test@example.com", "password": "TestPass1!"})
    print("signin (unverified):", r2.status_code, r2.json())

    r3 = client.post("/auth/forgot-password", json={"email": "test@example.com"})
    print("forgot-password:", r3.status_code, r3.json())

    r4 = client.post("/auth/refresh-token", json={"refresh_token": "garbage"})
    print("refresh bad token:", r4.status_code, r4.json())

    r5 = client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    print("me bad token:", r5.status_code, r5.json())

    r6 = client.post("/auth/signup", json={"email": "test@example.com", "password": "TestPass1!"})
    print("signup duplicate:", r6.status_code, r6.json())
