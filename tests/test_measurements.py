"""Stated physical measurements become named claims on the source chunk."""

from cpu_llm.measurements import extract_literal_numeric_claims, measurement_provenance
from cpu_llm.pipeline import _structure_metadata
from cpu_llm.source import validation_chunks


def _lobster_description() -> str:
    return next(
        text
        for document_id, _title, text in validation_chunks()
        if document_id == "wikitext2-homarus-gammarus-p0002"
    )


def test_body_length_keeps_both_written_units_and_the_maximum():
    claims = extract_literal_numeric_claims("body length is up to 60 centimetres (24 in)")
    assert claims == {"body_length_cm": 60.0, "body_length_in": 24.0}
    provenance = measurement_provenance("body length is up to 60 centimetres (24 in)")
    assert provenance["body_length_cm"]["qualifier"] == "maximum"
    assert provenance["body_length_in"]["qualifier"] == "maximum"
    assert provenance["body_length_cm"]["source"] == "60"
    assert "60 centimetres" in provenance["body_length_cm"]["context"]
    assert "24 in" in provenance["body_length_in"]["context"]


def test_lobster_paragraph_names_only_measurements_written_in_it():
    text = _lobster_description()
    claims = extract_literal_numeric_claims(text)
    provenance = measurement_provenance(text)
    assert claims["body_length_cm"] == 60.0
    assert claims["body_length_in"] == 24.0
    assert provenance["body_length_cm"]["qualifier"] == "maximum"
    assert claims["weight_kg_min"] == 5.0
    assert claims["weight_kg_max"] == 6.0
    assert provenance["weight_kg_min"]["qualifier"] == "maximum"
    assert provenance["weight_kg_max"]["qualifier"] == "maximum"
    assert claims["weight_lb_min"] == 11.0
    assert claims["weight_lb_max"] == 13.0
    assert claims["length_cm_min"] == 23.0
    assert claims["length_cm_max"] == 38.0
    assert provenance["length_cm_min"]["qualifier"] == "minimum"
    assert provenance["length_cm_max"]["qualifier"] == "maximum"
    assert claims["length_in_min"] == 9.0
    assert claims["length_in_max"] == 15.0
    assert claims["weight_kg_min_2"] == 0.7
    assert claims["weight_kg_max_2"] == 2.2
    assert provenance["weight_kg_min_2"]["qualifier"] == "minimum"
    assert claims["weight_lb_min_2"] == 1.5
    assert claims["weight_lb_max_2"] == 4.9
    for key, value in claims.items():
        record = provenance[key]
        assert text[record["start"] : record["end"]] == record["source"]
        assert record["source"] in text
        assert record["context"] in text
        rendered = str(int(value)) if float(value).is_integer() else str(value)
        assert rendered in record["source"]
    assert "year" not in "".join(claims)


def test_growth_limit_stays_a_maximum_on_the_words_the_sentence_uses():
    text = "It may grow to a length of 60 cm (24 in) and a mass of 6 kilograms (13 lb)."
    assert extract_literal_numeric_claims(text) == {
        "length_cm": 60.0,
        "length_in": 24.0,
        "mass_kg": 6.0,
        "mass_lb": 13.0,
    }
    provenance = measurement_provenance(text)
    assert {item["qualifier"] for item in provenance.values()} == {"maximum"}


def test_minimum_landing_size_stays_a_minimum():
    text = "The minimum landing size for H. gammarus is a carapace length of 87 mm (3.4 in)."
    assert extract_literal_numeric_claims(text) == {
        "carapace_length_mm": 87.0,
        "carapace_length_in": 3.4,
    }
    provenance = measurement_provenance(text)
    assert provenance["carapace_length_mm"]["qualifier"] == "minimum"
    assert provenance["carapace_length_in"]["qualifier"] == "minimum"


def test_a_paragraph_without_measurements_has_no_numeric_claims():
    text = "Homarus gammarus, known as the European lobster or common lobster, is a species of clawed lobster."
    assert extract_literal_numeric_claims(text) == {}
    assert measurement_provenance(text) == {}


def test_ambiguous_or_unsupported_phrases_do_not_invent_values():
    assert extract_literal_numeric_claims("The sample is 5 in the pot.") == {}
    assert extract_literal_numeric_claims("The carapace is 12 furlongs.") == {}
    assert extract_literal_numeric_claims("body length up to sixty centimetres") == {}
    assert extract_literal_numeric_claims("The limit exceeds 10 million.") == {}
    assert extract_literal_numeric_claims("It sheds once every 1 – 2 years.") == {}
    assert extract_literal_numeric_claims("60 centimetres") == {"length_cm": 60.0}


def test_exact_and_approximate_qualifiers_stay_distinct():
    exact = measurement_provenance("body length is 40 cm")
    approximate = measurement_provenance("body length of about 40 cm")
    assert exact["body_length_cm"]["qualifier"] == "exact"
    assert approximate["body_length_cm"]["qualifier"] == "approximate"
    assert extract_literal_numeric_claims("body length is 40 cm")["body_length_cm"] == 40.0


def test_finance_claims_stay_on_their_chunk_and_physical_claims_do_not_cross():
    description = _lobster_description()
    lead = "Homarus gammarus, known as the European lobster or common lobster, is a species of clawed lobster."
    policy = "The policy must apply because the limit exceeds 10 million."
    metadata = _structure_metadata(
        [
            {"chunk_id": "wikitext2-homarus-gammarus-p0002", "chunk_text": description},
            {"chunk_id": "wikitext2-homarus-gammarus-p0001", "chunk_text": lead},
            {"chunk_id": "case_a_policy", "chunk_text": policy},
        ]
    )
    measured = metadata["wikitext2-homarus-gammarus-p0002"]
    assert measured["numeric_claims"]["body_length_cm"] == 60.0
    assert measured["numeric_claims"]["body_length_in"] == 24.0
    assert measured["numeric_qualifiers"]["body_length_cm"]["qualifier"] == "maximum"
    assert "body_length_cm" not in metadata["wikitext2-homarus-gammarus-p0001"].get("numeric_claims", {})
    assert metadata["case_a_policy"]["numeric_claims"]["amount_min"] == 10_000_000.0
    assert "body_length_cm" not in metadata["case_a_policy"]["numeric_claims"]
    assert "amount_min" not in measured["numeric_claims"]


def test_a_metre_span_is_not_money_and_a_million_span_is_kept():
    metres = _structure_metadata([{"chunk_id": "height-m", "chunk_text": "4,399 m"}])
    assert metres["height-m"]["numeric_claims"]["length_m"] == 4399.0
    assert "amount_min" not in metres["height-m"]["numeric_claims"]

    feet = _structure_metadata([{"chunk_id": "height-ft", "chunk_text": "14,440 feet"}])
    assert feet["height-ft"]["numeric_claims"]["length_ft"] == 14440.0
    assert "amount_min" not in feet["height-ft"]["numeric_claims"]

    million = _structure_metadata([{"chunk_id": "cash", "chunk_text": "10 million"}])
    assert million["cash"]["numeric_claims"]["amount_min"] == 10_000_000.0

    exceeds = _structure_metadata(
        [{"chunk_id": "limit", "chunk_text": "The limit exceeds 10 million."}]
    )
    assert exceeds["limit"]["numeric_claims"]["amount_min"] == 10_000_000.0

    both = (
        "The mountain rises 4,399 m above sea level. "
        "The restoration project received 10 million dollars."
    )
    mixed = _structure_metadata([{"chunk_id": "both", "chunk_text": both}])
    assert mixed["both"]["numeric_claims"]["amount_min"] == 10_000_000.0
    assert mixed["both"]["numeric_claims"]["elevation_m"] == 4399.0


def test_elevation_written_in_feet_and_metres_stays_physical():
    text = "Originally measured as 14,433 feet (4,399 m) in height."
    claims = extract_literal_numeric_claims(text)
    assert claims["height_ft"] == 14433.0
    assert claims["height_m"] == 4399.0
    metadata = _structure_metadata([{"chunk_id": "elbert", "chunk_text": text}])
    assert "amount_min" not in metadata["elbert"].get("numeric_claims", {})


def test_money_is_a_currency_span_and_a_counted_noun_is_not():
    cases = {
        "15 million copies": None,
        "4.16 million viewers": None,
        "20 million men and 6 million horses": None,
        "around 28 million years ago": None,
        "five million years ago": None,
        "12 km": None,
        "10 million": 10_000_000.0,
        "The limit exceeds 10 million.": 10_000_000.0,
        "five million": 5_000_000.0,
        "$5 m": 5_000_000.0,
        "£ 1.7 million": 1_700_000.0,
        "$ 2.5 million in grants": 2_500_000.0,
        "US $ 780 million worldwide": 780_000_000.0,
        "CZK 8 million (~ US $ 400,000)": 8_000_000.0,
        "10 million dollars": 10_000_000.0,
        "28 million years ago. The grant was £ 4 million.": 4_000_000.0,
        "4,399 m and the budget was $ 10 million": 10_000_000.0,
        "a viewership of 8.69 million.": None,
        "the population of 3 million.": None,
        "a cost of 10 million.": 10_000_000.0,
    }
    for text, expected in cases.items():
        metadata = _structure_metadata([{"chunk_id": "span", "chunk_text": text}])
        claims = metadata["span"].get("numeric_claims", {})
        assert claims.get("amount_min") == expected, text

    currency_metre = _structure_metadata([{"chunk_id": "abbr", "chunk_text": "$5 m"}])
    assert "length_m" not in currency_metre["abbr"]["numeric_claims"]

    hyphen = extract_literal_numeric_claims("The summit is a 14,440-foot (4,399 m) peak.")
    assert hyphen["elevation_ft"] == 14440.0
    assert hyphen["elevation_m"] == 4399.0

    massive = "Mount Massive differs in elevation by only 12 feet (3.7 m)."
    claims = extract_literal_numeric_claims(massive)
    assert claims["elevation_ft"] == 12.0
    assert claims["elevation_m"] == 3.7
    assert "mass_ft" not in claims


def test_a_bad_vectorprism_number_does_not_drop_the_other_paragraph():
    metadata = _structure_metadata(
        [
            {"chunk_id": "broken", "chunk_text": "The note says . m on the map."},
            {"chunk_id": "limit", "chunk_text": "The limit exceeds 10 million."},
        ]
    )
    assert "amount_min" not in metadata["broken"].get("numeric_claims", {})
    assert metadata["limit"]["numeric_claims"]["amount_min"] == 10_000_000.0
