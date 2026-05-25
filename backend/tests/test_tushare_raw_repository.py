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
