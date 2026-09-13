"""Fixtures deterministicas para demonstracao e testes sem depender da rede.

Cenarios cobrem todas as cidades dos segurados reais:
- chuva_intensa_sp: São Paulo → Eliezer (residencial, empresarial), Mariana B. (residencial)
- granizo_rj: Rio de Janeiro → Adelson (residencial), Bruno (empresarial)
- ventos_fortes_ba: Salvador → Daniel (automovel)
- alagamento_rs: Porto Alegre → Denis (residencial), Diego (residencial)
- granizo_sc: São Joaquim → Sami (automovel, empresarial)
"""

from seguramente.models import WeatherObservation


def chuva_intensa_sao_paulo() -> WeatherObservation:
    return WeatherObservation(
        source="Open-Meteo (fixture demonstrativa)",
        source_url="https://open-meteo.com/en/docs",
        location="São Paulo, São Paulo, Brasil",
        latitude=-23.55,
        longitude=-46.63,
        observed_at="2026-08-18T12:00",
        temperature_c=20.4,
        precipitation_mm=18.0,
        wind_speed_kmh=22.0,
        wind_gust_kmh=34.0,
        precipitation_probability=82,
        weather_code=63,
        raw={"fixture": True, "scenario": "chuva_intensa"},
    )


def granizo_rio_de_janeiro() -> WeatherObservation:
    return WeatherObservation(
        source="Open-Meteo (fixture demonstrativa)",
        source_url="https://open-meteo.com/en/docs",
        location="Rio de Janeiro, Rio de Janeiro, Brasil",
        latitude=-22.91,
        longitude=-43.17,
        observed_at="2026-08-18T12:00",
        temperature_c=22.0,
        precipitation_mm=12.0,
        wind_speed_kmh=35.0,
        wind_gust_kmh=55.0,
        precipitation_probability=90,
        weather_code=96,
        raw={"fixture": True, "scenario": "granizo"},
    )


def ventos_fortes_salisvador() -> WeatherObservation:
    return WeatherObservation(
        source="Open-Meteo (fixture demonstrativa)",
        source_url="https://open-meteo.com/en/docs",
        location="Salvador, Bahia, Brasil",
        latitude=-12.97,
        longitude=-38.51,
        observed_at="2026-08-18T12:00",
        temperature_c=26.0,
        precipitation_mm=2.0,
        wind_speed_kmh=52.0,
        wind_gust_kmh=78.0,
        precipitation_probability=30,
        weather_code=3,
        raw={"fixture": True, "scenario": "ventos_fortes"},
    )


def alagamento_porto_alegre() -> WeatherObservation:
    return WeatherObservation(
        source="Open-Meteo (fixture demonstrativa)",
        source_url="https://open-meteo.com/en/docs",
        location="Porto Alegre, Rio Grande do Sul, Brasil",
        latitude=-30.03,
        longitude=-51.23,
        observed_at="2026-08-18T12:00",
        temperature_c=18.0,
        precipitation_mm=38.0,
        wind_speed_kmh=18.0,
        wind_gust_kmh=28.0,
        precipitation_probability=95,
        weather_code=65,
        raw={"fixture": True, "scenario": "alagamento"},
    )


def granizo_sao_joaquim() -> WeatherObservation:
    return WeatherObservation(
        source="Open-Meteo (fixture demonstrativa)",
        source_url="https://open-meteo.com/en/docs",
        location="São Joaquim, Santa Catarina, Brasil",
        latitude=-28.29,
        longitude=-49.93,
        observed_at="2026-08-18T12:00",
        temperature_c=12.0,
        precipitation_mm=8.0,
        wind_speed_kmh=30.0,
        wind_gust_kmh=48.0,
        precipitation_probability=85,
        weather_code=96,
        raw={"fixture": True, "scenario": "granizo_sc"},
    )


FIXTURES = {
    "chuva_intensa_sp": chuva_intensa_sao_paulo,
    "granizo_rj": granizo_rio_de_janeiro,
    "ventos_fortes_ba": ventos_fortes_salisvador,
    "alagamento_rs": alagamento_porto_alegre,
    "granizo_sc": granizo_sao_joaquim,
}
