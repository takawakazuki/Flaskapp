from flask import Flask, render_template, request, redirect, g
import sqlite3
import os
from flask_login import (
    UserMixin, LoginManager, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
import calendar
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)
DATABASE = "gasoline.db"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ========== DB接続 ==========
def connect_db():
    rv = sqlite3.connect(DATABASE)
    rv.row_factory = sqlite3.Row
    return rv

def get_db():
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

def get_locations():
    return get_db().execute("SELECT id, name FROM locations").fetchall()

# ========== ユーザークラス ==========
class User(UserMixin):
    def __init__(self, user_id, userid):
        self.id = user_id
        self.userid = userid

@login_manager.user_loader
def load_user(user_id):
    row = get_db().execute("SELECT id, userid FROM user WHERE id=?", [user_id]).fetchone()
    if row:
        return User(row["id"], row["userid"])
    return None

@login_manager.unauthorized_handler
def unauthorized():
    return redirect('/login')

# ========== カレンダー ==========
class SimpleCalendar(calendar.HTMLCalendar):
    def __init__(self, year, month):
        super().__init__()
        self.year = year
        self.month = month

    def formatmonth_with_days(self):
        return self.formatmonth(self.year, self.month)

# ========== 認証 ==========
@app.route("/signup", methods=['GET', 'POST'])
def signup():
    error_message = ''
    if request.method == 'POST':
        userid = request.form.get('userid')
        password = request.form.get('password')
        name = request.form.get('name')
        pass_hash = generate_password_hash(password, method='pbkdf2:sha256')

        db = get_db()
        user_check = db.execute("SELECT userid FROM user WHERE userid=?", [userid]).fetchone()
        if not user_check:
            db.execute("INSERT INTO user (userid, password, name) VALUES (?, ?, ?)", [userid, pass_hash, name])
            db.commit()
            return redirect('/login')
        else:
            error_message = '入力されたユーザIDはすでに利用されています'

    return render_template('signup.html', error_message=error_message)

@app.route("/login", methods=['GET', 'POST'])
def login():
    error_message = ''
    if request.method == 'POST':
        userid = request.form.get('userid')
        password = request.form.get('password')
        user = get_db().execute("SELECT id, userid, password FROM user WHERE userid=?", [userid]).fetchone()
        if user and check_password_hash(user['password'], password):
            login_user(User(user['id'], user['userid']))
            return redirect('/')
        error_message = '入力されたIDもしくはパスワードが誤っています'
    return render_template('login.html', error_message=error_message)

@app.route("/logout")
def logout():
    logout_user()
    return redirect('/login')

# ========== メイン画面 ==========
@app.route("/")
@login_required
def index():
    # 月指定（デフォルトは今月）
    month_str = request.args.get("month")
    if month_str:
        year, month = map(int, month_str.split("-"))
    else:
        now = datetime.now()
        year, month = now.year, now.month
        month_str = now.strftime("%Y-%m")

    db = get_db()
    ride_list = db.execute("""
        SELECT r.id, r.date, g.name as go_location, r.go_driver, 
               b.name as back_location, r.back_driver
        FROM ride_records r
        LEFT JOIN locations g ON r.go_location_id = g.id
        LEFT JOIN locations b ON r.back_location_id = b.id
        WHERE r.user_id = ?
        AND strftime('%Y-%m', r.date) = ?
        ORDER BY r.date DESC
    """, [current_user.id, month_str]).fetchall()

    # 曜日付加 & 登録日リスト
    def get_weekday(date_str):
        y, m, d = map(int, date_str.split("-"))
        return ["月", "火", "水", "木", "金", "土", "日"][datetime(y, m, d).weekday()]

    rides = []
    registered_dates = set()
    for r in ride_list:
        r = dict(r)
        r['weekday'] = get_weekday(r['date'])
        registered_dates.add(r['date'])
        rides.append(r)

    # 新規登録可能日（たとえば当月の1日だけを例示）
    new_reg_date = f"{month_str}-01"
    can_register = new_reg_date not in registered_dates
    already_registered_dates = [r["date"] for r in ride_list]

    return render_template(
        "index.html",
        ride_list=rides,
        selected_month=month_str,
        already_registered_dates=registered_dates if not can_register else set()
    )




# ========== 新規登録 ==========
@app.route("/regist", methods=['GET', 'POST'])
@login_required
def regist():
    db = get_db()
    error_message = None

    # URLから指定された日付
    date_param = request.args.get('date') or request.form.get('date')

    # 自分の登録済み日付一覧を取得
    existing_dates = db.execute("""
        SELECT date FROM ride_records
        WHERE user_id = ?
    """, [current_user.id]).fetchall()

    registered_dates = [row['date'] for row in existing_dates]

    if date_param in registered_dates:
        # 同日登録済み → エラーメッセージ
        error_message = f"{date_param} はすでに登録されています。"

    if request.method == 'POST' and not error_message:
        user_id = current_user.id
        date = request.form.get('date')
        go_location_id = request.form.get('go_location_id')
        back_location_id = request.form.get('back_location_id')

        go_driver_list = request.form.getlist("go_driver")
        go_driver = int(go_driver_list[-1]) if go_driver_list else 0

        back_driver_list = request.form.getlist("back_driver")
        back_driver = int(back_driver_list[-1]) if back_driver_list else 0

        if not (date and go_location_id and back_location_id):
            error_message = "すべての項目を入力してください。"
        else:
            db.execute("""
                INSERT INTO ride_records (user_id, date, go_location_id, go_driver, back_location_id, back_driver)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [user_id, date, go_location_id, go_driver, back_location_id, back_driver])
            db.commit()
            return redirect("/")

    locations = get_locations()
    return render_template(
        "regist.html",
        locations=locations,
        error_message=error_message,
        default_date=date_param  # 日付フォーム初期値用
    )


# ========== 編集 ==========
@app.route("/<id>/edit", methods=['GET', 'POST'])
@login_required
def edit(id):
    db = get_db()
    if request.method == 'POST':
        date = request.form.get('date')
        go_location_id = request.form.get('go_location_id')
        go_driver = int(request.form.get('go_driver') or 0)
        back_location_id = request.form.get('back_location_id')
        back_driver = int(request.form.get('back_driver') or 0)

        db.execute("""
            UPDATE ride_records
            SET date=?, go_location_id=?, go_driver=?, back_location_id=?, back_driver=?
            WHERE id=? AND user_id=?
        """, [date, go_location_id, go_driver, back_location_id, back_driver, id, current_user.id])
        db.commit()
        return redirect("/")

    post = db.execute("SELECT * FROM ride_records WHERE id=? AND user_id=?", (id, current_user.id)).fetchone()
    locations = get_locations()
    return render_template("edit.html", post=post, locations=locations)


# ========== 削除 ==========
@app.route("/<id>/delete", methods=['GET', 'POST'])
@login_required
def delete(id):
    db = get_db()
    if request.method == 'POST':
        db.execute("DELETE FROM ride_records WHERE id=?", (id,))
        db.commit()
        return redirect("/")

    post = db.execute("SELECT * FROM ride_records WHERE id=?", (id,)).fetchone()
    return render_template("delete.html", post=post)

# ========== 精算画面 ==========
@app.route("/settlement")
@login_required
def settlement():
    db = get_db()

    # 🔽 クエリパラメータから年月を取得（例: 2025-07）
    month_str = request.args.get("month")
    if not month_str:
        month_str = datetime.now().strftime("%Y-%m")

    # ride_recordsとlocationsをJOINし、選択月のデータを取得
    records = db.execute("""
        SELECT 
            r.user_id,
            strftime('%Y-%m', r.date) AS month,
            r.go_driver, r.back_driver,
            g.price AS go_price, b.price AS back_price,
            u.name
        FROM ride_records r
        JOIN user u ON u.id = r.user_id
        LEFT JOIN locations g ON r.go_location_id = g.id
        LEFT JOIN locations b ON r.back_location_id = b.id
        WHERE strftime('%Y-%m', r.date) = ?
    """, [month_str]).fetchall()

    monthly_data = {}

    for row in records:
        key = (row["month"], row["user_id"], row["name"])
        if key not in monthly_data:
            monthly_data[key] = {"ride_total": 0, "drive_total": 0}

        if not row["go_driver"]:
            monthly_data[key]["ride_total"] += row["go_price"] or 0
        else:
            monthly_data[key]["drive_total"] += row["go_price"] or 0

        if not row["back_driver"]:
            monthly_data[key]["ride_total"] += row["back_price"] or 0
        else:
            monthly_data[key]["drive_total"] += row["back_price"] or 0

    # 月単位で合計
    ride_sum = sum(d["ride_total"] for d in monthly_data.values())
    drive_sum = sum(d["drive_total"] for d in monthly_data.values())

    result = []
    for (month, _, name), data in monthly_data.items():
        ride = data["ride_total"]
        drive = data["drive_total"]
        reward = (ride_sum * drive / drive_sum) if drive_sum > 0 else 0
        final = round(reward - ride)

        result.append({
            "month": month,
            "name": name,
            "ride_total": ride,
            "drive_reward": round(reward),
            "final_amount": final,
            "status": "受取" if final > 0 else "支払"
        })

    return render_template("settlement.html", settlements=result, selected_month=month_str)

# ========== 全体精算画面 ==========
@app.route("/settlement_all")
@login_required
def settlement_all():
    db = get_db()

    # クエリパラメータで月を取得（デフォルトは今月）
    month_str = request.args.get("month")
    if not month_str:
        month_str = datetime.now().strftime("%Y-%m")

    # 指定月のレコードを取得
    records = db.execute("""
        SELECT 
            r.user_id,
            strftime('%Y-%m', r.date) AS month,
            r.go_driver, r.back_driver,
            g.price AS go_price, b.price AS back_price,
            u.name
        FROM ride_records r
        JOIN user u ON u.id = r.user_id
        LEFT JOIN locations g ON r.go_location_id = g.id
        LEFT JOIN locations b ON r.back_location_id = b.id
        WHERE strftime('%Y-%m', r.date) = ?
    """, [month_str]).fetchall()

    # ユーザー単位で集計
    monthly_data = {}
    for row in records:
        key = (row["month"], row["user_id"], row["name"])
        if key not in monthly_data:
            monthly_data[key] = {"ride_total": 0, "drive_total": 0}

        if not row["go_driver"]:
            monthly_data[key]["ride_total"] += row["go_price"] or 0
        else:
            monthly_data[key]["drive_total"] += row["go_price"] or 0

        if not row["back_driver"]:
            monthly_data[key]["ride_total"] += row["back_price"] or 0
        else:
            monthly_data[key]["drive_total"] += row["back_price"] or 0

    # 月合計
    ride_sum = sum(d["ride_total"] for d in monthly_data.values())
    drive_sum = sum(d["drive_total"] for d in monthly_data.values())

    result = []
    for (month, _, name), data in monthly_data.items():
        ride = data["ride_total"]
        drive = data["drive_total"]
        reward = (ride_sum * drive / drive_sum) if drive_sum > 0 else 0
        final = round(reward - ride)

        result.append({
            "month": month,
            "name": name,
            "ride_total": ride,
            "drive_reward": round(reward),
            "final_amount": final,
            "status": "受取" if final > 0 else "支払"
        })

    return render_template("settlement_all.html", settlements=result, selected_month=month_str)

# ========== アプリ起動 ==========
if __name__ == "__main__":
    app.run(debug=True)
