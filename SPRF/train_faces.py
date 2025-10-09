import face_recognition
import cv2
import numpy as np
import pickle
import os
import argparse
from db_config import obtenir_connexion

# -------- Arguments --------
parser = argparse.ArgumentParser(description="Enregistrer des visages dans la base")
parser.add_argument(
    "--force-update",
    action="store_true",
    help="Met à jour l'encodage si l'utilisateur existe déjà"
)
args = parser.parse_args()

# Dossier contenant les photos des personnes connues
dossier_connus = "images/connues"

# Connexion à la base
connexion = obtenir_connexion()
curseur = connexion.cursor()

for fichier in os.listdir(dossier_connus):
    chemin_image = os.path.join(dossier_connus, fichier)

    # Charger l'image
    image = face_recognition.load_image_file(chemin_image)

    # Extraire l'encodage du visage
    encodages = face_recognition.face_encodings(image)

    if len(encodages) > 0:
        encodage = encodages[0]

        # Convertir l'encodage en binaire
        encodage_binaire = pickle.dumps(encodage)

        # Nom du fichier sans extension (ex: "ousmane diop informatique")
        nom_complet = os.path.splitext(fichier)[0]

        # Découper en parties
        parties = nom_complet.split(" ")

        if len(parties) < 3:
            print(f"[ERREUR] Le fichier '{fichier}' doit être au format: prenom nom service")
            continue

        prenom, nom, service = parties[0], parties[1], " ".join(parties[2:])

        # Vérifier si l'utilisateur existe déjà
        curseur.execute(
            "SELECT id FROM utilisateurs WHERE prenom = %s AND nom = %s AND service = %s",
            (prenom, nom, service),
        )
        resultat = curseur.fetchone()

        if resultat:
            if args.force_update:
                curseur.execute(
                    "UPDATE utilisateurs SET encodage = %s, service = %s WHERE prenom = %s AND nom = %s",
                    (encodage_binaire, service, prenom, nom),
                )
                connexion.commit()
                print(f"[MAJ] Encodage de {prenom} {nom} mis à jour (service={service}).")
            else:
                print(f"[IGNORÉ] {prenom} {nom} {service} existe déjà.")
        else:
            # Sinon, insertion
            curseur.execute(
                "INSERT INTO utilisateurs (prenom, nom, service, encodage) VALUES (%s, %s, %s, %s)",
                (prenom, nom, service, encodage_binaire),
            )
            connexion.commit()
            print(f"[OK] {prenom} {nom} ({service}) enregistré avec succès.")

curseur.close()
connexion.close()
