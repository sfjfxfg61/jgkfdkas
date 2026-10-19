import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from words import LANGS,t


def test_three_labels_every_language():
    for lg in LANGS:
        for code in ('trial','forever','vip'):
            title=t(lg,'button_'+code)
            assert title and not title.startswith('button_')
            assert '/stop' not in t(lg,'notify_on')
        assert '⭐' in t(lg,'buy',trial=100,forever=250,vip=500,vip_days=30)


def test_user_requested_russian_names():
    assert t('ru','button_trial') == '💜 Наш секретик'
    assert t('ru','button_forever') == '💎 Безлимит навсегда'
    assert t('ru','button_vip') == '👑 VIP (доступ + личный чат)'


def test_user_can_opt_out_in_notifications_menu():
    # The old /stop command is removed, while the existing menu toggle still respects user choice.
    source=(Path(__file__).resolve().parents[1]/'main.py').read_text(encoding='utf8')
    assert "@router.message(Command('stop'))" not in source
    assert "callback_data='notify:off'" in source
