#!/usr/bin/env python3
# bootstrap5_1.py — добавляет juggler_sync.py и интеграцию с Camoufox
from pathlib import Path

FILES = {}

FILES["twitch-redteam/core/juggler_sync.py"] = '''\
<вставить содержимое core/juggler_sync.py из ответа выше>
'''

# Патч browser_factory.py — добавляем ветку camoufox
# (полный файл перезаписывать не нужно, только фрагмент)
FILES["twitch-redteam/patches/browser_factory_camoufox_patch.py"] = '''\
"""
Фрагмент для ручной интеграции в core/browser_factory.py.

Найдите метод create_context и добавьте в начало:
    if self.engine == "camoufox":
        return await self._create_camoufox_context(profile, fp_profile)

Затем добавьте сам метод _create_camoufox_context.
"""
'''

FILES["twitch-redteam/tools/check_juggler.py"] = '''\
"""
Проверка согласованности Camoufox config для профиля из Profiles Bank.

Запуск:
  python tools/check_juggler.py
  python tools/check_juggler.py --profile win_rtx3060_1080p
"""
import argparse
from core.fingerprint_manager import ProfilesBank
from core.juggler_sync import JugglerSync


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    bank = ProfilesBank("config/profiles_bank.yaml")
    if args.profile:
        fp = next((p for p in bank.profiles if p.id == args.profile), None)
        if not fp:
            print(f"Профиль {args.profile} не найден")
            return
    else:
        fp = bank.pick()

    print(f"Профиль: {fp.id}")
    sync = JugglerSync(fp)
    report = sync.verify_config()

    print(f"\\nСогласованность: {report['consistent']}")
    if report["issues"]:
        for issue in report["issues"]:
            print(f"  ✗ {issue}")
    else:
        print("  ✓ Все поля согласованы")

    print("\\nConfig (первые 10 ключей):")
    for k, v in list(report["config"].items())[:10]:
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
'''

def write_all():
    for rel, content in FILES.items():
        p = Path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        print(f"  ok {rel}")

if __name__ == "__main__":
    write_all()
    print()
    print("Next steps:")
    print("  1. Вручную добавьте ветку camoufox в core/browser_factory.py")
    print("  2. Проверьте config:")
    print("     python tools/check_juggler.py")
    print("  3. Переключите движок:")
    print("     bash tools/switch_engine.sh camoufox")
    print("  4. Запустите:")
    print("     python run_lab_v5.py")