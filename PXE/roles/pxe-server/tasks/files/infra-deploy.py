import time
import yaml
import os
import requests
import sys
import subprocess
from getpass import getpass

def call_curl(nom_ordinateur, os_name, username):
    # Récupération de l'utilisateur courant connecté
    current_user = os.getlogin()

    # Appel de la route du serveur Flask
    #url = f"https://127.0.0.1:5000/infra/{nom_ordinateur}/{os_name}/{current_user}"

    # Demande du nom d'utilisateur et du mot de passe
    username = input("Entrez votre nom d'utilisateur : ")
    password = getpass("Entrez votre mot de passe : ")

    # Appel de la route du serveur Flask en utilisant les informations saisies
    url = f"https://{username}:{password}@127.0.0.1:5000/infra/{nom_ordinateur}/{os_name}/{current_user}"

    # Appel de la commande curl
    subprocess.call(['curl', '-k', url])

def check_machine_state(nom_ordinateur):
    while True:
        url = "https://127.0.0.1:5000/read"
        with open(os.devnull, 'w') as null_file:
            response = subprocess.check_output(['curl', '-k', url], stderr=null_file)
        machines_data = yaml.safe_load(response.decode('utf-8'))

        #url = "https://127.0.0.1:5000/read"
        #response = subprocess.check_output(['curl', '-k', url])
        #machines_data = yaml.safe_load(response.decode('utf-8'))


        machine_info =machines_data.get(nom_ordinateur)
        if machine_info['STATE'] == 'on/ready':

            # Appelle de la route ip
            url=f"https://127.0.0.1:5000/ip"
            subprocess.call(['curl', '-k', url])
            break

        #attente avant la prochaine verification
        time.sleep(3)


if __name__ == '__main__':

    # Vérification si les arguments sont corrects
    if len(sys.argv) != 3:
        print("Veuillez fournir les arguments au format <nom_ordinateur> <os_name>")
        sys.exit(1)

    # Extraire les arguments
    nom_ordinateur = sys.argv[1]
    os_name = sys.argv[2]

    # Appel de la fonction avec les arguments fournis
    call_curl(nom_ordinateur, os_name, os.getlogin())

    check_machine_state(nom_ordinateur)

