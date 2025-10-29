# -*- coding: utf-8 -*-
import os
import uuid
import logging
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

IMAGE_FOLDER = 'images'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

ACCIDENT_LOG = []

os.makedirs(IMAGE_FOLDER, exist_ok=True)

app.config['IMAGE_FOLDER'] = IMAGE_FOLDER


def generate_priority_string(seat_data):
    scores = [data.get('score', 0) for data in seat_data.values()]
    max_score = max(scores) if scores else 0
    return str(max_score)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index14.html')

@app.route('/api/accident_trigger', methods=['POST'])
def accident_trigger():
    try:
        data = request.get_json()
        seat_data = {key: data[key] for key in data if key.startswith('seat')}

        if not seat_data:
            return jsonify({'error': 'Missing required seat data'}), 400

        accident_id = str(uuid.uuid4())

        now = datetime.now()
        priority_str = generate_priority_string(seat_data)

        log_entry = {
            'id': accident_id,
            'year': now.strftime('%Y'),
            'month': now.strftime('%m'),
            'day': now.strftime('%d'),
            'hour': now.strftime('%H'),
            'minute': now.strftime('%M'),
            'second': now.strftime('%S'),
            'priority_score': priority_str,
            'seat_details': seat_data,
            'image_url': None,
            'player_url': f'/player/{accident_id}'
        }

        ACCIDENT_LOG.insert(0, log_entry)
        logger.info(f"Accident Logged: ID={accident_id}, Max Score={priority_str}")

        return jsonify({'status': 'Accident logged', 'id': accident_id, 'log_entry': log_entry})
    except Exception as e:
        logger.error(f"Error processing accident trigger: {e}")
        return jsonify({'error': f'Invalid request or server error: {e}'}), 500


@app.route('/api/upload_image/<accident_id>', methods=['POST'])
def upload_image(accident_id):

    log_entry = next((log for log in ACCIDENT_LOG if log['id'] == accident_id), None)
    if not log_entry:
        return jsonify({'error': 'Accident ID not found.'}), 404

    if 'file' not in request.files:
        return jsonify({'error': 'No file part in the request.'}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file.'}), 400

    if file and allowed_file(file.filename):
        filename = f"{accident_id}.jpg"
        save_path = os.path.join(app.config['IMAGE_FOLDER'], filename)

        try:
            file.save(save_path)

            log_entry['image_url'] = f'/image/{filename}'
            logger.info(f"Image uploaded for ID {accident_id} to {save_path}")

            return jsonify({'status': 'Image uploaded successfully', 'image_url': log_entry['image_url']}), 200

        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return jsonify({'error': f'Failed to save image: {e}'}), 500

    return jsonify({'error': 'File type not allowed.'}), 400

@app.route('/image/<filename>')
def serve_image(filename):
    return send_from_directory(app.config['IMAGE_FOLDER'], filename)

@app.route('/accidents')
def accident_list():
    return jsonify(ACCIDENT_LOG)

@app.route('/player/<accident_id>')
def player(accident_id):
    log_entry = next((log for log in ACCIDENT_LOG if log['id'] == accident_id), {})

    return render_template(
        'player14.html',
        accident_id=accident_id,
        priority_score=log_entry.get('priority_score', 'N/A'),
        seat_details=log_entry.get('seat_details', {}),
        image_url=log_entry.get('image_url')
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
