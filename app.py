# app.py
from flask import Flask, request, jsonify, send_from_directory, redirect, url_for, session
from neo4j import GraphDatabase
import traceback
from flask_cors import CORS
import os
from datetime import datetime # Import datetime for dynamic sync date

URI = "neo4j://neo4j:7680" 
USERNAME = "username"
PASSWORD = "password!"
DATABASE = "verification"

driver = None
try:
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    # Test connection by running a simple query
    with driver.session(database=DATABASE) as session:
        session.run("RETURN 1")
    print("--- Koneksi ke Neo4j berhasil terjalin! ---")
except Exception as e:
    print(f"--- Gagal terhubung ke Neo4j: {e} ---")
    print("Pastikan Neo4j di VM berjalan, IP dan port benar, serta tidak ada masalah firewall/VPN.")
    driver = None # Set driver to None if connection fails

# --- 2. Inisialisasi Aplikasi Flask ---
app = Flask(__name__, static_folder='.', static_url_path='') 

# Konfigurasi SECRET_KEY untuk manajemen sesi (penting untuk fitur sesi Flask)
# Ganti dengan kunci yang lebih kuat di produksi
app.secret_key = os.urandom(24) 

# Konfigurasi CORS
CORS(app, resources={
    r"/v1/*": {
        "origins": [
            "http://localhost:8000", 
            "http://127.0.0.1:5000", 
            "http://localhost:5000",
            "http://localhost:5500",  # Contoh untuk Live Server VS Code
            "http://127.0.0.1:5500",  # Contoh untuk Live Server VS Code
            "http://localhost:3000",  # Contoh untuk React/Vue/Angular dev server
            "http://127.0.0.1:3000",
            "null"  # PENTING: Untuk membuka index.html langsung dari browser (file:// protocol)
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": [],
        "supports_credentials": True
    }
})

# --- Fungsi Helper untuk Format Node/Relationship ke Dictionary (EXISTING) ---
def format_neo4j_entity(entity):
    """Formats a Neo4j Node or Relationship object into a dictionary."""
    if hasattr(entity, 'labels'): # It's a Node
        entity_id = str(entity.id)
        # Prioritize specific properties for ID if available
        if 'User' in entity.labels and entity.get('nik'): entity_id = entity.get('nik')
        elif 'Email' in entity.labels and entity.get('email_address'): entity_id = entity.get('email_address')
        elif 'Phone' in entity.labels and entity.get('phone_number'): entity_id = entity.get('phone_number')
        elif 'Company' in entity.labels and entity.get('company_id'): entity_id = entity.get('company_id')
        
        return {
            "id": entity_id,
            "labels": list(entity.labels),
            "properties": dict(entity)
        }
    elif hasattr(entity, 'type'): # It's a Relationship
        # Ensure start_node and end_node are accessible
        start_node_id = None
        end_node_id = None
        # Access properties directly from start_node/end_node objects
        # Note: In some Neo4j driver versions, start_node/end_node might be just IDs or dicts
        # This assumes they are full Node objects
        if hasattr(entity, 'start_node') and entity.start_node:
            if 'User' in entity.start_node.labels and entity.start_node.get('nik'):
                start_node_id = entity.start_node.get('nik')
            elif 'Email' in entity.start_node.labels and entity.start_node.get('email_address'):
                start_node_id = entity.start_node.get('email_address')
            elif 'Phone' in entity.start_node.labels and entity.start_node.get('phone_number'):
                start_node_id = entity.start_node.get('phone_number')
            elif 'Company' in entity.start_node.labels and entity.start_node.get('company_id'):
                start_node_id = entity.start_node.get('company_id')
            else:
                start_node_id = str(entity.start_node.id)

        if hasattr(entity, 'end_node') and entity.end_node:
            if 'User' in entity.end_node.labels and entity.end_node.get('nik'):
                end_node_id = entity.end_node.get('nik')
            elif 'Email' in entity.end_node.labels and entity.end_node.get('email_address'):
                end_node_id = entity.end_node.get('email_address')
            elif 'Phone' in entity.end_node.labels and entity.end_node.get('phone_number'):
                end_node_id = entity.end_node.get('phone_number')
            elif 'Company' in entity.end_node.labels and entity.end_node.get('company_id'):
                end_node_id = entity.end_node.get('company_id')
            else:
                end_node_id = str(entity.end_node.id)

        return {
            "id": str(entity.id),
            "type": entity.type,
            "start_node_id": start_node_id,
            "end_node_id": end_node_id,
            "properties": dict(entity)
        }
    return entity

# --- Fungsi Pembantu untuk Memformat Data Neo4j ke vis.js (VISUALIZATION SPECIFIC) ---
# Ini adalah fungsi yang akan dipanggil oleh endpoint identity_risk_check
# untuk mengonversi hasil query Neo4j menjadi format yang langsung dapat digunakan oleh vis.js
# di frontend (nodes dan edges dengan properti yang dibutuhkan: id, label, group, shape, color, etc.)
def convert_neo4j_to_visjs_format(neo4j_nodes, neo4j_relationships, primary_entity_value):
    vis_nodes = []
    vis_edges = []
    unique_vis_node_ids = set()

    # Tambahkan primary_entity_value sebagai node pusat jika belum ada
    if primary_entity_value and primary_entity_value not in unique_vis_node_ids:
        vis_nodes.append({
            'id': primary_entity_value,
            'label': primary_entity_value,
            'group': 'primary_entity',
            'shape': 'dot',
            'size': 30,
            'font': {'color': '#FFFFFF', 'size': 14, 'strokeWidth': 1, 'strokeColor': '#4A00B7'},
            'color': {'background': '#4A00B7', 'border': '#3B0091'}
        })
        unique_vis_node_ids.add(primary_entity_value)

    # Proses nodes
    for node in neo4j_nodes:
        # Gunakan format_neo4j_entity untuk mendapatkan ID dan label yang benar
        formatted_node_data = format_neo4j_entity(node)
        node_id = formatted_node_data['id']
        node_labels = formatted_node_data['labels']
        node_properties = formatted_node_data['properties']

        if node_id not in unique_vis_node_ids:
            vis_node = {'id': node_id, 'label': node_id} # Default label
            
            # Tentukan group, shape, dan color berdasarkan label Neo4j
            if 'User' in node_labels:
                vis_node['group'] = 'nik'
                vis_node['shape'] = 'box'
                vis_node['label'] = f"NIK: {node_properties.get('nik', node_id)}"
                vis_node['color'] = {'background': '#F1F5F9', 'border': '#CBD5E1'}
            elif 'Email' in node_labels:
                vis_node['group'] = 'email_linked'
                vis_node['shape'] = 'ellipse'
                vis_node['label'] = node_properties.get('email_address', node_id)
                vis_node['color'] = {'background': '#D1FAE5', 'border': '#065F46'}
            elif 'Phone' in node_labels:
                vis_node['group'] = 'phone_linked'
                vis_node['shape'] = 'diamond'
                vis_node['label'] = f"Phone: {node_properties.get('phone_number', node_id)}"
                vis_node['color'] = {'background': '#FFFAEC', 'border': '#B54708'}
            elif 'Company' in node_labels:
                vis_node['group'] = 'company'
                vis_node['shape'] = 'hexagon'
                vis_node['label'] = f"Company: {node_properties.get('company_name', node_id)}"
                vis_node['color'] = {'background': '#E0D0FF', 'border': '#4A00B7'} # Default purple
            else:
                vis_node['group'] = 'unknown'
                vis_node['shape'] = 'circle'
                vis_node['color'] = {'background': '#E2E8F0', 'border': '#94A3B8'} # Light gray

            # Override label if it's the primary entity
            if node_id == primary_entity_value:
                vis_node['group'] = 'primary_entity'
                vis_node['shape'] = 'dot'
                vis_node['size'] = 30
                vis_node['font'] = {'color': '#FFFFFF', 'size': 14, 'strokeWidth': 1, 'strokeColor': '#4A00B7'}
                vis_node['color'] = {'background': '#4A00B7', 'border': '#3B0091'}

            vis_nodes.append(vis_node)
            unique_vis_node_ids.add(node_id)

    # Proses edges
    for rel in neo4j_relationships:
        formatted_rel_data = format_neo4j_entity(rel)
        start_node_id = formatted_rel_data['start_node_id']
        end_node_id = formatted_rel_data['end_node_id']
        rel_type = formatted_rel_data['type']

        # Pastikan node sumber dan target ada di daftar node sebelum membuat edge
        if start_node_id in unique_vis_node_ids and end_node_id in unique_vis_node_ids:
            vis_edges.append({
                'from': start_node_id,
                'to': end_node_id,
                'label': rel_type.replace('_', ' ').title(),
                'arrows': 'to',
                'color': {'color': '#CBD5E1'}
            })

    return {"nodes": vis_nodes, "edges": vis_edges}


# --- 3. Endpoint API Pertama (untuk menguji koneksi DB) ---
@app.route('/test-db', methods=['GET'])
def test_db_connection():
    """Tests the Neo4j database connection and returns node count."""
    if not driver:
        return jsonify({"status": "error", "message": "Koneksi ke Neo4j tidak tersedia. Mohon cek log aplikasi."}), 500
    try:
        with driver.session(database=DATABASE) as session:
            query = "MATCH (n) RETURN count(n) AS total_nodes"
            result = session.run(query)
            total_nodes = result.single()["total_nodes"]
            return jsonify({"status": "success", "message": "Terhubung ke Neo4j dan berhasil mengambil data.", "total_nodes_in_db": total_nodes})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Terjadi kesalahan saat mengakses database: {e}"}), 500

# --- 4. Endpoint API untuk Real-time Identity Risk Assessment ---
@app.route('/v1/risk/identity-check', methods=['POST'])
def identity_risk_check():
    """Performs identity risk assessment based on NIK, Email, or Phone."""
    print("\n--- identity_risk_check: Request Received ---")

    if not driver:
        print("--- identity_risk_check: Neo4j driver not available ---")
        return jsonify({"status": "error", "message": "Koneksi ke Neo4j tidak tersedia."}), 500
    if not request.is_json:
        print("--- identity_risk_check: Request is not JSON ---")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    input_data = request.get_json()
    print(f"--- identity_risk_check: Input Data: {input_data} ---")
    
    input_nik = input_data.get('nik')
    input_email = input_data.get('email')
    input_phone_number = input_data.get('phone_number')
    input_company_id = input_data.get('system_id') # Asumsi system_id dari frontend adalah company_id
    context_id = input_data.get('context_id', 'N/A')

    # Validasi awal yang mutlak: setidaknya satu input harus ada
    if not (input_nik or input_email or input_phone_number):
        print("--- identity_risk_check: No NIK, Email, or Phone provided ---")
        return jsonify({"status": "error", "message": "Setidaknya NIK, Email, atau Nomor Telepon harus diberikan."}), 400

    overall_risk_score = 0
    risk_level = "LOW"
    recommendation = "APPROVE"
    fraud_indicators = []
    related_anomalies = {}
    
    # Inisialisasi graph_data di sini
    graph_data_for_frontend = {"nodes": [], "edges": []} 

    primary_entity_type = None 
    primary_entity_value = None
    user_node_found = None
    user_nik_for_indicators = None

    try:
        with driver.session(database=DATABASE) as session: 
            print("--- identity_risk_check: Neo4j session opened ---")

            # --- START: Logika Pencarian User ---
            if input_nik:
                print(f"--- identity_risk_check: Searching by NIK: {input_nik} ---")
                user_result = session.run("MATCH (u:User {nik: $nik}) RETURN u LIMIT 1", nik=input_nik).single()
                if user_result:
                    user_node_found = user_result["u"]
            
            if not user_node_found and input_email:
                print(f"--- identity_risk_check: Searching by Email: {input_email} ---")
                user_result = session.run("MATCH (e:Email {email_address: $email})<-[:HAS_EMAIL]-(u:User) RETURN u LIMIT 1", email=input_email).single()
                if user_result:
                    user_node_found = user_result["u"]
            
            if not user_node_found and input_phone_number:
                print(f"--- identity_risk_check: Searching by Phone: {input_phone_number} ---")
                user_result = session.run("MATCH (p:Phone {phone_number: $phone})<-[:HAS_PHONE]-(u:User) RETURN u LIMIT 1", phone=input_phone_number).single()
                if user_result:
                    user_node_found = user_result["u"]
            
            if not user_node_found:
                print(f"--- identity_risk_check: User not found for NIK: '{input_nik}', Email: '{input_email}', Phone: '{input_phone_number}' ---")
                return jsonify({"status": "error", "message": "Tidak dapat menemukan pengguna dengan NIK, Email, atau Nomor Telepon yang diberikan."}), 404
            
            user_nik_for_indicators = user_node_found.get("nik")
            if not user_nik_for_indicators:
                    print(f"--- identity_risk_check: User found but no valid NIK property: {user_node_found.properties} ---")
                    return jsonify({"status": "error", "message": "User ditemukan tetapi tidak memiliki NIK yang valid."}), 404

            print(f"--- identity_risk_check: User found, NIK for indicators: {user_nik_for_indicators} ---")

            # --- START: Logika Konsistensi & Penentuan Primary Entity Type ---
            if input_nik and user_node_found.get('nik') == input_nik:
                print("--- identity_risk_check: Primary entity type: SINGLE_NIK (from NIK input) ---")
                # Logika konsistensi NIK + Email/Phone
                if input_email:
                    consistency_check = session.run("""
                        MATCH (u:User {nik: $nik})-[:HAS_EMAIL]->(e:Email {email_address: $email})
                        RETURN u LIMIT 1
                    """, nik=input_nik, email=input_email).single()
                    if not consistency_check:
                        print(f"--- identity_risk_check: NIK-Email inconsistency: {input_nik}, {input_email} ---")
                        return jsonify({
                            "status": "error",
                            "message": f"Kombinasi NIK '{input_nik}' dan Email '{input_email}' tidak konsisten (tidak terhubung di database)."
                        }), 400
                
                if input_phone_number:
                    consistency_check = session.run("""
                        MATCH (u:User {nik: $nik})-[:HAS_PHONE]->(p:Phone {phone_number: $phone})
                        RETURN u LIMIT 1
                    """, nik=input_nik, phone=input_phone_number).single()
                    if not consistency_check:
                        print(f"--- identity_risk_check: NIK-Phone inconsistency: {input_nik}, {input_phone_number} ---")
                        return jsonify({
                            "status": "error",
                            "message": f"Kombinasi NIK '{input_nik}' dan Nomor Telepon '{input_phone_number}' tidak konsisten (tidak terhubung di database)."
                        }), 400
                
                primary_entity_type = 'SINGLE_NIK'
                primary_entity_value = input_nik
            
            elif input_email: 
                print("--- identity_risk_check: Primary entity type: based on Email input ---")
                num_connected_users_email_hub = session.run("""
                    MATCH (e:Email {email_address: $email})<-[:HAS_EMAIL]-(u:User)
                    RETURN COUNT(u) AS count
                """, email=input_email).single()["count"]
                
                if num_connected_users_email_hub > 1:
                    primary_entity_type = 'EMAIL_HUB'
                    primary_entity_value = input_email
                    print(f"--- identity_risk_check: Detected EMAIL_HUB with {num_connected_users_email_hub} users ---")

                    hub_result_for_email_hub = session.run("""
                        MATCH (e:Email {email_address: $email})<-[:HAS_EMAIL]-(u:User)
                        OPTIONAL MATCH (u)-[:HAS_EMAIL]->(other_e:Email) WHERE other_e.email_address <> e.email_address
                        OPTIONAL MATCH (u)-[:HAS_PHONE]->(p:Phone) 
                        OPTIONAL MATCH (u)-[:REGISTERED_VIA_COMPANY]->(c:Company)
                        WITH e, u, c, COLLECT(DISTINCT other_e.email_address) AS collected_other_emails_for_user, COLLECT(DISTINCT p.phone_number) AS collected_other_phones_for_user
                        RETURN e.email_address AS hub_email,
                                COUNT(DISTINCT u) AS num_connected_users,
                                COLLECT(DISTINCT {
                                    nik: u.nik, 
                                    dukcapil_score: u.dukcapil_matchscore, 
                                    dukcapil_response: u.dukcapil_response_desc,
                                    certificate_status: u.certificate_status, 
                                    company_id: c.company_id, 
                                    company_name: COALESCE(c.company_name, null), 
                                    other_emails: collected_other_emails_for_user,
                                    other_phones: collected_other_phones_for_user
                                }) AS connected_users_details
                    """, email=input_email).single()
                    if hub_result_for_email_hub:
                        related_anomalies["hub_details"] = {
                            "hub_type": "email",
                            "hub_value": input_email,
                            "num_connected_users": hub_result_for_email_hub["num_connected_users"],
                            "connected_users_details": hub_result_for_email_hub["connected_users_details"]
                        }
                    else: 
                        print("--- identity_risk_check: Failed to get email hub details ---")
                        return jsonify({"status": "error", "message": "Kesalahan internal: Gagal mendapatkan detail hub email."}), 500
                else:
                    primary_entity_type = 'SINGLE_NIK' 
                    primary_entity_value = user_nik_for_indicators 
                    print(f"--- identity_risk_check: Detected SINGLE_NIK via email: {primary_entity_value} ---")
            
            elif input_phone_number: 
                print("--- identity_risk_check: Primary entity type: based on Phone input ---")
                num_connected_users_phone_hub = session.run("""
                    MATCH (p:Phone {phone_number: $phone})<-[:HAS_PHONE]-(u:User)
                    RETURN COUNT(u) AS count
                """, phone=input_phone_number).single()["count"]

                if num_connected_users_phone_hub > 1:
                    primary_entity_type = 'PHONE_HUB'
                    primary_entity_value = input_phone_number
                    print(f"--- identity_risk_check: Detected PHONE_HUB with {num_connected_users_phone_hub} users ---")
                    
                    hub_result_for_phone_hub = session.run("""
                        MATCH (p:Phone {phone_number: $phone})<-[:HAS_PHONE]-(u:User)
                        OPTIONAL MATCH (u)-[:HAS_EMAIL]->(e:Email)
                        OPTIONAL MATCH (u)-[:HAS_PHONE]->(other_p:Phone) WHERE other_p.phone_number <> p.phone_number
                        OPTIONAL MATCH (u)-[:REGISTERED_VIA_COMPANY]->(c:Company)
                        WITH p, u, c, COLLECT(DISTINCT e.email_address) AS collected_other_emails_for_user, COLLECT(DISTINCT other_p.phone_number) AS collected_other_phones_for_user
                        RETURN p.phone_number AS hub_phone, COUNT(DISTINCT u) AS num_connected_users,
                                COLLECT(DISTINCT {
                                    nik: u.nik, 
                                    dukcapil_score: u.dukcapil_matchscore, 
                                    dukcapil_response: u.dukcapil_response_desc,
                                    certificate_status: u.certificate_status, 
                                    company_id: c.company_id, 
                                    company_name: COALESCE(c.company_name, null), 
                                    other_emails: collected_other_emails_for_user,
                                    other_phones: collected_other_phones_for_user
                                }) AS connected_users_details
                    """, phone=input_phone_number).single()
                    if hub_result_for_phone_hub:
                        related_anomalies["hub_details"] = {
                            "hub_type": "phone",
                            "hub_value": input_phone_number,
                            "num_connected_users": hub_result_for_phone_hub["num_connected_users"],
                            "connected_users_details": hub_result_for_phone_hub["connected_users_details"]
                        }
                    else: 
                        print("--- identity_risk_check: Failed to get phone hub details ---")
                        return jsonify({"status": "error", "message": "Kesalahan internal: Gagal mendapatkan detail hub nomor telepon."}), 500
                else:
                    primary_entity_type = 'SINGLE_NIK' 
                    primary_entity_value = user_nik_for_indicators 
                    print(f"--- identity_risk_check: Detected SINGLE_NIK via phone: {primary_entity_value} ---")
            # --- END: Logika Konsistensi & Penentuan Primary Entity Type ---

            # --- Tambahan: Ambil Email dan Phone untuk Summary Card (jika NIK yang dicari) ---
            summary_email_address = None
            summary_phone_number = None
            if user_node_found:
                emails_for_summary = session.run("MATCH (u:User {nik: $nik})-[:HAS_EMAIL]->(e:Email) RETURN e.email_address AS email", nik=user_node_found.get("nik")).value()
                if emails_for_summary:
                    summary_email_address = emails_for_summary[0] # Ambil email pertama

                phones_for_summary = session.run("MATCH (u:User {nik: $nik})-[:HAS_PHONE]->(p:Phone) RETURN p.phone_number AS phone", nik=user_node_found.get("nik")).value()
                if phones_for_summary:
                    summary_phone_number = phones_for_summary[0] # Ambil phone pertama


            # --- START: Logika Kalkulasi Risiko & Indikator Fraud ---
            print("--- identity_risk_check: Calculating risk score and fraud indicators ---")
            if primary_entity_type == 'EMAIL_HUB' or primary_entity_type == 'PHONE_HUB':
                overall_risk_score += 30

                fraud_indicators.append({
                    "type": "SHARED_CONTACT_HUB",
                    "detail": f"{primary_entity_type.replace('_',' ')} '{primary_entity_value}' terhubung ke {related_anomalies['hub_details']['num_connected_users']} NIK. Ini adalah hub mencurigakan.",
                    "impact": "CRITICAL"
                })
                
                problematic_niks_in_hub = []
                for user_detail in related_anomalies["hub_details"]["connected_users_details"]:
                    is_low_score_in_hub = (user_detail.get("dukcapil_score") is not None and user_detail.get("dukcapil_score") < 6)
                    is_not_success_response_in_hub = (user_detail.get("dukcapil_response") is not None and user_detail.get("dukcapil_response").strip().strip('.').lower() not in ['sukses', 'cocok'])

                    if is_low_score_in_hub or is_not_success_response_in_hub:
                        overall_risk_score += 5
                        problematic_niks_in_hub.append(user_detail['nik'])
                
                if problematic_niks_in_hub:
                    fraud_indicators.append({
                        "type": "HUB_CONTAINS_PROBLEMATIC_NIKS",
                        "detail": f"Hub ini terhubung ke {len(problematic_niks_in_hub)} NIK dengan Dukcapil bermasalah.",
                        "impact": "HIGH"
                    })
                    related_anomalies.setdefault("hub_problematic_niks", []).extend(problematic_niks_in_hub)
                
            elif primary_entity_type == 'SINGLE_NIK':
                print("--- identity_risk_check: Processing SINGLE_NIK logic ---")
                company_rel_result = session.run("""
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:REGISTERED_VIA_COMPANY]->(c:Company)
                    RETURN c.company_id AS company_id, COALESCE(c.company_name, null) AS company_name
                """, user_nik_for_indicators=user_nik_for_indicators).single()

                if company_rel_result:
                    related_anomalies["company_details"] = {
                        "company_id": company_rel_result["company_id"],
                        "company_name": company_rel_result["company_name"]
                    }

                response_desc_raw = user_node_found.get("dukcapil_response_desc")
                matchscore = user_node_found.get("dukcapil_matchscore")

                response_desc = None
                if response_desc_raw:
                    response_desc = response_desc_raw.strip().strip('.').strip().lower()

                is_low_score = (matchscore is not None and matchscore < 6)
                is_not_success_response = (response_desc is not None and response_desc not in ['sukses', 'cocok'])

                if is_low_score or is_not_success_response:
                    detail_message_parts = []
                    if is_low_score: detail_message_parts.append(f"Matchscore rendah ({matchscore}).")
                    if is_not_success_response: detail_message_parts.append(f"Respon Dukcapil '{response_desc_raw}' menunjukkan penolakan.")
                    
                    fraud_indicators.append({
                        "type": "DUKCAPIL_MISMATCH",
                        "detail": f"Dukcapil Mismatch untuk NIK ini: {' '.join(detail_message_parts)}",
                        "impact": "CRITICAL"
                    })
                    overall_risk_score += 50
                    if risk_level != "CRITICAL": risk_level = "CRITICAL"; recommendation = "REJECT"

                shared_email_result = session.run("""
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:HAS_EMAIL]->(e:Email)<-[:HAS_EMAIL]-(other_user:User)
                    WHERE other_user.nik <> $user_nik_for_indicators
                            AND other_user.certificate_status = 'active'
                    WITH e, COLLECT(DISTINCT other_user.nik) AS connected_nicks
                    WHERE SIZE(connected_nicks) > 0
                    RETURN e.email_address AS shared_email, SIZE(connected_nicks) AS num_sharing_users
                """, user_nik_for_indicators=user_nik_for_indicators)
                
                for record in shared_email_result:
                    shared_email = record["shared_email"]
                    num_sharing_users = record["num_sharing_users"]
                    
                    fraud_indicators.append({
                        "type": "SHARED_CONTACT",
                        "detail": f"Email '{shared_email}' terhubung ke {num_sharing_users} NIK aktif lain.",
                        "impact": "HIGH"
                    })
                    overall_risk_score += (num_sharing_users * 5)
                    related_anomalies.setdefault("shared_emails", []).append(shared_email)

                shared_phone_result = session.run("""
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:HAS_PHONE]->(p:Phone)<-[:HAS_PHONE]-(other_user:User)
                    WHERE other_user.nik <> $user_nik_for_indicators
                            AND other_user.certificate_status = 'active'
                    WITH p, COLLECT(DISTINCT other_user.nik) AS connected_nicks
                    WHERE SIZE(connected_nicks) > 0
                    RETURN p.phone_number AS shared_phone, SIZE(connected_nicks) AS num_sharing_users
                """, user_nik_for_indicators=user_nik_for_indicators)
                
                for record in shared_phone_result:
                    shared_phone = record["shared_phone"]
                    num_sharing_users = record["num_sharing_users"]
                    
                    fraud_indicators.append({
                        "type": "MULTI_ACCOUNT_PHONE",
                        "detail": f"Nomor telepon '{shared_phone}' terhubung ke {num_sharing_users} NIK aktif lain.",
                        "impact": "HIGH"
                    })
                    overall_risk_score += (num_sharing_users * 5)
                    related_anomalies.setdefault("shared_phones", []).extend(shared_phone)

                emails_for_nik_result = session.run("""
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:HAS_EMAIL]->(e:Email)
                    RETURN COUNT(e) AS num_emails, COLLECT(e.email_address) AS email_list
                """, user_nik_for_indicators=user_nik_for_indicators).single()
                if emails_for_nik_result and emails_for_nik_result["num_emails"] > 1:
                    fraud_indicators.append({
                        "type": "MULTI_EMAIL_PER_NIK",
                        "detail": f"NIK ini terhubung ke {emails_for_nik_result['num_emails']} alamat email yang berbeda: {', '.join(emails_for_nik_result['email_list'])}.",
                        "impact": "MEDIUM"
                    })
                    overall_risk_score += (emails_for_nik_result['num_emails'] * 3)
                    if risk_level == "LOW": risk_level = "MEDIUM"; recommendation = "REVIEW_MANUAL"
                    related_anomalies.setdefault("emails_for_nik", []).extend(emails_for_nik_result['email_list'])

                phones_for_nik_result = session.run("""
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:HAS_PHONE]->(p:Phone)
                    RETURN COUNT(p) AS num_phones, COLLECT(p.phone_number) AS phone_list
                """, user_nik_for_indicators=user_nik_for_indicators).single()
                if phones_for_nik_result and phones_for_nik_result["num_phones"] > 1:
                    fraud_indicators.append({
                        "type": "MULTI_PHONE_PER_NIK",
                        "detail": f"NIK ini terhubung ke {phones_for_nik_result['num_phones']} nomor telepon yang berbeda: {', '.join(phones_for_nik_result['phone_list'])}.",
                        "impact": "MEDIUM"
                    })
                    overall_risk_score += (phones_for_nik_result['num_phones'] * 3)
                    if risk_level == "LOW": risk_level = "MEDIUM"; recommendation = "REVIEW_MANUAL"
                    related_anomalies.setdefault("phones_for_nik", []).extend(phones_for_nik_result['phone_list'])

                company_id_to_check = input_company_id
                if not company_id_to_check and user_node_found.get("company_id"):
                    company_id_to_check = user_node_found.get("company_id")

                if company_id_to_check:
                    problem_company_result = session.run("""
                        MATCH (c:Company {company_id: $company_id_to_check})<-[:REGISTERED_VIA_COMPANY]-(u_problematic:User)
                        WHERE u_problematic.dukcapil_response_desc CONTAINS 'Tidak Cocok' OR u_problematic.dukcapil_matchscore < 6
                        WITH c, COLLECT(u_problematic.nik) AS problematic_nicks WHERE SIZE(problematic_nicks) > 0
                        RETURN COALESCE(c.company_name, null) AS company_name, SIZE(problematic_nicks) AS num_problematic_users
                    """, company_id_to_check=company_id_to_check).single()
                    if problem_company_result:
                        fraud_indicators.append({
                            "type": "PROBLEM_DUKCAPIL_COMPANY",
                            "detail": f"Perusahaan '{problem_company_result['company_name']}' terhubung ke {problem_company_result['num_problematic_users']} NIK bermasalah Dukcapil.",
                            "impact": "HIGH"
                        })
                        overall_risk_score += (problem_company_result['num_problematic_users'] * 10)

                connected_emails_for_user = session.run("""
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:HAS_EMAIL]->(e:Email)
                    RETURN e.email_address AS email
                """, user_nik_for_indicators=user_nik_for_indicators).value()

                for current_user_email in connected_emails_for_user:
                    violating_email_check_result = session.run("""
                        MATCH (e:Email {email_address: $current_user_email})<-[:HAS_EMAIL]-(u1:User)-[:REGISTERED_VIA_COMPANY]->(c:Company)
                        MATCH (e)<-[:HAS_EMAIL]-(u2:User)-[:REGISTERED_VIA_COMPANY]->(c)
                        WHERE u1.nik <> u2.nik AND u1.certificate_status = 'active' AND u2.certificate_status = 'active'
                        WITH e, c, COLLECT(DISTINCT u1.nik) AS users_violating_uniqueness, COUNT(DISTINCT u1) AS num_violating_users
                        WHERE num_violating_users >= 2
                        RETURN e.email_address AS ViolatingEmail, c.company_id AS ViolatingCompanyId, COALESCE(c.company_name, null) AS ViolatingCompanyName,
                                num_violating_users, users_violating_uniqueness
                    """, current_user_email=current_user_email).single()
                    if violating_email_check_result:
                        fraud_indicators.append({
                            "type": "EMAIL_NOT_UNIQUE_PER_COMPANY_SUCCESS_KYC",
                            "detail": f"Email '{violating_email_check_result['ViolatingEmail']}' digunakan oleh {violating_email_check_result['num_violating_users']} NIK (termasuk {user_nik_for_indicators}) di perusahaan '{violating_email_check_result['ViolatingCompanyName']}' ({violating_email_check_result['ViolatingCompanyId']}), dengan sertifikat aktif. Melanggar aturan unik email per perusahaan.",
                            "impact": "CRITICAL"
                        })
                        overall_risk_score += 100
                        if risk_level != "CRITICAL": risk_level = "CRITICAL"; recommendation = "REJECT"
                        related_anomalies.setdefault("violating_emails_per_company", []).append({
                            "email": violating_email_check_result['ViolatingEmail'],
                            "company_id": violating_email_check_result['ViolatingCompanyId'],
                            "violating_nicks": violating_email_check_result['users_violating_uniqueness']
                        })

                cypher_query_for_fraud_hub = """
                    MATCH (u:User {nik: $user_nik_for_indicators})-[:HAS_EMAIL]->(e_hub:Email)
                    MATCH (e_hub)<-[:HAS_EMAIL]-(other_user:User)
                    WHERE other_user.nik <> u.nik
                            AND other_user.certificate_status = 'active'
                    OPTIONAL MATCH (other_user)-[:HAS_EMAIL]->(other_user_email:Email)
                    WHERE other_user_email.email_address <> e_hub.email_address
                    OPTIONAL MATCH (other_user)-[:REGISTERED_VIA_COMPANY]->(c:Company)
                    WITH e_hub, other_user, c, COLLECT(DISTINCT other_user_email.email_address) AS collected_other_emails
                    WITH e_hub.email_address AS fraud_hub_email,
                            {
                                nik: other_user.nik, dukcapil_score: other_user.dukcapil_matchscore,
                                dukcapil_response: other_user.dukcapil_response_desc, certificate_status: other_user.certificate_status,
                                company_id: c.company_id, company_name: COALESCE(c.company_name, null), 
                                other_emails: collected_other_emails
                            } AS other_user_detail_map
                    WITH fraud_hub_email, COLLECT(other_user_detail_map) AS connected_users_details_list
                    WHERE SIZE(connected_users_details_list) >= 5
                    RETURN fraud_hub_email, SIZE(connected_users_details_list) AS num_connected_active_users,
                            connected_users_details_list AS connected_users_details
                    LIMIT 1
                """
                fraud_hub_result = session.run(cypher_query_for_fraud_hub, user_nik_for_indicators=user_nik_for_indicators).single()

                if fraud_hub_result:
                    fraud_indicators.append({
                        "type": "FRAUD_RING_MEMBERSHIP",
                        "detail": f"Pengguna terhubung ke email hub '{fraud_hub_result['fraud_hub_email']}' yang mengkoordinasikan {fraud_hub_result['num_connected_active_users']} NIK aktif lainnya. Detail jaringan ada di 'related_anomalies'.",
                        "impact": "CRITICAL"
                    })
                    overall_risk_score += 70
                    if risk_level != "CRITICAL": risk_level = "CRITICAL"; recommendation = "REJECT"
                    related_anomalies.setdefault("fraud_hubs", []).append({
                        "hub_email": fraud_hub_result['fraud_hub_email'],
                        "num_connected_active_users": fraud_hub_result['num_connected_active_users'],
                        "connected_users_details": fraud_hub_result['connected_users_details']
                    })
            # --- END: Logika Kalkulasi Risiko & Indikator Fraud ---
            
            # --- START: Ambil Data Grafik untuk Frontend ---
            # Tentukan node awal untuk query grafik
            graph_start_node_value = primary_entity_value # Default ke primary_entity_value
            graph_match_clause = ""

            if input_nik:
                graph_match_clause = "MATCH (start_node:User {nik: $value})"
            elif input_email:
                graph_match_clause = "MATCH (start_node:Email {email_address: $value})"
            elif input_phone_number:
                graph_match_clause = "MATCH (start_node:Phone {phone_number: $value})"
            
            # Query untuk mengambil nodes dan relationships dalam 1 hop
            graph_query = f"""
                {graph_match_clause}
                OPTIONAL MATCH path = (start_node)-[r]-(n)
                RETURN COLLECT(DISTINCT start_node) + COLLECT(DISTINCT n) AS nodes, COLLECT(DISTINCT r) AS relationships
            """
            
            graph_result = session.run(graph_query, value=graph_start_node_value).single()

            if graph_result:
                raw_neo4j_nodes = graph_result.get("nodes", [])
                raw_neo4j_relationships = graph_result.get("relationships", [])
                
                # Konversi ke format vis.js menggunakan fungsi pembantu yang baru
                graph_data_for_frontend = convert_neo4j_to_visjs_format(
                    raw_neo4j_nodes, 
                    raw_neo4j_relationships, 
                    primary_entity_value
                )
            # --- END: Ambil Data Grafik untuk Frontend ---

            # --- START: Penentuan Risk Level Akhir ---
            if overall_risk_score > 60 and recommendation != "REJECT":
                risk_level = "CRITICAL"
                recommendation = "REJECT"
            elif overall_risk_score > 30 and recommendation == "APPROVE":
                risk_level = "HIGH"
                recommendation = "REVIEW_MANUAL"
            elif overall_risk_score > 10 and recommendation == "APPROVE":
                risk_level = "MEDIUM"

            response = {
                "request_id": context_id,
                "primary_entity_type": primary_entity_type,
                "primary_entity_value": primary_entity_value,
                
                "nik": user_nik_for_indicators,
                "email_input": input_email,
                "phone_number_input": input_phone_number,
                
                "dukcapil_score_for_identified_nik": user_node_found.get("dukcapil_matchscore") if user_node_found else None,
                "dukcapil_response_for_identified_nik": user_node_found.get("dukcapil_response_desc") if user_node_found else None,
                
                "overall_risk_score": overall_risk_score,
                "risk_level": risk_level,
                "recommendation": recommendation,
                "fraud_indicators": fraud_indicators,
                "related_anomalies": related_anomalies,

                # Tambahan untuk summary display di frontend
                "summary_email_address": summary_email_address, 
                "summary_phone_number": summary_phone_number,
                "last_sync_date": datetime.now().strftime("%d/%m/%Y"), # Tanggal sinkronisasi dinamis
                
                # DATA GRAFIK UNTUK FRONTEND
                "graph_data": graph_data_for_frontend # Ini adalah data yang akan digunakan oleh vis.js
            }
            print("--- identity_risk_check: Returning JSON Response ---")
            return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        print(f"--- identity_risk_check: Error in function: {e} ---")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan internal: {e}"
        }), 500

# --- 5. Endpoint API untuk Identity Network Explorer (EXISTING) ---
# Endpoint ini sudah ada dan mengembalikan nodes/relationships.
# Frontend Anda mungkin memanggil ini secara terpisah untuk eksplorasi lebih lanjut.
@app.route('/v1/identity/<string:entity_value>/network', methods=['GET'])
def identity_network_explorer(entity_value):
    """Explores the network around a given NIK, Email, or Phone."""
    if not driver:
        return jsonify({"status": "error", "message": "Koneksi ke Neo4j tidak tersedia."}), 500

    try:
        hops = request.args.get('hops', default=1, type=int)
        if hops < 1 or hops > 3:
            return jsonify({"status": "error", "message": "Parameter 'hops' harus antara 1 dan 3."}), 400

        with driver.session(database=DATABASE) as session:
            # Determine if entity_value is NIK, Email, or Phone
            match_clause = ""
            if len(entity_value) == 16 and entity_value.isdigit():
                match_clause = "MATCH (u:User {nik: $value})"
            elif '@' in entity_value:
                match_clause = "MATCH (e:Email {email_address: $value})"
            elif entity_value.replace('+', '').isdigit() and (entity_value.startswith('08') or entity_value.startswith('+62')):
                match_clause = "MATCH (p:Phone {phone_number: $value})"
            else:
                return jsonify({"status": "error", "message": "Format nilai entitas tidak dikenal (harus NIK, Email, atau Nomor Telepon)."}), 400

            # Find the starting node
            start_node_result = session.run(f"{match_clause} RETURN COLLECT(DISTINCT n) AS nodes", value=entity_value).single()
            if not start_node_result or not start_node_result["nodes"]:
                return jsonify({"status": "error", "message": f"Entitas '{entity_value}' tidak ditemukan."}), 404
            
            # Get the actual node object to use its ID for the path query
            start_node_id_in_db = start_node_result["nodes"][0].id
            
            query = f"""
                MATCH path = (start_node)-[*1..{hops}]-(n)
                WHERE ID(start_node) = $start_node_id
                WITH COLLECT(DISTINCT nodes(path)) AS all_node_lists, COLLECT(DISTINCT relationships(path)) AS all_rel_lists
                UNWIND all_node_lists AS node_list
                UNWIND node_list AS node
                UNWIND all_rel_lists AS rel_list
                UNWIND rel_list AS rel
                RETURN COLLECT(DISTINCT node) AS nodes, COLLECT(DISTINCT rel) AS relationships
            """
            result = session.run(query, start_node_id=start_node_id_in_db).single()

            all_nodes_formatted = []
            all_relationships_formatted = []
            node_labels_count = {}
            relationship_types_count = {}

            if result:
                for node in result.get("nodes", []): # Use .get() for safety
                    formatted_node = format_neo4j_entity(node)
                    all_nodes_formatted.append(formatted_node)
                    for label in formatted_node['labels']:
                        node_labels_count[label] = node_labels_count.get(label, 0) + 1

                for rel in result.get("relationships", []): # Use .get() for safety
                    formatted_rel = format_neo4j_entity(rel)
                    all_relationships_formatted.append(formatted_rel)
                    relationship_types_count[formatted_rel['type']] = relationship_types_count.get(formatted_rel['type'], 0) + 1
            
            response = {
                "query_entity_value": entity_value,
                "network_summary": {
                    "total_nodes": len(all_nodes_formatted),
                    "total_relationships": len(all_relationships_formatted),
                    "node_labels": node_labels_count,
                    "relationship_types": relationship_types_count
                },
                "nodes": all_nodes_formatted,
                "relationships": all_relationships_formatted
            }
            return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        print(f"Error dalam fungsi identity_network_explorer: {e}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan internal: {e}"
        }), 500

# --- 6. Endpoint API untuk Shared Resource Inquiry (EXISTING) ---
@app.route('/v1/shared-resource/<string:resource_type>/<string:resource_value>', methods=['GET'])
def shared_resource_inquiry(resource_type, resource_value):
    """Retrieves details of users connected to a shared resource (email, phone, company)."""
    if not driver:
        return jsonify({"status": "error", "message": "Koneksi ke Neo4j tidak tersedia."}), 500

    connected_users_details = []
    num_connected_users = 0
    query = ""

    try:
        with driver.session(database=DATABASE) as session:
            if resource_type == 'email':
                query = """
                    MATCH (res:Email {email_address: $value})<-[:HAS_EMAIL]-(u:User)
                    OPTIONAL MATCH (u)-[:HAS_EMAIL]->(e:Email) WHERE e.email_address <> res.email_address
                    OPTIONAL MATCH (u)-[:HAS_PHONE]->(p:Phone)
                    OPTIONAL MATCH (u)-[:REGISTERED_VIA_COMPANY]->(c:Company)
                    RETURN u.nik AS nik, u.dukcapil_matchscore AS dukcapil_score,
                            u.dukcapil_response_desc AS dukcapil_response,
                            u.certificate_status AS certificate_status,
                            c.company_id AS company_id, COALESCE(c.company_name, null) AS company_name, 
                            COLLECT(DISTINCT e.email_address) AS emails_connected,
                            COLLECT(DISTINCT p.phone_number) AS phones_connected
                """
            elif resource_type == 'phone':
                query = """
                    MATCH (res:Phone {phone_number: $value})<-[:HAS_PHONE]-(u:User)
                    OPTIONAL MATCH (u)-[:HAS_EMAIL]->(e:Email)
                    OPTIONAL MATCH (u)-[:HAS_PHONE]->(p:Phone) WHERE p.phone_number <> res.phone_number
                    OPTIONAL MATCH (u)-[:REGISTERED_VIA_COMPANY]->(c:Company)
                    WITH res, u, c, COLLECT(DISTINCT e.email_address) AS collected_emails, COLLECT(DISTINCT p.phone_number) AS collected_phones
                    RETURN u.nik AS nik, u.dukcapil_matchscore AS dukcapil_score,
                            u.dukcapil_response_desc AS dukcapil_response,
                            u.certificate_status AS certificate_status,
                            c.company_id AS company_id, COALESCE(c.company_name, null) AS company_name, 
                            collected_emails AS emails_connected,
                            collected_phones AS phones_connected
                """
            elif resource_type == 'company':
                query = """
                    MATCH (res:Company {company_id: $value})<-[:REGISTERED_VIA_COMPANY]-(u:User)
                    OPTIONAL MATCH (u)-[:HAS_EMAIL]->(e:Email)
                    OPTIONAL MATCH (u)-[:HAS_PHONE]->(p:Phone)
                    WITH res, u, COLLECT(DISTINCT e.email_address) AS collected_emails, COLLECT(DISTINCT p.phone_number) AS collected_phones
                    RETURN u.nik AS nik, u.dukcapil_matchscore AS dukcapil_score,
                            u.dukcapil_response_desc AS dukcapil_response,
                            u.certificate_status AS certificate_status,
                            res.company_id AS company_id, COALESCE(res.company_name, null) AS company_name, 
                            collected_emails AS emails_connected,
                            collected_phones AS phones_connected
                """
            else:
                return jsonify({"status": "error", "message": "Tipe sumber daya tidak valid. Gunakan 'email', 'phone', atau 'company'."}), 400

            result = session.run(query, value=resource_value)
            
            for record in result:
                if record["nik"]: # Ensure NIK exists for a valid user entry
                    connected_users_details.append({
                        "nik": record["nik"],
                        "dukcapil_score": record["dukcapil_score"],
                        "dukcapil_response": record["dukcapil_response"],
                        "certificate_status": record["certificate_status"],
                        "company_id": record["company_id"],
                        "company_name": record["company_name"], # This will be null if COALESCE returned null
                        "other_emails": [e for e in record["emails_connected"] if e is not None], # Renamed for consistency with frontend
                        "other_phones": [p for p in record["phones_connected"] if p is not None]  # Renamed for consistency with frontend
                    })
                    num_connected_users += 1
            
            if num_connected_users == 0:
                # Check if the resource itself exists even if no users are connected
                resource_exists_query = ""
                if resource_type == 'email': resource_exists_query = "MATCH (e:Email {email_address: $value}) RETURN e LIMIT 1"
                elif resource_type == 'phone': resource_exists_query = "MATCH (p:Phone {phone_number: $value}) RETURN p LIMIT 1"
                elif resource_type == 'company': resource_exists_query = "MATCH (c:Company {company_id: $value}) RETURN c LIMIT 1"
                
                if resource_exists_query and not session.run(resource_exists_query, value=resource_value).single():
                    return jsonify({"status": "error", "message": f"Sumber daya '{resource_value}' dengan tipe '{resource_type}' tidak ditemukan."}), 404

            response = {
                "resource_type": resource_type,
                "resource_value": resource_value,
                "num_connected_users": num_connected_users,
                "connected_users_details": connected_users_details
            }
            return jsonify(response)

    except Exception as e:
        traceback.print_exc()
        print(f"Error dalam fungsi shared_resource_inquiry: {e}")
        return jsonify({
            "status": "error",
            "message": f"Terjadi kesalahan internal: {e}"
        }), 500

# --- ROUTES UNTUK MENYAJIKAN FILE FRONTEND ---

# Route untuk halaman login lama (jika masih digunakan)
@app.route('/login')
def login_page():
    return send_from_directory('risk-asses-v2', 'login.html')

# Route untuk melayani file statis dari folder risk-asses-v2 (CSS, JS, images, dll.)
@app.route('/risk-asses-v2/<path:filename>')
def serve_risk_asses_static(filename):
    return send_from_directory('risk-asses-v2', filename)

# Route untuk dashboard utama lama (jika masih digunakan)
@app.route('/risk-asses-v2/')
def old_dashboard():
    return send_from_directory('risk-asses-v2', 'index.html')

# Route untuk logout (jika menggunakan server-side session)
@app.route('/logout')
def logout():
    # Contoh: session.pop('logged_in', None)
    return redirect(url_for('login_page'))

# Route untuk halaman utama revamp (index.html di folder risk-asses-revamp)
@app.route('/revamp/')
def new_revamp_dashboard():
    # DEBUG: Menampilkan jalur yang dicari Flask
    current_working_directory = os.getcwd()
    target_directory = os.path.join(current_working_directory, 'risk-asses-revamp') 
    target_file_path = os.path.join(target_directory, 'index.html')

    print(f"DEBUG: Current Working Directory: {current_working_directory}")
    print(f"DEBUG: Attempting to serve from Directory: {target_directory}")
    print(f"DEBUG: Attempting to serve File Path: {target_file_path}")
    
    # Pastikan folder 'risk-asses-revamp' berada di direktori yang sama dengan app.py
    return send_from_directory('risk-asses-revamp', 'index.html') 

# Route untuk melayani file statis dari folder risk-asses-revamp (CSS, JS, images, lib)
@app.route('/revamp/<path:filename>')
def serve_revamp_static(filename):
    # DEBUG: Menampilkan jalur yang dicari Flask
    current_working_directory = os.getcwd()
    target_directory = os.path.join(current_working_directory, 'risk-asses-revamp') 
    target_file_path = os.path.join(target_directory, filename)

    print(f"DEBUG: Current Working Directory: {current_working_directory}")
    print(f"DEBUG: Attempting to serve static from Directory: {target_directory}")
    print(f"DEBUG: Attempting to serve Static File Path: {target_file_path}")
    
    # Pastikan folder 'risk-asses-revamp' berada di direktori yang sama dengan app.py
    return send_from_directory('risk-asses-revamp', filename) 

# Route default (misal, untuk root URL)
@app.route('/')
def index():
    # Anda bisa redirect ke halaman revamp atau halaman lama sesuai preferensi
    return redirect(url_for('new_revamp_dashboard'))


if __name__ == '__main__':
    # Pastikan debug=True hanya saat pengembangan.
    # host='0.0.0.0' memungkinkan akses dari IP lain di jaringan lokal Anda.
    app.run(debug=True, host='0.0.0.0', port=5000)
