"""Tests for pure game logic functions."""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.game_logic import (
    VALID_DART_SCORES,
    Outcome,
    Prompt,
    build_indexes,
    build_prompt_pool,
    clean_player_record,
    evaluate_submission,
    matches_prompt,
    normalize_name_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_player(name='Test Player', country='ENG', positions='MF', clubs='Arsenal', apps=100):
    return {
        'name': name,
        'name_key': normalize_name_key(name),
        'country': country,
        'positions': positions,
        'clubs': clubs,
        'apps': apps,
    }


def make_index(players):
    return build_indexes(players)


# ---------------------------------------------------------------------------
# VALID_DART_SCORES
# ---------------------------------------------------------------------------

class TestDartScores:
    def test_zero_included(self):
        assert 0 in VALID_DART_SCORES

    def test_180_included(self):
        assert 180 in VALID_DART_SCORES

    def test_classic_checkouts(self):
        # Common finishing scores
        for score in [100, 50, 36, 40, 32, 170, 160]:
            assert score in VALID_DART_SCORES

    def test_unreachable_excluded(self):
        for score in [163, 166, 169, 172, 173, 175, 176, 178, 179]:
            assert score not in VALID_DART_SCORES

    def test_no_score_above_180(self):
        assert max(VALID_DART_SCORES) == 180

    def test_minimum_30_valid_scores_under_180(self):
        assert len([s for s in VALID_DART_SCORES if s <= 180]) >= 100


# ---------------------------------------------------------------------------
# clean_player_record
# ---------------------------------------------------------------------------

class TestCleanPlayerRecord:
    def test_dedupes_positions(self):
        raw = {'name': 'X', 'country': 'ENG', 'clubs': 'Arsenal',
               'position': 'DF, MF, DF, MF', 'apps': 50}
        c = clean_player_record(raw)
        positions = set(c['positions'].split(','))
        assert positions == {'DF', 'MF'}

    def test_dedupes_clubs(self):
        raw = {'name': 'X', 'country': 'ENG',
               'clubs': 'Arsenal, Arsenal, Chelsea', 'position': 'MF', 'apps': 50}
        c = clean_player_record(raw)
        clubs = [cl for cl in c['clubs'].split(',') if cl]
        assert clubs.count('Arsenal') == 1

    def test_filters_invalid_positions(self):
        raw = {'name': 'X', 'country': 'ENG', 'clubs': 'Arsenal',
               'position': 'DF, UNKNOWN, GK', 'apps': 50}
        c = clean_player_record(raw)
        positions = set(c['positions'].split(','))
        assert 'UNKNOWN' not in positions
        assert {'DF', 'GK'} == positions

    def test_name_key_normalised(self):
        raw = {'name': 'Tévez', 'country': 'ARG', 'clubs': 'Chelsea',
               'position': 'FW', 'apps': 100}
        c = clean_player_record(raw)
        assert c['name_key'] == 'tevez'


# ---------------------------------------------------------------------------
# Prompt matching (the country_club bug fix)
# ---------------------------------------------------------------------------

class TestMatchesPrompt:
    def _player(self, country='ENG', positions='MF', clubs='Arsenal'):
        return make_player(country=country, positions=positions, clubs=clubs)

    def test_club_position_match(self):
        p = make_player(positions='MF', clubs='Arsenal')
        prompt = Prompt('club_position', 'Arsenal', 'arsenal', '', 'MF', '', 0)
        assert matches_prompt(p, prompt)

    def test_club_position_wrong_position(self):
        p = make_player(positions='GK', clubs='Arsenal')
        prompt = Prompt('club_position', 'Arsenal', 'arsenal', '', 'MF', '', 0)
        assert not matches_prompt(p, prompt)

    def test_club_position_wrong_club(self):
        p = make_player(positions='MF', clubs='Chelsea')
        prompt = Prompt('club_position', 'Arsenal', 'arsenal', '', 'MF', '', 0)
        assert not matches_prompt(p, prompt)

    def test_country_position_match(self):
        p = make_player(country='ENG', positions='FW')
        prompt = Prompt('country_position', '', '', 'ENG', 'FW', '', 0)
        assert matches_prompt(p, prompt)

    def test_country_position_wrong_country(self):
        p = make_player(country='FRA', positions='FW')
        prompt = Prompt('country_position', '', '', 'ENG', 'FW', '', 0)
        assert not matches_prompt(p, prompt)

    def test_country_club_match_no_position_required(self):
        """country_club should NOT check position (bug fix)."""
        p = make_player(country='BRA', positions='MF', clubs='Chelsea')
        prompt = Prompt('country_club', 'Chelsea', 'chelsea', 'BRA', '', '', 0)
        assert matches_prompt(p, prompt)

    def test_country_club_wrong_country(self):
        p = make_player(country='ARG', clubs='Chelsea')
        prompt = Prompt('country_club', 'Chelsea', 'chelsea', 'BRA', '', '', 0)
        assert not matches_prompt(p, prompt)

    def test_country_club_wrong_club(self):
        p = make_player(country='BRA', clubs='Arsenal')
        prompt = Prompt('country_club', 'Chelsea', 'chelsea', 'BRA', '', '', 0)
        assert not matches_prompt(p, prompt)


# ---------------------------------------------------------------------------
# evaluate_submission
# ---------------------------------------------------------------------------

class TestEvaluateSubmission:
    def _setup(self, apps=50):
        player = make_player(name='Harry Kane', country='ENG',
                             positions='FW', clubs='Tottenham', apps=apps)
        idx = make_index([player])
        prompt = Prompt('club_position', 'Tottenham', 'tottenham', '', 'FW', '', 99)
        return idx, prompt

    def test_not_found(self):
        idx, prompt = self._setup()
        outcome, _, _ = evaluate_submission(501, 'Nobody Here', set(), prompt, idx)
        assert outcome == Outcome.NOT_FOUND

    def test_scored(self):
        idx, prompt = self._setup(apps=50)
        outcome, points, player = evaluate_submission(501, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.SCORED
        assert points == 50

    def test_already_used(self):
        idx, prompt = self._setup()
        used = {normalize_name_key('Harry Kane')}
        outcome, _, _ = evaluate_submission(501, 'Harry Kane', used, prompt, idx)
        assert outcome == Outcome.ALREADY_USED

    def test_not_matching(self):
        idx, prompt = self._setup()
        bad_prompt = Prompt('club_position', 'Arsenal', 'arsenal', '', 'FW', '', 0)
        outcome, _, _ = evaluate_submission(501, 'Harry Kane', set(), bad_prompt, idx)
        assert outcome == Outcome.NOT_MATCHING

    def test_over_180(self):
        idx, prompt = self._setup(apps=200)
        outcome, _, _ = evaluate_submission(501, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.OVER_180

    def test_invalid_dart_score(self):
        # 163 is not a valid dart score
        idx, prompt = self._setup(apps=163)
        outcome, _, _ = evaluate_submission(501, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.INVALID_DART_SCORE

    def test_bust(self):
        # score=30, apps=55 → new_score=-25 < -20 → bust
        idx, prompt = self._setup(apps=55)
        outcome, _, _ = evaluate_submission(30, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.BUST

    def test_win_exact(self):
        idx, prompt = self._setup(apps=50)
        outcome, points, _ = evaluate_submission(50, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.WIN
        assert points == 50

    def test_win_within_range(self):
        # score=10, apps=20 → new_score=-10 (≥-20) → win
        idx, prompt = self._setup(apps=20)
        outcome, _, _ = evaluate_submission(10, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.WIN

    def test_bust_boundary(self):
        # score=10, apps=31 → new_score=-21 → bust
        idx, prompt = self._setup(apps=31)
        outcome, _, _ = evaluate_submission(10, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.BUST

    def test_win_boundary(self):
        # score=10, apps=30 → new_score=-20 → win
        idx, prompt = self._setup(apps=30)
        outcome, _, _ = evaluate_submission(10, 'Harry Kane', set(), prompt, idx)
        assert outcome == Outcome.WIN


# ---------------------------------------------------------------------------
# Prompt pool guarantees
# ---------------------------------------------------------------------------

class TestPromptPool:
    def _make_sample_data(self):
        """Generate enough synthetic players to produce a non-empty pool."""
        players = []
        for i in range(200):
            players.append({
                'name': f'Player {i}',
                'name_key': f'player {i}',
                'country': 'ENG',
                'positions': 'MF',
                'clubs': 'Arsenal',
                'apps': 50 + (i % 50),
            })
        return players

    def test_all_prompts_meet_min_answers(self):
        players = self._make_sample_data()
        idx = build_indexes(players)
        pool = build_prompt_pool(idx, min_answers=5)
        for p in pool:
            assert p.answer_count >= 5, (
                f'Prompt "{p.text}" has only {p.answer_count} valid answers'
            )

    def test_country_club_prompts_in_pool_when_sufficient(self):
        """country_club prompts appear when enough players satisfy the combo."""
        players = []
        for i in range(50):
            players.append({
                'name': f'Brazilian {i}',
                'name_key': f'brazilian {i}',
                'country': 'BRA',
                'positions': 'MF',
                'clubs': 'Chelsea',
                'apps': 50,
            })
        idx = build_indexes(players)
        pool = build_prompt_pool(idx, min_answers=5)
        country_club_prompts = [p for p in pool if p.type == 'country_club']
        assert len(country_club_prompts) > 0
