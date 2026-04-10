from flask import Flask, render_template, request, jsonify, send_file
import sqlite3, os, shutil

app = Flask(__name__)

# ========================================
#  DATABASE SETUP (Render Free Plan /tmp)
# ========================================

TMP_DB = "/tmp/leave.db"      # Live DB (writable)
LOCAL_DB = "leave.db"         # GitHub packaged DB (initial copy)

DB = TMP_DB

# Create DB inside /tmp on first run only
if not os.path.exists(TMP_DB):
    print("Database missing, creating /tmp/leave.db ...")

    if os.path.exists(LOCAL_DB):
        shutil.copy(LOCAL_DB, TMP_DB)
    else:
        conn = sqlite3.connect(TMP_DB)
        cur = conn.cursor()

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


# ========================================
#  ROUTES
# ========================================

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- EMPLOYEES ----------------
@app.route("/employees")
def employees():
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute("SELECT id, name FROM employees ORDER BY name").fetchall()
    conn.close()
    return jsonify(rows)


# ---------------- ADD LEAVE ----------------
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


# ---------------- GANTT DATA ----------------
@app.route("/gantt")
def gantt():
    from datetime import datetime, timedelta

    y = int(request.args["year"])
    m = int(request.args["month"])

    start = datetime(y, m, 1)
    end = (datetime(y+1,1,1) if m==12 else datetime(y,m+1,1)) - timedelta(days=1)

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


# ---------------- LIST LEAVES ----------------
@app.route("/list_leaves")
def list_leaves():
    conn = get_db()
    cur = conn.cursor()
    rows = cur.execute("""
        SELECT l.id, e.name, l.start_date, l.end_date, l.out_station
        FROM leaves l
        JOIN employees e ON e.id = l.employee_id
        ORDER BY l.start_date DESC
    """).fetchall()
    conn.close()

    return jsonify([
        {
            "id": r[0],
            "name": r[1],
            "start": r[2],
            "end": r[3],
            "out": r[4]
        }
        for r in rows
    ])


# ---------------- DELETE LEAVE ----------------
@app.route("/delete_leave/<int:leave_id>", methods=["DELETE"])
def delete_leave(leave_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM leaves WHERE id=?", (leave_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "deleted"})


# ---------------- EXPORT CSV ----------------
@app.route("/export_csv")
def export_csv():
    import csv

    export_path = "/tmp/export_leaves.csv"   # Temporary file

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT l.id, e.name, l.start_date, l.end_date, l.out_station
        FROM leaves l
        JOIN employees e ON e.id=l.employee_id
        ORDER BY l.start_date
    """)
    rows = cur.fetchall()
    conn.close()

    with open(export_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Employee Name", "Start Date", "End Date", "Out Station"])
        writer.writerows(rows)

    return send_file(export_path, as_attachment=True,
                     download_name="leave_data.csv")


# ---------------- SECRET BACKEND RESET (NOT IN UI) ----------------
@app.route("/reset_db")
def reset_db():
    if os.path.exists(TMP_DB):
        os.remove(TMP_DB)

    # Restore from repo or recreate empty
    if os.path.exists(LOCAL_DB):
        shutil.copy(LOCAL_DB, TMP_DB)
    else:
        conn = sqlite3.connect(TMP_DB)
        cur = conn.cursor()

        cur.execute("CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
        cur.execute("""
            CREATE TABLE leaves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                start_date TEXT,
                end_date TEXT,
                out_station TEXT,
                FOREIGN KEY(employee_id) REFERENCES employees(id)
            )
        """)

        conn.commit()
        conn.close()

    return "Database reset ok."


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True)
