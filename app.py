from flask import Flask
from routes import register_routes
import os

app = Flask(__name__)
app.secret_key = 'your_super_secret_key'

# Define the clips folder path
CLIPS_FOLDER = 'static/clips'
app.config['CLIPS_FOLDER'] = CLIPS_FOLDER

# Make sure the clips folder exists
os.makedirs(CLIPS_FOLDER, exist_ok=True)

# Register all routes
register_routes(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
