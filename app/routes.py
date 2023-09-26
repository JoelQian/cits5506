# routes.py
from flask import render_template, flash, redirect, url_for, request
from app import app
from app.models import User
from flask_login import login_required, LoginManager
from flask_login import current_user, login_user, logout_user
from app.models import Residence
from app import db
from flask import jsonify

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(id):
    return User.query.get(int(id))


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.verify_password(password):
            login_user(user)
            # log user in
            return redirect(url_for('residence_list'))
        else:
            flash('Invalid username or password')
            # invalid login
            return redirect(url_for('login'))
    else:  # Handle GET request
        return render_template('login.html')


@login_required
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


###############################################login above###############################################
@login_required
@app.route('/residences', methods=['POST'])
def create_residence():
    """
    for creating the residence data in the database, data from residence_info_add_change
    example request:
    {
    "first_name": "John",
    "last_name": "Doe",
    "email": "johndoe@example.com",
    "phone_no": "123-456-7890",
    "unit_num": 12,
    "room_no": "A101",
    "nfc_id": "OPTIONAL_NFC_ID"
    }
    """
    data = request.get_json()
    new_residence = Residence(
        first_name=data['first_name'],
        last_name=data['last_name'],
        email=data['email'],
        phone_no=data['phone_no'],
        unit_num=data['unit_num'],
        room_no=data['room_no'],
        nfc_id=data.get('nfc_id', None)  # nfc_id is optional
    )

    db.session.add(new_residence)
    db.session.commit()

    return jsonify({'message': 'Residence created successfully'}), 201


@login_required
@app.route('/residence_info_add_change')
def residence_info():
    return render_template('residence_info_add_change.html')


@login_required
@app.route('/residence_list')
def residence_list():
    return render_template('residence_list.html')


@login_required
@app.route('/residence_list_data')
def residence_list_data():
    """
    #get name(last, firsr), room_no, email
    return format:
    [
        {
            "email": "23424251@student.uwa.edu.au",
            "name": "Z Zehua",
            "room_no": "222"
        },
        ......
    ]
    """
    residences = Residence.query.all()
    residence_list = []
    for residence in residences:
        residence_list.append({
            'name': residence.last_name + ' ' + residence.first_name,
            'room_no': residence.room_no,
            'email': residence.email
        })
    return jsonify(residence_list)
