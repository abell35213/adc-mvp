from app.services.weather.nws_parser import parse_nws_time_series_xml


def test_parse_nws_time_series_xml_partial_fields() -> None:
    xml_payload = """
    <dwml>
      <data>
        <parameters>
          <temp><value>72</value></temp>
          <qpf><value>0.1</value></qpf>
          <wspd><value>14</value></wspd>
        </parameters>
      </data>
    </dwml>
    """

    parsed = parse_nws_time_series_xml(xml_payload)

    assert parsed["weather"]["temp"]["present"] is True
    assert parsed["weather"]["temp"]["values"] == ["72"]
    assert parsed["weather"]["qpf"]["present"] is True
    assert parsed["weather"]["snow"]["present"] is False
    assert "snow" in parsed["missing_fields"]
    assert parsed["is_partial"] is True
