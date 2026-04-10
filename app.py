from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, os, shutil

app = Flask(__name__)

# ---------------------------
#  DATABASE SETUP (PERSISTENT)
# ---------------------------

PERSISTENT_DB = "/var/data/leave.db"     # Render persistent storage
LOCAL_DB = "leave.db"                    # DB shipped with your repo

DB = PERSISTENT_DB

# Create persistent DB on first deploy
if not os.path.exists(PERSISTENT_DB):
    os.makedirs("/var/data", exist_ok=True)
    if os.path.exists(LOCAL_DB):
        shutil.copy(LOCAL_DB, PERSISTENT_DB)
    else:
        conn = sqlite3.connect(PERSISTENT_DB)
        cur = conn.cursor()

        # Create tables
        cur.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                out_station TEXT CHECK(out_station IN ('Yes','No')),
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            );
        """)
        conn.commit()
        conn.close()


def get_db():
    return sqlite3.connect(DB)

# ---------------------------
#   ROUTES
# ---------------------------

@app.route("/")
def home():
    return render_template("index.html")


# ----- Employees -----

@app.route("/employees")
def employees():
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name FROM employees ORDER BY name").fetchall()
    conn.close()
    return jsonify(rows)


@app.route("/add_employee", methods=["POST"])
def add_employee():
    name = request.json["name"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO employees (name) VALUES (?)", (name,))
    conn.commit()
    conn.close()
    return jsonify({"status": "added"})


# ----- Add Leave -----

@app.route("/add_leave", methods=["POST"])
def add_leave():
    d = request.json
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO leaves (employee_id, start_date, end_date, out_station)
        VALUES (?, ?, ?, ?)
    """, (d["employee_id"], d["start"], d["end"], d["out"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ----- Gantt Data -----

@app.route("/gantt")
def gantt():
    from datetime import datetime, timedelta

    y = int(request.args["year"])
    m = int(request.args["month"])

    start = datetime(y, m, 1)
    end = (datetime(y+1,1,1) if m==12 else datetime(y, m+1, 1)) - timedelta(days=1)

    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT e.name, l.start_date, l.end_date, l.out_station
        FROM leaves l
        JOIN employees e ON e.id = l.employee_id
        WHERE NOT (l.end_date < ? OR l.start_date > ?)
        ORDER BY e.name
    """, (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))).fetchall()
    conn.close()

    data = {}
    for name, s, e, o in rows:
        data.setdefault(name, []).append({
            "start": max(s, start.strftime("%Y-%m-%d")),
            "end": min(e, end.strftime("%Y-%m-%d")),
            "out": o
        })

    return jsonify({
        "year": y,
        "month": m,
        "days": end.day,
        "data": data
    })


# ----- CSV Export -----

@app.route("/export_csv")
def export_csv():
    import csv

    export_path = "/var/data/leaves_export.csv"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.id, e.name, l.start_date, l.end_date, l.out_station
        FROM leaves l
        JOIN employees e ON e.id = l.employee_id
        ORDER BY l.start_date
    """)
    rows = cur.fetchall()
    conn.close()

    with open(export_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Employee Name", "Start Date", "End Date", "Out Station"])
        writer.writerows(rows)

    return send_file(export_path, as_attachment=True)


# ---------------------------
#   RUN APP
# ---------------------------

if __name__ == "__main__":
    app.run(debug=True)

