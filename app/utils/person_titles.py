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


def register_person_info(person_name: str, title: str | None = None, quote: str | None = None) -> None:
    """
    動的に人物情報を辞書に登録する。
    AIが取得した肩書・名言を画像生成前に登録するために使用。

    Args:
        person_name: 人物名
        title: 肩書（Noneまたは空文字の場合はスキップ）
        quote: 名言（Noneまたは空文字の場合はスキップ）
    """
    if title:
        PERSON_TITLES[person_name] = title
        logger.info(f"[INFO] 肩書を登録しました: {person_name} -> {title}")

    if quote:
        PERSON_QUOTES[person_name] = quote
        logger.info(f"[INFO] 名言を登録しました: {person_name} -> {quote}")

