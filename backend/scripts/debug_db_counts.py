import sqlite3


def main() -> None:
    db_path = "backend/backend/app/data/healthdiary.db"
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    print("db_path:", db_path)
    print("tables:", cur.execute("select name from sqlite_master where type='table'").fetchall())
    print("symptom by user:", cur.execute("select user_id, count(*) from symptom_entries group by user_id").fetchall())
    print("meal by user:", cur.execute("select user_id, count(*) from meal_entries group by user_id").fetchall())
    print(
        "demo-user-1 symptom min/max ts:",
        cur.execute("select min(ts), max(ts) from symptom_entries where user_id = 'demo-user-1'").fetchone(),
    )
    print(
        "demo-user-1 latest symptoms:",
        cur.execute(
            "select ts, symptom_raw from symptom_entries where user_id = 'demo-user-1' order by ts desc limit 5"
        ).fetchall(),
    )
    con.close()


if __name__ == "__main__":
    main()
