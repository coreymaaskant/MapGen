import csv
import io
from flask import Flask, render_template, request, Response

app = Flask(__name__)

def load_csv_data():
    masterlist = []
    rems = []
    
    # Load masterlist.csv
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
                
    # Load REMS.csv
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
    masterlist, rems = load_csv_data()
    # Initialize all 32 lines with "NA" as the default label
    loaded_data = {i: {"label": "NA"} for i in range(1, 33)}
    uploaded_filename = ""
    # Mapping labels to items for easy lookup in template
    masterlist_map = {item['label']: item for item in masterlist}

    # Handle .map file upload
    if request.method == 'POST' and 'upload_map' in request.files:
        file = request.files['upload_map']
        if file and file.filename != '':
            uploaded_filename = file.filename.rsplit('.', 1)[0]
            content = file.stream.read().decode("utf8")
            reader = csv.reader(io.StringIO(content))

            # Pre-build lookup tables for robust fallback matching
            label_lookup = {m['label']: m for m in masterlist}
            ip_lookup = {m['ip']: m for m in masterlist if m['ip'] != '0.0.0.0'}
            router_lookup = {m['router_in']: m for m in masterlist}

            for row in reader:
                # Format: cam_num, cam_id, ip, type, router_in, label
                if len(row) >= 6:
                    try:
                        idx = int(row[0].strip())
                        map_ip = row[2].strip()
                        map_router_in = row[4].strip()
                        map_label = row[5].strip()

                        match = None
                        # 1. Match by Label (Col 6)
                        if map_label in label_lookup:
                            match = label_lookup[map_label]
                        # 2. Match by IP (Col 3), skip if 0.0.0.0
                        elif map_ip != '0.0.0.0' and map_ip in ip_lookup:
                            match = ip_lookup[map_ip]
                        # 3. Match by Router Input (Col 5)
                        elif map_router_in in router_lookup:
                            match = router_lookup[map_router_in]

                        if match:
                            loaded_data[idx] = {"label": match['label'], "router_in": map_router_in}
                        else:
                            # Default back to NA if no criteria matches
                            loaded_data[idx] = {"label": "NA", "router_in": map_router_in}

                    except (ValueError, IndexError):
                        continue

    return render_template('index.html', masterlist=masterlist, rems=rems, loaded_data=loaded_data, masterlist_map=masterlist_map, uploaded_filename=uploaded_filename)

@app.route('/generate', methods=['POST'])
def generate():
    masterlist, _ = load_csv_data()
    # Create a map for quick lookup by label
    master_map = {item['label']: item for item in masterlist}
    
    output = io.StringIO()
    for i in range(1, 33):
        label = request.form.get(f'cam_{i}')
        rem_val = request.form.get(f'rem_{i}')
        
        data = master_map.get(label, {'cam_id': '99', 'ip': '0.0.0.0', 'type': 'S', 'router_in': '0', 'label': 'NA'})
        
        # Use REMS value for router input if camera is remote
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
    app.run(host='0.0.0.0', port=5000, debug=True)