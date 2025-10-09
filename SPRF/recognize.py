import face_recognition
import cv2
import numpy as np
import pickle
import threading
import requests
from datetime import datetime
import time
import logging
import traceback
import pyttsx3
from playsound import playsound
from db_config import obtenir_connexion

# -------------------------
# CONFIGURATION GLOBALE
# -------------------------
SEUIL = 0.45
COOLDOWN_SEC = 8
API_URL = "http://localhost:5000/api/pointage"
HTTP_TIMEOUT = 3
HTTP_RETRIES = 2
SON_RECONNU = "./sound_ok.wav"
SON_INCONNU = "./sound_error.wav"
LOG_LEVEL = logging.INFO

CAMERAS = [
    "rtsp://admin:Hymd2%4015@192.168.1.207:554/Streaming/Channels/101"
]

# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(level=LOG_LEVEL, format="[%(asctime)s] [%(threadName)s] %(levelname)s: %(message)s")

# -------------------------
# INITIALISATION VOIX
# -------------------------
engine = pyttsx3.init()
engine.setProperty('rate', 140)
engine.setProperty('volume', 3.0)
engine.setProperty('voice', 'com.apple.speech.synthesis.voice.thomas' if 'mac' in pyttsx3.drivers.SAPI5Driver.__name__ else None)

def parler(texte):
    try:
        engine.say(texte)
        engine.runAndWait()
    except Exception as e:
        logging.warning("Erreur TTS: %s", e)

# -------------------------
# JOUER UN SON
# -------------------------
def jouer_son(fichier):
    try:
        playsound(fichier, block=False)
    except Exception as e:
        logging.warning("Erreur son (%s): %s", fichier, e)

# -------------------------
# CHARGER UTILISATEURS CONNUS
# -------------------------
def charger_utilisateurs():
    conn = obtenir_connexion()
    cur = conn.cursor()
    cur.execute("SELECT id, prenom, nom, service, encodage FROM utilisateurs")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

rows = charger_utilisateurs()
encodages_connus, noms_connus = [], []
for id_utilisateur, prenom, nom, service, encodage_binaire in rows:
    try:
        enc = pickle.loads(encodage_binaire)
        encodages_connus.append(enc)
        noms_connus.append((id_utilisateur, prenom, nom, service))
    except Exception:
        logging.exception("Erreur encodage %s (id=%s)", nom, id_utilisateur)

logging.info(f"{len(noms_connus)} utilisateurs chargés.")

# -------------------------
# SESSIONS HTTP
# -------------------------
session = requests.Session()
last_post_time = {}

def poster_pointage(id_user):
    payload = {"id_utilisateur": id_user}
    for attempt in range(HTTP_RETRIES):
        try:
            r = session.post(API_URL, json=payload, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                return True
        except Exception:
            time.sleep(1)
    return False

# -------------------------
# TRAITEMENT D'UNE CAMERA
# -------------------------
def traiter_camera(rtsp_url, nom_camera):
    global last_post_time

    while True:
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            logging.error(f"[{nom_camera}] Impossible d'accéder au flux. Nouvelle tentative dans 5s...")
            time.sleep(5)
            continue

        logging.info(f"[{nom_camera}] Flux connecté avec succès.")
        try:
            while True:
                ret, frame_bgr = cap.read()
                if not ret:
                    logging.warning(f"[{nom_camera}] Frame non lue. Reconnexion...")
                    break

                small_frame = cv2.resize(frame_bgr, (0,0), fx=0.5, fy=0.5)
                image_rgb = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                positions = face_recognition.face_locations(image_rgb)
                encs = face_recognition.face_encodings(image_rgb, positions)

                for (top, right, bottom, left), enc in zip(positions, encs):
                    scale = 2
                    top *= scale; right *= scale; bottom *= scale; left *= scale
                    nom_affiche = "Inconnu"

                    if len(encodages_connus) > 0:
                        distances = face_recognition.face_distance(encodages_connus, enc)
                        idx = np.argmin(distances)
                        best = distances[idx]

                        if best < SEUIL:
                            id_user, prenom_user, nom_user, service_user = noms_connus[idx]
                            nom_affiche = f"{prenom_user} {nom_user} - {service_user}"

                            now = datetime.now()
                            last = last_post_time.get(id_user)
                            if not last or (now - last).total_seconds() >= COOLDOWN_SEC:
                                if poster_pointage(id_user):
                                    last_post_time[id_user] = now
                                    jouer_son(SON_RECONNU)
                                    parler(f"Bienvenue {prenom_user} {nom_user}, service {service_user}")
                                    logging.info(f"[{nom_camera}] Pointage {nom_affiche}")
                        else:
                            jouer_son(SON_INCONNU)
                            parler("Visage non reconnu")

                    cv2.rectangle(frame_bgr, (left, top), (right, bottom), (0,255,0), 2)
                    cv2.putText(frame_bgr, nom_affiche, (left, top-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)

                cv2.imshow(nom_camera, frame_bgr)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    return

        except Exception as e:
            logging.error(f"[{nom_camera}] Erreur: {e}")
            logging.debug(traceback.format_exc())
        finally:
            cap.release()
            time.sleep(3)

# -------------------------
# LANCER LES THREADS
# -------------------------
threads = []
for i, url in enumerate(CAMERAS, 1):
    t = threading.Thread(target=traiter_camera, args=(url, f"Caméra {i}"), daemon=True)
    t.start()
    threads.append(t)

logging.info(f"{len(threads)} caméras en cours d'exécution.")
for t in threads:
    t.join()
