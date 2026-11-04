"""날씨. 실제 공급자가 없어 기본은 항상 샘플이다. DB에 저장하지 않는다."""
from collections.abc import Callable

from .. import config, errors

SAMPLES = {
    "울산": {"tempC": 17.6, "condition": "맑음", "humidity": 52, "windMs": 3.2},
    "거제": {"tempC": 18.9, "condition": "구름조금", "humidity": 61, "windMs": 4.1},
    "목포": {"tempC": 16.2, "condition": "흐림", "humidity": 70, "windMs": 5.0},
}
REQUIRED = ("obsDt", "tempC", "condition", "humidity", "windMs")

# 공급자 이름 → 지역을 받아 관측값 dict를 돌려주는 함수
PROVIDERS: dict[str, Callable[[str], dict]] = {}


def _sample(region: str, error: str | None) -> dict:
    return {"region": region, "source": "SAMPLE", "obsDt": config.TODAY_ISO, **SAMPLES[region], "error": error}


def get(region: str) -> dict:
    if region not in SAMPLES:
        raise errors.validation("region", "지원하지 않는 지역입니다.")
    name = config.weather_provider()
    if not name:
        return _sample(region, "날씨 공급자가 설정되지 않았습니다.")
    provider = PROVIDERS.get(name)
    if not provider:
        return _sample(region, f"알 수 없는 날씨 공급자입니다: {name}")
    try:
        data = provider(region)
    except Exception as exc:  # 공급자 실패는 어떤 종류든 샘플로 대체한다
        return _sample(region, f"날씨 공급자 호출 실패: {exc}")
    if not isinstance(data, dict) or any(data.get(key) is None for key in REQUIRED):
        return _sample(region, "날씨 공급자 응답 형식 오류")
    return {"region": region, "source": "LIVE", **{key: data[key] for key in REQUIRED}, "error": None}
