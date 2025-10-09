import mysql.connector

def obtenir_connexion():
    connexion = mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="systeme_pointage"
    )
    return connexion
