"""
動的台本生成ビルダー。
固定テンプレートではなく、分析データに基づいてプロンプトを毎回動的に構築する。
"""

from __future__ import annotations

import random
from pathlib import Path

from app.models.analytics_models import ChannelDeepAnalysis, CompetitorAnalysis
from app.utils.logger import logger


# ==========================================
# フック戦略（5パターン）
# ==========================================

HOOK_STRATEGIES: dict[str, dict] = {
    "question": {
        "name": "問いかけ型",
        "description": "視聴者の好奇心を刺激する問いかけで始める",
        "instruction": (
            "冒頭は、視聴者が「え？」と思うような逆説的な問いかけから始めてください。"
            "「あなたは〇〇だと思っていませんか？実はそれ、完全に間違いです」のような形式。"
            "視聴者の常識を揺さぶり、答えを知りたいと思わせること。"
        ),
    },
    "contrarian": {
        "name": "常識破壊型",
        "description": "常識への反論から衝撃を与える",
        "instruction": (
            "冒頭は、「多くの人が信じている常識」を明確に否定してください。"
            "「〇〇は無意味です」「〇〇が成功を阻んでいます」のような断言。"
            "衝撃→根拠の提示→本論への誘導の流れを作ること。"
        ),
    },
    "story": {
        "name": "ストーリーテリング型",
        "description": "具体的なエピソードから共感を引き出す",
        "instruction": (
            "冒頭は、{person_name}の具体的なエピソード（逆境、転機、決断）から始めてください。"
            "「{person_name}が〇〇歳のとき、〇〇という壁にぶつかりました」のようなストーリー導入。"
            "視聴者が感情移入できる場面を描写し、この人物の話を聞きたいと思わせること。"
        ),
    },
    "statistic": {
        "name": "衝撃データ型",
        "description": "驚きの数字・事実で注意を引く",
        "instruction": (
            "冒頭は、{person_name}に関連する驚きの数字や事実から始めてください。"
            "「〇〇は、わずか〇年で〇〇億円を…」「〇〇%の人が知らない事実」のような形式。"
            "数字のインパクトで注意を引き、その裏にある思想への興味を喚起すること。"
        ),
    },
    "quote": {
        "name": "名言導入型",
        "description": "印象的な名言から開始する",
        "instruction": (
            "冒頭は、{person_name}の最も印象的な名言や発言から始めてください。"
            "名言を提示し、「この一言に、〇〇の全てが凝縮されています」と解説への橋渡し。"
            "名言の力で視聴者を引き込み、その真意を解き明かす旅に誘うこと。"
        ),
    },
    "provocation": {
        "name": "挑発型",
        "description": "視聴者の行動や価値観を直接挑発する",
        "instruction": (
            "冒頭は、視聴者の今の行動を直接否定する挑発から始めてください。"
            "「あなたが今やっていること、全部無駄です」「この動画を閉じるなら、一生そのままです」のような強い断言。"
            "{person_name}の哲学をもとに「なぜ無駄なのか」を鋭く突きつけ、視聴者を釘付けにすること。"
        ),
    },
    "comparison": {
        "name": "比較型",
        "description": "成功者と凡人の対比で引き込む",
        "instruction": (
            "冒頭は、{person_name}と一般人の「決定的な違い」を対比で見せてください。"
            "「ある人は○○しました。一方、多くの人は○○しています。この違いが、人生を分けました」のような形式。"
            "対比のギャップで「自分はどちら側か」と考えさせること。"
        ),
    },
    "future": {
        "name": "未来予測型",
        "description": "近い未来の予測で危機感を煽る",
        "instruction": (
            "冒頭は、3年後・5年後の未来予測から始めてください。"
            "「3年後、今の仕事の半分は消えます」「あと5年で○○は常識になります」のような近未来の変化を提示。"
            "{person_name}がなぜその未来を見抜いていたかに繋げ、「知らないと手遅れになる」と感じさせること。"
        ),
    },
}


# ==========================================
# 構成テンプレート（5パターン）
# ==========================================

STRUCTURE_TEMPLATES: dict[str, dict] = {
    "three_pillars": {
        "name": "3つの柱型",
        "description": "人物の哲学を3つの柱に整理",
        "sections": [
            {"title": "導入", "ratio": 0.10, "instruction": "フック＋人物紹介への橋渡し"},
            {"title": "人物紹介", "ratio": 0.13, "instruction": "人物の実績と権威性を紹介"},
            {"title": "第1章", "ratio": 0.20, "instruction": "1つ目の思考法・哲学を解説。具体例必須"},
            {"title": "第2章", "ratio": 0.20, "instruction": "2つ目の思考法・哲学を解説。前章との対比"},
            {"title": "第3章", "ratio": 0.20, "instruction": "3つ目の思考法・哲学を解説。集大成"},
            {"title": "現代への応用", "ratio": 0.10, "instruction": "3つの哲学を現代にどう活かすか"},
            {"title": "エンディング", "ratio": 0.07, "instruction": "まとめ＋行動喚起"},
        ],
    },
    "problem_solution": {
        "name": "問題解決型",
        "description": "現代の問題を提起し、偉人の知恵で解決",
        "sections": [
            {"title": "問題提起", "ratio": 0.12, "instruction": "視聴者が共感する現代の問題を提示"},
            {"title": "背景と人物紹介", "ratio": 0.15, "instruction": "なぜこの人物がその問題の答えを持つのか"},
            {"title": "解決策1", "ratio": 0.22, "instruction": "人物の思想に基づく1つ目の解決アプローチ"},
            {"title": "解決策2", "ratio": 0.22, "instruction": "2つ目の解決アプローチ。視点を変えて"},
            {"title": "実践方法", "ratio": 0.17, "instruction": "明日から実践できる具体的な方法"},
            {"title": "エンディング", "ratio": 0.12, "instruction": "まとめ＋未来への展望＋行動喚起"},
        ],
    },
    "chronological": {
        "name": "時系列型",
        "description": "人物の人生を時系列で追い、教訓を抽出",
        "sections": [
            {"title": "導入", "ratio": 0.10, "instruction": "フック＋この人生から何を学べるか予告"},
            {"title": "初期の挫折", "ratio": 0.18, "instruction": "若き日の失敗・挫折を描写"},
            {"title": "転機", "ratio": 0.18, "instruction": "人生を変えた出来事・気づき"},
            {"title": "成功と哲学", "ratio": 0.22, "instruction": "成功の核にある思考法を解説"},
            {"title": "教訓と現代への示唆", "ratio": 0.20, "instruction": "その人生から学べることを現代に当てはめる"},
            {"title": "エンディング", "ratio": 0.12, "instruction": "感動的な締めくくり＋行動喚起"},
        ],
    },
    "debate": {
        "name": "議論型",
        "description": "対立する視点を提示し、真実を探る",
        "sections": [
            {"title": "問い", "ratio": 0.10, "instruction": "議論の核となる問いを投げかける"},
            {"title": "視点A：一般論", "ratio": 0.20, "instruction": "多くの人が信じている考え方を提示"},
            {"title": "視点B：偉人の逆説", "ratio": 0.25, "instruction": "{person_name}が提示する逆説的な答え"},
            {"title": "統合と真実", "ratio": 0.20, "instruction": "両方の視点を統合し、より深い真実を導く"},
            {"title": "あなたへの問い", "ratio": 0.15, "instruction": "視聴者自身に考えさせる問いかけ"},
            {"title": "エンディング", "ratio": 0.10, "instruction": "余韻を残す締めくくり＋行動喚起"},
        ],
    },
    "deep_dive": {
        "name": "深掘り型",
        "description": "1つのテーマを徹底的に深掘り",
        "sections": [
            {"title": "フック", "ratio": 0.08, "instruction": "テーマの意外な側面でフック"},
            {"title": "テーマ全体像", "ratio": 0.15, "instruction": "テーマの全体像と{person_name}の位置づけ"},
            {"title": "深掘り1：本質", "ratio": 0.25, "instruction": "テーマの本質を{person_name}の視点で解剖"},
            {"title": "深掘り2：応用", "ratio": 0.22, "instruction": "本質を理解した上での具体的応用"},
            {"title": "反論と再考", "ratio": 0.15, "instruction": "批判や反論を取り上げ、再検討する"},
            {"title": "結論", "ratio": 0.15, "instruction": "深い洞察を凝縮したメッセージ＋行動喚起"},
        ],
    },
}


class DynamicScriptBuilder:
    """分析データに基づいて毎回異なる台本プロンプトを生成する"""

    def __init__(self):
        self.fallback_template_path = (
            Path("data/templates/prompts/script_template.md")
        )

    def build_dynamic_prompt(
        self,
        person_name: str,
        topic: str,
        duration_minutes: int,
        channel_analysis: ChannelDeepAnalysis | None = None,
        competitor_analysis: CompetitorAnalysis | None = None,
        previous_openings: list[str] | None = None,
    ) -> str:
        """
        分析データに基づいて動的なプロンプトを生成

        Args:
            person_name: 人物名
            topic: テーマ
            duration_minutes: 目標分数
            channel_analysis: チャンネル包括分析結果
            competitor_analysis: 競合分析結果

        Returns:
            完全なプロンプト文字列
        """
        # フック戦略を選択
        hook_key = self._select_hook_strategy(channel_analysis)
        hook = HOOK_STRATEGIES[hook_key]

        # 構成を選択
        structure_key = self._select_structure(channel_analysis, person_name)
        structure = STRUCTURE_TEMPLATES[structure_key]

        # ターゲット記述を生成
        audience_desc = self._adjust_target_audience(channel_analysis)

        # 競合差別化指示を生成
        competitive_context = self._build_competitive_context(competitor_analysis)

        # 維持率インサイト
        retention_insights = self._build_retention_insights(channel_analysis)

        logger.info(f"動的プロンプト生成:")
        logger.info(f"  フック戦略: {hook['name']} ({hook_key})")
        logger.info(f"  構成パターン: {structure['name']} ({structure_key})")
        logger.info(f"  ターゲット: {audience_desc[:50]}...")

        # 過去の冒頭テキストから重複回避指示を構築
        anti_repetition = self._build_anti_repetition(previous_openings)

        # プロンプトを組み立て
        prompt = self._assemble_prompt(
            person_name=person_name,
            topic=topic,
            duration_minutes=duration_minutes,
            hook=hook,
            hook_key=hook_key,
            structure=structure,
            structure_key=structure_key,
            audience_desc=audience_desc,
            competitive_context=competitive_context,
            retention_insights=retention_insights,
            anti_repetition=anti_repetition,
        )

        return prompt

    def _select_hook_strategy(
        self, analysis: ChannelDeepAnalysis | None
    ) -> str:
        """
        分析データからフック戦略を選択

        維持率が高い動画の特徴に基づいて選択。
        データがない場合はランダム。
        """
        if not analysis or not analysis.subscriber_impact:
            return random.choice(list(HOOK_STRATEGIES.keys()))

        # 登録者獲得率の高い動画の傾向を見る
        top_videos = analysis.top_subscriber_videos[:5]
        if not top_videos:
            return random.choice(list(HOOK_STRATEGIES.keys()))

        # タイトルのパターンから推測
        has_question = any("？" in v.title or "?" in v.title for v in top_videos)
        has_number = any(
            any(c.isdigit() for c in v.title) for v in top_videos
        )

        if has_question:
            return "question"
        if has_number:
            return "statistic"

        # ローテーション（前回と違うものを選ぶ）
        return random.choice(list(HOOK_STRATEGIES.keys()))

    def _select_structure(
        self,
        analysis: ChannelDeepAnalysis | None,
        person_name: str,
    ) -> str:
        """
        分析データと人物タイプから構成を選択

        歴史上の人物 → 時系列型も候補に
        経営者 → 問題解決型も候補に
        哲学者 → 議論型も候補に
        """
        # 人物タイプの推定
        business_keywords = ["経営", "CEO", "創業", "起業", "投資"]
        history_keywords = ["古代", "紀元前", "戦国", "明治", "江戸"]
        philosophy_keywords = ["哲学", "思想", "思考"]

        person_lower = person_name.lower()

        candidates = list(STRUCTURE_TEMPLATES.keys())

        # 人物タイプに応じて候補を調整
        if any(k in person_lower for k in business_keywords):
            # ビジネス系 → 問題解決型を優先
            candidates = ["problem_solution", "three_pillars", "deep_dive"]
        elif any(k in person_lower for k in history_keywords):
            # 歴史系 → 時系列型を優先
            candidates = ["chronological", "three_pillars", "story"]
        elif any(k in person_lower for k in philosophy_keywords):
            # 哲学系 → 議論型を優先
            candidates = ["debate", "deep_dive", "three_pillars"]

        # 分析データがあれば、登録者獲得の多い動画の構成を参考に
        if analysis and analysis.subscriber_impact:
            # デフォルトの候補からランダム選択
            pass

        return random.choice(candidates)

    def _adjust_target_audience(
        self, analysis: ChannelDeepAnalysis | None
    ) -> str:
        """デモグラフィックデータからターゲット記述を生成"""
        if not analysis or not analysis.demographics or not analysis.demographics.details:
            return (
                "現状に閉塞感を感じている20～40代のビジネスパーソン。"
                "AI時代への不安や、努力が報われない焦りを持っている層。"
            )

        top_age = analysis.demographics.top_age_group
        gender_ratio = analysis.demographics.gender_ratio

        # 年齢グループ名を読みやすく変換
        age_map = {
            "age13-17": "10代",
            "age18-24": "18～24歳",
            "age25-34": "25～34歳",
            "age35-44": "35～44歳",
            "age45-54": "45～54歳",
            "age55-64": "55～64歳",
            "age65-": "65歳以上",
        }
        age_desc = age_map.get(top_age, top_age)

        # 性別比率
        male_pct = gender_ratio.get("male", 0)
        female_pct = gender_ratio.get("female", 0)
        if male_pct > 60:
            gender_desc = "男性が多い視聴者層"
        elif female_pct > 60:
            gender_desc = "女性が多い視聴者層"
        else:
            gender_desc = "男女バランスの取れた視聴者層"

        # デバイス情報
        device_desc = ""
        if analysis.primary_device == "MOBILE":
            device_desc = "モバイル視聴が主流のため、テンポ良く簡潔に。"
        elif analysis.primary_device == "DESKTOP":
            device_desc = "PC視聴が多いため、じっくり深掘りしてOK。"
        elif analysis.primary_device == "TV":
            device_desc = "テレビ視聴も多いため、映像的な演出を意識。"

        return (
            f"メイン視聴者: {age_desc}の{gender_desc}。"
            f"{device_desc}"
            f"この層が共感できる言葉遣い・事例を意識してください。"
        )

    def _build_competitive_context(
        self, competitor: CompetitorAnalysis | None
    ) -> str:
        """競合分析に基づく差別化指示"""
        if not competitor or not competitor.trending_topics:
            return ""

        sections = ["## 競合との差別化ポイント"]
        sections.append(
            "以下の競合トレンドを意識しつつ、独自の切り口で差別化してください:"
        )

        for t in competitor.trending_topics[:5]:
            sections.append(f"- 「{t['topic']}」関連: 競合{t['count']}本")

        if competitor.gap_opportunities:
            sections.append("\n以下は競合で人気だが自チャンネル未カバーの機会です:")
            for g in competitor.gap_opportunities[:3]:
                sections.append(f"- {g['person']}: {g['reason']}")

        return "\n".join(sections)

    def _build_retention_insights(
        self, analysis: ChannelDeepAnalysis | None
    ) -> str:
        """視聴維持率に基づくインサイト"""
        if not analysis:
            return ""

        insights = []

        # トラフィックソースに基づく最適化ヒント
        if analysis.traffic_sources:
            top_source = analysis.top_traffic_source
            if top_source == "SUGGESTED":
                insights.append(
                    "おすすめ経由が多い → CTRが重要。サムネイル映えするキーワードを冒頭に含めること。"
                )
            elif top_source == "YT_SEARCH":
                insights.append(
                    "検索経由が多い → SEO重要。検索されやすいキーワードをタイトル・冒頭に配置。"
                )
            elif top_source == "EXTERNAL":
                insights.append(
                    "外部流入が多い → SNS共有しやすい引用・名言を含めること。"
                )

        if insights:
            return "## パフォーマンスインサイト\n" + "\n".join(
                f"- {i}" for i in insights
            )
        return ""

    def _build_anti_repetition(
        self, previous_openings: list[str] | None
    ) -> str:
        """過去の冒頭テキストから重複回避指示を構築"""
        if not previous_openings:
            return ""

        sections = [
            "## 冒頭の差別化（重要）",
            "以下は過去の動画で使用した冒頭です。これらと同じパターン・表現は絶対に使わないでください。",
            "特に「毎日…」「あなたの今の毎日…」のような固定的な導入パターンは避けてください。",
            "毎回まったく異なるアプローチで、視聴者が新鮮さを感じる冒頭にしてください。",
            "",
        ]
        for i, opening in enumerate(previous_openings[-5:], 1):
            # 長い場合は先頭100文字だけ
            truncated = opening[:100] + "..." if len(opening) > 100 else opening
            sections.append(f"- 過去{i}: 「{truncated}」")

        return "\n".join(sections)

    def _assemble_prompt(
        self,
        person_name: str,
        topic: str,
        duration_minutes: int,
        hook: dict,
        hook_key: str,
        structure: dict,
        structure_key: str,
        audience_desc: str,
        competitive_context: str,
        retention_insights: str,
        anti_repetition: str = "",
    ) -> str:
        """全パーツを組み合わせて最終プロンプトを構築"""

        # セクション定義を構築
        sections_text = ""
        for i, section in enumerate(structure["sections"], 1):
            section_minutes = duration_minutes * section["ratio"]
            section_seconds = int(section_minutes * 60)
            instruction = section["instruction"].replace(
                "{person_name}", person_name
            )
            sections_text += (
                f"**{i}. 【{section['title']}】(約{section_minutes:.1f}分, {section_seconds}秒)**\n"
                f"   {instruction}\n\n"
            )

        # フック指示をパーソナライズ
        hook_instruction = hook["instruction"].replace(
            "{person_name}", person_name
        )

        prompt = f"""# 命令書
あなたは、偉人や経営者の哲学をわかりやすく伝えるYouTubeチャンネル「偉人たちが導く道しるべ」の脚本家です。
視聴者が「今日から考え方を変えよう」と思えるような、力強いナレーション台本を作成してください。

# 今回の設定
- **ナレーターの人格**: 知的で落ち着いているが、時折ハッとするような「残酷な真実」や「強い言葉」を使う。
- **フック戦略**: {hook['name']}（{hook['description']}）
- **構成パターン**: {structure['name']}（{structure['description']}）

# ターゲット視聴者
{audience_desc}

# 入力テーマ
**【解説する人物・書籍】**: {person_name}
**【伝えたい核心的メッセージ】**: {topic}
**【動画の目標時間】**: {duration_minutes}分

# 冒頭フックの指示
{hook_instruction}

# 台本の構成要件
以下の構成で、合計で{duration_minutes}分程度の台本になるように詳細に書いてください。

{sections_text}

{competitive_context}

{retention_insights}

{anti_repetition}

# 冒頭パターンの多様性（厳守）
- 「毎日…」「あなたの今の毎日…」のような固定的な入りは禁止。毎回違う切り口で。
- 冒頭の最初の1文は特に重要。過去の動画と被らない、斬新なアプローチを実験してください。
- 同じフレーズの使い回しではなく、フック戦略に忠実な新しい表現を考えてください。

# 出力形式
以下のJSON形式で出力してください:

```json
{{
  "topic": "{topic}",
  "person_name": "{person_name}",
  "total_duration_minutes": {duration_minutes},
  "sections": [
    {{
      "title": "セクション名",
      "narration": "ここにナレーション原稿を記述...",
      "scene_description": "[画面表示] ... [BGM] ... [テンポ] ...",
      "duration_seconds": 90,
      "subtitles": [
        {{
          "text": "字幕テキスト",
          "start_time": 0.0,
          "duration": 3.5
        }}
      ]
    }}
  ]
}}
```

# トーンとスタイル
- **トーン**: 冷静だが情熱的。論理的で知的好奇心を刺激する。
- **言葉遣い**: 断言口調を効果的に使用。やや哲学的な言葉を使いつつ、すぐに簡単な言葉で噛み砕く。
- **文章のリズム**: 一文一文が短く、リズミカルに。重要なポイントは強調し、間を取る。

# 演出の指示
各セクションの`scene_description`には、[画面表示], [BGM], [画像/映像], [テンポ]の演出指示を含める。

# 字幕の区切り（重要）
各セクションの`subtitles`にナレーションを自然な区切りで1行ずつ分割。1行30文字程度。

# 読み上げ注意事項（最重要）
VOICEVOXで音声合成するため、**英語表記は必ずカタカナに変換**すること。
例: Google→グーグル, AI→エーアイ, CEO→シーイーオー, MBA→エムビーエー
人名もカタカナで: Steve Jobs→スティーブ・ジョブズ, Elon Musk→イーロン・マスク

**人名の読みがな注意（絶対厳守）:**
- 人名は正しい読みで記述すること。読み違いは絶対NG。
- 例: 藤田田→「ふじたでん」（「ふじたた」ではない）
- 不確実な読みの人名は必ず確認した正しい読みを使用すること

# 事実確認と正確性の要件（最重要）
- 人物の実績・発言・エピソードは正確な情報に基づくこと
- 引用は正確な表現を使用すること
- 不確実な情報は「〜と言われている」等の表現を使用すること
- **各セクションには必ず`subtitles`配列を含めること**
"""
        return prompt

    def get_fallback_template(self) -> str | None:
        """フォールバック用の固定テンプレートを読み込む"""
        if self.fallback_template_path.exists():
            with open(self.fallback_template_path, "r", encoding="utf-8") as f:
                return f.read()
        return None
