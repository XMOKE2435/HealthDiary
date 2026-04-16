import sqlite3


def inspect(path: str) -> None:
    con = sqlite3.connect(path)
    cur = con.cursor()
    count = cur.execute(
        "select count(*) from symptom_entries where user_id='demo-user-1'"
    ).fetchone()[0]
    rows = cur.execute(
        "select json_extract(fields_json, '$.symptom_label') as label, count(*) "
        "from symptom_entries where user_id='demo-user-1' "
        "group by label order by count(*) desc"
    ).fetchall()
    print("DB:", path)
    print("symptom_count:", count)
    print("labels:", rows)
    con.close()


if __name__ == "__main__":
    inspect("backend/backend/app/data/healthdiary.db")
    inspect("backend/app/data/healthdiary.db")
