import mysql.connector
import os
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

def obtenir_connexion():
    try:
        connexion = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
        return connexion
    except mysql.connector.Error as err:
        print(f"❌ Erreur de connexion à la base de données : {err}")
        return None
