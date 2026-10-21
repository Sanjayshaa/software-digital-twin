import psycopg2

db_url = "postgresql://digitaltwin_app:DigitalTwinEnterprise2026!Secure@db.ineuwvkzhhdqozqrsidv.supabase.co:5432/postgres?sslmode=require"

try:
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'repository_snapshots'
        ORDER BY ordinal_position;
    """)
    rows = cur.fetchall()
    print("COLUMNS IN repository_snapshots:")
    for r in rows:
        print(r)
    cur.close()
    conn.close()
except Exception as e:
    print("Error:", e)
