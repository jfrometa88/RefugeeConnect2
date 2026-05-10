import requests
import time

BASE_URL = "http://localhost:8000"

def test_hot_swap_flow():
    print("\n--- Cambiando a modo Local (Gemma 4 vía Ollama) ---")
    config_res = requests.post(f"{BASE_URL}/config/toggle", json={
    "use_local": True,
    "model_name_cloud": "gemma-4-31b-it",
    "model_name_local": "qwen2.5:3b"
    })
    print(f"Resultado cambio: {config_res.status_code}")

    # 3. Segunda pregunta: ¿Mantiene el contexto?
    print("\n--- Probando pregunta de seguimiento en modo Local ---")
    q2 = requests.post(f"{BASE_URL}/query", json={
        "user_id": "test_user_1",
        "message": "¿Cuál es la dirección de la primera que mencionaste?"
    })
    
    print(f"Respuesta Local (con contexto): {q2.json()['response'][:100]}...")

if __name__ == "__main__":
    test_hot_swap_flow()