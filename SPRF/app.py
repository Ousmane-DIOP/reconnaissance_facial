from flask import Flask, flash, render_template, request, redirect, url_for, session, jsonify, send_file
from flask_socketio import SocketIO, emit
from db_config import obtenir_connexion
from datetime import datetime, time, timedelta
import bcrypt
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from openpyxl import Workbook
from openpyxl.styles import Alignment
from reportlab.lib.utils import ImageReader
import base64
import sys


app = Flask(__name__)
app.secret_key = "super_secret_key"  # ⚠️ à changer en production
socketio = SocketIO(app)


# -------------------------------
# AUTHENTIFICATION ADMIN
# -------------------------------
def verifier_admin(username, password):
    connexion = obtenir_connexion()
    cur = connexion.cursor(dictionary=True)
    cur.execute("SELECT * FROM admins WHERE username=%s", (username,))
    admin = cur.fetchone()
    cur.close()
    connexion.close()

    if admin and bcrypt.checkpw(password.encode(), admin["password"].encode()):
        return True
    return False


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if verifier_admin(username, password):
            session["admin"] = username
            return redirect(url_for("dashboard"))
        else:
            return render_template("login.html", erreur="Identifiants invalides")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))


# -------------------------------
# AJOUT UTILISATEURS
# -------------------------------
@app.route("/api/add_user", methods=["POST"])
def api_add_user():
    """
    Ajout d'un utilisateur :
    - Vérifie s'il existe déjà (par nom).
    - Si existe -> ignore ou met à jour si --force-update est fourni.
    """
    data = request.json
    nom = data.get("nom")
    chemin_images = data.get("chemin_images")
    force_update = data.get("force_update", False)  # <--- option ajoutée

    if not nom or not chemin_images:
        return {"status": "error", "message": "Nom ou chemin_images manquant"}, 400

    connexion = obtenir_connexion()
    cur = connexion.cursor(dictionary=True)

    # Vérifier si utilisateur existe déjà
    cur.execute("SELECT id FROM utilisateurs WHERE nom = %s", (nom,))
    existing = cur.fetchone()

    if existing:
        if force_update:
            cur.execute(
                "UPDATE utilisateurs SET chemin_images = %s WHERE id = %s",
                (chemin_images, existing["id"])
            )
            connexion.commit()
            message = f"Utilisateur {nom} mis à jour avec succès (--force-update)."
            status = "updated"
        else:
            message = f"L'utilisateur {nom} existe déjà, ignoré."
            status = "exists"

        cur.close()
        connexion.close()
        return {"status": status, "message": message}

    # Sinon insérer
    cur.execute(
        "INSERT INTO utilisateurs (nom, chemin_images) VALUES (%s, %s)",
        (nom, chemin_images)
    )
    connexion.commit()
    cur.close()
    connexion.close()

    return {"status": "ok", "message": f"Utilisateur {nom} ajouté avec succès."}


# -------------------------------
# TABLEAU DE BORD ADMIN
# -------------------------------
@app.route("/")
def dashboard():
    date_str = request.args.get("date")
    service = request.args.get("service")
    statut = request.args.get("statut")

    connexion = obtenir_connexion()
    curseur = connexion.cursor(dictionary=True)

    query = """
        SELECT u.prenom, u.nom, u.service, p.date_pointage, p.heure_arrivee, p.heure_sortie, p.statut
        FROM utilisateurs u
        LEFT JOIN pointages p ON u.id = p.id_utilisateur
        WHERE 1=1
    """
    params = []

    # 🔹 Filtrer par date
    if date_str:
        query += " AND DATE(p.date_pointage) = %s"
        params.append(date_str)
    else:
        query += " AND DATE(p.date_pointage) = CURDATE()"

    # 🔹 Filtrer par service
    if service:
        query += " AND u.service = %s"
        params.append(service)

    # 🔹 Filtrer par statut
    if statut:
        query += " AND p.statut = %s"
        params.append(statut)

    query += " ORDER BY p.date_pointage DESC, p.heure_arrivee ASC"

    curseur.execute(query, params)
    utilisateurs = curseur.fetchall()

    # 🔹 Liste distincte des services
    curseur.execute("SELECT DISTINCT service FROM utilisateurs ORDER BY service")
    services = [row["service"] for row in curseur.fetchall()]

    # 🔹 Liste des employés
    curseur.execute("SELECT id, prenom, nom FROM utilisateurs ORDER BY prenom, nom")
    employes = curseur.fetchall()

    curseur.close()
    connexion.close()

    return render_template(
        "admin_dashboard.html",
        utilisateurs=utilisateurs,
        date_pointage=datetime.now(),
        services=services,
        employes=employes
    )



# -------------------------------
# EXPORTATION EXCEL / PDF
# -------------------------------
@app.route("/export", methods=["POST"])
def export_records():
    if "admin" not in session:
        return redirect(url_for("login"))

    export_format = request.form.get("format")
    export_type = request.form.get("export_type")  # all ou month
    mois = request.form.get("mois")

    connexion = obtenir_connexion()
    query = """
        SELECT u.id, u.prenom, u.nom, u.service, p.date_pointage, p.heure_arrivee, p.heure_sortie, p.statut
        FROM utilisateurs u
        LEFT JOIN pointages p ON u.id = p.id_utilisateur
    """
    params = []

    # 🔎 Filtrer si un mois a été choisi
    if export_type == "month" and mois:
        query += " WHERE MONTH(p.date_pointage) = %s"
        params.append(int(mois))

    cur = connexion.cursor(dictionary=True)
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    cur.close()
    connexion.close()

    if not rows:
        flash("Aucun enregistrement trouvé pour ce filtre.", "warning")
        return redirect(url_for("dashboard"))

    # ✅ Normaliser les heures avant DataFrame
    for row in rows:
        if row["heure_arrivee"]:
            row["heure_arrivee"] = str(row["heure_arrivee"])[:8]
        else:
            row["heure_arrivee"] = ""
        if row["heure_sortie"]:
            row["heure_sortie"] = str(row["heure_sortie"])[:8]
        else:
            row["heure_sortie"] = ""

    df = pd.DataFrame(rows)

    # ------------------ Excel ------------------
    if export_format == "excel":
        output = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Pointages"

        # ✅ Entêtes
        headers = ["ID", "Prenom", "Nom", "Service", "Date", "Arrivée", "Sortie", "Statut"]
        ws.append(headers)

        from datetime import date, time, datetime

        for row in rows:
            # 🔎 Conversion correcte
            date_val = None
            if row.get("date_pointage"):
                if isinstance(row["date_pointage"], (datetime, date)):
                    date_val = row["date_pointage"]
                else:
                    date_val = datetime.strptime(str(row["date_pointage"]), "%Y-%m-%d").date()

            arrivee_val = None
            if row.get("heure_arrivee"):
                if isinstance(row["heure_arrivee"], (datetime, time)):
                    arrivee_val = row["heure_arrivee"]
                else:
                    arrivee_val = datetime.strptime(str(row["heure_arrivee"]), "%H:%M:%S").time()

            sortie_val = None
            if row.get("heure_sortie"):
                if isinstance(row["heure_sortie"], (datetime, time)):
                    sortie_val = row["heure_sortie"]
                else:
                    sortie_val = datetime.strptime(str(row["heure_sortie"]), "%H:%M:%S").time()

            ws.append([
                row.get("id"),
                row.get("prenom"),
                row.get("nom"),
                row.get("service"),
                date_val,
                arrivee_val,
                sortie_val,
                row.get("statut")
            ])

        # ✅ Ajuster largeur colonnes
        for col in ws.columns:
            max_length = max(len(str(cell.value)) if cell.value else 0 for cell in col)
            ws.column_dimensions[col[0].column_letter].width = max_length + 2

        # ✅ Appliquer format date / heure (colonne 5 = Date, 6 = Arrivée, 7 = Sortie)
        for row in ws.iter_rows(min_row=2, min_col=5, max_col=7):
            date_cell, arrivee_cell, sortie_cell = row
            if date_cell.value:
                date_cell.number_format = "DD/MM/YYYY"
            if arrivee_cell.value:
                arrivee_cell.number_format = "HH:MM:SS"
            if sortie_cell.value:
                sortie_cell.number_format = "HH:MM:SS"

        wb.save(output)
        output.seek(0)
        return send_file(output, download_name="pointages.xlsx", as_attachment=True)

    # ------------------ PDF ------------------
    elif export_format == "pdf":
        output = BytesIO()

        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        )
        from reportlab.lib.styles import getSampleStyleSheet

        doc = SimpleDocTemplate(output, pagesize=letter)
        elements = []
        styles = getSampleStyleSheet()

        # Titre dynamique
        if export_type == "month" and mois:
            titre = f"Rapport de pointage - Mois {mois}"
        else:
            titre = "Rapport de pointage - Tous"

        elements.append(Paragraph(titre, styles['Title']))
        elements.append(Spacer(1, 12))

        # Tableau
        data = [["ID", "Prenom", "Nom", "Service", "Date", "Arrivée", "Sortie", "Statut"]]
        for index, row in df.iterrows():
            data.append([
                row.get("id", ""),
                row.get("prenom", ""),
                row.get("nom", ""),
                row.get("service", ""),
                str(row.get("date_pointage", "")),
                row.get("heure_arrivee", ""),
                row.get("heure_sortie", ""),
                row.get("statut", "")
            ])

        table = Table(data, repeatRows=1, hAlign="CENTER")
        style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ])

        # ✅ Mise en couleur dynamique
        for i, row in enumerate(data[1:], start=1):
            statut = row[5]
            if statut == "a_l_heure":
                style.add('BACKGROUND', (5, i), (5, i), colors.lightgreen)
            elif statut == "retard":
                style.add('BACKGROUND', (5, i), (5, i), colors.orange)
            elif statut == "absent":
                style.add('BACKGROUND', (5, i), (5, i), colors.red)

        table.setStyle(style)
        elements.append(table)
        doc.build(elements)

        output.seek(0)
        return send_file(output, download_name="pointages.pdf", as_attachment=True)

    else:
        flash("Format d'exportation non valide.", "danger")
        return redirect(url_for("dashboard"))


# -------------------------------
# API POUR AJOUTER / METTRE À JOUR POINTAGES
# -------------------------------
@app.route("/api/pointage", methods=["POST"])
def api_pointage():
    """
    Appelée depuis recognize.py quand un utilisateur est détecté.
    - Si pas encore pointé aujourd'hui => enregistre arrivée + statut
    - Si déjà arrivé mais pas encore sorti => met à jour la sortie
    """
    data = request.json
    id_utilisateur = data.get("id_utilisateur")

    if not id_utilisateur:
        return {"status": "error", "message": "id_utilisateur manquant"}, 400

    maintenant = datetime.now()
    heure_actuelle = maintenant.time()
    date_aujourdhui = maintenant.date()

    # Déterminer statut
    if heure_actuelle <= time(8, 30):
        statut = "a_l_heure"
    elif heure_actuelle <= time(9, 30):
        statut = "retard"
    else:
        statut = "absent"

    connexion = obtenir_connexion()
    cur = connexion.cursor(dictionary=True)

    # Vérifier si déjà pointé aujourd'hui
    cur.execute("""
        SELECT * FROM pointages 
        WHERE id_utilisateur = %s AND date_pointage = %s
    """, (id_utilisateur, date_aujourdhui))
    pointage = cur.fetchone()

    if not pointage:
        # Premier pointage du jour
        cur.execute("""
            INSERT INTO pointages (id_utilisateur, date_pointage, heure_arrivee, statut)
            VALUES (%s, %s, %s, %s)
        """, (id_utilisateur, date_aujourdhui, heure_actuelle, statut))
        connexion.commit()

        nouveau_pointage = {
            "id_utilisateur": id_utilisateur,
            "date_pointage": str(date_aujourdhui),
            "heure_arrivee": str(heure_actuelle),
            "heure_sortie": None,
            "statut": statut
        }
        notifier_nouveau_pointage(nouveau_pointage)

    else:
        # Déjà arrivé => mettre sortie
        cur.execute("""
            UPDATE pointages 
            SET heure_sortie = %s
            WHERE id = %s
        """, (heure_actuelle, pointage["id"]))
        connexion.commit()

        pointage["heure_sortie"] = str(heure_actuelle)
        notifier_nouveau_pointage(pointage)

    cur.close()
    connexion.close()
    return {"status": "ok"}


# -------------------------------
# API : DERNIERS POINTAGES
# -------------------------------
@app.route("/api/pointages")
def api_pointages():
    connexion = obtenir_connexion()
    cur = connexion.cursor(dictionary=True)
    cur.execute("""
        SELECT p.*, u.nom 
        FROM pointages p
        JOIN utilisateurs u ON u.id = p.id_utilisateur
        ORDER BY p.date_pointage DESC, p.heure_arrivee DESC
        LIMIT 20
    """)
    data = cur.fetchall()
    cur.close()
    connexion.close()
    return jsonify(data)


# -------------------------------
# STATISTIQUES
# -------------------------------
@app.route("/statistiques")
def statistiques():
    connexion = obtenir_connexion()
    curseur = connexion.cursor(dictionary=True)

    # 🔹 Récupérer la liste des services depuis la table utilisateurs
    curseur.execute("SELECT DISTINCT service FROM utilisateurs ORDER BY service")
    services = [row["service"] for row in curseur.fetchall()]

    # 🔹 Récupérer les statistiques globales (tous services confondus)
    curseur.execute("""
        SELECT statut, COUNT(*) as total
        FROM pointages
        GROUP BY statut
    """)
    rows = curseur.fetchall()

    curseur.close()
    connexion.close()

    # 🔹 Initialiser à 0 si aucune donnée
    stats = {"a_l_heure": 0, "retard": 0, "absent": 0}
    for row in rows:
        stats[row["statut"]] = row["total"]

    # 🔹 Rendre la page avec les services et les stats initiales
    return render_template(
        "statistiques.html",
        a_l_heure=stats["a_l_heure"],
        retard=stats["retard"],
        absent=stats["absent"],
        services=services
    )


@app.route("/api/statistiques")
def api_statistiques():
    periode = request.args.get("periode", "jour")
    service = request.args.get("service", "").strip()

    connexion = obtenir_connexion()
    curseur = connexion.cursor(dictionary=True)

    # 🔹 Base de la requête : jointure entre pointages et utilisateurs
    query = """
        SELECT p.statut, COUNT(*) AS total
        FROM pointages p
        JOIN utilisateurs u ON p.id_utilisateur = u.id
        WHERE 1=1
    """
    params = []

    # 🔹 Filtrer selon la période
    if periode == "jour":
        query += " AND DATE(p.date_pointage) = CURDATE()"
    elif periode == "semaine":
        query += " AND YEARWEEK(p.date_pointage, 1) = YEARWEEK(CURDATE(), 1)"
    elif periode == "mois":
        query += " AND YEAR(p.date_pointage) = YEAR(CURDATE()) AND MONTH(p.date_pointage) = MONTH(CURDATE())"

    # 🔹 Filtrer selon le service sélectionné
    if service:
        query += " AND u.service = %s"
        params.append(service)

    query += " GROUP BY p.statut"

    # 🔹 Exécution
    curseur.execute(query, params)
    rows = curseur.fetchall()

    curseur.close()
    connexion.close()

    # 🔹 Initialiser les valeurs
    stats = {"a_l_heure": 0, "retard": 0, "absent": 0}
    for row in rows:
        stats[row["statut"]] = row["total"]

    return jsonify(stats)

# -------------------------------
# EXPORTATION STATISTIQUES EN PDF
# -------------------------------
sys.stdout = sys.stderr
@app.route("/export-statistiques", methods=["POST"])
def export_statistiques():
    try:
        service = request.form.get("service", "tous")
        periode = request.form.get("periode", "jour")

        # 🔹 Images base64 des graphes
        chart1_data = request.form.get("chart1")
        chart2_data = request.form.get("chart2")

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        pdf.setTitle("Statistiques de présence")

        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(80, 800, f"📊 Statistiques de présence ({periode})")
        pdf.drawString(80, 785, f"Service : {service.upper()}")

        y = 740

        # 🔹 Insérer les graphiques si fournis
        if chart1_data and chart2_data:
            img1 = ImageReader(BytesIO(base64.b64decode(chart1_data.split(",")[1])))
            img2 = ImageReader(BytesIO(base64.b64decode(chart2_data.split(",")[1])))

            pdf.drawImage(img1, 60, y - 250, width=220, height=220, preserveAspectRatio=True)
            pdf.drawImage(img2, 320, y - 250, width=220, height=220, preserveAspectRatio=True)
            y -= 270
        else:
            pdf.setFont("Helvetica", 12)
            pdf.drawString(80, y, "⚠️ Graphiques non disponibles.")
            y -= 20

        # 🔹 Ajouter une section texte en dessous (résumé)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(80, y - 20, "Résumé des Statistiques :")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(100, y - 40, f"Période : {periode}")
        pdf.drawString(100, y - 55, f"Service : {service if service != 'tous' else 'Tous les services'}")

        pdf.showPage()
        pdf.save()
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name=f"statistiques_{service}_{periode}.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        print("❌ ERREUR EXPORT:", e)
        return jsonify({"error": str(e)}), 500

# -------------------------------
# SOCKET.IO : TEMPS RÉEL
# -------------------------------
def notifier_nouveau_pointage(pointage):
    socketio.emit("nouveau_pointage", pointage, broadcast=True)


@app.route("/api/notifier", methods=["POST"])
def api_notifier():
    data = request.json
    notifier_nouveau_pointage(data)
    return {"status": "ok"}


# -------------------------------
# MAIN
# -------------------------------
if __name__ == "__main__":
    socketio.run(app, debug=True)
