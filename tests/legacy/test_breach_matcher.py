"""Testes para `legacy/breach_matcher.py` (bug hunt + extensões)."""

from __future__ import annotations

import pytest

from legacy.breach_matcher import (
    bool_field_matches,
    data_class_matches,
    domain_matches,
    filter_breaches,
    is_valid_breach_name,
    name_matches,
    paginate,
    within_added_date,
    within_breach_date,
)

ADOBE = {
    "Name": "Adobe",
    "Domain": "adobe.com",
    "BreachDate": "2013-10-04",
    "AddedDate": "2013-12-04T00:00:00Z",
    "PwnCount": 152445165,
    "DataClasses": ["Email addresses", "Password hints", "Passwords"],
    "IsVerified": True,
    "IsSensitive": False,
    "IsSpamList": False,
}

DROPBOX = {
    "Name": "Dropbox",
    "Domain": "dropbox.com",
    "BreachDate": "2012-07-01",
    "AddedDate": "2016-08-31T00:00:00Z",
    "PwnCount": 68648009,
    "DataClasses": ["Email addresses", "Passwords"],
    "IsVerified": True,
    "IsSensitive": False,
    "IsSpamList": False,
}

NO_EXTRAS = {
    "Name": "NoExtrasBreach",
    "Domain": "",
    "BreachDate": "2020-01-01",
    "AddedDate": "2020-01-02T00:00:00Z",
    "PwnCount": 100,
    "DataClasses": [],
    "IsVerified": False,
    "IsSensitive": True,
    "IsSpamList": False,
}

SPAM_BREACH = {
    "Name": "SpamListExample",
    "Domain": "spamlist.example",
    "BreachDate": "2018-05-15",
    "AddedDate": "2018-05-16T00:00:00Z",
    "PwnCount": 5_000_000,
    "DataClasses": ["Email addresses"],
    "IsVerified": False,
    "IsSensitive": False,
    "IsSpamList": True,
}


class TestIsValidBreachName:
    @pytest.mark.parametrize("name", ["Adobe", "LinkedIn", "000webhost", "a.b-c", "123"])
    def test_valid_names(self, name):
        assert is_valid_breach_name(name) is True

    @pytest.mark.parametrize(
        "name",
        ["", "Ad obe", "test;name", 'name"quote', "with space", "name/slash"],
    )
    def test_invalid_names(self, name):
        assert is_valid_breach_name(name) is False


class TestDomainMatches:
    def test_partial_lowercase_query(self):
        assert domain_matches(ADOBE, "adobe") is True

    def test_query_not_substring(self):
        assert domain_matches(ADOBE, "linkedin") is False

    def test_empty_domain_never_matches_non_empty_query(self):
        assert domain_matches(NO_EXTRAS, "dropbox") is False

    def test_uppercase_query_matches_lowercase_domain_bug(self):
        """BUG #1 (Média): o contrato exige match CASE-INSENSITIVE, mas a
        implementação atual só normaliza `Domain` — não normaliza `query`.
        `query="Dropbox"` (com maiúscula) deveria casar com
        `Domain="dropbox.com"`, mas hoje retorna False.
        """
        assert domain_matches(DROPBOX, "Dropbox") is True


class TestNameMatches:
    def test_exact_match(self):
        assert name_matches(ADOBE, "Adobe") is True

    def test_case_sensitive(self):
        assert name_matches(ADOBE, "adobe") is False

    def test_no_match(self):
        assert name_matches(ADOBE, "LinkedIn") is False


class TestDataClassMatches:
    def test_case_insensitive_match(self):
        assert data_class_matches(ADOBE, "passwords") is True

    def test_no_match(self):
        assert data_class_matches(ADOBE, "credit cards") is False

    def test_empty_data_classes_never_match(self):
        assert data_class_matches(NO_EXTRAS, "passwords") is False


class TestWithinBreachDate:
    def test_no_bounds(self):
        assert within_breach_date(ADOBE) is True

    def test_within_range(self):
        assert within_breach_date(ADOBE, date_from="2013-01-01", date_to="2013-12-31") is True

    def test_before_range(self):
        assert within_breach_date(ADOBE, date_from="2014-01-01") is False

    def test_after_range(self):
        assert within_breach_date(ADOBE, date_to="2013-01-01") is False

    def test_inclusive_lower_bound(self):
        breach = {**ADOBE, "BreachDate": "2019-01-01"}
        assert within_breach_date(breach, date_from="2019-01-01") is True

    def test_inclusive_upper_bound_bug(self):
        """BUG #2 (Alta): `date_to` deveria ser INCLUSIVO, mas a implementação
        usa `bd >= date_to`, o que EXCLUI um breach cujo `BreachDate` é
        exatamente igual a `date_to`.
        """
        breach = {**ADOBE, "BreachDate": "2019-12-31"}
        assert within_breach_date(breach, date_to="2019-12-31") is True


class TestWithinAddedDate:
    def test_no_bounds(self):
        assert within_added_date(ADOBE) is True

    def test_within_range(self):
        assert within_added_date(ADOBE, date_from="2013-01-01", date_to="2013-12-31") is True

    def test_before_range(self):
        assert within_added_date(ADOBE, date_from="2014-01-01") is False

    def test_after_range(self):
        assert within_added_date(ADOBE, date_to="2013-01-01") is False

    def test_inclusive_bounds_use_only_date_portion(self):
        # AddedDate = "2013-12-04T00:00:00Z" -> compara só "2013-12-04"
        assert within_added_date(ADOBE, date_from="2013-12-04", date_to="2013-12-04") is True


class TestPaginate:
    def test_first_page(self):
        items = [1, 2, 3, 4, 5]
        assert paginate(items, page=1, page_size=2) == [1, 2]

    def test_second_page(self):
        items = [1, 2, 3, 4, 5]
        assert paginate(items, page=2, page_size=2) == [3, 4]

    def test_last_partial_page(self):
        items = [1, 2, 3, 4, 5]
        assert paginate(items, page=3, page_size=2) == [5]

    def test_page_size_is_respected_bug(self):
        """BUG #3 (Alta): `end = start + page_size - 1` faz `paginate`
        devolver `page_size - 1` itens em vez de `page_size`.
        """
        items = [1, 2, 3]
        assert paginate(items, page=1, page_size=2) == [1, 2]

    def test_page_size_one_returns_empty_bug(self):
        """BUG #3 (Alta), pior caso: com `page_size=1`, `start == end`
        sempre, então `items[start:end]` é SEMPRE uma lista vazia —
        `page_size=1` devolve 0 resultados, independentemente do conteúdo.
        """
        items = ["a", "b", "c"]
        assert paginate(items, page=1, page_size=1) == ["a"]

    def test_full_traversal_covers_all_items_bug(self):
        """BUG #3 (Alta), consequência: navegar de p1 a pN deveria cobrir
        100% dos itens, mas a implementação atual perde 1 item por página
        (o último item de cada página nunca aparece em nenhuma página).
        """
        items = ["a", "b", "c"]
        page_size = 2
        collected: list[str] = []
        for page in range(1, 3):  # 2 páginas cobrem 3 itens com page_size=2
            collected.extend(paginate(items, page=page, page_size=page_size))
        assert collected == items


class TestBoolFieldMatches:
    def test_true_field_matches_true(self):
        assert bool_field_matches(ADOBE, "IsVerified", True) is True

    def test_false_field_matches_false(self):
        assert bool_field_matches(ADOBE, "IsSensitive", False) is True

    def test_mismatch(self):
        assert bool_field_matches(ADOBE, "IsVerified", False) is False

    def test_missing_field_defaults_to_false(self):
        assert bool_field_matches({}, "IsSpamList", False) is True


class TestFilterBreaches:
    BREACHES = [ADOBE, DROPBOX, NO_EXTRAS, SPAM_BREACH]

    def test_no_filters_returns_all(self):
        assert filter_breaches(self.BREACHES) == self.BREACHES

    def test_filter_by_domain(self):
        assert filter_breaches(self.BREACHES, domain="dropbox") == [DROPBOX]

    def test_filter_by_name_exact(self):
        assert filter_breaches(self.BREACHES, name="Adobe") == [ADOBE]

    def test_filter_by_name_case_sensitive_no_match(self):
        assert filter_breaches(self.BREACHES, name="adobe") == []

    def test_filter_by_data_class(self):
        assert filter_breaches(self.BREACHES, data_class="password hints") == [ADOBE]

    def test_filter_by_added_date_range(self):
        result = filter_breaches(
            self.BREACHES, added_date_from="2016-01-01", added_date_to="2016-12-31"
        )
        assert result == [DROPBOX]

    def test_filter_by_breach_date_range(self):
        result = filter_breaches(
            self.BREACHES, breach_date_from="2018-01-01", breach_date_to="2018-12-31"
        )
        assert result == [SPAM_BREACH]

    def test_filter_by_pwn_count_range(self):
        result = filter_breaches(
            self.BREACHES, min_pwn_count=100_000_000, max_pwn_count=200_000_000
        )
        assert result == [ADOBE]

    def test_filter_by_max_pwn_count_excludes_larger(self):
        result = filter_breaches(self.BREACHES, max_pwn_count=10_000_000)
        assert result == [NO_EXTRAS, SPAM_BREACH]

    def test_filter_by_is_verified(self):
        assert filter_breaches(self.BREACHES, is_verified=False) == [NO_EXTRAS, SPAM_BREACH]

    def test_filter_by_is_sensitive(self):
        assert filter_breaches(self.BREACHES, is_sensitive=True) == [NO_EXTRAS]

    def test_filter_by_is_spam_list(self):
        assert filter_breaches(self.BREACHES, is_spam_list=True) == [SPAM_BREACH]

    def test_combined_filters_use_and_semantics(self):
        result = filter_breaches(
            self.BREACHES,
            data_class="passwords",
            min_pwn_count=50_000_000,
        )
        assert result == [ADOBE, DROPBOX]

    def test_combined_new_and_old_filters(self):
        result = filter_breaches(
            self.BREACHES,
            domain="adobe",
            is_verified=True,
            min_pwn_count=1,
        )
        assert result == [ADOBE]
