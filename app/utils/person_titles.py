"""
Person titles and affiliations for thumbnail generation.
"""

from app.utils.logger import logger

# 人物名から肩書を取得する辞書
PERSON_TITLES = {
    "ウォーレン・バフェット": "バークシャー・ハサウェイCEO・世界一の投資家",
    "Warren Buffett": "バークシャー・ハサウェイCEO・世界一の投資家",
    "ピーター・ティール": "PayPal・OpenAI共同創業者",
    "Peter Thiel": "PayPal・OpenAI共同創業者",
    "スティーブ・ジョブズ": "Apple創業者・元CEO",
    "Steve Jobs": "Apple創業者・元CEO",
    "イーロン・マスク": "Tesla・SpaceX CEO",
    "Elon Musk": "Tesla・SpaceX CEO",
    "ビル・ゲイツ": "Microsoft創業者",
    "Bill Gates": "Microsoft創業者",
    "チャーリー・マンガー": "バークシャー・ハサウェイ副会長",
    "Charlie Munger": "バークシャー・ハサウェイ副会長",
    "孫正義": "ソフトバンクグループ代表",
    "Masayoshi Son": "ソフトバンクグループ代表",
    "稲盛和夫": "京セラ創業者・経営の神様",
    "松下幸之助": "パナソニック創業者・経営の神様",
    "マキャヴェッリ": "『君主論』著者・政治思想家",
    "Niccolò Machiavelli": "『君主論』著者・政治思想家",
    "アダム・スミス": "『国富論』著者・経済学者",
    "Adam Smith": "『国富論』著者・経済学者",
    "ベンジャミン・フランクリン": "アメリカ建国の父・実業家",
    "Benjamin Franklin": "アメリカ建国の父・実業家",
    "ナポレオン・ヒル": "『思考は現実化する』著者",
    "Napoleon Hill": "『思考は現実化する』著者",
    "デール・カーネギー": "『人を動かす』著者",
    "Dale Carnegie": "『人を動かす』著者",
    "アルベルト・アインシュタイン": "理論物理学者・ノーベル物理学賞受賞者",
    "Albert Einstein": "理論物理学者・ノーベル物理学賞受賞者",
}

# 人物名から代表的な名言を取得する辞書
PERSON_QUOTES = {
    "ウォーレン・バフェット": "リスクは自分が何をやっているかよく分からない時に起こる",
    "Warren Buffett": "リスクは自分が何をやっているかよく分からない時に起こる",
    "ピーター・ティール": "競争は敗者のためのものだ",
    "Peter Thiel": "競争は敗者のためのものだ",
    "スティーブ・ジョブズ": "Stay Hungry Stay Foolish",
    "Steve Jobs": "Stay Hungry Stay Foolish",
    "イーロン・マスク": "失敗は選択肢の一つだ もし失敗していないなら十分に革新的ではない",
    "Elon Musk": "失敗は選択肢の一つだ もし失敗していないなら十分に革新的ではない",
    "アルベルト・アインシュタイン": "想像力は知識よりも重要である",
    "Albert Einstein": "想像力は知識よりも重要である",
}


# 人物の外見描写（AI画像生成プロンプト用・英語）
# 存命人物は現在の年齢、故人は最も有名な時期の年齢で記述
PERSON_APPEARANCES = {
    # テック系
    "ピーター・ティール": "middle-aged man in his late 50s, short brown hair, clean-shaven, sharp features, wearing a dark suit",
    "Peter Thiel": "middle-aged man in his late 50s, short brown hair, clean-shaven, sharp features, wearing a dark suit",
    "スティーブ・ジョブズ": "middle-aged man in his 50s, thin build, round glasses, short gray hair, wearing his iconic black turtleneck",
    "Steve Jobs": "middle-aged man in his 50s, thin build, round glasses, short gray hair, wearing his iconic black turtleneck",
    "イーロン・マスク": "middle-aged man in his early 50s, short dark hair, clean-shaven, wearing a dark suit or casual blazer",
    "Elon Musk": "middle-aged man in his early 50s, short dark hair, clean-shaven, wearing a dark suit or casual blazer",
    "ビル・ゲイツ": "elderly man in his early 70s, gray hair, glasses, gentle smile, wearing a casual sweater or suit",
    "Bill Gates": "elderly man in his early 70s, gray hair, glasses, gentle smile, wearing a casual sweater or suit",
    # 投資家・実業家
    "ウォーレン・バフェット": "elderly man in his mid 90s, white hair, glasses, warm friendly smile, wearing a dark suit with tie",
    "Warren Buffett": "elderly man in his mid 90s, white hair, glasses, warm friendly smile, wearing a dark suit with tie",
    "チャーリー・マンガー": "very elderly man in his late 90s, white hair, thick glasses, wise expression, wearing a dark suit",
    "Charlie Munger": "very elderly man in his late 90s, white hair, thick glasses, wise expression, wearing a dark suit",
    # 日本の実業家
    "孫正義": "middle-aged to elderly man in his late 60s, balding head, glasses, energetic expression, wearing a dark suit",
    "Masayoshi Son": "middle-aged to elderly man in his late 60s, balding head, glasses, energetic expression, wearing a dark suit",
    "稲盛和夫": "elderly man in his late 80s, white hair, glasses, dignified calm expression, wearing a dark suit",
    "松下幸之助": "elderly Japanese man in his 80s, white hair, wise gentle expression, wearing traditional dark suit",
    # 古典的思想家
    "マキャヴェッリ": "Renaissance-era Italian man in his 50s, dark hair, sharp intelligent eyes, wearing Renaissance-period clothing",
    "Niccolò Machiavelli": "Renaissance-era Italian man in his 50s, dark hair, sharp intelligent eyes, wearing Renaissance-period clothing",
    "アダム・スミス": "18th century gentleman in his 60s, white powdered wig, thoughtful expression, wearing 18th century formal attire",
    "Adam Smith": "18th century gentleman in his 60s, white powdered wig, thoughtful expression, wearing 18th century formal attire",
    "ベンジャミン・フランクリン": "elderly 18th century gentleman in his 70s, balding with long white hair on sides, round glasses, wearing 18th century formal attire",
    "Benjamin Franklin": "elderly 18th century gentleman in his 70s, balding with long white hair on sides, round glasses, wearing 18th century formal attire",
    "ナポレオン・ヒル": "middle-aged man in his 60s from early 20th century, wearing a suit and tie, confident expression",
    "Napoleon Hill": "middle-aged man in his 60s from early 20th century, wearing a suit and tie, confident expression",
    "デール・カーネギー": "middle-aged man in his 60s from mid 20th century, friendly warm smile, wearing a suit and tie",
    "Dale Carnegie": "middle-aged man in his 60s from mid 20th century, friendly warm smile, wearing a suit and tie",
    # 科学者
    "アルベルト・アインシュタイン": "elderly man in his 70s, iconic wild white hair, mustache, kind wise eyes, wearing a casual sweater or jacket",
    "Albert Einstein": "elderly man in his 70s, iconic wild white hair, mustache, kind wise eyes, wearing a casual sweater or jacket",
}


def get_person_appearance(person_name: str) -> str:
    """
    人物の外見描写を取得する（AI画像生成用）。

    Args:
        person_name: 人物名

    Returns:
        英語の外見描写文字列。未登録の場合は汎用的な描写を返す
    """
    appearance = PERSON_APPEARANCES.get(person_name, "")
    if not appearance:
        logger.info(f"[INFO] 外見描写が未登録です: {person_name}（汎用描写を使用）")
        appearance = "distinguished person, professional appearance, confident expression"
    return appearance


def get_person_title(person_name: str) -> str:
    """
    Get title/affiliation for a person.

    Args:
        person_name: Name of the person

    Returns:
        Title/affiliation string, or empty string if not found
    """
    return PERSON_TITLES.get(person_name, "")


def get_person_title_or_default(person_name: str) -> str:
    """
    Get title/affiliation for a person, with fallback.

    Args:
        person_name: Name of the person

    Returns:
        Title/affiliation string, or person_name if not found
    """
    title = PERSON_TITLES.get(person_name, "")
    if not title:
        # デフォルトとして、人物名をそのまま返す
        return person_name
    return title


def get_person_quote(person_name: str) -> str:
    """
    Get a famous quote for a person.

    Args:
        person_name: Name of the person

    Returns:
        Famous quote string, or empty string if not found
    """
    return PERSON_QUOTES.get(person_name, "")


def register_person_info(
    person_name: str,
    title: str | None = None,
    quote: str | None = None,
    appearance: str | None = None,
) -> None:
    """
    動的に人物情報を辞書に登録する。
    AIが取得した肩書・名言・外見描写を画像生成前に登録するために使用。

    Args:
        person_name: 人物名
        title: 肩書（Noneまたは空文字の場合はスキップ）
        quote: 名言（Noneまたは空文字の場合はスキップ）
        appearance: 外見描写（Noneまたは空文字の場合はスキップ）
    """
    if title:
        PERSON_TITLES[person_name] = title
        logger.info(f"[INFO] 肩書を登録しました: {person_name} -> {title}")

    if quote:
        PERSON_QUOTES[person_name] = quote
        logger.info(f"[INFO] 名言を登録しました: {person_name} -> {quote}")

    if appearance:
        PERSON_APPEARANCES[person_name] = appearance
        logger.info(f"[INFO] 外見描写を登録しました: {person_name} -> {appearance}")

