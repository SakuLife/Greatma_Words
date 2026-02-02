"""
YouTube自動コメント生成サービス

台本のエンディングで視聴者に求めている行動（CTA）を読み取り、
その「お手本」となるコメントを生成する。
1コメ目にお手本を書くことで、他の視聴者がコメントしやすくなる。
"""

import re
import random

import google.generativeai as genai

from app.config import settings
from app.utils.logger import logger


class CommentGenerator:
    """台本のCTAに対するお手本コメントを生成"""

    def __init__(self):
        """Initialize with Gemini API."""
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash")
        else:
            self.model = None
            logger.warning("Gemini API key not configured for comment generation")

    async def generate_comment(
        self,
        person_name: str,
        topic: str,
        script_sections: list | None = None,
    ) -> str:
        """
        台本のCTAに対するお手本コメントを生成する。

        Args:
            person_name: 人物名
            topic: 動画のトピック
            script_sections: 台本のセクションリスト（VideoScript.sections）

        Returns:
            お手本コメント文字列
        """
        # 台本のエンディングからCTAを抽出
        cta_text = self._extract_cta(script_sections)
        ending_narration = self._extract_ending_narration(script_sections)

        logger.info(f"抽出したCTA: {cta_text or '(なし)'}")

        # AI生成を試みる
        if self.model:
            try:
                comment = await self._generate_with_ai(
                    person_name, topic, cta_text, ending_narration
                )
                if comment:
                    logger.info(f"お手本コメント生成: {comment[:60]}...")
                    return comment
            except Exception as e:
                logger.warning(f"AIコメント生成失敗、テンプレート使用: {e}")

        # フォールバック
        return self._generate_from_template(person_name, topic, cta_text)

    def _extract_ending_narration(self, script_sections: list | None) -> str:
        """台本のエンディングセクションのナレーションを取得"""
        if not script_sections:
            return ""

        for section in reversed(script_sections):
            title = getattr(section, "title", "") or ""
            if "エンディング" in title or "まとめ" in title or "結論" in title:
                return getattr(section, "narration", "") or ""

        # 最後のセクションをフォールバックとして使う
        last = script_sections[-1]
        return getattr(last, "narration", "") or ""

    def _extract_cta(self, script_sections: list | None) -> str:
        """
        台本のエンディングから、視聴者に求めているコメントの内容を抽出する。

        例: "あなたの「逆張り」の第一歩を、コメント欄で宣言してくれると嬉しいです"
        → "逆張りの第一歩を宣言"
        """
        narration = self._extract_ending_narration(script_sections)
        if not narration:
            return ""

        # コメントに関する文を探す
        cta_patterns = [
            r"コメント[欄で]*[にで].*?[。\n]",
            r"コメント.*?(?:書いて|教えて|宣言|聞かせて|シェア).*?[。\n]",
            r"(?:書いて|教えて|宣言|聞かせて|シェア).*?コメント.*?[。\n]",
        ]

        for pattern in cta_patterns:
            match = re.search(pattern, narration)
            if match:
                return match.group(0).strip().rstrip("。")

        # コメントという単語を含む文を探す
        sentences = re.split(r'[。\n]', narration)
        for sentence in sentences:
            if "コメント" in sentence:
                return sentence.strip()

        return ""

    async def _generate_with_ai(
        self,
        person_name: str,
        topic: str,
        cta_text: str,
        ending_narration: str,
    ) -> str:
        """台本のCTAに対するお手本コメントをAIで生成"""
        prompt = f"""あなたはYouTubeチャンネルの運営者です。
自分の動画の1コメ目を書きます。

この動画のエンディングで、視聴者にこうお願いしています：
---
{ending_narration[-500:] if ending_narration else f"{person_name}の{topic}について、感想や今日から実践することをコメントで教えてください。"}
---

{f'特にこの部分がコメントのお題です：「{cta_text}」' if cta_text else ''}

【あなたがやること】
この「コメントのお題」に対して、自分自身のお手本回答を書いてください。
他の視聴者が「こういう風に書けばいいんだ」と思って、
マネしてコメントしやすくなるようなお手本です。

【要件】
- 動画の内容（{person_name}の{topic}）に具体的に関連した回答にする
- 視聴者と同じ目線で「自分はこうします」「自分はこう思った」という宣言・感想にする
- 2〜3文程度。短く、気軽に書いた感じ
- チャンネル運営者っぽくない。一人の視聴者として書く
- 「チャンネル登録」「いいね」は絶対に言わない
- 絵文字は0〜1個

【NG例】
- ❌ 「この動画を作りました！感想教えてください」（運営者目線すぎる）
- ❌ 「みなさんもコメントしてくださいね」（お願いしている＝運営者）

【OK例】
- ✅ 「自分は今日から、周りに流されず自分が本当に価値あると思うものに時間を使います！まずは毎朝30分、誰もやってない分野の勉強を始めてみます」
- ✅ 「一番刺さったのは「競争は敗者のもの」という言葉。自分も競争を避けて独自のポジションを作ることを意識してみます」

【出力】コメント本文のみ。説明不要。
"""

        response = self.model.generate_content(prompt)
        comment = response.text.strip()

        # 余計な引用符やマークダウンを除去
        if comment.startswith('"') and comment.endswith('"'):
            comment = comment[1:-1]
        if comment.startswith("```"):
            parts = comment.split("```")
            comment = parts[1].strip() if len(parts) > 1 else comment

        return comment

    def _generate_from_template(
        self,
        person_name: str,
        topic: str,
        cta_text: str,
    ) -> str:
        """テンプレートからお手本コメントを生成（AI失敗時のフォールバック）"""
        templates = [
            (
                f"自分は{person_name}の考え方を知って、"
                f"まず「周りと同じことをやめる」ことから始めてみます。"
                f"小さい一歩だけど、今日からやってみます！"
            ),
            (
                f"一番響いたのは、常識を疑うという部分。"
                f"自分も今日から、当たり前だと思ってたことを一つ見直してみます。"
            ),
            (
                f"{person_name}の{topic}を聞いて、"
                f"自分ももっと長期的な視点で物事を考えようと思いました。"
                f"焦らず、自分だけの道を進んでみます。"
            ),
        ]

        # CTAに「宣言」が含まれていた場合
        if cta_text and "宣言" in cta_text:
            templates.append(
                f"宣言します！自分は今日から、{person_name}の教えを実践して、"
                f"まずは自分の頭で考える習慣をつけていきます。"
            )

        return random.choice(templates)
