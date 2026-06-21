from datetime import date

from app.repositories.tushare_raw import TushareRawRepository


def test_deduplicate_records_keeps_last_record_for_same_key() -> None:
    records = [
        {"ts_code": "000001.SZ", "ann_date": "20260425", "value": 1},
        {"ts_code": "000001.SZ", "ann_date": "20260425", "value": 2},
        {"ts_code": "000002.SZ", "ann_date": "20260425", "value": 3},
    ]

    result = TushareRawRepository._deduplicate_records(
        records,
        key_columns=["ts_code", "ann_date"],
    )

    assert result == [
        {"ts_code": "000001.SZ", "ann_date": "20260425", "value": 2},
        {"ts_code": "000002.SZ", "ann_date": "20260425", "value": 3},
    ]


def test_normalize_record_converts_invalid_tushare_date_placeholders_to_null() -> None:
    result = TushareRawRepository._normalize_record(
        {
            "ts_code": "000001.SZ",
            "list_date": "0",
            "end_date": "00000000",
            "name": "",
            "ignored": "value",
        },
        allowed_columns={"ts_code", "list_date", "end_date", "name"},
        date_columns={"list_date", "end_date"},
    )

    assert result == {
        "ts_code": "000001.SZ",
        "list_date": None,
        "end_date": None,
        "name": None,
    }


def test_normalize_record_converts_yyyymm_date_to_first_day_of_month() -> None:
    result = TushareRawRepository._normalize_record(
        {
            "ts_code": "000001.SZ",
            "begin_date": "199806",
        },
        allowed_columns={"ts_code", "begin_date"},
        date_columns={"begin_date"},
    )

    assert result == {
        "ts_code": "000001.SZ",
        "begin_date": date(1998, 6, 1),
    }


def test_normalize_record_converts_year_only_date_to_first_day_of_year() -> None:
    result = TushareRawRepository._normalize_record(
        {
            "ts_code": "000001.SZ",
            "begin_date": "2002",
        },
        allowed_columns={"ts_code", "begin_date"},
        date_columns={"begin_date"},
    )

    assert result == {
        "ts_code": "000001.SZ",
        "begin_date": date(2002, 1, 1),
    }


def test_repair_primary_key_values_uses_report_date_when_ann_date_is_missing() -> None:
    result = TushareRawRepository._repair_primary_key_values(
        {"ts_code": "000001.SZ", "ann_date": None, "end_date": "20260331", "roe": 12.3},
        primary_keys=["ts_code", "ann_date", "end_date"],
    )

    assert result["ann_date"] == "20260331"


def test_has_primary_key_values_filters_records_with_unrepairable_null_keys() -> None:
    assert not TushareRawRepository._has_primary_key_values(
        {"ts_code": "000001.SZ", "ann_date": None},
        primary_keys=["ts_code", "ann_date"],
    )
    assert TushareRawRepository._has_primary_key_values(
        {"ts_code": "000001.SZ", "ann_date": "20260331"},
        primary_keys=["ts_code", "ann_date"],
    )
