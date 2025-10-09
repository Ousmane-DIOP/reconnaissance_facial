import bcrypt
import mysql.connector
from db_config import obtenir_connexion

def creer_admin(username, mot_de_passe_clair):
    # génération du hash bcrypt
    salt = bcrypt.gensalt(rounds=12)                # rounds = coût (12 raisonnable)
    hash_pw = bcrypt.hashpw(mot_de_passe_clair.encode('utf-8'), salt).decode('utf-8')

    conn = obtenir_connexion()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO admins (username, password) VALUES (%s, %s)", (username, hash_pw))
        conn.commit()
        print("Admin créé :", username)
    except mysql.connector.Error as e:
        print("Erreur:", e)
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    import getpass
    user = input("Nom d'utilisateur admin : ").strip()
    pwd = getpass.getpass("Mot de passe : ")
    creer_admin(user, pwd)
