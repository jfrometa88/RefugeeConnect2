import requests
import time

BASE_URL = "http://localhost:8000"

def test_query():
    print("--- Probando pregunta en modo Cloud ---")
    q1 = requests.post(f"{BASE_URL}/query", json={
    "message": "Hola, ¿qué organizaciones ayudan a refugiados en Valencia?",
    "session_id": "test",
    "user_id": "test_user_1"
    })
    print(f"Respuesta Cloud: {q1.json()['response'][:100]}...")

if __name__ == "__main__":
    test_query()

