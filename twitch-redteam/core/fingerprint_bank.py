import hashlib
import json
import random
from pathlib import Path
from typing import List
from dataclasses import dataclass, asdict

@dataclass
class FingerprintProfile:
    profile_id: str
    platform: str
    user_agent: str
    webgl_vendor: str
    webgl_renderer: str
    canvas_seed: int
    audio_seed: int
    fonts_seed: int
    screen_width: int
    screen_height: int
    timezone: str
    locale: str
    hardware_concurrency: int
    device_memory: int
    
    def to_dict(self) -> dict: return asdict(self)
    @classmethod
    def from_dict(cls, data: dict): return cls(**data)

class FingerprintBank:
    def __init__(self, profiles_file: str = "config/fingerprints.json"):
        self.profiles_file = Path(profiles_file)
        self.profiles: List[FingerprintProfile] = []
        self._load_or_generate()
    
    def _load_or_generate(self):
        if self.profiles_file.exists():
            with open(self.profiles_file, 'r') as f:
                self.profiles = [FingerprintProfile.from_dict(p) for p in json.load(f)]
            print(f"✅ Загружено {len(self.profiles)} fingerprint-профилей")
        else:
            self._generate_default_profiles()
            self._save()
    
    def _save(self):
        self.profiles_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.profiles_file, 'w') as f:
            json.dump([p.to_dict() for p in self.profiles], f, indent=2)
        print(f"✅ Сохранено {len(self.profiles)} профилей")
    
    def _generate_default_profiles(self):
        platforms = [
            ("Win32", "Windows NT 10.0; Win64; x64", "NVIDIA Corporation", "NVIDIA GeForce RTX 3060"),
            ("MacIntel", "Macintosh; Intel Mac OS X 10_15_7", "Apple Inc.", "Apple M1"),
            ("Linux x86_64", "X11; Linux x86_64", "Intel Open Source Technology Center", "Mesa DRI Intel(R) UHD Graphics 630"),
        ]
        for i in range(5):
            profile_id = f"fp_profile_{i+1}"
            platform, ua_os, webgl_vendor, webgl_renderer = platforms[i % len(platforms)]
            seed = hashlib.sha256(profile_id.encode()).hexdigest()
            self.profiles.append(FingerprintProfile(
                profile_id=profile_id, platform=platform,
                user_agent=f"Mozilla/5.0 ({ua_os}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                webgl_vendor=webgl_vendor, webgl_renderer=webgl_renderer,
                canvas_seed=int(seed[:8], 16) % 10000, audio_seed=int(seed[8:16], 16) % 10000,
                fonts_seed=int(seed[16:24], 16) % 10000, screen_width=1920, screen_height=1080,
                timezone="America/New_York", locale="en-US", hardware_concurrency=8, device_memory=8
            ))

def test_fingerprint_bank():
    print("🧪 Тест FingerprintBank...")
    bank = FingerprintBank()
    print(f"📊 Всего профилей: {len(bank.profiles)}")
    for p in bank.profiles[:3]:
        print(f"  ID: {p.profile_id} | Platform: {p.platform} | WebGL: {p.webgl_renderer}")
    print("✅ Тест завершён")

if __name__ == "__main__":
    test_fingerprint_bank()
