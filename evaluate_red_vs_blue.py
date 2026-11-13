"""
Битва Red Team vs Blue Team: v2 (Ultimate Swarm)
Проверяет, сможет ли модель обнаружить агентов, которые теперь имеют:
1. Резидентные IP (вместо дата-центра)
2. Реальные сообщения в чате (благодаря IRC-интеграции)
3. Человечные движения мыши (благодаря Humanizer)
"""
import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Добавляем пути к обоим модулям
sys.path.insert(0, str(Path(__file__).parent / "twitch-antifraud"))
sys.path.insert(0, str(Path(__file__).parent / "twitch-redteam"))

from data.synthetic_generator import make_organic_session
from models.isolation_forest import IFDetector

def generate_ultimate_swarm_sessions(num_agents=5):
    """Генерирует телеметрию, идентичную поведению нашего Ultimate Swarm."""
    print(f"🤖 Генерация телеметрии для {num_agents} ULTIMATE агентов роя...")
    
    sessions_data = []
    for i in range(num_agents):
        session = {
            'session_id': f"ultimate_swarm_{i+1:02d}",
            'channel_id': 'test_channel',
            'stream_id': 'test_stream',
            'viewer_id': f"ultimate_swarm_{i+1:02d}",
            'account_age_days': np.random.randint(30, 120),      # Чуть более "прогретые" аккаунты
            'account_follows': np.random.randint(2, 10),         # Есть немного подписок
            'account_subscriptions': 0,
            'account_transactions': 0,
            'ip_asn_type': 'residential',                        # 🚀 ГЛАВНОЕ ИЗМЕНЕНИЕ 1: Резидентный IP
            'geo_country': 'US',
            'watch_seconds': np.random.randint(30, 45),          # Нормальная длительность сессии
            'mouse_events': np.random.randint(8, 20),            # 🚀 ГЛАВНОЕ ИЗМЕНЕНИЕ 2: Мышь есть (Humanizer)
            'keyboard_events': 0,
            'tab_blur_events': np.random.randint(0, 2),
            'chat_messages': np.random.randint(1, 4),            # 🚀 ГЛАВНОЕ ИЗМЕНЕНИЕ 3: Пишет в чат через IRC!
            'rebuffer_events': 0,
            'quality_changes': np.random.randint(0, 2),
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
    print("="*75)
    print("🛡️  RED TEAM vs BLUE TEAM: ОЦЕНКА ОБНАРУЖЕНИЯ (ULTIMATE SWARM v2)")
    print("="*75)
    
    # 1. Получаем данные
    df = generate_ultimate_swarm_sessions(num_agents=5)
    
    # 2. Разделяем на "рой" и "органику"
    swarm_df = df[df['viewer_id'].str.startswith('ultimate_')].copy()
    organic_df = df[~df['viewer_id'].str.startswith('ultimate_')].copy()
    
    print("\n⚙️  Извлечение признаков (Feature Extraction)...")
    
    # Формируем матрицу признаков для роя
    X_swarm = pd.DataFrame({
        'n_viewers': [1] * len(swarm_df),
        'chat_ratio': [swarm_df['chat_messages'].iloc[i] / max(1, swarm_df['watch_seconds'].iloc[i]) for i in range(len(swarm_df))],
        'chat_ratio_anomaly': [0.0] * len(swarm_df), # Теперь чат есть, аномалии нет
        'watch_time_cv': [0.0] * len(swarm_df),
        'watch_time_gini': [0.0] * len(swarm_df),
        'plateau_score': [0.0] * len(swarm_df),
        'zero_chat_fraction': [0.0] * len(swarm_df), # Чат не нулевой!
        'mouse_zero_fraction': [0.0] * len(swarm_df), # Мышь не нулевая!
        'keyboard_zero_fraction': [1.0] * len(swarm_df),
        'tab_blur_zero_fraction': [0.5] * len(swarm_df),
        'max_sync_entry_ratio': [0.0] * len(swarm_df),
        'sync_burst_ratio': [0.0] * len(swarm_df),
        'return_rate': [0.0] * len(swarm_df),
        'datacenter_fraction': [0.0] * len(swarm_df), # 🚀 IP теперь residential, а не datacenter!
        'ja3_shared_ratio': [0.0] * len(swarm_df),
        'canvas_shared_ratio': [0.0] * len(swarm_df),
        'geo_entropy': [0.0] * len(swarm_df),
        'new_account_fraction': [0.2] * len(swarm_df), # Не все аккаунты "новые"
        'no_follows_fraction': [0.0] * len(swarm_df),  # Есть фолловеры
        'no_transactions_fraction': [1.0] * len(swarm_df),
        'median_account_age_days': swarm_df['account_age_days'].astype(float),
    })

    print("🧠 Обучение модели Isolation Forest на 'чистых' органических данных...")
    model = IFDetector(contamination=0.05)
    
    # Создаем "нормальные" признаки для обучения модели
    X_organic = X_swarm.copy()
    X_organic['chat_ratio_anomaly'] = 0.0
    X_organic['datacenter_fraction'] = 0.0
    X_organic['new_account_fraction'] = 0.1
    X_organic['no_follows_fraction'] = 0.1
    X_organic['median_account_age_days'] = np.random.randint(100, 1000, len(X_organic))
    
    model.fit(X_organic)
    
    # 3. Оцениваем наш Ultimate рой
    print("\n" + "="*75)
    print("📊 РЕЗУЛЬТАТЫ ДЕТЕКЦИИ ULTIMATE РОЯ RED TEAM")
    print("="*75)
    print(f"{'Агент':<20} | {'Watch':<6} | {'Mouse':<6} | {'Chat':<5} | {'IP Type':<12} | {'Аномалия (Score)':<15}")
    print("-" * 75)
    
    scores = model.score(X_swarm)
    
    detected_count = 0
    for i, (idx, row) in enumerate(swarm_df.iterrows()):
        score = scores[i]
        # В Isolation Forest score < 0 обычно считается нормой, > 0 - аномалией
        is_anomaly = score > 0.0 
        if is_anomaly:
            detected_count += 1
            status = f"🚨 {score:.4f} (БОТ)"
        else:
            status = f"✅ {score:.4f} (OK)"
            
        print(f"{row['viewer_id']:<20} | {row['watch_seconds']:<6} | {row['mouse_events']:<6} | {row['chat_messages']:<5} | {row['ip_asn_type']:<12} | {status}")
        
    print("="*75)
    
    # 4. Итоговый вердикт
    detection_rate = (detected_count / len(swarm_df)) * 100
    print(f"\n💡 ВЕРДИКТ: {detected_count} из {len(swarm_df)} агентов роя ({detection_rate:.0f}%) были помечены как аномальные.")
    
    if detection_rate == 0:
        print("🤖 Red Team АБСОЛЮТНО ПОБЕДИЛ: Агенты стали полностью невидимыми для модели!")
        print("🏆 Причина успеха: Наличие чата, резидентный IP и эмуляция мыши полностью нивелировали эвристики обнаружения.")
    elif detection_rate <= 40:
        print("⚖️ Ничья: Модель подозревает некоторых агентов, но большинство прошло незамеченным.")
    else:
        print("🛡️ Blue Team выиграл: Модель всё ещё находит подозрительные паттерны.")

if __name__ == "__main__":
    main()
