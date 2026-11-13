"""
Битва Red Team vs Blue Team.
Генерирует сессии, имитирующие поведение нашего роя агентов, 
и проверяет, сможет ли модель Isolation Forest их обнаружить.
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Добавляем пути к обоим модулям
sys.path.insert(0, str(Path(__file__).parent / "twitch-antifraud"))
sys.path.insert(0, str(Path(__file__).parent / "twitch-redteam"))

from data.synthetic_generator import make_organic_session, make_bot_session
from features.pipeline import build_feature_matrix
from models.isolation_forest import IFDetector

def generate_swarm_sessions(num_agents=5):
    """Генерирует данные, имитирующие поведение нашего продвинутого роя."""
    print(f"🤖 Генерация телеметрии для {num_agents} агентов роя...")
    
    sessions_data = []
    for i in range(num_agents):
        # Наш рой ведет себя "подозрительно идеально" для ML-модели:
        # - Нет чата (или очень мало)
        # - Мышь двигается, но паттерны могут быть выявлены
        # - IP часто выглядит как дата-центр (если нет резидентных прокси)
        session = {
            'session_id': f"swarm_agent_{i+1:02d}",
            'channel_id': 'test_channel',
            'stream_id': 'test_stream',
            'viewer_id': f"swarm_agent_{i+1:02d}",
            'account_age_days': np.random.randint(10, 50),      # Молодые аккаунты
            'account_follows': np.random.randint(0, 5),         # Мало подписок
            'account_subscriptions': 0,
            'account_transactions': 0,
            'ip_asn_type': np.random.choice(['datacenter', 'vpn'], p=[0.7, 0.3]), # Подозрительный IP
            'geo_country': 'US',
            'watch_seconds': np.random.randint(15, 30),         # Короткие сессии (как в нашем тесте)
            'mouse_events': np.random.randint(5, 15),           # Мышь есть (благодаря humanizer)
            'keyboard_events': 0,                               # Нет клавиатуры
            'tab_blur_events': 0,
            'chat_messages': 0,                                 # Чат не используется в браузере
            'rebuffer_events': 0,
            'quality_changes': 0,
            'fullscreen_events': 0,
        }
        sessions_data.append(session)
    
    # Для сравнения добавим 50 "нормальных" органических сессий
    print("👥 Генерация 50 нормальных органических сессий для контекста...")
    for _ in range(50):
        org_session = make_organic_session("test_channel", "test_stream")
        sessions_data.append({
            'session_id': f"organic_{_}",
            'channel_id': org_session.channel_id,
            'stream_id': org_session.stream_id,
            'viewer_id': org_session.viewer_id,
            'account_age_days': org_session.account_age_days,
            'account_follows': org_session.account_follows,
            'account_subscriptions': org_session.account_subscriptions,
            'account_transactions': org_session.account_transactions,
            'ip_asn_type': org_session.ip_asn_type,
            'geo_country': org_session.geo_country,
            'watch_seconds': org_session.watch_seconds,
            'mouse_events': org_session.mouse_events,
            'keyboard_events': org_session.keyboard_events,
            'tab_blur_events': org_session.tab_blur_events,
            'chat_messages': org_session.chat_messages,
            'rebuffer_events': org_session.rebuffer_events,
            'quality_changes': org_session.quality_changes,
            'fullscreen_events': org_session.fullscreen_events,
        })
    
    return pd.DataFrame(sessions_data)

def main():
    print("="*70)
    print("🛡️  RED TEAM vs BLUE TEAM: ОЦЕНКА ОБНАРУЖЕНИЯ")
    print("="*70)
    
    # 1. Получаем данные
    df = generate_swarm_sessions(num_agents=5)
    
    # 2. Разделяем на "рой" и "органику" для оценки
    swarm_df = df[df['viewer_id'].str.startswith('swarm_')].copy()
    organic_df = df[~df['viewer_id'].str.startswith('swarm_')].copy()
    
    print("\n⚙️  Извлечение признаков (Feature Extraction)...")
    # Упрощенная эмуляция build_feature_matrix для плоского DataFrame
    # В реальном пайплайне здесь был бы группировка по stream_id, но для демо адаптируем
    X_swarm = pd.DataFrame({
        'n_viewers': [1] * len(swarm_df),
        'chat_ratio': [0.0] * len(swarm_df),
        'chat_ratio_anomaly': [1.0] * len(swarm_df), # 0 чат при активности = аномалия
        'watch_time_cv': [0.0] * len(swarm_df),
        'watch_time_gini': [0.0] * len(swarm_df),
        'plateau_score': [0.0] * len(swarm_df),
        'zero_chat_fraction': [1.0] * len(swarm_df),
        'mouse_zero_fraction': [0.0] * len(swarm_df), # Мышь есть благодаря humanizer!
        'keyboard_zero_fraction': [1.0] * len(swarm_df),
        'tab_blur_zero_fraction': [1.0] * len(swarm_df),
        'max_sync_entry_ratio': [0.0] * len(swarm_df),
        'sync_burst_ratio': [0.0] * len(swarm_df),
        'return_rate': [0.0] * len(swarm_df),
        'datacenter_fraction': [1.0 if ip in ['datacenter', 'vpn'] else 0.0 for ip in swarm_df['ip_asn_type']],
        'ja3_shared_ratio': [0.0] * len(swarm_df),
        'canvas_shared_ratio': [0.0] * len(swarm_df),
        'geo_entropy': [0.0] * len(swarm_df),
        'new_account_fraction': [1.0] * len(swarm_df),
        'no_follows_fraction': [1.0] * len(swarm_df),
        'no_transactions_fraction': [1.0] * len(swarm_df),
        'median_account_age_days': swarm_df['account_age_days'].astype(float),
    })

    print("🧠 Обучение модели Isolation Forest на 'чистых' органических данных...")
    model = IFDetector(contamination=0.05)
    
    # Создаем "нормальные" признаки для обучения
    X_organic = X_swarm.copy()
    X_organic['chat_ratio_anomaly'] = 0.0
    X_organic['datacenter_fraction'] = 0.0
    X_organic['new_account_fraction'] = 0.0
    X_organic['no_follows_fraction'] = 0.0
    X_organic['median_account_age_days'] = np.random.randint(300, 2000, len(X_organic))
    
    model.fit(X_organic)
    
    # 3. Оцениваем наш рой
    print("\n" + "="*70)
    print("📊 РЕЗУЛЬТАТЫ ДЕТЕКЦИИ РОЯ RED TEAM")
    print("="*70)
    print(f"{'Агент':<18} | {'Watch (s)':<10} | {'Mouse':<6} | {'IP Type':<12} | {'Аномалия (Score)':<15}")
    print("-" * 70)
    
    scores = model.score(X_swarm)
    
    detected_count = 0
    for i, (idx, row) in enumerate(swarm_df.iterrows()):
        score = scores[i]
        # В Isolation Forest более высокий score = более высокая аномальность
        is_anomaly = score > 0.0 
        if is_anomaly:
            detected_count += 1
            status = f"🚨 {score:.4f} (БОТ)"
        else:
            status = f"✅ {score:.4f} (OK)"
            
        print(f"{row['viewer_id']:<18} | {row['watch_seconds']:<10} | {row['mouse_events']:<6} | {row['ip_asn_type']:<12} | {status}")
        
    print("="*70)
    
    # 4. Итоговый вердикт
    detection_rate = (detected_count / len(swarm_df)) * 100
    print(f"\n💡 ВЕРДИКТ: {detected_count} из {len(swarm_df)} агентов роя ({detection_rate:.0f}%) были помечены как аномальные.")
    
    if detection_rate > 50:
        print("🛡️  Blue Team ПОБЕДИЛ: Модель успешно выявила подозрительные паттерны (возраст аккаунта, IP, отсутствие чата).")
        print("🔧 Рекомендация Red Team: Добавьте эмуляцию чата через IRC, прогрев аккаунтов и резидентные прокси.")
    else:
        print("🤖 Red Team ПОБЕДИЛ: Агенты успешно замаскировались под нормальный трафик!")
        print("🔧 Рекомендация Blue Team: Ужесточите правила для новых аккаунтов с нулевым чатом.")

if __name__ == "__main__":
    main()
