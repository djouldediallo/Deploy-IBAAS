from flask import Flask, jsonify, request, Response
from flask_sslify import SSLify
import os,json
import shutil
import yaml
import subprocess
import schedule
import time
import nmap
import json

from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
auth = HTTPBasicAuth()

from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
sslify = SSLify(app)

base_directory = 'config/users/'
MACHINE_MAC = ""
MACHINE_IP = ""

scheduler = BackgroundScheduler()
scheduler.start()

# On utilise cette variable pour stocker le nom de la machine courante
# ETAT, MAC, IP,
current_machine_name = ""
machines_dictionary = {}


with open('authorized_keys.yml', 'r') as f:
    data = yaml.load(f, Loader=yaml.FullLoader)

users = {}
for user in data['users']:
    username = user['username']
    password = user['password']
    users[username] = generate_password_hash(password)

@auth.verify_password
def verify_password(username, password):
    if username in users:
        return check_password_hash(users.get(username), password)
    return False

@app.route("/infra/<nom_ordinateur>/<os_name>/<username>", methods=["GET", "POST"])
@auth.login_required
def wake_on_lan_and_copy_file(nom_ordinateur, os_name, username):

    global current_machine_name
    global MACHINE_MAC
    global machines_dictionary

    # Chargement des données YAML à partir du fichier pour les etats des machines
    with open('config/adresse-mac/config.yml', 'r') as file:
        machines_dictionary = yaml.safe_load(file)


    # Si la machine n'est pas présente on l'ajoute dans le dictionnaire
    if not nom_ordinateur in machines_dictionary :
        machines_dictionary[nom_ordinateur] = {}

    #allumage du service dnsmasq
    subprocess.run(['systemctl', 'start', 'dnsmasq'])

    # Lecture du fichier YAML contenant les adresses MAC
    mac_file_path = 'config/adresse-mac/config.yml'
    mac_addresses = {}
    with open(mac_file_path, 'r') as mac_file:
        mac_addresses = yaml.safe_load(mac_file)

    # Récupération de l'adresse MAC de l'ordinateur
    MACHINE_MAC = mac_addresses.get(nom_ordinateur, {}).get('MAC', 'Ordinateur non trouvé')


    if MACHINE_MAC == 'Ordinateur non trouvé':
        return f"L'ordinateur '{nom_ordinateur}' n'a pas été enregistré"

    # On stocke le nom de l'ordinateur courant dans la variable currenr_machine
    current_machine_name = nom_ordinateur

    # Chemins des répertoires source et destination pour la copie du fichier utilisateur
    user_source_directory = os.path.join(base_directory, username, 'user-data')
    user_destination_directory = '/var/www/html/ks/'
    user_destination_file = os.path.join(user_destination_directory, 'user-data')

    # Suppression du fichier utilisateur existant dans le répertoire de destination
    if os.path.isfile(user_destination_file):
        os.remove(user_destination_file)

    # Vérification si le répertoire utilisateur existe
    if not os.path.exists(user_source_directory):
        return f"L'utilisateur '{username}' n'existe pas."

    # Copie du fichier utilisateur vers le répertoire de destination
    shutil.copy(user_source_directory, user_destination_file)

    # Chemins des répertoires source et destination pour la copie du fichier OS
    os_source_directory = 'config/os/'
    os_destination_directory = '/pxeboot/config/'
    os_source_file = os.path.join(os_source_directory, os_name)
    os_destination_file = os.path.join(os_destination_directory, os_name)

    # Vérification si le fichier OS existe
    if not os.path.isfile(os_source_file):
        return f"L'OS '{os_name}' n'existe pas"

    # Suppression des fichiers OS existants dans le répertoire de destination
    for file_name in os.listdir(os_destination_directory):
        file_path = os.path.join(os_destination_directory, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # Copie du fichier OS vers le répertoire de destination
    shutil.copy(os_source_file, os_destination_file)

    # Renommage du fichier OS en "boot.ipxe"
    renamed_destination_file = os.path.join(os_destination_directory, 'boot.ipxe')
    os.rename(os_destination_file, renamed_destination_file)

    # Envoi de la commande Wake-on-LAN pour allumer l'ordinateur correspondant
    wakeonlan_command = f"wakeonlan {MACHINE_MAC}"
    os.system(wakeonlan_command)

    # On change l'état de la machine en boot
    machines_dictionary[current_machine_name]["STATE"] = "boot"

    return f"L'ordinateur '{nom_ordinateur}' a été allumé."

@app.route('/stop')
def stop_dnsmasq():
    global MACHINE_MAC
    global machines_dictionary
    try:
        result = subprocess.run(['systemctl', 'stop', 'dnsmasq'], capture_output=True, text=True)
        if result.returncode == 0:
            print ("dnsmasq stopped success")

            # On change l'état de la machine en CONFIGURE
            machines_dictionary[current_machine_name]["STATE"] = "CONFIGURE"
        else:
            print ("Failed to stop dnsmasq")
    except Exception as e:
        print (str(e))


    scheduler.add_job (func = findIpForMachine, trigger="interval", seconds=5, id="find_ip")

    return "Stop dnsmasq"

def scan_network(mac_address):
    nma = nmap.PortScanner()
    nma.scan('192.168.1.0/24', arguments="--min-hostgroup 100 -F -sS -n -T4")
    result = []

    for ip in nma.all_hosts():
        host = nma[ip]
        mac = "-"
        vendorName = "-"

        if 'mac' in host['addresses']:
            mac = host['addresses']['mac']
            print(f"Comparing {mac.lower()} and {mac_address.lower()}: {mac.lower() == mac_address.lower()}")
            if (mac.lower() == mac_address.lower()) :
                print("FOUND")
                return ip

    return None

def findIpForMachine ():
    global MACHINE_IP
    global machines_dictionary

    print ("Searching Machine IP for MAC : {}".format(MACHINE_MAC))

    ip = scan_network (MACHINE_MAC)
    if (ip != None):
        scheduler.remove_job ("find_ip")
        MACHINE_IP = ip

        # On remplit l'IP et l'etat de la machine
        machines_dictionary[current_machine_name]["STATE"] = "on/ready"
        machines_dictionary[current_machine_name]["IP"] = ip

    # Enregistrement des données YAML dans le fichier
    with open('config/adresse-mac/config.yml', 'w') as file:
        yaml.safe_dump(machines_dictionary, file)

@app.route('/ip', methods=['GET'])
def get_ip():
    global MACHINE_IP
    return jsonify({'voici l\'ip de la machine qui a ete reserve': MACHINE_IP})

@app.route('/read', methods=['GET'])
def read():
    global reponse
    with open('config/adresse-mac/config.yml', 'r') as mac_file:
        machines_data = yaml.safe_load(mac_file)

    response = Response(response=yaml.dump(machines_data),
                        mimetype='text/plain')
    return response

