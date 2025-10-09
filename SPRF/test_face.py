import face_recognition #bibliothèque Python qui utilise dlib derrière pour détecter et reconnaître les visages. Elle simplifie énormément la reconnaissance faciale.
import cv2 #bibliothèque OpenCV pour le traitement et l’affichage d’images. On l’utilise ici pour dessiner des rectangles et afficher l’image.

# Charger l'image
image = face_recognition.load_image_file("images/Aissatou BIAYE Informatique.jpeg") #load_image_file() : charge une image depuis ton disque en mémoire sous forme de tableau NumPy.

# Trouver les positions des visages
face_locations = face_recognition.face_locations(image) #détecte tous les visages dans l’image. Renvoie une liste de tuples (top, right, bottom, left) pour chaque visage trouvé. Chaque tuple donne les coordonnées du rectangle entourant un visage
print(f"Nombre de visages trouvés : {len(face_locations)}")

# Convertir en BGR pour OpenCV
image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR) #OpenCV utilise BGR au lieu de RGB. cvtColor convertit l’image de RGB → BGR pour que les couleurs soient correctes lors de l’affichage.

# Dessiner des rectangles
for (top, right, bottom, left) in face_locations:
    cv2.rectangle(image_bgr, (left, top), (right, bottom), (0, 255, 0), 2)
    # Pour chaque visage détecté :
    # (top, right, bottom, left) : coordonnées du visage.
    # cv2.rectangle() : dessine un rectangle sur l’image.
    # (left, top) → coin supérieur gauche
    # (right, bottom) → coin inférieur droit
    # (0, 255, 0) → couleur verte en BGR
    # 2 → épaisseur du rectangle

# Redimensionner si l’image est trop grande
scale_percent = 50  # réduit à 50% (tu peux changer)
width = int(image_bgr.shape[1] * scale_percent / 100)
height = int(image_bgr.shape[0] * scale_percent / 100)
resized = cv2.resize(image_bgr, (width, height))
# On réduit l’image pour l’afficher plus facilement si elle est grande.
# image_bgr.shape → (hauteur, largeur, canaux)
# cv2.resize() → redimensionne l’image avec les nouvelles dimensions.

# Afficher le résultat
cv2.imshow("Resultat", resized)
cv2.waitKey(0)
cv2.destroyAllWindows()

# cv2.imshow() → ouvre une fenêtre pour montrer l’image.
# cv2.waitKey(0) → attend que tu appuies sur une touche pour continuer.
# cv2.destroyAllWindows() → ferme toutes les fenêtres ouvertes par OpenCV.


# Résultat : image est un tableau 3D (hauteur, largeur, canaux RGB).


# import face_recognition  # bibliothèque Python qui utilise dlib derrière pour détecter et reconnaître les visages
# import cv2  # bibliothèque OpenCV pour le traitement et l’affichage d’images

# # Charger l'image
# image = face_recognition.load_image_file("images/test.jpg")
# # load_image_file() : charge une image depuis ton disque en mémoire sous forme de tableau NumPy.

# # Trouver les positions des visages
# face_locations = face_recognition.face_locations(image)
# # détecte tous les visages dans l’image.
# # Renvoie une liste de tuples (top, right, bottom, left) pour chaque visage trouvé.
# # Chaque tuple donne les coordonnées du rectangle entourant un visage.
# print(f"Nombre de visages trouvés : {len(face_locations)}")

# # Convertir en BGR pour OpenCV
# image_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
# # OpenCV utilise BGR au lieu de RGB. cvtColor convertit l’image de RGB → BGR pour que les couleurs soient correctes lors de l’affichage.

# # Dessiner des rectangles et afficher le numéro de chaque visage
# for i, (top, right, bottom, left) in enumerate(face_locations, start=1):
#     # Dessiner le rectangle vert autour du visage
#     cv2.rectangle(image_bgr, (left, top), (right, bottom), (0, 255, 0), 2)
#     # cv2.putText() pour afficher le numéro du visage
#     cv2.putText(
#         image_bgr,            # image sur laquelle écrire
#         f"Visage {i}",        # texte à afficher
#         (left, top - 10),     # position du texte (au-dessus du rectangle)
#         cv2.FONT_HERSHEY_SIMPLEX, # police de caractères
#         0.8,                  # taille du texte
#         (0, 0, 255),          # couleur rouge en BGR
#         2                     # épaisseur du texte
#     )
#     # enumerate(face_locations, start=1) : permet de numéroter les visages à partir de 1

# # Redimensionner si l’image est trop grande
# scale_percent = 50  # réduit à 50% (tu peux changer)
# width = int(image_bgr.shape[1] * scale_percent / 100)
# height = int(image_bgr.shape[0] * scale_percent / 100)
# resized = cv2.resize(image_bgr, (width, height))
# # On réduit l’image pour l’afficher plus facilement si elle est grande.
# # image_bgr.shape → (hauteur, largeur, canaux)
# # cv2.resize() → redimensionne l’image avec les nouvelles dimensions.

# # Afficher le résultat
# cv2.imshow("Resultat", resized)
# cv2.waitKey(0)
# cv2.destroyAllWindows()
# # cv2.imshow() → ouvre une fenêtre pour montrer l’image.
# # cv2.waitKey(0) → attend que tu appuies sur une touche pour continuer.
# # cv2.destroyAllWindows() → ferme toutes les fenêtres ouvertes par OpenCV.
