# Shotoku Map Generator - Flask Application
#
# Simple Flask app that loads camera metadata from CSV files,
# allows uploading a .map file for review, and generates a new
# downloadable .map file based on the current selections.

import csv
import io
from flask import Flask, render_template, request, Response

app = Flask(__name__)

def load_csv_data():
    """Load the camera master list and REMS entries from CSV files."""
    masterlist = []
    rems = []
    
    # Load masterlist.csv and convert each row into a dict for easy access.
    with open('/home/ubuntu/MapGen/masterlist.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                masterlist.append({
                    'id': row[0],
                    'cam_id': row[1],
                    'ip': row[2],
                    'type': row[3],
                    'router_in': row[4],
                    'label': row[5],
                    'location': row[6].strip().lower()
                })
                
    # Load REMS.csv and keep each value-label pair for remote routing.
    with open('/home/ubuntu/MapGen/REMS.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if row:
                rems.append({
                    'val': row[0],
                    'label': row[1]
                })
    return masterlist, rems

@app.route('/', methods=['GET', 'POST'])
def home():
    """Render the main page and optionally parse an uploaded .map file."""
    masterlist, rems = load_csv_data()

    # Initialize all 32 map positions using a default label of NA.
    loaded_data = {i: {'label': 'NA'} for i in range(1, 33)}
    uploaded_filename = ''

    # Use a map for quick access to masterlist entries by label.
    masterlist_map = {item['label']: item for item in masterlist}

    # If a map file is uploaded, parse it and replace default values.
    if request.method == 'POST' and 'upload_map' in request.files:
        file = request.files['upload_map']
        if file and file.filename != '':
            uploaded_filename = file.filename.rsplit('.', 1)[0]
            content = file.stream.read().decode('utf8')
            reader = csv.reader(io.StringIO(content))

            # Build lookup tables for matching uploaded rows to masterlist entries.
            label_lookup = {m['label']: m for m in masterlist}
            ip_lookup = {m['ip']: m for m in masterlist if m['ip'] != '0.0.0.0'}
            router_lookup = {m['router_in']: m for m in masterlist}

            for row in reader:
                # Expected uploaded row format: idx, cam_id, ip, type, router_in, label
                if len(row) >= 6:
                    try:
                        idx = int(row[0].strip())
                        map_ip = row[2].strip()
                        map_router_in = row[4].strip()
                        map_label = row[5].strip()

                        match = None

                        # Try to match by label first, then IP, then router input.
                        if map_label in label_lookup:
                            match = label_lookup[map_label]
                        elif map_ip != '0.0.0.0' and map_ip in ip_lookup:
                            match = ip_lookup[map_ip]
                        elif map_router_in in router_lookup:
                            match = router_lookup[map_router_in]

                        if match:
                            loaded_data[idx] = {
                                'label': match['label'],
                                'router_in': map_router_in
                            }
                        else:
                            # Keep NA if nothing could be matched.
                            loaded_data[idx] = {
                                'label': 'NA',
                                'router_in': map_router_in
                            }

                    except (ValueError, IndexError):
                        # Ignore malformed lines and continue processing.
                        continue

    return render_template(
        'index.html',
        masterlist=masterlist,
        rems=rems,
        loaded_data=loaded_data,
        masterlist_map=masterlist_map,
        uploaded_filename=uploaded_filename
    )

@app.route('/generate', methods=['POST'])
def generate():
    """Generate a camera map file from the submitted form selection."""
    masterlist, _ = load_csv_data()

    # Create a map for quick lookup by label.
    master_map = {item['label']: item for item in masterlist}
    
    output = io.StringIO()
    for i in range(1, 33):
        label = request.form.get(f'cam_{i}')
        rem_val = request.form.get(f'rem_{i}')
        
        data = master_map.get(label, {'cam_id': '99', 'ip': '0.0.0.0', 'type': 'S', 'router_in': '0', 'label': 'NA'})
        
        # Use REMS value for router input when the selected camera is remote.
        router_input = rem_val if rem_val and data.get('location') == 'remote' else data['router_in']
        
        line = f"{i}, {data['cam_id']}, {data['ip']}, {data['type']}, {router_input}, {data['label']}\n"
        output.write(line)

    filename = request.form.get('filename', 'camera_map').strip()
    if not filename:
        filename = 'camera_map'
    if not filename.endswith('.map'):
        filename += '.map'

    return Response(
        output.getvalue(),
        mimetype="text/plain",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

if __name__ == '__main__':
    # Start the Flask development server.
    app.run(host='0.0.0.0', port=5000, debug=True)