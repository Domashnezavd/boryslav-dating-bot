import sqlite3

DB_NAME = "boryslav_dating.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблиця користувачів
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT,
            age INTEGER,
            gender TEXT,
            search_gender TEXT,
            location TEXT,
            photo TEXT,
            bio TEXT,
            is_verified INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            rating INTEGER DEFAULT 0,
            zodiac TEXT,
            answers TEXT
        )
    ''')
    
    # Таблиця лайків
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            from_user INTEGER,
            to_user INTEGER,
            is_like INTEGER,
            PRIMARY KEY (from_user, to_user)
        )
    ''')
    
    # Таблиця скарг
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER,
            target_id INTEGER,
            reason TEXT,
            status TEXT DEFAULT 'pending'
        )
    ''')

    # Таблиця оголошень (Локальна стрічка)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            text TEXT,
            created_at REAL
        )
    ''')
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Базу даних успішно налаштовано!")
