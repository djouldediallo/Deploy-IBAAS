from flask import Flask
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import yaml


auth = HTTPBasicAuth()

app = Flask(__name__)


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
    return false

@app.route('/hello')
@auth.login_required
def hello_world():
    return 'Hello, World!'
