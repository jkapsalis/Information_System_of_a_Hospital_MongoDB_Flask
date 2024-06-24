from flask import Flask, request, jsonify, session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
from bson.objectid import ObjectId
from datetime import datetime

# Connect to our local MongoDB
mongodb_hostname = os.environ.get("MONGO_HOSTNAME", "localhost")
client = MongoClient('mongodb://' + mongodb_hostname + ':27017/')

# Initiate Flask App
app = Flask(__name__)
app.secret_key = 'secret_key' 

# HospitalDB database
db = client['HospitalDB']
# doctors collection
doctors = db['doctors']
# patients collection
patients = db['patients']
# appointments collection
appointments = db['appointments']
# admins collection
admins = db['admins']

# Create te first admin user if it doesn't exist
def create_admin():
    admin_user = admins.find_one({'username': 'admin'})
    if not admin_user:
        admin_user = {
            'username': 'admin',
            'password': generate_password_hash('@dm1n')
        }
        admins.insert_one(admin_user)
        print("Admin user created")
    else:
        print("Admin user already exists")

create_admin()

# check if admin is logged in
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            return jsonify({'message': 'Unauthorized access'}), 403
        return f(*args, **kwargs)
    return decorated_function

# check if doctor is logged in
def doctor_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'doctor' not in session:
            return jsonify({'message': 'Unauthorized access'}), 403
        return f(*args, **kwargs)
    return decorated_function

# check if patient is logged in
def patient_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'patient' not in session:
            return jsonify({'message': 'Unauthorized access'}), 403
        return f(*args, **kwargs)
    return decorated_function


##### ADMINS
# Admin login endpoint
@app.route('/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing username or password'}), 400

    username = data.get('username')
    password = data.get('password')

    admin_user = admins.find_one({'username': username})

    if admin_user and check_password_hash(admin_user['password'], password):
        session['admin'] = True
        return jsonify({'message': 'Login successful'})
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

# Admin logout endpoint
@app.route('/admin/logout', methods=['POST'])
@admin_required
def admin_logout():
    session.pop('admin', None)
    return jsonify({'message': 'Logout successful'})

# Create a doctor
@app.route('/admin/doctors', methods=['POST'])
@admin_required
def create_doctor():
    data = request.get_json()
    required_fields = ['first_name', 'last_name', 'email', 'username', 'password', 'specialization', 'appointment_cost']
    
    if not data or not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing fields'}), 400
    
    if doctors.find_one({'email': data['email']}) or doctors.find_one({'username': data['username']}):
        return jsonify({'message': 'Doctor already exists'}), 400
    
    data['password'] = generate_password_hash(data['password'])
    doctors.insert_one(data)
    
    return jsonify({'message': 'Doctor created successfully'}), 201

# Change doctor's password
@app.route('/admin/doctors/<username>/password', methods=['PUT'])
@admin_required
def change_doctor_password(username):
    data = request.get_json()
    if not data or not data.get('new_password'):
        return jsonify({'message': 'Missing new password'}), 400

    new_password = data.get('new_password')

    result = doctors.update_one({'username': username}, {'$set': {'password': generate_password_hash(new_password)}})
    
    if result.matched_count == 0:
        return jsonify({'message': 'Doctor not found'}), 404
    
    return jsonify({'message': 'Password updated successfully'})

# Delete a doctor
@app.route('/admin/doctors/<username>', methods=['DELETE'])
@admin_required
def delete_doctor(username):
    result = doctors.delete_one({'username': username})
    appointments.delete_many({'doctor_username': username})
    
    if result.deleted_count == 0:
        return jsonify({'message': 'Doctor not found'}), 404
    
    return jsonify({'message': 'Doctor deleted successfully'})

# Delete a patient
@app.route('/admin/patients/<username>', methods=['DELETE'])
@admin_required
def delete_patient(username):
    result = patients.delete_one({'username': username})
    appointments.delete_many({'patient_username': username})
    
    if result.deleted_count == 0:
        return jsonify({'message': 'Patient not found'}), 404
    
    return jsonify({'message': 'Patient deleted successfully'})


##### DOCTORS
# Doctor login endpoint
@app.route('/doctor/login', methods=['POST'])
def doctor_login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing username or password'}), 400

    username = data.get('username')
    password = data.get('password')

    doctor = doctors.find_one({'username': username})

    if doctor and check_password_hash(doctor['password'], password):
        session['doctor'] = username
        return jsonify({'message': 'Login successful'})
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

# Doctor logout endpoint
@app.route('/doctor/logout', methods=['POST'])
@doctor_required
def doctor_logout():
    session.pop('doctor', None)
    return jsonify({'message': 'Logout successful'})

# Change password 
@app.route('/doctor/password', methods=['PUT'])
@doctor_required
def doctor_change_password():
    data = request.get_json()
    if not data or not data.get('new_password'):
        return jsonify({'message': 'Missing new password'}), 400

    new_password = data.get('new_password')
    username = session['doctor']
    result = doctors.update_one({'username': username}, {'$set': {'password': generate_password_hash(new_password)}})
    
    if result.matched_count == 0:
        return jsonify({'message': 'Doctor not found'}), 404
    
    return jsonify({'message': 'Password updated successfully'})

# Change appointment cost
@app.route('/doctor/appointment-cost', methods=['PUT'])
@doctor_required
def change_appointment_cost():
    data = request.get_json()
    if not data or not data.get('new_cost'):
        return jsonify({'message': 'Missing new cost'}), 400

    new_cost = data.get('new_cost')
    username = session['doctor']
    result = doctors.update_one({'username': username}, {'$set': {'appointment_cost': new_cost}})
    
    if result.matched_count == 0:
        return jsonify({'message': 'Doctor not found'}), 404
    
    appointments.update_many({'doctor_username': username}, {'$set': {'appointment_cost': new_cost}})
    
    return jsonify({'message': 'Appointment cost updated successfully'})

# View appointments
@app.route('/doctor/appointments', methods=['GET'])
@doctor_required
def view_appointments():
    username = session['doctor']
    upcoming_appointments = list(appointments.find({'doctor_username': username, 'date': {'$gte': datetime.now()}}))
    
    for appointment in upcoming_appointments:
        appointment['_id'] = str(appointment['_id'])
        appointment['date'] = appointment['date'].isoformat() 

    return jsonify(upcoming_appointments)

##### PATIENTS
# Patient register
@app.route('/patient/register', methods=['POST'])
def patient_register():
    data = request.get_json()
    required_fields = ['first_name', 'last_name', 'email', 'amka', 'birthdate', 'username', 'password']

    if not data or not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing fields'}), 400
    
    if patients.find_one({'email': data['email']}) or patients.find_one({'username': data['username']}):
        return jsonify({'message': 'Patient already exists'}), 400
    
    data['password'] = generate_password_hash(data['password'])
    patients.insert_one(data)
    
    return jsonify({'message': 'Patient registered successfully'}), 201



# Patient login 
@app.route('/patient/login', methods=['POST'])
def patient_login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing username or password'}), 400

    username = data.get('username')
    password = data.get('password')

    patient = patients.find_one({'username': username})

    if patient and check_password_hash(patient['password'], password):
        session['patient'] = username
        return jsonify({'message': 'Login successful'})
    else:
        return jsonify({'message': 'Invalid credentials'}), 401

# Patient logout endpoint
@app.route('/patient/logout', methods=['POST'])
@patient_required
def patient_logout():
    session.pop('patient', None)
    return jsonify({'message': 'Logout successful'})

# book appointment
@app.route('/patient/appointments', methods=['POST'])
@patient_required
def book_appointment():
    data = request.get_json()
    required_fields = ['date', 'time', 'specialization', 'reason']

    if not data or not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing fields'}), 400

    date = datetime.strptime(data['date'], '%Y-%m-%d')
    time = data['time']
    specialization = data['specialization']
    reason = data['reason']
    doctor = doctors.find_one({'specialization': specialization, 'appointments': {'$not': {'$elemMatch': {'date': date, 'time': time}}}})

    if doctor:
        appointment = {
            'patient_username': session['patient'],
            'doctor_username': doctor['username'],
            'date': date,
            'time': time,
            'reason': reason,
            'cost': doctor['appointment_cost'],
            'specialization': specialization,
            'doctor_name': f"{doctor['first_name']} {doctor['last_name']}"
        }
        appointments.insert_one(appointment)
        return jsonify({'message': 'Appointment booked successfully'}), 201
    else:
        return jsonify({'message': 'No available doctor found'}), 404

# View booked appointments
@app.route('/patient/appointments', methods=['GET'])
@patient_required
def view_patient_appointments():
    try:
        username = session.get('patient')
        if not username:
            return jsonify({'message': 'Unauthorized access'}), 401

        upcoming_appointments = list(appointments.find({'patient_username': username, 'date': {'$gte': datetime.now()}}))
        
        # Convert ObjectId to string
        for appointment in upcoming_appointments:
            appointment['_id'] = str(appointment['_id'])
            appointment['date'] = appointment['date'].isoformat() 

        return jsonify(upcoming_appointments)
    except Exception as e:
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

# View appointment details
@app.route('/patient/appointments/<appointment_id>', methods=['GET'])
@patient_required
def view_appointment_details(appointment_id):
    try:
        appointment = appointments.find_one({'_id': ObjectId(appointment_id), 'patient_username': session['patient']})

        if appointment:
            appointment['_id'] = str(appointment['_id'])
            appointment['date'] = appointment['date'].isoformat()  # Ensure date is JSON serializable
            return jsonify(appointment)
        else:
            return jsonify({'message': 'Appointment not found'}), 404
    except Exception as e:
        return jsonify({'message': 'An error occurred', 'error': str(e)}), 500

# Cancel appointment
@app.route('/patient/appointments/<appointment_id>', methods=['DELETE'])
@patient_required
def cancel_appointment(appointment_id):
    result = appointments.delete_one({'_id': ObjectId(appointment_id), 'patient_username': session['patient']})

    if result.deleted_count == 0:
        return jsonify({'message': 'Appointment not found'}), 404

    return jsonify({'message': 'Appointment canceled successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
