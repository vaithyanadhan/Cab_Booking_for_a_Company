from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'secret123'

db = mysql.connector.connect(
    host="localhost", user="root", password="root", database="cab_system"
)
cursor = db.cursor(dictionary=True)

FARE = {
    'Central Bus Stand': 100,
    'Chathiram Bus Stand': 150,
    'Srirangam': 200,
    'TVS Tollgate': 150
}

# Home / Help
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/help')
def help():
    return render_template('help.html')

# Register
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        n,e,p,ph = (request.form[k] for k in ('name','email','password','phone'))
        cursor.execute("SELECT 1 FROM users WHERE email=%s",(e,))
        if cursor.fetchone():
            flash("Email already registered","danger")
        else:
            cursor.execute(
              "INSERT INTO users(name,email,password,phone) VALUES(%s,%s,%s,%s)",
              (n,e,p,ph)
            ); db.commit()
            flash("Registered! Please log in.","success")
            return redirect(url_for('user_login'))
    return render_template('register.html')

# User Login / Logout
@app.route('/user_login', methods=['GET','POST'])
def user_login():
    if request.method=='POST':
        e,p = request.form['email'],request.form['password']
        cursor.execute("SELECT * FROM users WHERE email=%s AND password=%s",(e,p))
        u = cursor.fetchone()
        if u:
            session['user_id'], session['user_name'] = u['id'], u['name']
            return redirect(url_for('user_dashboard'))
        flash("Invalid credentials","danger")
    return render_template('user_login.html')

@app.route('/user_logout')
def user_logout():
    session.clear()
    return redirect(url_for('home'))

# User Dashboard / Request Ride
@app.route('/user_dashboard', methods=['GET','POST'])
def user_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))

    # get wallet
    cursor.execute("SELECT wallet FROM users WHERE id=%s",(session['user_id'],))
    wallet = cursor.fetchone()['wallet']

    # live availability
    cursor.execute("SELECT location,name FROM drivers WHERE is_available=1")
    avail = {r['location']: r['name'] for r in cursor.fetchall()}

    if request.method=='POST':
        pickup = request.form['pickup']
        time   = request.form['time']
        fare   = FARE[pickup]
        cursor.execute(
          "INSERT INTO rides(user_id,pickup,time,fare) VALUES(%s,%s,%s,%s)",
          (session['user_id'],pickup,time,fare)
        ); db.commit()
        flash(f"Requested ride for ₹{fare}.","info")
        return redirect(url_for('user_history'))

    return render_template('user_dashboard.html',
                           fares=FARE, avail=avail, wallet=wallet)

# User History / Complete / Cancel
@app.route('/user_history')
def user_history():
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    # wallet
    cursor.execute("SELECT wallet FROM users WHERE id=%s",(session['user_id'],))
    wallet = cursor.fetchone()['wallet']

    cursor.execute("""
      SELECT r.*, d.name driver_name, d.phone driver_phone
        FROM rides r
        LEFT JOIN drivers d ON d.id=r.driver_id
       WHERE r.user_id=%s
       ORDER BY r.id DESC
    """,(session['user_id'],))
    rides = cursor.fetchall()
    return render_template('user_history.html',
                           rides=rides, wallet=wallet)

@app.route('/user_complete/<int:ride_id>')
def user_complete(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    # Only assigned→completed
    cursor.execute("""
      UPDATE rides
         SET status='completed'
       WHERE id=%s AND user_id=%s AND status='assigned'
    """,(ride_id,session['user_id']))
    # driver earnings +100
    cursor.execute("SELECT driver_id FROM rides WHERE id=%s",(ride_id,))
    d = cursor.fetchone()['driver_id']
    if d:
        cursor.execute("UPDATE drivers SET earnings=earnings+100 WHERE id=%s",(d,))
    db.commit()
    flash("Ride completed.","success")
    return redirect(url_for('user_history'))

@app.route('/user_cancel/<int:ride_id>')
def user_cancel(ride_id):
    if 'user_id' not in session:
        return redirect(url_for('user_login'))
    cursor.execute("SELECT status,fare,driver_id FROM rides WHERE id=%s AND user_id=%s",
                   (ride_id,session['user_id']))
    row = cursor.fetchone()
    if not row or row['status'] in ('completed','cancelled'):
        flash("Cannot cancel.","warning")
    else:
        status,fare,drv = row['status'],row['fare'],row['driver_id']
        if status=='pending':
            refund = fare
        else:
            refund = fare//2
            # driver gets 50
            if drv:
                cursor.execute("UPDATE drivers SET earnings=earnings+50 WHERE id=%s",(drv,))
        cursor.execute("UPDATE users SET wallet=wallet+%s WHERE id=%s",(refund,session['user_id']))
        cursor.execute("UPDATE rides SET status='cancelled' WHERE id=%s",(ride_id,))
        db.commit()
        flash(f"Cancelled. ₹{refund} refunded.", "info")
    return redirect(url_for('user_history'))

# Driver Login / Logout
@app.route('/driver_login', methods=['GET','POST'])
def driver_login():
    if request.method=='POST':
        ph = request.form['phone']
        cursor.execute("SELECT * FROM drivers WHERE phone=%s",(ph,))
        d = cursor.fetchone()
        if d:
            session['driver_id'], session['driver_name'] = d['id'], d['name']
            return redirect(url_for('driver_dashboard'))
        flash("Driver not found","danger")
    return render_template('driver_login.html')

@app.route('/driver_logout')
def driver_logout():
    session.clear()
    return redirect(url_for('home'))

# Driver Dashboard / Assign / Complete
@app.route('/driver_dashboard', methods=['GET','POST'])
def driver_dashboard():
    if 'driver_id' not in session:
        return redirect(url_for('driver_login'))

    if request.method=='POST':
        if 'toggle' in request.form:
            cursor.execute("UPDATE drivers SET is_available=NOT is_available WHERE id=%s",
                           (session['driver_id'],)); db.commit()
            flash("Availability toggled.","info")
        if 'assign' in request.form:
            cursor.execute("SELECT 1 FROM rides WHERE driver_id=%s AND status='assigned'",
                           (session['driver_id'],))
            if cursor.fetchone():
                flash("Finish current ride.","warning")
            else:
                rid = request.form['assign']
                cursor.execute("UPDATE rides SET driver_id=%s,status='assigned' WHERE id=%s",
                               (session['driver_id'],rid)); db.commit()
                flash("Ride assigned.","success")
        if 'complete' in request.form:
            rid = request.form['complete']
            cursor.execute("UPDATE rides SET status='completed' WHERE id=%s AND driver_id=%s",
                           (rid,session['driver_id']))
            cursor.execute("UPDATE drivers SET earnings=earnings+100 WHERE id=%s",
                           (session['driver_id'],))
            db.commit()
            flash("Ride completed.","success")

    # Pending
    cursor.execute("""
      SELECT r.id,u.name user_name,u.phone user_phone,r.pickup,r.time,r.fare
        FROM rides r JOIN users u ON u.id=r.user_id
       WHERE r.status='pending'
       ORDER BY r.time
    """)
    pending = cursor.fetchall()

    # Current
    cursor.execute("""
      SELECT r.id,u.name user_name,r.pickup,r.time,r.fare
        FROM rides r JOIN users u ON u.id=r.user_id
       WHERE r.driver_id=%s AND r.status='assigned'
    """,(session['driver_id'],))
    current = cursor.fetchone()

    # Availability
    cursor.execute("SELECT is_available,earnings FROM drivers WHERE id=%s",
                   (session['driver_id'],))
    info = cursor.fetchone()
    available, earnings = info['is_available'], info['earnings']

    return render_template('driver_dashboard.html',
                           pending=pending,
                           current=current,
                           available=available,
                           earnings=earnings)

# Driver History & Earnings
@app.route('/driver_history')
def driver_history():
    if 'driver_id' not in session:
        return redirect(url_for('driver_login'))

    cursor.execute("""
      SELECT r.id, r.pickup, r.time, r.fare, r.status,
             CASE
               WHEN r.status='completed' THEN 100
               WHEN r.status='cancelled' THEN 50
               ELSE 0
             END AS earned
        FROM rides r
       WHERE r.driver_id=%s
       ORDER BY r.time DESC
    """,(session['driver_id'],))
    history = cursor.fetchall()

    total = sum(r['earned'] for r in history)
    return render_template('driver_history.html',
                           history=history,
                           total=total)

# Admin Login / Dashboard
@app.route('/admin_login', methods=['GET','POST'])
def admin_login():
    if request.method=='POST':
        u,p = request.form['username'],request.form['password']
        if u=='admin' and p=='admin@123':
            session['admin']=True
            return redirect(url_for('admin_dashboard'))
        flash("Invalid admin","danger")
    return render_template('admin_login.html')

@app.route('/admin_dashboard', methods=['GET','POST'])
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if request.method=='POST' and 'update_user' in request.form:
        uid,n,e,ph = (request.form[k] for k in ('u_id','u_name','u_email','u_phone'))
        cursor.execute("UPDATE users SET name=%s,email=%s,phone=%s WHERE id=%s",
                       (n,e,ph,uid)); db.commit()
        flash("User updated","success")
    if request.method=='POST' and 'add_driver' in request.form:
        dn,dp,dl = (request.form[k] for k in ('d_name','d_phone','d_location'))
        cursor.execute("INSERT INTO drivers(name,phone,location) VALUES(%s,%s,%s)",
                       (dn,dp,dl)); db.commit()
        flash("Driver added","success")

    cursor.execute("SELECT * FROM users");   users   = cursor.fetchall()
    cursor.execute("SELECT * FROM drivers"); drivers = cursor.fetchall()
    cursor.execute("""
      SELECT r.id, u.name AS user_name, d.name AS driver_name,
             r.pickup, r.time, r.fare, r.status
        FROM rides r
        LEFT JOIN users u   ON u.id=r.user_id
        LEFT JOIN drivers d ON d.id=r.driver_id
       ORDER BY r.id DESC
    """); rides = cursor.fetchall()

    return render_template('admin_dashboard.html',
                           users=users,
                           drivers=drivers,
                           rides=rides)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__=='__main__':
    app.run(debug=True)
