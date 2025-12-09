#!/usr/bin/env python3
"""Initialize and populate the travel agency database with attractions data."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / 'travel_agency.db'


def init_attractions_table(conn: sqlite3.Connection):
    """Create attractions table if it doesn't exist."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attractions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            city TEXT NOT NULL,
            country TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            rating REAL,
            opening_hours TEXT,
            entry_fee REAL,
            recommended_duration_hours REAL,
            coordinates TEXT,
            tags TEXT
        )
    """)
    conn.commit()
    print("✓ Attractions table created")


def populate_attractions(conn: sqlite3.Connection):
    """Populate attractions table with sample data."""
    cursor = conn.cursor()
    
    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM attractions")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"✓ Attractions table already has {count} records")
        return
    
    attractions = [
        # フランス/パリ
        ("エッフェル塔", "Paris", "France", "Landmark", "パリの象徴的な鉄塔", 4.7, "09:00-23:00", 26.0, 2.0, "48.8584,2.2945", "観光,記念碑,夜景"),
        ("ルーヴル美術館", "Paris", "France", "Museum", "世界最大の美術館の一つ", 4.8, "09:00-18:00", 17.0, 4.0, "48.8606,2.3376", "美術,歴史,文化"),
        ("ノートルダム大聖堂", "Paris", "France", "Religious", "ゴシック建築の傑作", 4.6, "08:00-18:45", 0.0, 1.5, "48.8530,2.3499", "歴史,建築,宗教"),
        ("シャンゼリゼ通り", "Paris", "France", "Shopping", "パリのメインストリート", 4.5, "全天", 0.0, 2.0, "48.8698,2.3081", "ショッピング,レストラン"),
        ("モンマルトル", "Paris", "France", "Historic", "芸術家の街", 4.6, "全天", 0.0, 3.0, "48.8867,2.3431", "観光,芸術,パノラマ"),
        
        # イギリス/ロンドン
        ("ビッグ・ベン", "London", "United Kingdom", "Landmark", "ロンドンの象徴的な時計塔", 4.6, "全天", 0.0, 0.5, "51.4994,-0.1245", "観光,記念碑"),
        ("大英博物館", "London", "United Kingdom", "Museum", "世界最大級の博物館", 4.7, "10:00-17:00", 0.0, 3.0, "51.5194,-0.1270", "歴史,文化,美術"),
        ("タワー・ブリッジ", "London", "United Kingdom", "Landmark", "ロンドンの名橋", 4.5, "09:30-17:00", 12.0, 1.5, "51.5055,-0.0754", "観光,建築"),
        ("バッキンガム宮殿", "London", "United Kingdom", "Historic", "イギリス王室の宮殿", 4.5, "09:30-19:30", 32.0, 2.0, "51.5014,-0.1419", "歴史,文化,観光"),
        ("ハイドパーク", "London", "United Kingdom", "Park", "ロンドン最大の公園", 4.6, "05:00-00:00", 0.0, 2.0, "51.5074,-0.1638", "自然,リラックス,散歩"),
        
        # 日本/東京
        ("東京スカイツリー", "Tokyo", "Japan", "Landmark", "世界一高いタワー", 4.6, "08:00-22:00", 23.0, 2.0, "35.7101,139.8107", "観光,夜景,展望台"),
        ("浅草寺", "Tokyo", "Japan", "Religious", "東京最古の寺院", 4.5, "06:00-17:00", 0.0, 1.5, "35.7148,139.7967", "歴史,文化,参拝"),
        ("東京ディズニーランド", "Tokyo", "Japan", "Entertainment", "夢の国", 4.7, "08:00-22:00", 84.0, 8.0, "35.6329,139.8804", "エンターテインメント,家族"),
        ("皇居", "Tokyo", "Japan", "Historic", "天皇の住まい", 4.4, "09:00-16:30", 0.0, 2.0, "35.6812,139.7536", "歴史,文化,散歩"),
        ("渋谷スクランブル交差点", "Tokyo", "Japan", "Landmark", "世界一混雑する交差点", 4.3, "全天", 0.0, 0.5, "35.6598,139.7006", "観光,ショッピング"),
        
        # アメリカ/ニューヨーク
        ("自由の女神像", "New York", "United States", "Landmark", "アメリカの象徴", 4.6, "09:00-17:00", 24.0, 2.0, "40.6892,-74.0445", "観光,歴史,記念碑"),
        ("エンパイアステートビル", "New York", "United States", "Landmark", "アールデコ様式の高層ビル", 4.6, "08:00-02:00", 44.0, 1.5, "40.7484,-73.9857", "観光,展望台"),
        ("セントラルパーク", "New York", "United States", "Park", "マンハッタンのオアシス", 4.7, "06:00-01:00", 0.0, 3.0, "40.7829,-73.9654", "自然,リラックス"),
        ("メトロポリタン美術館", "New York", "United States", "Museum", "世界最大級の美術館", 4.7, "10:00-17:30", 25.0, 4.0, "40.7794,-73.9632", "美術,文化,歴史"),
        ("タイムズスクエア", "New York", "United States", "Entertainment", "世界の十字路", 4.5, "全天", 0.0, 1.0, "40.7580,-73.9855", "ショッピング,エンターテインメント"),
        
        # イタリア/ローマ
        ("コロッセオ", "Rome", "Italy", "Historic", "古代ローマの円形闘技場", 4.7, "08:30-19:00", 16.0, 2.5, "41.8902,12.4922", "歴史,建築,観光"),
        ("バチカン市国", "Rome", "Italy", "Religious", "世界最小の独立国家", 4.8, "07:00-19:00", 0.0, 4.0, "41.9029,12.4534", "宗教,歴史,美術"),
        ("トレヴィの泉", "Rome", "Italy", "Landmark", "願い事の泉", 4.5, "全天", 0.0, 0.5, "41.9009,12.4833", "観光,願掛け"),
        ("スペイン階段", "Rome", "Italy", "Landmark", "ローマの有名な階段", 4.4, "全天", 0.0, 0.5, "41.9058,12.4822", "観光,建築"),
        
        # スペイン/バルセロナ
        ("サグラダ・ファミリア", "Barcelona", "Spain", "Religious", "ガウディの未完の傑作", 4.7, "09:00-18:00", 26.0, 2.0, "41.4036,2.1744", "建築,宗教,観光"),
        ("グエル公園", "Barcelona", "Spain", "Park", "ガウディのモザイク公園", 4.6, "08:00-20:30", 10.0, 2.0, "41.4145,2.1527", "建築,公園,観光"),
        ("ランブラス通り", "Barcelona", "Spain", "Shopping", "バルセロナのメインストリート", 4.5, "全天", 0.0, 2.0, "41.3802,2.1734", "ショッピング,レストラン"),
    ]
    
    cursor.executemany("""
        INSERT INTO attractions (name, city, country, category, description, rating, opening_hours, entry_fee, recommended_duration_hours, coordinates, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, attractions)
    
    conn.commit()
    print(f"✓ Inserted {len(attractions)} attraction records")


def enhance_existing_data(conn: sqlite3.Connection):
    """Add more flights, hotels, and rental cars data."""
    cursor = conn.cursor()
    
    # Add more flights
    additional_flights = [
        # 日本関連
        ("JAL", 51, "NRT", "CDG", "ECONOMY", 850.0),
        ("JAL", 51, "NRT", "CDG", "BUSINESS", 2500.0),
        ("ANA", 101, "NRT", "LHR", "ECONOMY", 900.0),
        ("ANA", 101, "NRT", "LHR", "BUSINESS", 2800.0),
        ("JAL", 61, "NRT", "JFK", "ECONOMY", 1100.0),
        # ヨーロッパ関連
        ("Air France", 201, "CDG", "LHR", "ECONOMY", 200.0),
        ("British Airways", 301, "LHR", "FCO", "ECONOMY", 250.0),
        ("Lufthansa", 401, "FRA", "BCN", "ECONOMY", 180.0),
    ]
    
    # Check existing flights count
    cursor.execute("SELECT COUNT(*) FROM flights")
    flight_count = cursor.fetchone()[0]
    if flight_count < 50:
        cursor.executemany("""
            INSERT OR IGNORE INTO flights (carrier, flight_number, from_airport, to_airport, ticket_class, price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, additional_flights)
        print(f"✓ Added {len(additional_flights)} additional flights")
    
    # Add more hotels
    additional_hotels = [
        ("パリ・リッツ・ホテル", "Paris", "HOTEL", "SUITE", 450.0),
        ("ザ・サボイ", "London", "HOTEL", "SUITE", 500.0),
        ("東京帝國ホテル", "Tokyo", "HOTEL", "SUITE", 350.0),
        ("ザ・プラザ", "New York", "HOTEL", "SUITE", 600.0),
        ("ホテル・デ・クリヨン", "Paris", "HOTEL", "DOUBLE", 380.0),
        ("コニャック・ジェイ", "London", "HOTEL", "DOUBLE", 320.0),
    ]
    
    cursor.execute("SELECT COUNT(*) FROM hotels")
    hotel_count = cursor.fetchone()[0]
    if hotel_count < 30:
        cursor.executemany("""
            INSERT OR IGNORE INTO hotels (name, city, hotel_type, room_type, price_per_night)
            VALUES (?, ?, ?, ?, ?)
        """, additional_hotels)
        print(f"✓ Added {len(additional_hotels)} additional hotels")
    
    conn.commit()


def main():
    """Main function."""
    print("Initializing travel agency database...")
    
    db_path = Path(DB_PATH)
    if not db_path.exists():
        print(f"✗ Database not found at {db_path}")
        sys.exit(1)
    
    try:
        conn = sqlite3.connect(str(db_path))
        init_attractions_table(conn)
        populate_attractions(conn)
        enhance_existing_data(conn)
        conn.close()
        print("\n✓ Database initialization completed successfully!")
    except Exception as e:
        print(f"\n✗ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

