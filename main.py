from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# =========================================================
# 京房六爻排盘引擎（校正版）
# =========================================================
# 核心修正：
# 1. 八卦编码改为“自下而上”：初爻 -> 三爻 / 四爻 -> 上爻
# 2. 纳甲改为按“上下经卦”装，不按所属宫硬套
# 3. 纳甲保留完整天干、地支、五行
# 4. 六亲以“宫五行”为我动态计算
# 5. 64卦数据库由京房八宫序列自动生成，避免手写键值错位
# 6. 静爻纳甲、六亲、六神保持不变
# 7. 只为动爻生成化出信息，不重构完整变卦六爻
# 8. 排盘层与分析层分离，用神与伏神判断交给 AnalysisEngine
# =========================================================


class YinYang(Enum):
    YANG = 1
    YIN = 0


@dataclass
class Line:
    index: int
    value: int
    yin_yang: YinYang
    changing: bool
    earthly_branch: str = ""
    heavenly_stem: str = ""
    element: str = ""
    six_relative: str = ""
    six_spirit: str = ""
    hidden_spirit: Optional["HiddenSpirit"] = None
    tags: List[str] = field(default_factory=list)

    def to_bit(self) -> int:
        return 1 if self.yin_yang == YinYang.YANG else 0

    def changed_to_bit(self) -> int:
        if not self.changing:
            return self.to_bit()
        return 0 if self.yin_yang == YinYang.YANG else 1

    def changed(self) -> YinYang:
        if not self.changing:
            return self.yin_yang
        return YinYang.YIN if self.yin_yang == YinYang.YANG else YinYang.YANG


@dataclass
class Hexagram:
    name: str
    palace: str
    palace_index: int
    lines: List[int]
    shi_index: int
    ying_index: int
    relation_type: str


@dataclass
class ArrangedLine:
    index: int
    yin_yang: YinYang
    heavenly_stem: str
    earthly_branch: str
    element: str
    six_relative: str


@dataclass
class ChangedLine:
    index: int
    original_line: Line
    yin_yang: YinYang
    heavenly_stem: str
    earthly_branch: str
    element: str
    six_relative: str
    tags: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpiritInfo:
    six_relative: str
    heavenly_stem: str
    earthly_branch: str
    element: str

    def display(self) -> str:
        return f"{self.six_relative}{self.heavenly_stem}{self.earthly_branch}{self.element}"


@dataclass(frozen=True)
class HiddenSpirit(SpiritInfo):
    source_palace: str
    flying_line_index: int

    def display(self) -> str:
        return f"伏{super().display()}"


@dataclass(frozen=True)
class YongShenResult:
    found_visible: bool
    visible_line: Optional[int]
    hidden_line: Optional[int]
    hidden_from_palace: Optional[str]
    hidden_spirit: Optional[HiddenSpirit] = None


@dataclass(frozen=True)
class QueryInfo:
    gender: str
    primary_yongshen: Optional[str] = None
    yongshen_line: Optional[int] = None
    subject: str = ""
    sub_subject: str = ""
    question: str = ""


@dataclass(frozen=True)
class DivinationTime:
    qigua_datetime: datetime
    month_branch: str
    month_element: str
    month_term: str
    day_stem: str
    day_branch: str
    day_element: str
    day_ganzhi: str
    void_branches: Tuple[str, str]


@dataclass(frozen=True)
class BranchRef:
    label: str
    branch: str
    source: str
    line_index: Optional[int] = None


@dataclass(frozen=True)
class RelationshipHint:
    name: str
    refs: Tuple[BranchRef, ...]


# =========================================================
# 基础数据
# =========================================================

PALACE_ELEMENT = {
    "乾": "金",
    "兑": "金",
    "离": "火",
    "震": "木",
    "巽": "木",
    "坎": "水",
    "艮": "土",
    "坤": "土",
}

BRANCH_ELEMENT = {
    "子": "水",
    "丑": "土",
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
}

STEM_ELEMENT = {
    "甲": "木",
    "乙": "木",
    "丙": "火",
    "丁": "火",
    "戊": "土",
    "己": "土",
    "庚": "金",
    "辛": "金",
    "壬": "水",
    "癸": "水",
}

HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

MONTH_BUILD_TERMS = [
    ("小寒", 285.0, "丑"),
    ("立春", 315.0, "寅"),
    ("惊蛰", 345.0, "卯"),
    ("清明", 15.0, "辰"),
    ("立夏", 45.0, "巳"),
    ("芒种", 75.0, "午"),
    ("小暑", 105.0, "未"),
    ("立秋", 135.0, "申"),
    ("白露", 165.0, "酉"),
    ("寒露", 195.0, "戌"),
    ("立冬", 225.0, "亥"),
    ("大雪", 255.0, "子"),
]

SOLAR_TERM_CACHE: Dict[Tuple[int, float], datetime] = {}

SIX_SPIRIT_RULES = {
    "甲": ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"],
    "乙": ["青龙", "朱雀", "勾陈", "螣蛇", "白虎", "玄武"],
    "丙": ["朱雀", "勾陈", "螣蛇", "白虎", "玄武", "青龙"],
    "丁": ["朱雀", "勾陈", "螣蛇", "白虎", "玄武", "青龙"],
    "戊": ["勾陈", "螣蛇", "白虎", "玄武", "青龙", "朱雀"],
    "己": ["螣蛇", "白虎", "玄武", "青龙", "朱雀", "勾陈"],
    "庚": ["白虎", "玄武", "青龙", "朱雀", "勾陈", "螣蛇"],
    "辛": ["白虎", "玄武", "青龙", "朱雀", "勾陈", "螣蛇"],
    "壬": ["玄武", "青龙", "朱雀", "勾陈", "螣蛇", "白虎"],
    "癸": ["玄武", "青龙", "朱雀", "勾陈", "螣蛇", "白虎"],
}

GENERATE = {
    "木": "火",
    "火": "土",
    "土": "金",
    "金": "水",
    "水": "木",
}

CONTROL = {
    "木": "土",
    "土": "水",
    "水": "火",
    "火": "金",
    "金": "木",
}


VALID_GENDERS = {"男", "女"}
VALID_SUBJECTS = {"感情", "婚姻", "工作", "财运"}
VALID_RELATIVES = {"兄弟", "父母", "子孙", "妻财", "官鬼"}
PREPARATION_SECONDS = 20

YONGSHEN_RELATION_RULES = {
    "父母": {"original": "官鬼", "hostile": "妻财", "enemy": "子孙"},
    "兄弟": {"original": "父母", "hostile": "官鬼", "enemy": "妻财"},
    "子孙": {"original": "兄弟", "hostile": "父母", "enemy": "官鬼"},
    "妻财": {"original": "子孙", "hostile": "兄弟", "enemy": "父母"},
    "官鬼": {"original": "妻财", "hostile": "子孙", "enemy": "兄弟"},
}

LIU_HE_PAIRS = {
    frozenset(("子", "丑")),
    frozenset(("寅", "亥")),
    frozenset(("卯", "戌")),
    frozenset(("辰", "酉")),
    frozenset(("巳", "申")),
    frozenset(("午", "未")),
}

LIU_CHONG_PAIRS = {
    frozenset(("子", "午")),
    frozenset(("丑", "未")),
    frozenset(("寅", "申")),
    frozenset(("卯", "酉")),
    frozenset(("辰", "戌")),
    frozenset(("巳", "亥")),
}

SAN_XING_GROUPS = [
    ("寅", "巳", "申"),
    ("丑", "戌", "未"),
    ("子", "卯"),
]

SELF_XING_BRANCHES = {"辰", "午", "酉", "亥"}

SUBJECT_ITEMS: Dict[str, List[str]] = {
    "感情": ["其他", "单身何时有对象", "暧昧能否发展", "复合", "对方是否真心"],
    "婚姻": ["其他", "婚姻稳定", "能否结婚", "离婚倾向", "伴侣关系"],
    "工作": ["其他", "找工作", "面试结果", "升职调动", "离职跳槽", "工资奖金", "合同手续"],
    "财运": ["其他", "近期财运", "投资收益", "回款到账", "借钱能否收回", "生意项目收入"],
}


def get_sub_subjects(subject: str) -> List[str]:
    if subject not in VALID_SUBJECTS:
        raise ValueError("求测事项必须是：感情 / 婚姻 / 工作 / 财运")
    return list(SUBJECT_ITEMS[subject])


def build_query_info(
    gender: str,
    yongshen: Optional[str] = None,
    yongshen_line: Optional[int] = None,
    subject: str = "",
    sub_subject: str = "",
    question: str = "",
) -> QueryInfo:
    gender = gender.strip()
    subject = subject.strip()
    sub_subject = sub_subject.strip()
    question = question.strip()

    if gender not in VALID_GENDERS:
        raise ValueError("求测者性别必须是：男 / 女")

    if yongshen is not None and yongshen not in VALID_RELATIVES:
        raise ValueError("用神必须是：兄弟、父母、子孙、妻财、官鬼")

    if yongshen_line is not None and yongshen_line not in {1, 2, 3, 4, 5, 6}:
        raise ValueError("用神爻位必须是 1 到 6")

    return QueryInfo(
        gender=gender,
        primary_yongshen=yongshen,
        yongshen_line=yongshen_line,
        subject=subject,
        sub_subject=sub_subject,
        question=question,
    )


def create_divination(
    totals: List[int],
    gender: str,
    yongshen: Optional[str] = None,
    yongshen_line: Optional[int] = None,
    subject: str = "",
    sub_subject: str = "",
    question: str = "",
    qigua_datetime: Optional[datetime] = None,
    fu_shen_mode: str = "yongshen_only",
) -> "AnalysisEngine":
    query_info = build_query_info(
        gender=gender,
        yongshen=yongshen,
        yongshen_line=yongshen_line,
        subject=subject,
        sub_subject=sub_subject,
        question=question,
    )
    divination_time = build_divination_time(qigua_datetime)
    chart = LiuYaoEngine(
        totals=totals,
        divination_time=divination_time,
    )
    return AnalysisEngine(
        chart=chart,
        query_info=query_info,
        fu_shen_mode=fu_shen_mode,
    )


def normalize_datetime(dt: Optional[datetime] = None) -> datetime:
    shanghai_tz = ZoneInfo("Asia/Shanghai")
    if dt is None:
        return datetime.now(shanghai_tz)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=shanghai_tz)
    return dt.astimezone(shanghai_tz)


def julian_day(dt: datetime) -> float:
    utc_dt = dt.astimezone(timezone.utc)
    year = utc_dt.year
    month = utc_dt.month
    day = utc_dt.day
    hour = (
        utc_dt.hour
        + utc_dt.minute / 60
        + utc_dt.second / 3600
        + utc_dt.microsecond / 3_600_000_000
    )

    if month <= 2:
        year -= 1
        month += 12

    a = year // 100
    b = 2 - a + a // 4
    return (
        math.floor(365.25 * (year + 4716))
        + math.floor(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
        + hour / 24
    )


def sun_ecliptic_longitude(dt: datetime) -> float:
    jd = julian_day(dt)
    n = jd - 2451545.0
    mean_longitude = (280.46646 + 0.98564736 * n) % 360
    mean_anomaly = math.radians((357.52911 + 0.98560028 * n) % 360)
    center = (
        1.914602 * math.sin(mean_anomaly)
        + 0.019993 * math.sin(2 * mean_anomaly)
        + 0.000289 * math.sin(3 * mean_anomaly)
    )
    return (mean_longitude + center) % 360


def angle_passed(start: float, end: float, target: float) -> bool:
    distance = (target - start) % 360
    span = (end - start) % 360
    return 0 <= distance <= span


def find_solar_longitude_time(year: int, target_longitude: float) -> datetime:
    cache_key = (year, target_longitude)
    if cache_key in SOLAR_TERM_CACHE:
        return SOLAR_TERM_CACHE[cache_key]

    tz = ZoneInfo("Asia/Shanghai")
    cursor = datetime(year, 1, 1, tzinfo=tz)
    end = datetime(year + 1, 1, 8, tzinfo=tz)

    previous = cursor
    previous_longitude = sun_ecliptic_longitude(previous)
    cursor += timedelta(days=1)

    while cursor <= end:
        current_longitude = sun_ecliptic_longitude(cursor)
        if angle_passed(previous_longitude, current_longitude, target_longitude):
            low = previous
            high = cursor
            for _ in range(32):
                mid = low + (high - low) / 2
                mid_longitude = sun_ecliptic_longitude(mid)
                if angle_passed(previous_longitude, mid_longitude, target_longitude):
                    high = mid
                else:
                    low = mid
            SOLAR_TERM_CACHE[cache_key] = high
            return high

        previous = cursor
        previous_longitude = current_longitude
        cursor += timedelta(days=1)

    raise RuntimeError(f"无法计算 {year} 年太阳黄经 {target_longitude} 度对应节令")


def get_month_build(dt: datetime) -> Tuple[str, str]:
    term_points = []
    for name, longitude, branch in MONTH_BUILD_TERMS:
        term_time = find_solar_longitude_time(dt.year, longitude)
        term_points.append((term_time, name, branch))

    previous_year_dashue = find_solar_longitude_time(dt.year - 1, 255.0)
    term_points.append((previous_year_dashue, "大雪", "子"))
    term_points.sort(key=lambda item: item[0])

    active_name = "大雪"
    active_branch = "子"
    for term_time, name, branch in term_points:
        if dt >= term_time:
            active_name = name
            active_branch = branch
        else:
            break

    return active_branch, active_name


def gregorian_jdn(year: int, month: int, day: int) -> int:
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def get_day_ganzhi(dt: datetime) -> Tuple[str, str]:
    jdn = gregorian_jdn(dt.year, dt.month, dt.day)
    index = (jdn + 49) % 60
    return HEAVENLY_STEMS[index % 10], EARTHLY_BRANCHES[index % 12]


def get_void_branches(day_stem: str, day_branch: str) -> Tuple[str, str]:
    stem_index = HEAVENLY_STEMS.index(day_stem)
    branch_index = EARTHLY_BRANCHES.index(day_branch)
    xun_start_branch_index = (branch_index - stem_index) % 12
    return (
        EARTHLY_BRANCHES[(xun_start_branch_index + 10) % 12],
        EARTHLY_BRANCHES[(xun_start_branch_index + 11) % 12],
    )


def build_divination_time(dt: Optional[datetime] = None) -> DivinationTime:
    qigua_datetime = normalize_datetime(dt)
    month_branch, month_term = get_month_build(qigua_datetime)
    day_stem, day_branch = get_day_ganzhi(qigua_datetime)
    return DivinationTime(
        qigua_datetime=qigua_datetime,
        month_branch=month_branch,
        month_element=BRANCH_ELEMENT[month_branch],
        month_term=month_term,
        day_stem=day_stem,
        day_branch=day_branch,
        day_element=BRANCH_ELEMENT[day_branch],
        day_ganzhi=f"{day_stem}{day_branch}",
        void_branches=get_void_branches(day_stem, day_branch),
    )


# =========================================================
# 八卦编码：必须自下而上
# 例如：
# 乾 = 初阳、二阳、三阳 = (1,1,1)
# 震 = 初阳、二阴、三阴 = (1,0,0)
# 艮 = 初阴、二阴、三阳 = (0,0,1)
# 巽 = 初阴、二阳、三阳 = (0,1,1)
# 兑 = 初阳、二阳、三阴 = (1,1,0)
# =========================================================

TRIGRAMS: Dict[Tuple[int, int, int], str] = {
    (1, 1, 1): "乾",
    (1, 1, 0): "兑",
    (1, 0, 1): "离",
    (1, 0, 0): "震",
    (0, 1, 1): "巽",
    (0, 1, 0): "坎",
    (0, 0, 1): "艮",
    (0, 0, 0): "坤",
}

TRIGRAM_BITS: Dict[str, Tuple[int, int, int]] = {
    name: bits for bits, name in TRIGRAMS.items()
}


# =========================================================
# 纳甲：按经卦内外装纳甲，不按所属宫装纳甲
# 下卦用 inner：初、二、三
# 上卦用 outer：四、五、上
# =========================================================

NAJIA = {
    "乾": {
        "inner": [("甲", "子"), ("甲", "寅"), ("甲", "辰")],
        "outer": [("壬", "午"), ("壬", "申"), ("壬", "戌")],
    },
    "坤": {
        "inner": [("乙", "未"), ("乙", "巳"), ("乙", "卯")],
        "outer": [("癸", "丑"), ("癸", "亥"), ("癸", "酉")],
    },
    "震": {
        "inner": [("庚", "子"), ("庚", "寅"), ("庚", "辰")],
        "outer": [("庚", "午"), ("庚", "申"), ("庚", "戌")],
    },
    "巽": {
        "inner": [("辛", "丑"), ("辛", "亥"), ("辛", "酉")],
        "outer": [("辛", "未"), ("辛", "巳"), ("辛", "卯")],
    },
    "坎": {
        "inner": [("戊", "寅"), ("戊", "辰"), ("戊", "午")],
        "outer": [("戊", "申"), ("戊", "戌"), ("戊", "子")],
    },
    "离": {
        "inner": [("己", "卯"), ("己", "丑"), ("己", "亥")],
        "outer": [("己", "酉"), ("己", "未"), ("己", "巳")],
    },
    "艮": {
        "inner": [("丙", "辰"), ("丙", "午"), ("丙", "申")],
        "outer": [("丙", "戌"), ("丙", "子"), ("丙", "寅")],
    },
    "兑": {
        "inner": [("丁", "巳"), ("丁", "卯"), ("丁", "丑")],
        "outer": [("丁", "亥"), ("丁", "酉"), ("丁", "未")],
    },
}


# =========================================================
# 京房八宫序列
# =========================================================

PALACE_NAMES = {
    "乾": ["乾为天", "天风姤", "天山遁", "天地否", "风地观", "山地剥", "火地晋", "火天大有"],
    "兑": ["兑为泽", "泽水困", "泽地萃", "泽山咸", "水山蹇", "地山谦", "雷山小过", "雷泽归妹"],
    "离": ["离为火", "火山旅", "火风鼎", "火水未济", "山水蒙", "风水涣", "天水讼", "天火同人"],
    "震": ["震为雷", "雷地豫", "雷水解", "雷风恒", "地风升", "水风井", "泽风大过", "泽雷随"],
    "巽": ["巽为风", "风天小畜", "风火家人", "风雷益", "天雷无妄", "火雷噬嗑", "山雷颐", "山风蛊"],
    "坎": ["坎为水", "水泽节", "水雷屯", "水火既济", "泽火革", "雷火丰", "地火明夷", "地水师"],
    "艮": ["艮为山", "山火贲", "山天大畜", "山泽损", "火泽睽", "天泽履", "风泽中孚", "风山渐"],
    "坤": ["坤为地", "地雷复", "地泽临", "地天泰", "雷天大壮", "泽天夬", "水天需", "水地比"],
}

RELATION_TYPES = ["本宫", "一世", "二世", "三世", "四世", "五世", "游魂", "归魂"]

SHI_YING_RULES = {
    "本宫": (6, 3),
    "一世": (1, 4),
    "二世": (2, 5),
    "三世": (3, 6),
    "四世": (4, 1),
    "五世": (5, 2),
    "游魂": (4, 1),
    "归魂": (3, 6),
}


def build_palace_keys(palace: str) -> List[Tuple[int, int, int, int, int, int]]:
    """按京房八宫变爻路径生成一宫八卦。"""
    base = list(TRIGRAM_BITS[palace] + TRIGRAM_BITS[palace])
    result = [tuple(base)]

    current = base[:]

    # 一世到五世：初、二、三、四、五爻依次变
    for idx in range(5):
        current[idx] = 1 - current[idx]
        result.append(tuple(current))

    # 游魂：第四爻复变
    current[3] = 1 - current[3]
    result.append(tuple(current))

    # 归魂：内卦回归本宫
    current[0:3] = list(TRIGRAM_BITS[palace])
    result.append(tuple(current))

    return result


def build_hexagrams() -> Dict[Tuple[int, int, int, int, int, int], Hexagram]:
    data: Dict[Tuple[int, int, int, int, int, int], Hexagram] = {}

    for palace, names in PALACE_NAMES.items():
        keys = build_palace_keys(palace)
        for idx, key in enumerate(keys):
            relation_type = RELATION_TYPES[idx]
            shi, ying = SHI_YING_RULES[relation_type]
            data[key] = Hexagram(
                name=names[idx],
                palace=palace,
                palace_index=idx,
                lines=list(key),
                shi_index=shi,
                ying_index=ying,
                relation_type=relation_type,
            )

    if len(data) != 64:
        raise RuntimeError(f"64卦数据库生成失败，当前只有 {len(data)} 卦")

    return data


HEXAGRAMS = build_hexagrams()


# =========================================================
# 五行六亲
# =========================================================

def get_relative(palace_element: str, line_element: str) -> str:
    """以宫五行为我计算六亲。"""
    if palace_element == line_element:
        return "兄弟"
    if GENERATE[palace_element] == line_element:
        return "子孙"
    if GENERATE[line_element] == palace_element:
        return "父母"
    if CONTROL[palace_element] == line_element:
        return "妻财"
    if CONTROL[line_element] == palace_element:
        return "官鬼"
    raise ValueError(f"无法计算六亲：宫五行={palace_element}, 爻五行={line_element}")


# =========================================================
# 铜钱算法：唯一允许三枚铜钱求和
# =========================================================

class CoinEngine:
    @staticmethod
    def parse(total: int) -> Tuple[YinYang, bool]:
        if total == 6:
            return YinYang.YIN, True
        if total == 7:
            return YinYang.YANG, False
        if total == 8:
            return YinYang.YIN, False
        if total == 9:
            return YinYang.YANG, True
        raise ValueError("铜钱结果必须为6/7/8/9")


# =========================================================
# 六爻主引擎
# =========================================================

class LiuYaoEngine:
    def __init__(
        self,
        totals: List[int],
        divination_time: Optional[DivinationTime] = None,
    ):
        if len(totals) != 6:
            raise ValueError("必须输入六次铜钱结果")

        self.totals = totals
        self.divination_time = divination_time or build_divination_time()
        self.lines = self.build_lines()
        self.original_hexagram = self.build_hexagram(changed=False)
        self.assign_najia_and_relatives()
        self.assign_six_spirits()
        self.changed_lines = self.build_changed_lines()

    def build_lines(self) -> List[Line]:
        lines: List[Line] = []
        for idx, total in enumerate(self.totals):
            yy, changing = CoinEngine.parse(total)
            lines.append(Line(index=idx + 1, value=total, yin_yang=yy, changing=changing))
        return lines

    def build_hexagram(self, changed: bool = False) -> Hexagram:
        if changed:
            arr = [line.changed_to_bit() for line in self.lines]
        else:
            arr = [line.to_bit() for line in self.lines]

        key = tuple(arr)
        if key not in HEXAGRAMS:
            raise ValueError(f"未找到卦：{key}")
        return HEXAGRAMS[key]

    def arrange_hexagram_lines(
        self,
        hexagram: Hexagram,
        relative_palace: str,
    ) -> List[ArrangedLine]:
        """按卦象装纳甲；六亲以 relative_palace 的宫五行为我。"""
        lower_bits = tuple(hexagram.lines[0:3])
        upper_bits = tuple(hexagram.lines[3:6])

        lower_trigram = TRIGRAMS[lower_bits]
        upper_trigram = TRIGRAMS[upper_bits]

        najia_items = NAJIA[lower_trigram]["inner"] + NAJIA[upper_trigram]["outer"]
        palace_element = PALACE_ELEMENT[relative_palace]

        arranged_lines = []
        for i, line_value in enumerate(hexagram.lines):
            stem, branch = najia_items[i]
            element = BRANCH_ELEMENT[branch]
            arranged_lines.append(
                ArrangedLine(
                    index=i + 1,
                    yin_yang=YinYang(line_value),
                    heavenly_stem=stem,
                    earthly_branch=branch,
                    element=element,
                    six_relative=get_relative(palace_element, element),
                )
            )

        return arranged_lines

    def assign_najia_and_relatives(self) -> None:
        """主卦纳甲：按上下经卦装纳甲；六亲：按本卦所属宫五行计算。"""
        arranged_lines = self.arrange_hexagram_lines(
            self.original_hexagram,
            relative_palace=self.original_hexagram.palace,
        )

        for line, arranged in zip(self.lines, arranged_lines):
            line.heavenly_stem = arranged.heavenly_stem
            line.earthly_branch = arranged.earthly_branch
            line.element = arranged.element
            line.six_relative = arranged.six_relative

    def build_changed_lines(self) -> List[ChangedLine]:
        """只为动爻生成化出信息；静爻不重装纳甲、六亲、六神。"""
        changed_bits = [line.changed_to_bit() for line in self.lines]
        lower_trigram = TRIGRAMS[tuple(changed_bits[0:3])]
        upper_trigram = TRIGRAMS[tuple(changed_bits[3:6])]
        najia_items = NAJIA[lower_trigram]["inner"] + NAJIA[upper_trigram]["outer"]
        palace_element = PALACE_ELEMENT[self.original_hexagram.palace]

        changed_lines = []
        for line in self.lines:
            if not line.changing:
                continue

            stem, branch = najia_items[line.index - 1]
            element = BRANCH_ELEMENT[branch]
            changed_lines.append(
                ChangedLine(
                    index=line.index,
                    original_line=line,
                    yin_yang=line.changed(),
                    heavenly_stem=stem,
                    earthly_branch=branch,
                    element=element,
                    six_relative=get_relative(palace_element, element),
                )
            )

        return changed_lines

    def get_changed_line_by_index(self, index: int) -> ChangedLine:
        for changed_line in self.changed_lines:
            if changed_line.index == index:
                return changed_line
        raise ValueError(f"{index}爻不是动爻，没有化出信息")

    def assign_six_spirits(self) -> None:
        """六神按日干起，从初爻顺排至上爻，只装本卦。"""
        spirits = SIX_SPIRIT_RULES[self.divination_time.day_stem]
        for line, spirit in zip(self.lines, spirits):
            line.six_spirit = spirit

    def get_pure_palace_line_infos(self) -> List[Tuple[str, str, str, str]]:
        """返回本宫纯卦六爻的六亲、天干、地支、五行，用于伏神。"""
        palace = self.original_hexagram.palace
        pure_bits = TRIGRAM_BITS[palace] + TRIGRAM_BITS[palace]
        lower_trigram = TRIGRAMS[pure_bits[0:3]]
        upper_trigram = TRIGRAMS[pure_bits[3:6]]
        najia_items = NAJIA[lower_trigram]["inner"] + NAJIA[upper_trigram]["outer"]
        palace_element = PALACE_ELEMENT[palace]

        result = []
        for stem, branch in najia_items:
            element = BRANCH_ELEMENT[branch]
            relative = get_relative(palace_element, element)
            result.append((relative, stem, branch, element))
        return result

    def get_yao_symbol(self, yin_yang: YinYang) -> str:
        return "———" if yin_yang == YinYang.YANG else "— —"

    def hidden_spirit_to_dict(self, hidden_spirit: HiddenSpirit) -> Dict[str, object]:
        return {
            "six_relative": hidden_spirit.six_relative,
            "heavenly_stem": hidden_spirit.heavenly_stem,
            "earthly_branch": hidden_spirit.earthly_branch,
            "element": hidden_spirit.element,
            "source_palace": hidden_spirit.source_palace,
            "flying_line_index": hidden_spirit.flying_line_index,
            "display": hidden_spirit.display(),
        }

    def line_to_dict(self, line: Line) -> Dict[str, object]:
        return {
            "index": line.index,
            "coin_total": line.value,
            "yin_yang": "阳" if line.yin_yang == YinYang.YANG else "阴",
            "bit": line.to_bit(),
            "yao": self.get_yao_symbol(line.yin_yang),
            "changing": line.changing,
            "change_symbol": "O" if line.value == 9 else "X" if line.value == 6 else "",
            "six_spirit": line.six_spirit,
            "six_relative": line.six_relative,
            "heavenly_stem": line.heavenly_stem,
            "earthly_branch": line.earthly_branch,
            "element": line.element,
            "is_shi": line.index == self.original_hexagram.shi_index,
            "is_ying": line.index == self.original_hexagram.ying_index,
            "hidden_spirit": (
                self.hidden_spirit_to_dict(line.hidden_spirit)
                if line.hidden_spirit is not None
                else None
            ),
            "tags": list(line.tags),
            "display": self.format_line_body(line),
        }

    def changed_line_to_dict(self, line: ChangedLine) -> Dict[str, object]:
        return {
            "index": line.index,
            "yin_yang": "阳" if line.yin_yang == YinYang.YANG else "阴",
            "bit": 1 if line.yin_yang == YinYang.YANG else 0,
            "yao": self.get_yao_symbol(line.yin_yang),
            "six_relative": line.six_relative,
            "heavenly_stem": line.heavenly_stem,
            "earthly_branch": line.earthly_branch,
            "element": line.element,
            "tags": list(line.tags),
            "display": self.format_changed_line_body(line),
        }

    def changing_line_to_dict(self, line: Line) -> Dict[str, object]:
        changed_line = self.get_changed_line_by_index(line.index)
        return {
            "index": line.index,
            "from": self.line_to_dict(line),
            "to": self.changed_line_to_dict(changed_line),
            "display": (
                f"{line.index}爻 "
                f"{self.format_line_core(line)} -> "
                f"{self.format_changed_line_body(changed_line)}"
            ),
        }

    def to_dict(self) -> Dict[str, object]:
        return {
            "time": {
                "qigua_datetime": self.divination_time.qigua_datetime.isoformat(),
                "month_branch": self.divination_time.month_branch,
                "month_element": self.divination_time.month_element,
                "month_term": self.divination_time.month_term,
                "day_stem": self.divination_time.day_stem,
                "day_branch": self.divination_time.day_branch,
                "day_element": self.divination_time.day_element,
                "day_ganzhi": self.divination_time.day_ganzhi,
                "void_branches": list(self.divination_time.void_branches),
            },
            "original_hexagram": {
                "name": self.original_hexagram.name,
                "palace": self.original_hexagram.palace,
                "palace_index": self.original_hexagram.palace_index,
                "relation_type": self.original_hexagram.relation_type,
                "shi_index": self.original_hexagram.shi_index,
                "ying_index": self.original_hexagram.ying_index,
                "lines": [self.line_to_dict(line) for line in self.lines],
            },
            "changing_lines": [
                self.changing_line_to_dict(line)
                for line in self.lines
                if line.changing
            ],
        }

    def format_line_body(self, line: Line) -> str:
        return f"{line.six_spirit} {line.six_relative}{line.heavenly_stem}{line.earthly_branch}{line.element}"

    def format_line_core(self, line: Line) -> str:
        return f"{line.six_relative}{line.heavenly_stem}{line.earthly_branch}{line.element}"

    def format_changed_line_body(self, line: ChangedLine) -> str:
        return f"{line.six_relative}{line.heavenly_stem}{line.earthly_branch}{line.element}"

    def print_result(self) -> None:
        print("=" * 60)
        print("京房六爻排盘")
        print("=" * 60)
        print(f"起卦时间：{self.divination_time.qigua_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(
            f"月建：{self.divination_time.month_branch}{self.divination_time.month_element}"
            f"（{self.divination_time.month_term}后）"
        )
        print(
            f"日辰：{self.divination_time.day_ganzhi}"
            f"{self.divination_time.day_element}"
        )
        print(f"旬空：{'、'.join(self.divination_time.void_branches)}")
        print()
        print(f"本卦：{self.original_hexagram.name}")
        print(f"宫位：{self.original_hexagram.palace}宫")
        print(f"关系：{self.original_hexagram.relation_type}")
        print()
        print("本卦六爻：")

        for i in reversed(range(6)):
            line = self.lines[i]
            yao = "———" if line.yin_yang == YinYang.YANG else "— —"

            if line.changing:
                yao += " O" if line.value == 9 else " X"

            marker = ""
            if line.index == self.original_hexagram.shi_index:
                marker += " 世"
            if line.index == self.original_hexagram.ying_index:
                marker += " 应"

            hidden = f"  {line.hidden_spirit.display()}" if line.hidden_spirit else ""
            changed = ""
            if line.changing:
                changed_line = self.get_changed_line_by_index(line.index)
                changed = f" -> {self.format_changed_line_body(changed_line)}"

            print(
                f"{line.index}爻 {yao:<6} "
                f"{self.format_line_body(line)}"
                f"{marker}{hidden}{changed}"
            )

        print("=" * 60)


class YongShenLocator:
    def __init__(
        self,
        chart: LiuYaoEngine,
        yongshen: str,
        selected_line: Optional[int] = None,
    ):
        if yongshen not in VALID_RELATIVES:
            raise ValueError("用神必须手动指定为：兄弟、父母、子孙、妻财、官鬼")

        if selected_line is not None and selected_line not in {1, 2, 3, 4, 5, 6}:
            raise ValueError("用神爻位必须是 1 到 6")

        self.chart = chart
        self.yongshen = yongshen
        self.selected_line = selected_line

    def locate(self) -> YongShenResult:
        if self.selected_line is not None:
            line = self.chart.lines[self.selected_line - 1]
            if line.six_relative != self.yongshen:
                raise ValueError(
                    f"{self.selected_line}爻为{line.six_relative}，不能指定为{self.yongshen}用神"
                )
            return YongShenResult(
                found_visible=True,
                visible_line=line.index,
                hidden_line=None,
                hidden_from_palace=None,
            )

        for line in self.chart.lines:
            if line.six_relative == self.yongshen:
                return YongShenResult(
                    found_visible=True,
                    visible_line=line.index,
                    hidden_line=None,
                    hidden_from_palace=None,
                )

        for idx, (relative, stem, branch, element) in enumerate(
            self.chart.get_pure_palace_line_infos()
        ):
            if relative == self.yongshen:
                line_index = idx + 1
                hidden_spirit = HiddenSpirit(
                    six_relative=relative,
                    heavenly_stem=stem,
                    earthly_branch=branch,
                    element=element,
                    source_palace=self.chart.original_hexagram.palace,
                    flying_line_index=line_index,
                )
                return YongShenResult(
                    found_visible=False,
                    visible_line=None,
                    hidden_line=line_index,
                    hidden_from_palace=self.chart.original_hexagram.palace,
                    hidden_spirit=hidden_spirit,
                )

        return YongShenResult(
            found_visible=False,
            visible_line=None,
            hidden_line=None,
            hidden_from_palace=None,
        )


class AnalysisEngine:
    def __init__(
        self,
        chart: LiuYaoEngine,
        query_info: QueryInfo,
        fu_shen_mode: str = "yongshen_only",
    ):
        if fu_shen_mode not in {"yongshen_only", "missing_only", "full_mapping"}:
            raise ValueError("fu_shen_mode 必须是 yongshen_only / missing_only / full_mapping")

        self.chart = chart
        self.query_info = query_info
        self.fu_shen_mode = fu_shen_mode
        self.yongshen = query_info.primary_yongshen
        self.related_spirits = self.build_related_spirits()
        self.yongshen_locator = (
            YongShenLocator(
                chart=chart,
                yongshen=self.yongshen,
                selected_line=query_info.yongshen_line,
            )
            if self.yongshen is not None
            else None
        )
        self.yongshen_result = (
            self.yongshen_locator.locate()
            if self.yongshen_locator is not None
            else YongShenResult(
                found_visible=False,
                visible_line=None,
                hidden_line=None,
                hidden_from_palace=None,
            )
        )
        self.assign_fu_shen()
        self.assign_tags()
        self.relationship_hints = self.build_relationship_hints()

    @property
    def divination_time(self) -> DivinationTime:
        return self.chart.divination_time

    def build_related_spirits(self) -> Dict[str, Optional[str]]:
        if self.yongshen is None:
            return {"original": None, "hostile": None, "enemy": None}
        return dict(YONGSHEN_RELATION_RULES[self.yongshen])

    def assign_fu_shen(self) -> None:
        for line in self.chart.lines:
            line.hidden_spirit = None

        if self.yongshen is None:
            return

        required = {"兄弟", "父母", "子孙", "妻财", "官鬼"}
        existing = {line.six_relative for line in self.chart.lines}

        if self.fu_shen_mode == "yongshen_only":
            if self.yongshen_result.hidden_line is None or self.yongshen_result.hidden_spirit is None:
                return
            self.chart.lines[self.yongshen_result.hidden_line - 1].hidden_spirit = (
                self.yongshen_result.hidden_spirit
            )
            return
        elif self.fu_shen_mode == "missing_only":
            targets = required - existing
        elif self.fu_shen_mode == "full_mapping":
            targets = required
        else:
            raise ValueError("未知伏神模式")

        if not targets:
            return

        pure_infos = self.chart.get_pure_palace_line_infos()
        for idx, (relative, stem, branch, element) in enumerate(pure_infos):
            if self.fu_shen_mode == "full_mapping" or relative in targets:
                self.chart.lines[idx].hidden_spirit = HiddenSpirit(
                    six_relative=relative,
                    heavenly_stem=stem,
                    earthly_branch=branch,
                    element=element,
                    source_palace=self.chart.original_hexagram.palace,
                    flying_line_index=idx + 1,
                )

    def add_tag(self, tags: List[str], tag: str) -> None:
        if tag not in tags:
            tags.append(tag)

    def apply_branch_tags(self, tags: List[str], branch: str) -> None:
        if branch == self.divination_time.month_branch:
            self.add_tag(tags, "月建")

        if branch == self.divination_time.day_branch:
            self.add_tag(tags, "临日")

        if branch in self.divination_time.void_branches:
            self.add_tag(tags, "旬空")

    def assign_tags(self) -> None:
        for line in self.chart.lines:
            line.tags.clear()
            self.apply_branch_tags(line.tags, line.earthly_branch)

        for changed_line in self.chart.changed_lines:
            changed_line.tags.clear()
            self.apply_branch_tags(changed_line.tags, changed_line.earthly_branch)

    def get_line_roles(self, line: Line) -> List[str]:
        roles = []
        if self.yongshen is None:
            return roles

        if self.yongshen_result.visible_line == line.index:
            roles.append("用神")
        if line.six_relative == self.related_spirits["original"]:
            roles.append("原神")
        if line.six_relative == self.related_spirits["hostile"]:
            roles.append("忌神")
        if line.six_relative == self.related_spirits["enemy"]:
            roles.append("仇神")
        return roles

    def get_changed_line_roles(self, line: ChangedLine) -> List[str]:
        return []

    def get_line_role_marker(self, line: Line) -> str:
        markers = self.get_line_roles(line)
        return f" [{'、'.join(markers)}]" if markers else ""

    def get_changed_line_role_marker(self, line: ChangedLine) -> str:
        markers = self.get_changed_line_roles(line)
        return f" [{'、'.join(markers)}]" if markers else ""

    def format_tags(self, tags: List[str]) -> str:
        return f" <{' '.join(tags)}>" if tags else ""

    def build_branch_refs(self) -> List[BranchRef]:
        refs = [
            BranchRef(
                label=f"月建{self.divination_time.month_branch}",
                branch=self.divination_time.month_branch,
                source="month",
            ),
            BranchRef(
                label=f"日辰{self.divination_time.day_branch}",
                branch=self.divination_time.day_branch,
                source="day",
            ),
        ]

        for line in self.chart.lines:
            refs.append(
                BranchRef(
                    label=f"本卦{line.index}爻{line.earthly_branch}",
                    branch=line.earthly_branch,
                    source="original",
                    line_index=line.index,
                )
            )

        for changed_line in self.chart.changed_lines:
            refs.append(
                BranchRef(
                    label=f"化爻{changed_line.index}爻{changed_line.earthly_branch}",
                    branch=changed_line.earthly_branch,
                    source="changed",
                    line_index=changed_line.index,
                )
            )

        return refs

    def branch_ref_to_dict(self, ref: BranchRef) -> Dict[str, object]:
        return {
            "label": ref.label,
            "branch": ref.branch,
            "source": ref.source,
            "line_index": ref.line_index,
        }

    def relationship_hint_to_dict(self, hint: RelationshipHint) -> Dict[str, object]:
        return {
            "name": hint.name,
            "refs": [self.branch_ref_to_dict(ref) for ref in hint.refs],
            "display": self.format_relationship_hint(hint),
        }

    def add_relationship_hint(
        self,
        hints: List[RelationshipHint],
        seen: set,
        name: str,
        refs: Tuple[BranchRef, ...],
    ) -> None:
        key = (
            name,
            tuple((ref.source, ref.line_index, ref.branch, ref.label) for ref in refs),
        )
        if key in seen:
            return
        seen.add(key)
        hints.append(RelationshipHint(name=name, refs=refs))

    def build_relationship_hints(self) -> List[RelationshipHint]:
        refs = self.build_branch_refs()
        hints: List[RelationshipHint] = []
        seen = set()

        for i, left in enumerate(refs):
            for right in refs[i + 1:]:
                pair = frozenset((left.branch, right.branch))
                if pair in LIU_HE_PAIRS:
                    self.add_relationship_hint(hints, seen, "六合", (left, right))
                if pair in LIU_CHONG_PAIRS:
                    self.add_relationship_hint(hints, seen, "六冲", (left, right))

        for group in SAN_XING_GROUPS:
            matched = [ref for ref in refs if ref.branch in group]
            matched_branches = {ref.branch for ref in matched}
            if len(matched_branches) >= 2:
                self.add_relationship_hint(
                    hints,
                    seen,
                    "三刑",
                    tuple(matched),
                )

        for branch in SELF_XING_BRANCHES:
            matched = [ref for ref in refs if ref.branch == branch]
            if len(matched) >= 2:
                self.add_relationship_hint(
                    hints,
                    seen,
                    "自刑",
                    tuple(matched),
                )

        return hints

    def format_relationship_hint(self, hint: RelationshipHint) -> str:
        return f"{hint.name}：" + " + ".join(ref.label for ref in hint.refs)

    def line_to_dict(self, line: Line) -> Dict[str, object]:
        data = self.chart.line_to_dict(line)
        data["roles"] = self.get_line_roles(line)
        data["tags"] = list(line.tags)
        return data

    def changed_line_to_dict(self, line: ChangedLine) -> Dict[str, object]:
        data = self.chart.changed_line_to_dict(line)
        data["roles"] = self.get_changed_line_roles(line)
        data["tags"] = list(line.tags)
        return data

    def changing_line_to_dict(self, line: Line) -> Dict[str, object]:
        changed_line = self.chart.get_changed_line_by_index(line.index)
        return {
            "index": line.index,
            "from": self.line_to_dict(line),
            "to": self.changed_line_to_dict(changed_line),
            "display": (
                f"{line.index}爻 "
                f"{self.chart.format_line_core(line)} -> "
                f"{self.chart.format_changed_line_body(changed_line)}"
            ),
        }

    def yongshen_result_to_dict(self) -> Dict[str, object]:
        return {
            "found_visible": self.yongshen_result.found_visible,
            "visible_line": self.yongshen_result.visible_line,
            "hidden_line": self.yongshen_result.hidden_line,
            "hidden_from_palace": self.yongshen_result.hidden_from_palace,
            "hidden_spirit": (
                self.chart.hidden_spirit_to_dict(self.yongshen_result.hidden_spirit)
                if self.yongshen_result.hidden_spirit is not None
                else None
            ),
        }

    def to_dict(self) -> Dict[str, object]:
        data = self.chart.to_dict()
        data["query"] = {
            "gender": self.query_info.gender,
            "primary_yongshen": self.query_info.primary_yongshen,
            "yongshen_line": self.query_info.yongshen_line,
            "subject": self.query_info.subject,
            "sub_subject": self.query_info.sub_subject,
            "question": self.query_info.question,
        }
        data["fu_shen"] = {
            "mode": self.fu_shen_mode,
            "yongshen": self.yongshen,
            "yongshen_result": self.yongshen_result_to_dict(),
        }
        data["yongshen_relations"] = {
            "yongshen": self.yongshen,
            "original": self.related_spirits["original"],
            "hostile": self.related_spirits["hostile"],
            "enemy": self.related_spirits["enemy"],
        }
        data["relationship_hints"] = [
            self.relationship_hint_to_dict(hint)
            for hint in self.relationship_hints
        ]
        data["original_hexagram"]["lines"] = [
            self.line_to_dict(line) for line in self.chart.lines
        ]
        data["changing_lines"] = [
            self.changing_line_to_dict(line)
            for line in self.chart.lines
            if line.changing
        ]
        return data

    def print_result(self) -> None:
        chart = self.chart
        print("=" * 60)
        print("京房六爻排盘")
        print("=" * 60)
        print(f"求测者：{self.query_info.gender}")
        if self.query_info.subject:
            print(f"求测事项：{self.query_info.subject}")
        if self.query_info.sub_subject:
            print(f"细分事项：{self.query_info.sub_subject}")
        if self.query_info.question:
            print(f"所问问题：{self.query_info.question}")
        if self.query_info.primary_yongshen:
            print(f"主用神：{self.query_info.primary_yongshen}")
        if self.query_info.yongshen_line:
            print(f"用神爻位：{self.query_info.yongshen_line}爻")
        print()
        print(f"起卦时间：{self.divination_time.qigua_datetime.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(
            f"月建：{self.divination_time.month_branch}{self.divination_time.month_element}"
            f"（{self.divination_time.month_term}后）"
        )
        print(f"日辰：{self.divination_time.day_ganzhi}{self.divination_time.day_element}")
        print(f"旬空：{'、'.join(self.divination_time.void_branches)}")
        print()
        print(f"本卦：{chart.original_hexagram.name}")
        print(f"宫位：{chart.original_hexagram.palace}宫")
        print(f"关系：{chart.original_hexagram.relation_type}")
        print()
        if self.yongshen is not None:
            print(f"伏神模式：{self.fu_shen_mode}")
            print(f"指定用神：{self.yongshen}")
            print()
        print("本卦六爻：")

        for i in reversed(range(6)):
            line = chart.lines[i]
            yao = chart.get_yao_symbol(line.yin_yang)
            if line.changing:
                yao += " O" if line.value == 9 else " X"

            marker = ""
            if line.index == chart.original_hexagram.shi_index:
                marker += " 世"
            if line.index == chart.original_hexagram.ying_index:
                marker += " 应"

            hidden = f"  {line.hidden_spirit.display()}" if line.hidden_spirit else ""
            changed = ""
            if line.changing:
                changed_line = chart.get_changed_line_by_index(line.index)
                changed = (
                    f" -> {chart.format_changed_line_body(changed_line)}"
                    f"{self.get_changed_line_role_marker(changed_line)}"
                    f"{self.format_tags(changed_line.tags)}"
                )

            print(
                f"{line.index}爻 {yao:<6} "
                f"{chart.format_line_body(line)}"
                f"{marker}{self.get_line_role_marker(line)}"
                f"{self.format_tags(line.tags)}{hidden}{changed}"
            )

        if self.relationship_hints:
            print()
            print("关系提示：")
            for hint in self.relationship_hints:
                print(self.format_relationship_hint(hint))

        print("=" * 60)


def prompt_choice(prompt: str, choices: List[str]) -> str:
    choice_text = " / ".join(choices)
    while True:
        value = input(f"{prompt}（{choice_text}）：").strip()
        if value in choices:
            return value
        print(f"输入无效，请输入：{choice_text}")


def prompt_required(prompt: str) -> str:
    while True:
        value = input(f"{prompt}：").strip()
        if value:
            return value
        print("不能为空，请重新输入。")


def prompt_coin_total(line_name: str) -> int:
    while True:
        value = input(f"{line_name}（6老阴/7少阳/8少阴/9老阳）：").strip()
        if value in {"6", "7", "8", "9"}:
            return int(value)
        print("输入无效，只能输入 6 / 7 / 8 / 9。")


def prompt_optional_line_index(prompt: str) -> Optional[int]:
    while True:
        value = input(f"{prompt}（1-6，回车跳过）：").strip()
        if value == "":
            return None
        if value in {"1", "2", "3", "4", "5", "6"}:
            return int(value)
        print("输入无效，只能输入 1 / 2 / 3 / 4 / 5 / 6，或直接回车跳过。")


def run_interactive_cli() -> None:
    print("=" * 60)
    print("京房六爻排盘 - 交互输入")
    print("=" * 60)
    gender = prompt_choice("求测者性别", ["男", "女"])

    print()
    print("请自下而上输入六次摇卦结果。")
    totals = [
        prompt_coin_total("初爻"),
        prompt_coin_total("二爻"),
        prompt_coin_total("三爻"),
        prompt_coin_total("四爻"),
        prompt_coin_total("五爻"),
        prompt_coin_total("上爻"),
    ]

    print()
    chart = LiuYaoEngine(totals=totals)
    base_query_info = build_query_info(gender=gender)
    AnalysisEngine(chart=chart, query_info=base_query_info).print_result()

    print()
    selected_line = prompt_optional_line_index("请选择用神爻位")
    if selected_line is None:
        return

    selected = chart.lines[selected_line - 1]
    query_info = build_query_info(
        gender=gender,
        yongshen=selected.six_relative,
        yongshen_line=selected_line,
    )
    engine = AnalysisEngine(chart=chart, query_info=query_info)
    print()
    engine.print_result()


if __name__ == "__main__":
    run_interactive_cli()
