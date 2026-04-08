import httpx
import base64
import os
from dotenv import load_dotenv

load_dotenv()

ALEGRA_EMAIL = os.getenv("ALEGRA_EMAIL")
ALEGRA_TOKEN = os.getenv("ALEGRA_TOKEN")

auth_str = f"{ALEGRA_EMAIL}:{ALEGRA_TOKEN}"
auth_header = base64.b64encode(auth_str.encode()).decode()
headers = {
    "Authorization": f"Basic {auth_header}",
    "Content-Type": "application/json"
}

def list_categories():
    response = httpx.get("https://api.alegra.com/api/v1/categories?type=expense", headers=headers)
    if response.status_code == 200:
        categories = response.json()
        print("\n=== LISTA DE CUENTAS DE GASTOS EN TU ALEGRA ===")
        print(f"{'ID':<10} | {'Nombre':<30}")
        print("-" * 45)
        for cat in categories:
            print(f"{cat.get('id', 'N/A'):<10} | {cat.get('name', 'N/A'):<30}")
    else:
        print(f"Error al conectar con Alegra: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    list_categories()
