from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
import os

DB = "/var/data/leave.db"
def db():
    return sqlite3.connect(DB)
# Ensure persistent DB exists
if not os.path.exists(DB):
    import shutil
    shutil.copy("leave.db", DB)

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/employees")
def employees():
    c = db()
    rows = c.execute("SELECT id, name FROM employees").fetchall()
    c.close()
    return jsonify(rows)


@app.route("/add_leave", methods=["POST"])
def add_leave():
    d = request.json
    c = db()
    c.execute("""
        INSERT INTO leaves (employee_id, start_date, end_date, out_station)
        VALUES (?, ?, ?, ?)
    """, (d["employee_id"], d["start"], d["end"], d["out"]))
    c.commit()
    c.close()
    return jsonify({"status": "ok"})


@app.route("/gantt")
def gantt():
    y = int(request.args["year"])
    m = int(request.args["month"])

    start = datetime(y, m, 1)
    end = (datetime(y+1,1,1) if m==12 else datetime(y,m+1,1)) - timedelta(days=1)

    c = db()
    rows = c.execute("""
        SELECT e.name, l.start_date, l.end_date, l.out_station
        FROM leaves l
        JOIN employees e ON e.id=l.employee_id
        WHERE NOT (l.end_date < ? OR l.start_date > ?)
        ORDER BY e.name
    """, (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))).fetchall()
    c.close()

    data = {}
    for n,s,e,o in rows:
        data.setdefault(n, []).append({
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

@app.route("/add_employee", methods=["POST"])
def add_employee():
    name = request.json["name"]
    c = db()
    c.execute("INSERT OR IGNORE INTO employees (name) VALUES (?)", (name,))
    c.commit()
    c.close()
    return jsonify({"status": "added"})
    
@app.route("/export_csv")
def export_csv():
    import csv
    from flask import send_file

    temp_path = "/var/data/export_leaves.csv"

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        SELECT l.id, e.name, l.start_date, l.end_date, l.out_station
        FROM leaves l
        JOIN employees e ON e.id = l.employee_id
        ORDER BY l.start_date
    """)
    rows = cur.fetchall()
    conn.close()

    with open(temp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Employee Name", "Start Date", "End Date", "Out Station"])
        writer.writerows(rows)

    return send_file(temp_path, as_attachment=True)

if __name__ == "__main__":
    app.run()
